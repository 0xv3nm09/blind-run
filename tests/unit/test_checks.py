from blindrun.adapters.ear_fake import BROKEN
from blindrun.pipeline.checks import keyboard_trap, run_checks
from blindrun.ports import EarResult
from blindrun.schemas import Phrase
from blindrun.types import EarDriver


def ear(lines: list[str], reached: bool = False) -> EarResult:
    return EarResult(
        driver=EarDriver.fake,
        phrases=[Phrase(i=i, text=t, t_ms=i * 500, step=0) for i, t in enumerate(lines)],
        reached_success=reached,
    )


def test_keyboard_trap_detected():
    cycle = ["Size picker, dialog", "button", "button", "button"] * 4  # 16 phrases, cycling
    out = run_checks(ear(cycle))
    assert len(out) == 1
    assert out[0].wcag_sc == "2.1.2"
    assert out[0].severity == "blocker"


def test_progress_not_a_trap():
    lines = [p.text for p in [Phrase(i=i, text=t, t_ms=i, step=0) for i, t in enumerate(BROKEN)]]
    assert keyboard_trap(ear(lines)) == []


def test_success_reached_not_a_trap():
    cycle = ["a", "b", "c", "d"] * 4
    assert keyboard_trap(ear(cycle, reached=True)) == []
