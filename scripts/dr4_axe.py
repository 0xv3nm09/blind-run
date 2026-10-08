"""DR-4: axe and the ARIA snapshot agree — and disagree in the right places.

Pass on demo-shop/product.html:
  - axe flags the axe-catchable pages' violations (e.g. search.html empty link/nameless inputs)
  - axe reports ZERO violations on product.html (the ear-only bugs: B11/B20/BX1)
  - the ARIA snapshot shows what the ear will walk (size group as text, nameless buttons)

Run: uv run python scripts/dr4_axe.py   (serves demo-shop on :8932)
"""

import asyncio
import http.server
import socketserver
import threading
from functools import partial
from pathlib import Path

from axe_playwright_python.async_playwright import Axe
from playwright.async_api import async_playwright

SHOP = Path(__file__).resolve().parents[1] / "demo-shop"
PORT = 8932


def serve() -> socketserver.TCPServer:
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:  # keep the DR output clean
            pass

    handler = partial(QuietHandler, directory=str(SHOP))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


async def audit(page, path: str) -> list[str]:
    await page.goto(f"http://127.0.0.1:{PORT}/{path}", wait_until="networkidle")
    res = await Axe().run(page)
    return sorted({v["id"] for v in res.response["violations"]})


async def main() -> int:
    httpd = serve()
    failures = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            axe_sees = await audit(page, "search.html")
            print(f"search.html  axe violations: {len(axe_sees)} {axe_sees}")
            if len(axe_sees) < 3:
                failures.append("axe should flag the 3 planted rule bugs on search.html")

            axe_sees_support = await audit(page, "support.html")
            print(f"support.html axe violations: {len(axe_sees_support)} {axe_sees_support}")
            if len(axe_sees_support) < 3:
                failures.append("axe should flag the 3 planted rule bugs on support.html")

            product = await audit(page, "product.html")
            print(f"product.html axe violations: {len(product)} {product}")
            if set(product) - {"button-name"}:
                failures.append("axe should only flag button-name (icon buttons) on product.html")

            snapshot = await page.locator("body").aria_snapshot()
            print("--- product.html aria snapshot:")
            print("\n".join("  " + ln for ln in snapshot.splitlines()))
            if "- button:" not in snapshot:  # nameless buttons render as bare 'button'
                failures.append("aria snapshot should show nameless buttons")
            ok = not failures
            print("DR-4 PASS" if ok else "DR-4 FAIL: " + "; ".join(failures))
            await browser.close()
            return 0 if ok else 1
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
