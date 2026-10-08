import pytest

from blindrun.pipeline.policy import confidence, route
from blindrun.types import Route, Severity


@pytest.mark.parametrize(
    "sev,conf,want",
    [
        (Severity.blocker, 0.91, Route.auto_fix),
        (Severity.blocker, 0.79, Route.fix_and_flag),
        (Severity.major, 0.95, Route.fix_and_flag),  # only blockers auto-fix
        (Severity.minor, 0.49, Route.human),
    ],
)
def test_route(sev, conf, want):
    assert route(sev, conf) == want


def test_confidence_needs_evidence_not_just_model():
    # model says 1.0 but nothing corroborates -> below the auto-fix bar
    assert confidence(1.0, reproduced=False, heard=False, axe_agrees=False) < 0.8
    # model unsure but transcript reproduces + quote exists -> strong
    assert confidence(0.5, reproduced=True, heard=True, axe_agrees=True) >= 0.8


def test_confidence_capped_at_1():
    assert confidence(1.0, reproduced=True, heard=True, axe_agrees=True) == 1.0
