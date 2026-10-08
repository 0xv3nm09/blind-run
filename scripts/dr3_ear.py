"""DR-3: the virtual ear hears a real page. Pass: transcript contains bare 'button'
for the planted unlabeled size divs, and the named elements are announced properly.

Run: uv run python scripts/dr3_ear.py
"""

import asyncio
import http.server
import socketserver
import threading
import time
from functools import partial
from pathlib import Path

from blindrun.adapters.ear_real import VirtualEar
from blindrun.schemas import Plan

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
PORT = 8931


def serve() -> tuple[socketserver.TCPServer, threading.Thread]:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t


async def main() -> int:
    httpd, _ = serve()
    url = f"http://127.0.0.1:{PORT}/product_broken.html"
    try:
        ear = VirtualEar()
        # walk the whole page: jump to heading, then next through every element
        plan = Plan(steps=["heading"] + ["next"] * 16, success_phrase="Order confirmed")
        t = time.perf_counter()
        result = await ear.run(url, plan, timeout_s=90)
        dt = time.perf_counter() - t
        print(f"--- transcript ({len(result.phrases)} phrases, {dt:.1f}s wall):")
        for p in result.phrases:
            print(f"  {p.t_ms:>6}ms step{p.step}  {p.text!r}")
        print("--- aria snapshot (first 10 lines):")
        print("\n".join("  " + ln for ln in result.aria_yaml.splitlines()[:10]))
        texts = [p.text for p in result.phrases]
        bare = sum(1 for t_ in texts if t_.strip().lower() == "button")  # nameless icon buttons
        named = any("add to cart" in t_.lower() and "button" in t_.lower() for t_ in texts)
        size_as_text = any(
            t_.strip() in ("S", "M", "L") for t_ in texts
        )  # sizes as bare text = invisible controls
        print(f"--- bare 'button' announcements: {bare} (nameless icon buttons = planted bug)")
        print(f"--- 'Add to cart' announced with role: {named}")
        print(f"--- size picker visible as text: {size_as_text}")
        ok = bare >= 2 and named and size_as_text
        print("DR-3 PASS" if ok else "DR-3 FAIL")
        return 0 if ok else 1
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
