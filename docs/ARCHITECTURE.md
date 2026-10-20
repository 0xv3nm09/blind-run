# Blind-Run — Technical Architecture

Deep-dive companion to the [README](../README.md). Every claim here is checkable in the
repo; file paths point at the code that implements it. Diagrams live in
[`docs/diagrams/`](diagrams/) (rendered by `make_diagrams.py`, light + dark variants).

**One line:** `plan → listen → audit → triage → fix → parallel sandbox verification → PR`,
orchestrated as a state machine where **models draft and deterministic code verifies** —
the pass/fail oracle is a string check on a screen-reader transcript, never a model opinion.

---

## 1. The pipeline, stage by stage

### 1.1 Plan — `orchestrator.run_flow` → `TokenFactoryLLM.structured()`

- `_snapshot(url)` grabs the page's **ARIA snapshot** (python-playwright, headless) — the
  planner sees the accessibility tree, not pixels.
- **Model:** `nvidia/nemotron-3-super-120b-a12b` (Token Factory), reasoning enabled,
  `temperature 1.0 / top_p 0.95` per NVIDIA's model-card guidance.
- Output is a pydantic-validated `Plan`: `steps` (walk commands), `success_phrase` +
  `alternates` (the deterministic oracle), `max_steps`.
- The verifier later **canonicalizes the walk** (`["heading"] + ["next"] × (max_steps−1)`) so
  planner step-variance can never destabilize verification.
- Robustness: `json_schema` response format with `sanitize_schema()` stripping the
  `pattern` keyword client-side (we found it returns HTTP 500 — see FEEDBACK.md), a
  tolerant parse ladder (strict → JSON-object scanner → lenient → envelope remap → repair
  turn), and tenacity retries on 429/5xx.

### 1.2 Listen — `runner/virtual_run.mjs` (the ear)

