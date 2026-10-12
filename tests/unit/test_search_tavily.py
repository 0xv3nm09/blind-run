"""TavilySearch: live-retrieval behavior, fully offline via a mocked transport.

The bonus lane requires a functional runtime Tavily call as part of the solution —
these tests pin exactly what that call does: APG guidance for the fixer, the
WCAG Understanding doc for findings, and hard degradation to CachedSearch."""

import httpx
import pytest

from blindrun.adapters.search_tavily import TavilySearch


def _client(payload=None, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"detail": "boom"})
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


_APG = {
    "answer": "Radio group: use native radio inputs in a fieldset; arrow keys move.",
    "results": [
        {"title": "MDN radio", "url": "https://developer.mozilla.org/radio", "content": "x"},
        {"title": "APG", "url": "https://www.w3.org/WAI/ARIA/apg/patterns/radio/", "content": "y"},
    ],
}
_DOCS = {"results": [{"url": "https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html"}]}


@pytest.mark.anyio
async def test_pattern_uses_tavily_and_prefers_w3():
    ts = TavilySearch(api_key="tvly-test", client=_client(_APG))
    p = await ts.pattern("radio")
    assert p.source == "tavily"
    assert p.url == "https://www.w3.org/WAI/ARIA/apg/patterns/radio/"
    assert "fieldset" in p.summary
    assert p.keyboard  # stable interaction model kept


@pytest.mark.anyio
async def test_docs_returns_understanding_url():
    ts = TavilySearch(api_key="tvly-test", client=_client(_DOCS))
    assert await ts.docs("4.1.2") == "https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html"


@pytest.mark.anyio
async def test_degrades_to_cache_on_error():
    ts = TavilySearch(api_key="tvly-test", client=_client(None, status=500))
    p = await ts.pattern("dialog")
    assert p.source == "cache"
    assert "w3.org" in await ts.docs("2.1.1")


@pytest.mark.anyio
async def test_no_key_degrades_without_network():
    ts = TavilySearch(api_key="", client=None)
    p = await ts.pattern("combobox")
    assert p.source == "cache"
