"""Closed sets and small value types. Import from here, never redefine."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints


class RunStatus(StrEnum):
    queued = "queued"
    planning = "planning"
    listening = "listening"
    auditing = "auditing"
    fixing = "fixing"
    verifying = "verifying"
    done = "done"
    escalated = "escalated"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL = {RunStatus.done, RunStatus.escalated, RunStatus.failed, RunStatus.cancelled}

# Which transitions advance() allows (wrong order is a code bug, not a data error).
ALLOWED: dict[RunStatus, set[RunStatus]] = {
    RunStatus.queued: {RunStatus.planning, RunStatus.cancelled},
    RunStatus.planning: {RunStatus.listening, RunStatus.escalated, RunStatus.failed},
    RunStatus.listening: {RunStatus.auditing, RunStatus.failed},
    RunStatus.auditing: {RunStatus.fixing, RunStatus.done, RunStatus.escalated},
    RunStatus.fixing: {RunStatus.verifying, RunStatus.escalated, RunStatus.failed},
    RunStatus.verifying: {RunStatus.done, RunStatus.fixing, RunStatus.escalated},
}


class Severity(StrEnum):
    blocker = "blocker"
    major = "major"
    minor = "minor"


class Category(StrEnum):
    label = "label"
    role = "role"
    state = "state"
    focus = "focus"
    order = "order"
    feedback = "feedback"
    navigation = "navigation"
    contrast = "contrast"
    other = "other"


class Route(StrEnum):
    auto_fix = "auto_fix"
    fix_and_flag = "fix_and_flag"
    human = "human"


class EarDriver(StrEnum):
    virtual = "virtual"
    voiceover = "voiceover"
    nvda = "nvda"
    fake = "fake"


class Evidence(StrEnum):
    heard = "heard"
    seen = "seen"
    axe = "axe"
    reproduced = "reproduced"


class BranchVerdict(StrEnum):
    passed = "passed"
    failed_apply = "failed_apply"
    failed_build = "failed_build"
    failed_axe = "failed_axe"
    failed_ear = "failed_ear"
    timeout = "timeout"


class VerifyLevel(StrEnum):
    virtual = "virtual"
    real = "real"
    both = "both"


class ReviewVerdict(StrEnum):
    confirm = "confirm"
    false_positive = "false_positive"
    wont_fix = "wont_fix"


class Scope(StrEnum):
    runs_create = "runs:create"
    runs_read = "runs:read"
    fixes_write = "fixes:write"
    runner_claim = "runner:claim"
    admin = "admin"


# Value types: validated once, then trusted everywhere.
RunId = Annotated[str, StringConstraints(pattern=r"^run_[0-9a-f]{12}$")]
FindingId = Annotated[str, StringConstraints(pattern=r"^fnd_[0-9a-f]{12}$")]
FixId = Annotated[str, StringConstraints(pattern=r"^fix_[0-9a-f]{12}$")]
WcagSC = Annotated[str, StringConstraints(pattern=r"^[1-4]\.\d{1,2}\.\d{1,2}$")]
Prob = Annotated[float, Field(ge=0.0, le=1.0)]
USD = Annotated[float, Field(ge=0.0)]
Tokens = Annotated[int, Field(ge=0)]

StepCmd = Annotated[
    str,
    StringConstraints(
        pattern=r"^(next|previous|act|type:.{1,200}|press:[A-Za-z+]{1,30}|heading|landmark|form)$"
    ),
]
