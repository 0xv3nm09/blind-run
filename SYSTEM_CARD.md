# Blind-Run system card

One-page summary of what the system is, what it does, what it must not be trusted for.

## Purpose

Blind-Run checks whether a **web task can be completed by ear** — using only what a screen
reader announces — and proposes source fixes until it can. It is a developer tool for
accessibility regression testing, aimed at flows that get sued (checkout, sign-up, forms).

## Models and services

| Role | Model (Nebius Token Factory) | Notes |
|---|---|---|
| Planner | `nvidia/nemotron-3-super-120b-a12b` | plans keyboard-only walk; picks success phrase(s) |
| Auditor | same, text-only | transcript + ARIA tree → findings (WCAG-labeled) |
| Fixer | same | proposes 3 verbatim search/replace edits per round (max 2 rounds) |
| Escalation | `nvidia/Nemotron-3-Ultra-550b-a55b` | reserved for multi-file fixes (not used in MVP) |
| Dedupe (later) | `Qwen/Qwen3-Embedding-8B` | merges duplicate findings |
| Execution | Nebius Token Factory Sandboxes (beta) | fix branches build + get ear-verified in isolated microVMs |

## What the screen reader is (and isn't)

The default "ear" is Guidepup's **Virtual Screen Reader**: a spec-based simulation of announced
text (WAI-ARIA 1.2 + accname), headless, no audio. Its authors say it should **augment, not
replace**, real screen-reader testing. Findings and fix verification are labeled
`verified: virtual`. Real-reader confirmation (VoiceOver/NVDA) is supported behind the same
interface and is the intended pre-merge human step. **A virtual-reader pass is necessary
evidence, not proof a real screen-reader user is unblocked.**

## Decision rules that hold everywhere

- Pass/fail is a **string check on the transcript** (a confirmation phrase spoken *after* an
  action), never a model opinion.
- Findings need **≥2 kinds of evidence** (heard + seen / axe / reproduced); confidence is computed
  from evidence weights, calibrated on the planted-bug benchmark, with the model's own rating the
  weakest input.
- **Nothing auto-merges.** The output is a labeled pull request (accessibility, ai-generated) with
  a before/after transcript diff. A human reviews and merges.
- Untrusted page text is data, never instructions; injection probes are part of the benchmark.
- Per-run token budget (default 400K), max 2 fix rounds, wall-clock caps.

## Known limits

- **English only** (auditor models' language support).
- **Web only**; desktop/mobile readers out of scope for the MVP.
- The virtual reader follows specs, not NVDA/JAWS quirks; find-verify disagreement with real
  readers is recorded as data, not hidden.
- Detection recall on the planted benchmark is reported with 95% Wilson intervals because 20 bugs
  is a small sample; numbers are not estimates of real-world recall on unseen sites.
- Screenshots/transcripts are treated as possibly-personal: redaction before model calls,
  14-day retention for images, findings kept.
- Benchmarked fixes are single-file, ≤ a few lines of dependent-JS changes; multi-file fixes route
  to a human.

## Evaluation

Planted-bug benchmark (21 bugs: 10 axe-catchable, 11 axe-invisible, + 5 clean controls), three
conditions (axe-only / ear+auditor / real-reader confirm), 95% CIs, control false-positive rate,
cost and wall-clock per fixed issue. Results: `bench/results.json`, dashboard: `/` of the API.

## Data kept

Runs, findings, redacted transcripts (text), patch diffs. Screenshots/audio (when a real reader
records) deleted after 14 days. No customer code leaves the user's repo + Sandboxes; model calls
carry only the cited file and evidence quotes.

## Real-world validation (Oct 12)

- Real product page (books.toscrape.com, not authored by us): walk + auditor found 2 genuine
  blockers (nameless buttons announced as silence) — `evidence/real-sites/books-toscrape-product.jsonl`.
- Wikipedia "Web accessibility" article: 0 findings on two independent runs (41–42 phrases,
  degraded=false) — precision holds on a real, mostly-accessible page. Zero findings is a
  claim of nothing found, not nothing ran: the recordings contain the full transcript.
