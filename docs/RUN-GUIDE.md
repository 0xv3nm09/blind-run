# Real-run guide — from zero to a verified run

Everything needed to run Blind-Run for real: live Nemotron inference on Nebius Token
Factory, a real virtual screen reader, and fix verification inside Nebius Sandboxes.
Total cost per full run: **≈$0.01–0.03**.

## 1. Prerequisites

| Need | Get it | Used by |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | python env |
| Node 22+ | nodejs.org or nvm | the ear (virtual screen reader) |
| **Nebius Token Factory account + API key** | console.tokenfactory.nebius.com → API keys | every model call + Sandboxes |
| Nebius Project ID | console → project settings (starts with `aiproject-`) | Sandboxes auth |
| Tavily key *(optional)* | app.tavily.com free tier | live W3C/WCAG retrieval (else cached) |

## 2. One-time setup

```bash
git clone https://github.com/0xv3nm09/blind-run.git && cd blind-run
make setup          # python env + the ear's Guidepup/Playwright deps + Chromium
```

Create `.env` in the repo root (copy `.env.example`):

```ini
NEBIUS_API_KEY=v1.CmQK...            # your Token Factory key
NEBIUS_PROJECT_ID=aiproject-...      # your project id
LLM_BACKEND=tokenfactory             # real inference
EAR_DRIVER=virtual                   # real screen reader
SANDBOX_BACKEND=contree              # fix verification inside Nebius Sandboxes
VCS_BACKEND=local                    # PR artifacts land in evidence/
# SEARCH_BACKEND=tavily              # uncomment + TAVILY_API_KEY for live retrieval
# TAVILY_API_KEY=tvly-...
```

`make test` should pass with **zero keys** — that's the offline health check.

## 3. Run it

```bash
# terminal 1 — the planted-bug shop (8 bug pages, 5 clean controls)
make serve-shop

# terminal 2 — a real run (full loop, ~2–5 min, ≈$0.01)
LLM_BACKEND=tokenfactory EAR_DRIVER=virtual SANDBOX_BACKEND=contree VCS_BACKEND=local \
  uv run python -m blindrun run \
  --url http://127.0.0.1:8932/product.html \
  --task "buy the cheapest item" \
  --repo demo/shop
```

What you'll see while it runs — every inference call logged live:

```
llm.call role=planner model=nvidia/nemotron-3-super-120b-a12b tokens=1100 base_url=...
llm.call role=auditor model=nvidia/nemotron-3-super-120b-a12b tokens=505  base_url=...
llm.call role=fixer   model=nvidia/Nemotron-3-Ultra-550b-a55b tokens=9353 base_url=...
```

…then the findings table (severity, WCAG criterion, the exact phrase heard, confidence,
route) and the final status. Watch it live: open http://localhost:8000/app (or `make up`)
and paste the printed `run_…` id.

Detection-only (no fixing — faster, ~10–25s):

```bash
... --no-fix      # same pipeline minus the fix rounds and Sandboxes
```

## 4. What "done" vs "escalated" means

- **done** — a fix candidate was applied, served and ear-verified inside a Sandboxes
  branch; the PR artifact lands in `evidence/` (VCS_BACKEND=local) or opens on GitHub
  (GitHub adapter).
- **escalated** — no candidate completed the task by ear, and the run refused to ship an
  unverified fix. This is the honest outcome, not a crash. Fix quality varies with model
  sampling: re-run, or replay the recorded flagship (`make up` → Play demo run).

## 5. First Sandboxes build & rate limits

- The Sandboxes **parent checkpoint** (python + Node 22 + Playwright + Chromium + the ear)
  builds once per process: ~2–4 min. Branches after that take ~3–6s each.
- Token Factory limits: 60 requests/min, 400K tokens/min (adaptive windows). A single
  agent loop never approaches them; parallel benchmark sweeps might.
- Everything is recorded: add `--record path.jsonl` and replay any run in the dashboard.

## 6. The use-case tasks (all real, measured Oct 26)

Run any of these against `make serve-shop` (recordings from our own runs are in
`evidence/real-sites/`, numbers on the console's Use cases page):

| Page | Task | Findings | Tokens | Time |
|---|---|---|---|---|
| product.html | "buy the cheapest item" | 2 | 1,946 | 21.3s |
| catalog.html | "find the cheapest trail shoe and open it" | 2 | 1,645 | 12.9s |
| checkout.html | "complete the checkout" | 4 | 2,633 | 22.6s |
| search.html | "search for running shoes" | 3 | 3,082 | 23.1s |
| controls/dialog.html | "open the dialog and submit it" | 4 | 2,786 | 21.3s |
| controls/tabs.html | "read what is on the shipping tab" | 1 | 2,424 | 15.4s |
| controls/combobox.html | "select a country from the dropdown" | 2 | 1,721 | 12.2s |
| controls/live-cart.html | "add an item and hear the cart update" | **0** | 962 | 9.0s |

The last row is the control-lane proof: the task completed by ear on the first call —
nothing to audit, nothing to fix.

## 7. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `403 Insufficient permissions: spawn` | wrong `NEBIUS_PROJECT_ID` — check every character; `whoami` endpoint shows the permission map |
| `500 Internal server error` on structured calls | a `pattern` keyword in a json_schema (known platform bug) — we sanitize client-side; update if the platform fixes it |
| empty model output, normal finish | reasoning consumed the budget — our adapter retries with headroom; keep `max_tokens` + `reasoning_budget` set |
| first model call slow (~9s) | connection warm-up — subsequent calls ~1.8s |
| escalate on every run | sampling variance — re-run; or verify the sandbox path with the winner-patch probe (see ARCHITECTURE.md §8) |
| `SEARCH-NOT-FOUND` in branch tails | the candidate's search text drifted — round 2 gets the feedback and retries; both apply ladders are indentation-tolerant |
