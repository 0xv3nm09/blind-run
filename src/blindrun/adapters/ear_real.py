"""Real ear adapters: drive a screen reader and return what it announced.

VirtualEar (default): Guidepup's Virtual Screen Reader — a spec-based, headless,
text-only simulation that runs anywhere (sandbox included) via runner/virtual_run.mjs.
VoiceOver/NVDA arrive later behind this same interface (UC-14).
"""

import asyncio
import json
import shutil
from pathlib import Path

from blindrun.errors import EarError, EarTimeout
from blindrun.ports import (
    Budget,  # noqa: F401 (parity with other adapters)
    EarResult,
    Plan,
)
from blindrun.schemas import Phrase

_RUNNER = Path(__file__).resolve().parents[3] / "runner"
_BUNDLE = (
    _RUNNER / "node_modules" / "@guidepup" / "virtual-screen-reader" / "lib" / "esm" / "index.browser.js"
)


class VirtualEar:
    driver = "virtual"

    def __init__(self, *, node_bin: str = "node"):
        if shutil.which(node_bin) is None:
            raise EarError("node not found on PATH (brew install node)")
        if not _BUNDLE.is_file():
            raise EarError(f"virtual screen reader bundle missing at {_BUNDLE} — cd runner && npm install")
        self.node = node_bin

    async def run(
        self,
        url: str,
        plan: Plan,
        *,
        timeout_s: int = 180,
        on_phrase=None,  # Callable[[str, int, int], Awaitable[None]] | None
    ) -> EarResult:
        cfg = json.dumps(
            {
                "url": url,
                "steps": plan.steps[: plan.max_steps],
                "successPhrases": [plan.success_phrase, *plan.alternates],
                "maxSteps": plan.max_steps,
                "bundle": str(_BUNDLE),
            }
        )
        proc = await asyncio.create_subprocess_exec(
            self.node,
            "virtual_run.mjs",
            cfg,
            cwd=str(_RUNNER),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        phrases: list[Phrase] = []
        raw_err: list[str] = []

        async def pump_stderr() -> None:
            assert proc.stderr is not None
            async for raw in proc.stderr:
                line = raw.decode().strip()
                if not line:
                    continue
                raw_err.append(line)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue  # browser/node noise — kept in raw_err for diagnostics
                if "phrase" in ev:
                    i = len(phrases)
                    phrases.append(
                        Phrase(
                            i=i, text=ev["phrase"], t_ms=int(ev.get("t_ms", 0)), step=int(ev.get("step", 0))
                        )
                    )
                    if on_phrase is not None:
                        await on_phrase(ev["phrase"], i, phrases[-1].step)

        stderr_task = asyncio.create_task(pump_stderr())
        assert proc.stdout is not None
        stdout_task = asyncio.create_task(proc.stdout.read())  # one reader per stream
        try:
            await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=timeout_s)
        except TimeoutError as e:
            proc.kill()
            raise EarTimeout(
                f"virtual ear exceeded {timeout_s}s on {url}\nstderr: {''.join(raw_err[-10:])}"
            ) from e
        await proc.wait()
        out = stdout_task.result()
        if proc.returncode != 0:
            raise EarError(f"virtual ear exited {proc.returncode}: {''.join(raw_err[-15:])}")

        payload = json.loads(out.decode())
        return EarResult(
            driver="virtual",
            phrases=[Phrase.model_validate(p) for p in payload["phrases"]],
            shots=[],
            aria_yaml=payload.get("aria_yaml", ""),
            reached_success=payload["reached_success"],
            duration_s=round(payload["phrases"][-1]["t_ms"] / 1000, 1) if payload["phrases"] else 0.0,
        )


RealEar = VirtualEar  # make_ear maps all real drivers here until Vo/NVDA adapters land
