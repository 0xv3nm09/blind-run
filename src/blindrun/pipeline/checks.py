"""Model-free checks: deterministic detectors that run on the transcript alone.

The keyboard-trap detector from UC-05: the same few phrases cycling with no
progress is a focus trap (WCAG 2.1.2), and no model is needed to see it."""

from blindrun.ports import EarResult, RawFinding
from blindrun.types import Category, Evidence, Severity


def keyboard_trap(ear: EarResult, *, window: int = 4, repeats: int = 3) -> list[RawFinding]:
    t = ear.transcript()
    for start in range(len(t) - window * repeats + 1):
        cycle = t[start : start + window]
        if (
            all(t[start + k * window : start + (k + 1) * window] == cycle for k in range(repeats))
            and not ear.reached_success
        ):
            return [
                RawFinding(
                    wcag_sc="2.1.2",
                    category=Category.focus,
                    severity=Severity.blocker.value,
                    heard=" → ".join(cycle),
                    seen="",
                    model_conf=0.0,  # deterministic: no model involved
                    evidence=frozenset({Evidence.heard, Evidence.reproduced}),
                )
            ]
    return []


CHECKS = [keyboard_trap]


def run_checks(ear: EarResult) -> list[RawFinding]:
    out: list[RawFinding] = []
    for fn in CHECKS:
        out.extend(fn(ear))
    return out
