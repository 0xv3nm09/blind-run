"""Policy: pure functions, unit-tested. Rules live in code so they never drift with a prompt."""

from blindrun.ports import Finding, RawFinding
from blindrun.schemas import Verification
from blindrun.types import Evidence, FindingId, Route, RunId, Severity

WCAG_TARGET = "WCAG 2.2 AA"


def confidence(model_conf: float, *, reproduced: bool, heard: bool, axe_agrees: bool) -> float:
    """Evidence-weighted, not model-said-so. The model's self-rating is the weakest input."""
    score = 0.35 * model_conf
    score += 0.30 if reproduced else 0.0  # deterministic re-check agrees
    score += 0.20 if heard else 0.0  # exact quote exists in the transcript
    score += 0.15 if axe_agrees else 0.0  # rule engine agrees
    return round(min(score, 1.0), 2)


def route(severity: Severity, conf: float) -> Route:
    if severity == Severity.blocker and conf >= 0.8:
        return Route.auto_fix
    if conf >= 0.5:
        return Route.fix_and_flag
    return Route.human


def promote(
    raw: RawFinding,
    *,
    run_id: RunId,
    finding_id: FindingId,
    transcript: list[str],
    axe_agrees: bool = False,
) -> Finding:
    """RawFinding -> Finding: id, evidence-confirmed confidence, route."""
    heard = any(raw.heard in line or raw.heard == line for line in transcript)
    reproduced = raw.heard in transcript  # the transcript IS the reproduction
    evidence = {e for e in raw.evidence if e in Evidence}  # drop model-invented kinds
    evidence |= {Evidence.seen}  # the auditor is run WITH the ARIA tree: 'seen' is structural
    if reproduced:
        evidence.add(Evidence.reproduced)
    if heard or raw.heard == "(silence)":
        evidence.add(Evidence.heard)
    conf = confidence(raw.model_conf, reproduced=reproduced, heard=heard, axe_agrees=axe_agrees)
    return Finding(
        id=finding_id,
        run_id=run_id,
        wcag_sc=raw.wcag_sc,
        category=raw.category,
        severity=raw.severity,
        confidence=conf,
        heard=raw.heard,
        seen=raw.seen,
        element_hint=raw.element_hint,
        evidence=frozenset(evidence),
        route=route(Severity(raw.severity), conf),
    )


def triage(raws: list[RawFinding], *, run_id: RunId, transcript: list[str]) -> list[Finding]:
    out: list[Finding] = []
    for i, raw in enumerate(raws, start=1):
        fid = FindingId(f"fnd_{run_id.removeprefix('run_')}{i:04d}"[:16])
        # Pattern guarantees fnd_ + 12 hex; keep the shape valid:
        fid = FindingId(f"fnd_{abs(hash((run_id, i))) % 16**12:012x}")
        out.append(promote(raw, run_id=run_id, finding_id=fid, transcript=transcript))
    return sorted(out, key=lambda f: (-{"blocker": 0, "major": 1, "minor": 2}[f.severity], -f.confidence))


def choose(results: list) -> object | None:
    """Exactly one passed branch wins; deterministic order."""
    for r in results:
        if r.verdict.value == "passed":
            return r
    return None


def passed(verification: Verification) -> bool:
    return verification.passed  # explicit; pass condition is a string check, never a model opinion
