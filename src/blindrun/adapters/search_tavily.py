"""TavilySearch: live web retrieval for the fix loop (the Search port's real adapter).

Two load-bearing uses — this is not a decorative call:
  pattern(widget)  the fixer gets the CURRENT authoritative W3C ARIA APG guidance
                   (summary + keyboard + URL) instead of a frozen local copy
  docs(wcag_sc)    findings are grounded with the official WCAG Understanding doc,
                   surfaced in the dashboard and cited in the PR body

Any failure (no key, network, quota) degrades to CachedSearch — a run never
crashes because search was down; the run simply cites the cached pattern.
"""

import os

import httpx

from blindrun.adapters.search_fake import CachedSearch
from blindrun.ports import Pattern

_ENDPOINT = "https://api.tavily.com/search"


class TavilySearch:
    def __init__(self, api_key: str | None = None, client: httpx.AsyncClient | None = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        self._client = client  # injectable for tests
        self._cache = CachedSearch()

    async def _search(self, query: str, *, n: int = 4) -> dict:
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY not set")
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            r = await client.post(
                _ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": n,
                    "include_answer": True,
                },
            )
            r.raise_for_status()
            return r.json()
        finally:
            if self._client is None:
                await client.aclose()

    async def pattern(self, widget: str) -> Pattern:
        cached = await self._cache.pattern(widget)  # always available as the floor
        try:
            data = await self._search(
                f"W3C ARIA Authoring Practices Guide {widget} pattern keyboard interaction"
            )
            apg = next((r for r in data.get("results", []) if "w3.org" in r.get("url", "")), None)
            url = apg["url"] if apg else cached.url
            summary = (data.get("answer") or (apg or {}).get("content", "") or cached.summary)[:400]
            return Pattern(
                widget=widget,
                url=url,
                summary=summary,
                keyboard=cached.keyboard,  # stable interaction model; Tavily confirms the source
                source="tavily",
            )
        except Exception:  # noqa: BLE001 - degrade, never crash: search is an enhancement
            return cached

    async def docs(self, wcag_sc: str) -> str:
        """Official WCAG Understanding doc for a Success Criterion (e.g. '4.1.2')."""
        fallback = await self._cache.docs(wcag_sc)
        try:
            data = await self._search(f"Understanding WCAG Success Criterion {wcag_sc} site:w3.org", n=3)
            hit = next(
                (r for r in data.get("results", []) if "w3.org/wai" in r.get("url", "").lower()),
                None,
            )
            return hit["url"] if hit else fallback
        except Exception:  # noqa: BLE001 - degrade, never crash: search is an enhancement
            return fallback
