"""Live Token Factory checks — run with `uv run pytest -m slow` (needs NEBIUS_API_KEY)."""

import pytest

from blindrun.adapters.llm_tokenfactory import TokenFactoryLLM, sanitize_schema
from blindrun.config import get_settings
from blindrun.schemas import Budget, Plan

pytestmark = pytest.mark.slow

ARIA = '- heading "Running shoes" [level=2]\n- button "Add to cart"\n- group:\n  - button\n  - button\n  - button\n- link "Cart (0)"\n'


def test_sanitize_strips_only_pattern():
    schema = {"type": "object", "properties": {"a": {"type": "string", "pattern": "^x$", "minLength": 1}}}
    out = sanitize_schema(schema)
    assert "pattern" not in out["properties"]["a"]
    assert out["properties"]["a"]["minLength"] == 1  # other constraints survive


async def test_super_returns_valid_plan():
    s = get_settings()
    if not s.nebius_api_key.get_secret_value():
        pytest.skip("NEBIUS_API_KEY not set")
    llm = TokenFactoryLLM(api_key=s.nebius_api_key.get_secret_value(), models=s.model_map())
    plan = await llm.structured(
        "planner",
        [
            {
                "role": "system",
                "content": "You plan keyboard-only screen-reader steps. Allowed steps: next, previous, act, type:<text>, press:<key>, heading, landmark, form. Reply only with JSON matching the schema.",
            },
            {"role": "user", "content": f"Task: buy the cheapest item\n<aria>\n{ARIA}\n</aria>"},
        ],
        Plan,
        budget=Budget(),
    )
    assert 1 <= len(plan.steps) <= 60
    assert len(plan.success_phrase) >= 2
