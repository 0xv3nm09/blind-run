"""FakeEar: a recorded transcript that flips from 'broken' to 'fixed' when the
winning patch is applied, so the verify stage can prove pass/fail honestly."""

from blindrun.ports import EarResult, Plan
from blindrun.schemas import Phrase

BROKEN = [
    "Shop, web content",
    "Running shoes, heading level 2",
    "$49, Add to cart, button",
    "button",  # size S  <- the planted bug
    "button",  # size M
    "button",  # size L
    "Cart (0), link",
]

FIXED = [
    "Shop, web content",
    "Running shoes, heading level 2",
    "$49, Add to cart, button",
    "Size, S, radio button, 1 of 3",
    "Size, M, radio button, 2 of 3, selected",
    "Size, L, radio button, 3 of 3",
    "Cart (1), link",
    "Order confirmed",
]


class FakeEar:
    driver = "fake"

    def __init__(self, *, world: dict | None = None):
        self.world = world if world is not None else {"fixed": False}

    async def run(self, url: str, plan: Plan, *, timeout_s: int = 180, on_phrase=None) -> EarResult:
        lines = FIXED if self.world.get("fixed") else BROKEN
        phrases: list[Phrase] = []
        t = 0
        reached = False
        for i, text in enumerate(lines):
            t += 700 + (i % 3) * 150
            phrases.append(Phrase(i=i, text=text, t_ms=t, step=min(i, len(plan.steps) - 1)))
            if on_phrase is not None:
                await on_phrase(text, i, phrases[-1].step)
            goals = [plan.success_phrase, *plan.alternates]
            if any(g and g in text for g in goals):
                reached = True
        return EarResult(
            driver="fake",
            phrases=phrases,
            aria_yaml="- heading 'Running shoes'\n- button 'Add to cart'\n- group:\n  - button\n  - button\n  - button\n",
            reached_success=reached,
            duration_s=round(t / 1000, 1),
        )
