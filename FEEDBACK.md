# Tool feedback — Nebius Token Factory, Sandboxes, NVIDIA models

Built during the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/), October 2026.
Every item below was hit while building Blind-Run and verified live against the service; repro steps are real.

## Token Factory inference (models API)

1. **A regex `pattern` anywhere in a `json_schema` response_format crashes the server with HTTP 500.**
   Found by keyword bisection against `nvidia/nemotron-3-super-120b-a12b`: a minimal
   object/properties/required schema succeeds; adding only `"pattern": "^next$"` to one property
   makes every call return `500 Internal server error`. Other constraint keywords (`minLength`,
   `maxLength`, `minItems`, `maxItems`, integer `minimum`/`maximum`, `additionalProperties`,
   `enum`-via-Literal) all work. Workaround: strip `pattern` client-side and enforce with pydantic
   + a repair turn (`sanitize_schema` in our adapter). Expected: either guided-decoding support for
   JSON Schema `pattern` or a 4xx with a clear message instead of a 500.
2. **Reasoning output can consume the entire token budget and return empty content.** With
   `enable_thinking: true` and no `max_tokens`, the fixer role sometimes returns `content: ""` after
   spending its whole budget on `reasoning`. Documented workaround works: set `max_tokens` explicitly
   and cap with `chat_template_kwargs.reasoning_budget`. Suggestion: document this interaction on the
   model catalog page (the workbook's model-card note was the only place we saw it).
3. **Strict json_schema is a suggestion, not a guarantee, for reasoning models.** Even with
   `strict: true`, models returned (a) wrong envelope keys (`alternatives` for our declared
   `patches`), (b) prose around the JSON, (c) real newlines inside JSON strings, (d) empty `[]`
   payloads after a failed repair turn. We built a tolerant parse ladder (JSON-object scanner +
   lenient JSON + envelope remap + repair turn) to compensate. Suggestion: server-side validation
   feedback in the error message (which key failed) would shrink repair turns dramatically.
4. **The `nvidia/nemotron-3-nano-omni-*` model was absent from the catalog for the entire
   hackathon** (present in May 2026 per the cookbook git history; absent Oct 2026). Our design had
   a vision auditor fallback precisely because of this; it would be good to publish
   add/remove announcements per model so hacks can plan around multimodal availability.
5. **Credit redemption**: the `NEBIUS-DEVPOST-GLOBAL26` promo flow required being signed in to the
   Token Factory console first; the failure mode when signed out is an unhelpful generic error.
6. **Loved**: OpenAI compatibility is exact (SDK drop-in), price/performance is excellent for agent
   loops (our whole 21-page benchmark costs cents), and the Nemotron models' instruction-following
   on JSON tasks is strong once schemas avoid `pattern`.

## Token Factory Sandboxes (ConTree, beta)

1. **`run(...).wait()` returns the checkpoint object — this is the key API and it's undocumented.**
   Ignoring the return value (treating `wait()` as void) leaves you holding an object with
   `state == PREPARED` and `uuid == None`, which reads exactly like a stuck build. The state name
   `PREPARED` also sounds intermediate when it is terminal-for-that-object. Expected: docs showing
   `parent = base.run(...).wait()` and then `images.use(parent.uuid)`.
2. **No Node.js images in the catalog.** `python:3.12-slim` resolves; `node:22-slim`,
   `docker.io/library/node:22-slim` all 404 ("Image with tag ... not found"). We install Node 22 via
   NodeSource inside the parent checkpoint and snapshot it — works fine, but a maintained `node:*`
   image would remove ~90s of parent-build time for the many browser/JS-agent use cases.
3. **Checkpoints capture filesystem, not processes** — correct design, worth calling out loudly:
   a server started in one run is not running in the next. Our server+replay branches fold both into
   a single `run(shell=...)`.
4. **`files=` upload is great** (concurrent, sha256-deduped) — we migrated from base64-heredoc
   payloads to `run(files={dest: bytes})` and deleted a whole class of quoting bugs.
5. **Transport retries are caller-side by design**, but the exception hierarchy has no
   retryable/permanent marker. We retry `OperationTimedOutError`-shaped failures blindly today.
   A `retryable: bool` on `ContreeError` would standardize this.
6. **Beta free-tier note**: parallel branch runs (3–6 per run, ~6s each) never came close to the
   50-op cap, and sandbox usage never consumed credits — this made the "3 parallel fix branches"
   demo economically trivial. Thank you.
7. **One onboarding snag, fully resolved**: our project ID was initially wrong (one character), and
   the failure mode was `403 Insufficient permissions: spawn_disposable or spawn` even though
   `whoami` showed beta limits. Suggestion: validate the `Project` header against known projects
   and 404 with "unknown project" instead of surfacing it as a permission failure. The `whoami`
   permission map endpoint was the decisive debugging tool — promote it in the quickstart.

## NVIDIA models (via Token Factory)

- **Nemotron 3 Super (120B-A12B)**: excellent planner/fixer. Sampling guidance (temp 1.0, top_p
  0.95) reproduced cleanly; `reasoning_budget` capping works as documented. SWE-bench-flavored
  reliability showed in the fix proposals — when given verbatim search/replace edit semantics, it
  proposed correct W3C-APG-pattern fixes (fieldset+legend+radios for a div-based size picker).
- **Prompt-format finding**: the model writes reliable markdown search/replace blocks but unreliable
  JSON-escaped diffs; we switched the fixer to plain-text output with block extraction and both
  parse success and fix quality jumped. Worth adding to the agent-cookbook as a pattern.
- **Nemotron 3.5 Lightning**: used for triage/summaries in our cost plan; pricing ($0.06/$0.24 per
  1M) makes agent loops effectively free at hackathon scale.

## What we built on top (so support can gauge the surface)

- 7-port adapter architecture (LLM/Ear/Sandbox/Search/VCS/Store/Events) with fakes + reals.
- Ear replay = Guidepup Virtual Screen Reader inside Sandboxes (Node 22 + Playwright/Chromium
  checkpoint), streaming phrases over SSE.
- Benchmarks: axe-only vs ear+auditor recall/precision on 21 planted bugs + 5 clean controls.
