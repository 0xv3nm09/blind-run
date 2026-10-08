"""FakeLLM: canned, role-aware replies so the whole pipeline runs on day 1.

The fixer returns three candidate patches; the one whose marker is "good"
(simulated proper radio group) is the branch that passes in FakeSandbox.
"""

import json
from typing import get_args

from pydantic import BaseModel

from blindrun.ports import Budget, Role


class FakeLLM:
    def __init__(self, *, world: dict | None = None):
        self.world = world or {}
        self.calls = 0

    def _check_role(self, role: Role) -> None:
        if role not in get_args(Role):
            raise ValueError(f"unknown role {role}")

    async def structured(
        self, role, messages, schema: type[BaseModel], *, images=(), budget: Budget, thinking=None
    ) -> BaseModel:
        self._check_role(role)
        self.calls += 1
        budget.calls += 1
        budget.tokens_used += 1_500  # plausible fake usage so the meter moves
        payload = self._reply(role, schema)
        return schema.model_validate(payload)

    async def text(self, role, messages, *, budget: Budget) -> str:
        self._check_role(role)
        self.calls += 1
        budget.calls += 1
        if role == "fixer":
            # three canned edits; markers drive FakeSandbox's verdicts (see sandbox_fake)
            return (
                '```fix\n<<<SEARCH\n<div class="size" onclick="pick(this)">S</div>\n'
                '===\n<div class="size" aria-label="S" onclick="pick(this)">S</div><!-- aria-label-only -->\n>>>\n```\n'
                '```fix\n<<<SEARCH\n<div class="size" onclick="pick(this)">M</div>\n'
                '===\n<fieldset><legend>Size</legend><input type="radio" name="size"><!-- native-radio-group --></fieldset>\n>>>\n```\n'
                '```fix\n<<<SEARCH\n<div class="size" onclick="pick(this)">L</div>\n'
                '===\n<div role="listbox"><!-- listbox-missing-keys --></div>\n>>>\n```'
            )
        return json.dumps({"note": f"fake {role} reply"})

    def _reply(self, role, schema) -> dict:
        if role == "planner":
            return {
                "steps": ["next", "next", "next", "act", "next", "act", "next", "next", "act"],
                "success_phrase": "Order confirmed",
                "max_steps": 40,
            }
        if role == "auditor":
            # Two findings: one auto-fixable blocker (the planted size picker),
            # one lower-confidence navigation issue that routes to human.
            return {
                "findings": [
                    {
                        "wcag_sc": "4.1.2",
                        "category": "label",
                        "severity": "blocker",
                        "heard": "button",
                        "seen": "Size option 'S'",
                        "element_hint": "ProductPage > SizePicker",
                        "model_conf": 0.91,
                        "evidence": ["heard", "seen"],
                    },
                    {
                        "wcag_sc": "2.4.3",
                        "category": "navigation",
                        "severity": "major",
                        # inferred, NOT a transcript quote -> low evidence -> human route
                        "heard": "(silence after Add to cart — focus moved, nothing announced)",
                        "seen": "Focus returned to page top after Add",
                        "element_hint": "ProductPage",
                        "model_conf": 0.46,
                        "evidence": ["heard", "seen"],
                    },
                ]
            }
        if role == "fixer":
            finding_id = "fnd_000000000001"
            return {
                "patches": [
                    {
                        "id": "fix_aaaaaaaa0001",
                        "finding_id": finding_id,
                        "diff": "--- a/SizePicker.tsx\n+++ b/SizePicker.tsx\n-marker: aria-label-only\n",
                        "rationale": "aria-label on each div (weak: still not keyboard operable)",
                        "pattern_url": "https://www.w3.org/WAI/ARIA/apg/patterns/radio/",
                    },
                    {
                        "id": "fix_bbbbbbbb0002",
                        "finding_id": finding_id,
                        "diff": "--- a/SizePicker.tsx\n+++ b/SizePicker.tsx\n-marker: native-radio-group\n",
                        "rationale": "native <fieldset> + radio inputs with labels (W3C radio group pattern)",
                        "pattern_url": "https://www.w3.org/WAI/ARIA/apg/patterns/radio/",
                    },
                    {
                        "id": "fix_cccccccc0003",
                        "finding_id": finding_id,
                        "diff": "--- a/SizePicker.tsx\n+++ b/SizePicker.tsx\n-marker: listbox-missing-keys\n",
                        "rationale": "role=listbox + aria-selected, but arrow keys do nothing",
                        "pattern_url": "https://www.w3.org/WAI/ARIA/apg/patterns/listbox/",
                    },
                ]
            }
        if role == "guard":
            return {"verdict": "allow", "reason": "fake guard allows"}
        return {"note": f"fake {role} structured reply"}