- [Guidepup Virtual Screen Reader](https://github.com/guidepup/virtual-screen-reader) is
  injected as an **ES module via blob URL** (`mod.virtual → window.__v`) because the browser
  build exports a singleton, not a global.
- Walker policy: `next/previous/act/press/perform` per plan; **auto-act** on interactive
  announcements (`/(button|radio|checkbox|combobox|option|menu ?item|tab)/i` minus
  `link|end of`); navigation recovery re-injects the VSR if a link navigates away.
- **Success window:** after every act, the following announcements are checked against the
  success-phrase set (the confirmation lands *after* the act). Success stops the walk.
- The whole loop is try/catch-wrapped — a broken step **degrades** (phrases so far +
  `degraded: true`) instead of crashing; the result JSON prints before `stop()` so a
  stop()-throw can never eat the transcript.
- Runs as a Node subprocess (`ear_real.py`), one reader per stream (stdout task + stderr
  pump — `communicate()` on both raises).

### 1.3 Audit — `TokenFactoryLLM.structured()` + server-side evidence weighting

- **Model:** Nemotron-3 Super, `temperature 0.2`, thinking off — we want a careful reader.
- Input: the **heard transcript** (what was announced) vs the **ARIA snapshot** (what
  exists); the auditor must quote real transcript lines.
- Output: WCAG-labeled findings (`wcag_sc`, `category`, `severity` as Literal enums — the
  model invented free-text values until we pinned them; enums are safe on Token Factory).
- **Confidence is computed, never asked:** `policy.promote` derives it from evidence kinds
  (heard-in-transcript, seen-in-ARIA-tree, reproduced), drops model-invented kinds, and
  routes each finding `auto_fix | fix_and_flag | human`. A low-evidence finding (e.g. the
  "(silence)" blocker at conf 0.17) routes to a human honestly.

### 1.4 Fix — the search/replace protocol

- **Model:** `nvidia/Nemotron-3-Ultra-550b-a55b` (quality-first; Super is the `.env` switch),
  `max_tokens 16384` + `reasoning_budget 4096` — without the explicit cap, reasoning
  consumes the whole budget and content comes back empty (live-found, documented).
- Models cannot reliably write unified diffs or JSON-escaped diffs. The protocol is
  **verbatim search/replace blocks**: `<<<SEARCH / === / >>>`, with a worked example built
  from the target file's own lines — that example is what unlocked copy fidelity.
- Three failure modes, three defenses (all unit-tested):
  - *prose instead of blocks* → one format-anchored retry ("first character must be a
    backtick");
  - *all alternatives inside one unclosed mega-block* → the extractor splits on
    `<<<SEARCH` so each pair becomes its own candidate;
  - *re-indented quotes* → the apply ladder falls back to per-line whitespace-flexible
    matching and re-indents the replacement (content drift still fails, correctly).
- Up to `MAX_FIX_ROUNDS=2`: a failed round feeds back **verdict tails** — the last phrases
  the sandbox ear heard — external signal only, never "try harder".

### 1.5 Verify — best-of-3 in parallel Nebius Sandboxes (`sandbox_contree.py`)

- One **parent checkpoint** is built once per process: `python:3.12-slim` + Node 22
  (NodeSource — the catalog has no node images) + Playwright + Chromium + Guidepup,
  uniquely tagged so no state is ever inherited.
- Each candidate = a **disposable branch** from the parent: the site ships in as a tar
  (byte-faithful; md5-checked in-branch against the source on every apply), the patch
  applies via `apply.py` (strict → indentation-tolerant ladder), the patched site is
  served on `:8000` *inside the branch*, and the ear replays the task there.
- Verdicts: `passed` (success phrase heard in-branch) / `failed_ear` (applied, task still
  impossible — tail carries what the walker last heard) / `failed_apply` / `failed_build`.
- `policy.choose` picks the winner; ties break on evidence. **The verifier refusing to
  ship an unverified fix is a successful run** — the CLI says so explicitly.

### 1.6 Report — the PR is the receipt

`PRDraft` carries the WCAG criterion, the heard evidence, the W3C pattern URL (with its
source), and the **before/after transcript diff**. Local VCS writes artifacts to
`evidence/` (served at `/evidence` by the API); the recorded flagship's PR body + patch are
committed verbatim. Nothing auto-merges.

---

## 2. Model matrix (all on Nebius Token Factory)

| Role | Model | Sampling | Why |
|---|---|---|---|
| Planner | `nvidia/nemotron-3-super-120b-a12b` | temp 1.0, top_p 0.95, thinking on | card-recommended; plans the walk |
| Auditor | `nvidia/nemotron-3-super-120b-a12b` | temp 0.2, thinking off | careful reading, no creativity |
| Fixer | `nvidia/Nemotron-3-Ultra-550b-a55b` | temp 1.0, top_p 0.95, thinking on, max_tokens 16384 + reasoning_budget 4096 | quality-first code writing |
| Escalation | Nemotron-3 Ultra | same as fixer | last-resort rounds |
| Fast lane / Guard | `nvidia/Nemotron-3_5-Lightning` / Nano-30B | temp 0.3 / 0.0 | routed in config; high-volume lanes |
| Embeddings | `Qwen/Qwen3-Embedding-8B` | — | routed for dedupe; the shipped loop dedupes structurally in code |

Every call logs `llm.call role=… model=… tokens=… base_url=…` — run live and watch the
stack prove itself (see README → *For judges: verifying the stack is real*).

---

## 3. Tavily — two load-bearing runtime calls (`search_tavily.py`)

1. **`pattern(widget)`** — before the fixer writes code: Tavily `search_depth="advanced"`
   retrieves the **current authoritative W3C ARIA APG pattern** for the barrier category;
   w3.org results are preferred; the summary + keyboard model + URL go into the fixer
   prompt, and the PR cites the fetched URL **with its source** (`cache` or `tavily`).
2. **`docs(wcag_sc)`** — every finding is grounded with the **official WCAG Understanding
   document**, retrieved live, surfaced as a link in the dashboard findings table.

Degradation ladder (never a failed run): Tavily error / no key / quota → `CachedSearch`
floor — bundled APG patterns + a **live-verified SC→slug map** for the 13 criteria we emit
(W3C URLs use names like `name-role-value.html`, not `4-1-2.html` — the naive pattern
404s), unknown SCs fall back to the Understanding index, never a dead link. Behavior is
pinned by offline tests with a mocked transport: call shape, w3.org preference, 500-degrade,
no-key-degrade.

---

## 4. Ports & adapters — swappable by `.env`, never code

| Port | Fake | Real | Switch |
|---|---|---|---|
| LLM | FakeLLM (canned plans/edits) | `llm_tokenfactory.py` | `LLM_BACKEND` |
| Ear | FakeEar (scripted phrases) | `ear_real.py` → `runner/virtual_run.mjs` | `EAR_DRIVER` |
| Sandbox | FakeSandbox | `sandbox_contree.py` (Nebius), `sandbox_local.py` | `SANDBOX_BACKEND` |
| Search | `search_fake.py` (CachedSearch) | `search_tavily.py` | `SEARCH_BACKEND` |
| VCS | FakeVCS | `vcs_local.py` (GitHub adapter slot) | `VCS_BACKEND` |
| Store | memory | sqlite | `STORE_BACKEND` |
| Events | in-proc pub/sub | + SSE | `EVENTS_BACKEND` |

Fakes aren't stubs — the full pipeline runs on them offline, which is why the 19-test suite
covers the real wiring paths with zero keys and no network.

## 5. Event stream, API, dashboard

Event vocabulary: `run.started/status/finished/failed`, `plan.ready`, `ear.phrase`,
`ear.done`, `finding.new` (with `wcag_url`), `fix.branch`, `fix.verified` (transcript +
patch diffs), `pr.opened`. The API (FastAPI) streams them over SSE; run id `demo` replays
the recorded flagship at `?interval=` (0.12s/event default, slower for readability); the
dashboard auto-plays it on load (judge cold-open), renders findings/branches/diffs live,
and serves `evidence/` at `/evidence` so the PR banner link resolves.

## 6. Failure-handling catalogue (degrade, don't crash)

| Failure | Behavior |
|---|---|
| Tavily down / no key | cached patterns + verified slug map |
| Sandbox unreachable | `SANDBOX_BACKEND=local` runs the same verification |
| 3,000-char real-world announcement | clipped at the `Phrase` schema boundary |
| Fixer replies prose / mega-blocks / re-indents | format retry / split / tolerant apply |
| Reasoning eats the output budget | explicit `max_tokens` + `reasoning_budget` caps |
| A step breaks mid-walk | partial transcript + `degraded: true` |
| No candidate passes | **escalated** with evidence — the honest outcome, stated as such |

## 7. Security & safety invariants

Page text is untrusted data (prompt-injection surface: findings must quote transcript
lines, which the transcript verifies). Models never run commands — worker code does, under
policy; the fix protocol is a constrained edit format, not shell. Secrets live only in a
gitignored `.env`; nothing auto-merges; the human review gate is the end of every flow.

## 8. Testing & verification

19 offline tests (apply ladder, extraction splitting, Tavily behavior, policy routing,
pipeline-on-fakes) + CI gating `ruff check`/`format` repo-wide; the **winner-patch probe**
(re-run the recorded flagship's winning diff through `check_branch`, expect `passed`) is the
fast live regression for the Sandboxes path.

Known limits and honest numbers live in [SYSTEM_CARD.md](../SYSTEM_CARD.md); platform
feedback in [FEEDBACK.md](../FEEDBACK.md).
