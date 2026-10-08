"""Pipeline models. All frozen: a stage returns a new object instead of mutating."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blindrun.types import (
    USD,
    BranchVerdict,
    Category,
    EarDriver,
    Evidence,
    FindingId,
    Prob,
    Route,
    RunId,
    StepCmd,
    Tokens,
    VerifyLevel,
    WcagSC,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class Plan(Frozen):
    steps: list[StepCmd] = Field(min_length=1, max_length=60)
    success_phrase: str = Field(min_length=2, max_length=80)  # e.g. "Order confirmed"
    alternates: list[str] = Field(default=[], max_length=5)  # other terminal confirmations
    max_steps: int = Field(default=40, ge=5, le=120)
    notes: str = ""


class Phrase(Frozen):
    i: int = Field(ge=0)  # order in the transcript
    text: str = Field(max_length=500)  # what the screen reader announced
    t_ms: int = Field(ge=0)  # time since the ear started
    step: int = Field(ge=0)  # which plan step produced it


class Shot(Frozen):
    step: int
    png_path: str  # object-store key, never inline bytes
    bbox: "BBox | None" = None  # focused element; the auditor crops to it
    redacted: bool = False


class BBox(Frozen):
    x: int
    y: int
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class EarResult(Frozen):
    driver: EarDriver
    phrases: list[Phrase]
    shots: list[Shot] = []
    aria_yaml: str = ""  # Playwright aria_snapshot() of the start page
    reached_success: bool = False  # success_phrase heard?
    degraded: bool = False
    duration_s: float = 0

    @model_validator(mode="after")
    def _phrases(self):
        if not self.phrases and not self.degraded:
            raise ValueError("empty transcript must be marked degraded")
        return self

    def transcript(self) -> list[str]:
        return [p.text for p in self.phrases]


class RawFinding(Frozen):
    """Auditor output before policy adds id, route and calibrated confidence."""

    wcag_sc: WcagSC
    category: Category
    severity: str
    heard: str
    seen: str
    element_hint: str = ""
    model_conf: Prob = 0.5
    evidence: frozenset[Evidence] = frozenset({Evidence.heard})


class Finding(Frozen):
    id: FindingId
    run_id: RunId
    wcag_sc: WcagSC
    category: Category
    severity: str
    confidence: Prob  # calibrated score, set by policy
    heard: str
    seen: str
    element_hint: str = ""
    evidence: frozenset[Evidence]
    occurrences: int = 1
    route: Route | None = None  # None until policy.route() runs

    @model_validator(mode="after")
    def _two_kinds(self):
        if len(self.evidence) < 2:
            raise ValueError("a finding needs at least two kinds of evidence")
        return self


class Patch(Frozen):
    id: str
    finding_id: str = ""
    diff: str = Field(max_length=20_000)  # unified diff
    path: str = ""  # file the diff targets (unified headers are authoritative)
    rationale: str = Field(max_length=600)
    pattern_url: str | None = None  # W3C APG page it follows


class BranchResult(Frozen):
    patch_id: str
    verdict: BranchVerdict
    axe_before: int = 0
    axe_after: int = 0
    ear: EarResult | None = None  # virtual-reader rerun on this branch
    duration_s: float = 0.0
    log_tail: str = ""


class Verification(Frozen):
    level: VerifyLevel
    before: list[str]
    after: list[str]
    transcript_diff: str
    passed: bool


class PRDraft(Frozen):
    title: str = Field(max_length=120)
    body_md: str
    branch: str = Field(pattern=r"^blindrun/[a-z0-9-]{3,60}$")
    labels: tuple[str, ...] = ("accessibility", "ai-generated")


class Event(BaseModel):
    seq: int  # per-run counter; clients resume with Last-Event-ID
    run_id: RunId
    type: str
    at: datetime
    data: dict


class Budget(BaseModel):  # mutable on purpose: the router updates it
    tokens_used: Tokens = 0
    tokens_cap: Tokens = 400_000
    usd_used: USD = 0.0
    calls: int = 0

    def left(self) -> int:
        return self.tokens_cap - self.tokens_used
