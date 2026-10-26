# Submission compliance — every requirement, where it's satisfied

Mapped line-by-line against the hackathon's official rules. Statuses: ✅ done ·
⏳ activates at submission (repo flip). Every "where" is checkable in this repo.

## Project requirements

| Official rule | Status | Where |
|---|---|---|
| Working software app that **runs on Nebius Token Factory or AI Cloud** | ✅ | Every model call hits `api.tokenfactory.nebius.com` — [llm_tokenfactory.py](../src/blindrun/adapters/llm_tokenfactory.py); per-call logs print role + model + tokens live |
| Uses **at least one NVIDIA open source model** | ✅ | Nemotron-3 Super (plan, audit) + Nemotron-3 Ultra (fix) — model matrix in [ARCHITECTURE.md](ARCHITECTURE.md#2-model-matrix-all-on-nebius-token-factory) |
| Fits a **track** — ours: *Coding and Agentic Engineering* ("agents that write, run, and test code in Token Factory") | ✅ | Candidates are applied, served and ear-tested inside **Nebius Sandboxes** branches — [sandbox_contree.py](../src/blindrun/adapters/sandbox_contree.py); the recorded flagship proves it end-to-end |
| Capable of **running consistently** and functioning as depicted | ✅ | Cold-start verified (`make setup`); dashboard replay is deterministic; live-run variance is disclosed (SYSTEM_CARD) with the recorded run as the always-works demo |
| Third-party integrations legally used | ✅ | Tavily (free tier), Guidepup / axe-core / Playwright (OSS), GitHub |

## Submission requirements

| Official rule | Status | Where |
|---|---|---|
| **URL to a working demo** / hosted application | ⏳ | Static demo mode ships in-repo; goes live as <https://0xv3nm09.github.io/blind-run/> the moment the repo flips public (README → *Hosted demo*) — free of charge, no login, nothing to keep warm through the judging period |
| **Text description** of features and functionality | ✅ | Devpost form (drafted); README covers features + quick start |
| **Public code repository** (GitHub/GitLab/Bitbucket) | ⏳ | github.com/0xv3nm09/blind-run — flips public at submission |
| Repo contains **all source, assets, instructions** | ✅ | `make setup` installs everything incl. the ear's Node deps + Chromium (clean-room validated) |
| **Open-source license**, detectable in About | ✅ | MIT — [LICENSE](../LICENSE), auto-detected by GitHub |
| **README** with setup instructions | ✅ | Quick start, prerequisites, judge 2-minute test |
| README **highlights NVIDIA Nemotron use, where Token Factory accelerated, other Nebius tools** | ✅ | *Powered by Nebius Token Factory + NVIDIA Nemotron* section + Tavily section + model matrix |
| **Demo video** < 3 min, public on YouTube, shows the project functioning, no third-party music/trademarks | ✅ | 2:45, real UI/terminal/diff footage, no music; uploaded at submission |
| **Track identified** | ✅ | Coding and Agentic Engineering |
| **Feedback** on Token Factory / AI Cloud / NVIDIA tools | ✅ | [FEEDBACK.md](../FEEDBACK.md) — two live-found, bisected platform bugs + SDK DX items (also entered in the Most Valuable Feedback lane) |
| English | ✅ | All materials |
| Free, unrestricted judge access **until the judging period ends** | ✅ | Static GitHub Pages demo — no keys, no login, no expiry risk |

## Judging — how we match

**Stage One (pass/fail): theme fit + real API/SDK use, "not a superficial rebrand"** — the project
*is* the track sentence: an agent that writes, runs, and tests code in Token Factory, with runtime
inference calls provable from the repo and the per-call logs.

**Stage Two (equal weight):**

| Criterion | Our case |
|---|---|
| Technological Implementation | Per-role model routing with tuned sampling, canonical Sandboxes usage (parent checkpoint + parallel disposable branches), hardened integration (2 platform bugs found + documented), 19 tests + CI, per-call model logging |
| Design | Complete product: auto-playing dashboard (stage timeline, pause/speed), CLI, deterministic replay, evidence trail — not a proof of concept |
| Potential Impact | Sourced problem stats (WebAIM / UsableNet / GDS / Deque), real blockers found on pages we didn't author, cents-per-page economics, compliance clock (ADA Title II 2027/28) |
| Quality of the Idea | The ear as deterministic oracle (models draft, code verifies), best-of-3 parallel rejection, honest benchmark + SYSTEM_CARD showing domain understanding |

**Tie-break** resolves on Technological Implementation first — our strongest criterion, and the one
we picked for judge feedback on the form.
