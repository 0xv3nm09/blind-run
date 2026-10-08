"""Real LLM adapter: Nebius Token Factory (OpenAI-compatible) with NVIDIA Nemotron models.

Sampling per NVIDIA model cards; reasoning switch per role; strict JSON with one
repair turn; tenacity owns retries (never stacked); every call updates the Budget.
"""

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from blindrun.errors import BudgetExceeded, RateLimited, SchemaError, UpstreamError
from blindrun.ports import Budget

DEFAULT_MODELS = {
    "planner": "nvidia/nemotron-3-super-120b-a12b",
    "fixer": "nvidia/nemotron-3-super-120b-a12b",
    "auditor": "nvidia/nemotron-3-super-120b-a12b",  # text-only audit (no NVIDIA vision model on the catalog, DR-0 Oct 6)
    "guard": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "lightning": "nvidia/Nemotron-3_5-Lightning",
    "escalation": "nvidia/Nemotron-3-Ultra-550b-a55b",
}

SAMPLING: dict[str, dict] = {  # NVIDIA's recommended settings per role
    "planner": {
        "temperature": 1.0,
        "top_p": 0.95,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
    },
    "fixer": {
        "temperature": 1.0,
        "top_p": 0.95,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True, "force_nonempty_content": True}},
    },
    "auditor": {"temperature": 0.2, "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "guard": {"temperature": 0.0, "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "lightning": {"temperature": 0.3, "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "escalation": {
        "temperature": 1.0,
        "top_p": 0.95,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
    },
}


def _rescue_json(raw: str):
    """Lenient parse: models often emit real newlines/tabs inside JSON strings
    (invalid strictly, but recoverable locally — no repair call needed)."""
    import json

    try:
        return json.loads(raw, strict=False)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json(raw: str) -> str:
    """Reasoning models sometimes write prose around the JSON; pull the outermost object."""
    if raw.lstrip().startswith("{"):
        return raw
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _json_objects(raw: str) -> list[str]:
    """Scan for every complete top-level {...} object (string/escape aware).
    Handles prose before/after the JSON, trailing text, and multiple blocks."""
    out: list[str] = []
    depth, start, in_str, esc = 0, -1, False, False
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth and depth == 1 and start != -1:
                out.append(raw[start : i + 1])
            depth = max(0, depth - 1)
    return out


def _rescue_json(raw: str):
    """Lenient parse: models often emit real newlines/tabs inside JSON strings
    (invalid strictly, but recoverable locally — no repair call needed)."""
    import json

    try:
        return json.loads(raw, strict=False)
    except (json.JSONDecodeError, ValueError):
        return None


def _remap_to_schema(obj, schema: type[BaseModel]):
    """Models occasionally use a wrong envelope key ('alternatives' for 'patches').
    If the object has one list value and the schema wants a list, remap it."""
    if not isinstance(obj, dict):
        return None
    props = schema.model_json_schema().get("properties", {})
    list_keys = [k for k, v in props.items() if v.get("type") == "array"]
    if not list_keys:
        return obj
    target = list_keys[0]
    if target in obj:
        return obj
    for v in obj.values():
        if isinstance(v, list):
            return {target: v}
    return None


def _parse_into(raw: str, schema: type[BaseModel]) -> BaseModel:
    """The full local ladder: strict → lenient+remapped, across every JSON block found."""
    candidates = [raw, _extract_json(raw), *_json_objects(raw)]
    for cand in candidates:
        try:
            return schema.model_validate_json(cand)
        except ValidationError:
            pass
        obj = _rescue_json(cand)
        if obj is not None:
            remapped = _remap_to_schema(obj, schema)
            for candidate in (obj, remapped):
                if candidate is not None:
                    try:
                        return schema.model_validate(candidate)
                    except ValidationError:
                        pass
    raise ValueError(f"no parseable {schema.__name__} payload found in reply")


def sanitize_schema(schema: dict) -> dict:
    """Strip keys that crash Token Factory's guided decoding (found by bisect, Oct 6:
    a regex `pattern` anywhere in the schema -> HTTP 500). Pydantic still enforces
    every stripped constraint client-side, and the repair turn fixes violations."""
    if isinstance(schema, dict):
        return {k: sanitize_schema(v) for k, v in schema.items() if k != "pattern"}
    if isinstance(schema, list):
        return [sanitize_schema(x) for x in schema]
    return schema


class TokenFactoryLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.tokenfactory.nebius.com/v1/",
        models: dict[str, str] | None = None,
        timeout: float = 300.0,
    ):
        self.c = AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0
        )  # tenacity owns retries
        self.models = {**DEFAULT_MODELS, **(models or {})}

    def _sampling(self, role: str, thinking: bool | None) -> dict:
        s = dict(SAMPLING[role])
        if thinking is not None:
            s["extra_body"] = {
                **s.get("extra_body", {}),
                "chat_template_kwargs": {
                    **s.get("extra_body", {}).get("chat_template_kwargs", {}),
                    "enable_thinking": thinking,
                },
            }
        return s

    @retry(
        retry=retry_if_exception_type((RateLimited, UpstreamError)),
        wait=wait_random_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _call(
        self,
        role: str,
        model: str,
        messages: list[dict],
        schema: type[BaseModel] | None,
        budget: Budget,
        sampling: dict,
        max_tokens: int | None = None,
    ) -> str:
        if budget.left() < 4_000:
            raise BudgetExceeded(f"tokens left < 4K ({budget.left()})")
        kwargs: dict = {"model": model, "messages": messages, **sampling}
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": sanitize_schema(schema.model_json_schema()),
                    "strict": True,
                },
            }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        try:
            r = await self.c.chat.completions.create(**kwargs)
        except (APITimeoutError, APIConnectionError) as e:
            raise UpstreamError("tokenfactory", None) from e  # retryable: transport/timeout
        except RateLimitError as e:
            raise RateLimited("tokenfactory") from e
        except APIStatusError as e:
            if e.status_code == 429:
                raise RateLimited("tokenfactory") from e
            if e.status_code >= 500:
                raise UpstreamError("tokenfactory", e.status_code) from e
            raise  # 4xx: our bug or a bad request — no retry
        if r.usage is not None:
            budget.tokens_used += r.usage.total_tokens or 0
        budget.calls += 1
        return r.choices[0].message.content or ""

    async def structured(
        self,
        role: str,
        messages: list[dict],
        schema: type[BaseModel],
        *,
        images: tuple[bytes, ...] = (),
        budget: Budget,
        thinking: bool | None = None,
    ) -> BaseModel:
        model = self.models.get(role) or DEFAULT_MODELS[role]
        sampling = self._sampling(role, thinking)
        if images:
            assert len(images) == 1, "vision audit: one image per request (send one cropped shot per call)"
            import base64

            b64 = base64.b64encode(images[0]).decode()
            last = messages[-1]
            messages = messages[:-1] + [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {
                            "type": "text",
                            "text": last["content"]
                            if isinstance(last["content"], str)
                            else str(last["content"]),
                        },
                    ],
                }
            ]
        raw = await self._call(role, model, messages, schema, budget, sampling)
        if not raw.strip():
            # reasoning consumed the whole output budget (workbook fail-case 9): retry with headroom
            raw = await self._call(role, model, messages, schema, budget, sampling, max_tokens=16384)
        try:
            return _parse_into(raw, schema)
        except ValueError:
            pass
        # repair turn: quote the failure, demand the full payload again
        repair = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": "Your reply did not match the required JSON schema (wrong envelope key, "
                "trailing text, or malformed strings). Reply again with the COMPLETE payload as pure JSON "
                "matching the schema exactly — no prose before or after, no empty collections.",
            },
        ]
        raw2 = await self._call(role, model, repair, schema, budget, sampling)
        try:
            return _parse_into(raw2, schema)
        except ValueError as e2:
            raise SchemaError(role, e2) from e2

    async def text(self, role: str, messages: list[dict], *, budget: Budget) -> str:
        model = self.models.get(role) or DEFAULT_MODELS[role]
        raw = await self._call(role, model, messages, None, budget, self._sampling(role, None))
        if not raw.strip():
            # reasoning consumed the whole output budget (fail-case 9): retry with headroom
            raw = await self._call(
                role, model, messages, None, budget, self._sampling(role, None), max_tokens=16384
            )
        return raw
