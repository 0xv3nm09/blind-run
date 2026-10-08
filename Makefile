.PHONY: setup up test lint dr7 serve bench demo

setup: ## install everything (day 1: lean core)
	uv sync && uv run python -m blindrun --help

up: ## API + dashboard (fakes, no Docker needed)
	uv run uvicorn blindrun.api.main:app --reload

test: ## unit + pipeline (no network, no keys)
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

dr7: ## whole pipeline on fakes — the day-1 milestone
	uv run python -m blindrun run --url http://shop.test/product/1 --task "buy the cheapest item" --repo demo/shop

dr3: ## the real virtual ear hears the demo page
	uv run python scripts/dr3_ear.py

dr4: ## axe vs the ARIA snapshot on the demo shop
	uv run python scripts/dr4_axe.py

dr1: ## real Nemotron Super planner call (needs NEBIUS_API_KEY)
	uv run python scripts/dr1_plan.py

serve-shop: ## demo shop on :8932
	uv run python -m http.server 8932 --directory demo-shop

bench: ## axe vs ear over the planted-bug shop -> bench/results.json
	uv run python -m blindrun.eval.benchmark --condition both
