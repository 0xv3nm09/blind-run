"""Nebius Sandboxes (ConTree) adapter — the real thing.

Parent checkpoint (built once): python:3.12-slim + Node 22 + Playwright/Chromium
+ the Guidepup Virtual Screen Reader. Every candidate fix then runs as a parallel
branch from that checkpoint ON NEBIUS: it applies its search/replace edit to the
site copy, serves the site on localhost inside the sandbox, and replays the ear
task there. A candidate passes only when the task completes by ear.
SDK semantics (live-verified Oct 7): `run(...).wait()` RETURNS the checkpoint
object (state SUCCEEDED + uuid); branching = `images.use(parent_uuid).run(...)`;
concurrent runs on one uuid are parallel branches; free while in beta.
"""

import asyncio
import json
import shlex
import time
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from blindrun.errors import SandboxError
from blindrun.ports import BranchResult
from blindrun.schemas import EarResult, Phrase
from blindrun.schemas import Plan as PlanModel
from blindrun.types import BranchVerdict

_EAR_SCRIPT = Path(__file__).resolve().parents[3] / "runner" / "virtual_run.mjs"
_EAR_IMAGE = "python:3.12-slim"  # catalog carries python but not node images (verified Oct 7)
_PARENT_SETUP = (
    "apt-get update -qq && apt-get install -y -qq curl ca-certificates >/dev/null"
    " && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null"
    " && apt-get install -y -qq nodejs >/dev/null"
    " && mkdir -p /ear && cd /ear && npm init -y >/dev/null"
    " && npm i playwright @guidepup/virtual-screen-reader >/dev/null 2>&1"
    " && npx playwright install --with-deps chromium >/dev/null 2>&1"
    " && node --version && echo EAR-READY"
)

_APPLY_PY = r"""
import sys, re
path, edits = sys.argv[1], open(sys.argv[2]).read()
content = open(path).read()
NL = chr(10)
pattern = "<<<SEARCH" + NL + "(.*?)" + NL + "===" + NL + "(.*?)" + NL + ">>>"
pairs = re.findall(pattern, edits, re.S)
if not pairs:
    sys.exit("no SEARCH/REPLACE pairs")
for search, replace in pairs:
    if search not in content:
        sys.exit(f"SEARCH-NOT-FOUND: {search[:80]!r}")
    content = content.replace(search, replace)  # ALL occurrences
open(path, "w").write(content)
print("APPLIED")
"""


class ContreeSandbox:
    def __init__(
        self, *, base_dir: str = "demo-shop", world: dict | None = None, ear_image: str = _EAR_IMAGE
    ):
        self.base = Path(base_dir)
        if not self.base.is_dir():
            raise SandboxError(f"sandbox base dir not found: {self.base}")
        self.world = world or {}
        self.ear_image = ear_image
        self._parent = None  # checkpoint object with .uuid, built once per process

    # ---- parent preparation (once per process) ----
    @retry(
        retry=retry_if_exception_type(Exception),  # narrowed below: transport/timeout classes
        wait=wait_random_exponential(min=5, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _build_parent_sync(self) -> object:
        from contree_sdk import ContreeSync

        client = ContreeSync()
        base = client.images.use(self.ear_image)
        parent = base.run(shell=_PARENT_SETUP, timeout=1800, disposable=False, tag="blindrun-ear").wait()
        state = str(getattr(parent, "state", ""))
        if "SUCCEEDED" not in state or "EAR-READY" not in (parent.stdout or ""):
            raise SandboxError(f"ear parent build failed (state {state}): {(parent.stderr or '')[-300:]}")
        return parent

    async def prepare(self, repo: str, ref: str, setup: list[str]):
        if self._parent is None:
            self._parent = await asyncio.to_thread(self._build_parent_sync)
        return self._parent

    # ---- one candidate = one parallel branch from the parent checkpoint ----
    async def check_branch(self, patch: dict, *, axe_before: int = 0, plan=None) -> BranchResult:
        if self._parent is None:
            await self.prepare("demo-shop", "main", [])
        t0 = time.perf_counter()
        if plan is None:
            raise SandboxError("ContreeSandbox.check_branch needs the plan for the ear replay")
        p = PlanModel.model_validate(plan)
        page_file = self.world.get("page_file", "index.html")

        cfg = json.dumps(
            {
                "url": "http://127.0.0.1:8000/" + page_file,
                "steps": (p.steps + ["next"] * max(0, p.max_steps - len(p.steps)))[: p.max_steps],
                "successPhrase": p.success_phrase,
                "successPhrases": [p.success_phrase, *p.alternates],
                "maxSteps": p.max_steps,
                "bundle": "/ear/node_modules/@guidepup/virtual-screen-reader/lib/esm/index.browser.js",
            }
        )
        # files= is the documented upload path (concurrent, sha256-deduped) — no heredocs.
        # Server + replay share ONE run: checkpoints save filesystem, not processes.
        site_files = {
            q.name: q.read_text()
            for q in sorted(self.base.rglob("*"))
            if q.is_file() and q.suffix in (".html", ".css", ".js")
        }
        files_payload: dict[str, bytes] = {
            **{f"/site/{name}": content.encode() for name, content in site_files.items()},
            "/tmp/edits": patch.get("diff", "").encode(),
            "/tmp/apply.py": _APPLY_PY.encode(),
            "/ear/virtual_run.mjs": Path(_EAR_SCRIPT).read_bytes(),
        }
        inner = chr(10).join(
            [
                "set -e",
                f"python3 /tmp/apply.py /site/{page_file} /tmp/edits",
                "cd /site && nohup python3 -m http.server 8000 >/dev/null 2>&1 &",
                "sleep 1",
                f"cd /ear && node virtual_run.mjs {shlex.quote(cfg)}",
            ]
        )

        from contree_sdk import ContreeSync

        client = ContreeSync()
        parent_uuid = self._parent.uuid

        @retry(
            retry=retry_if_exception_type(Exception),
            wait=wait_random_exponential(min=2, max=30),
            stop=stop_after_attempt(3),
            reraise=True,
        )
        def run_branch():
            return (
                client.images.use(parent_uuid)
                .run(shell=inner, files=files_payload, timeout=600, disposable=True)
                .wait()
            )

        r = await asyncio.to_thread(run_branch)
        state = str(getattr(r, "state", ""))
        out = r.stdout or ""
        tail = ((r.stderr or "") + "|" + out)[-400:]
        if "SUCCEEDED" not in state or "reached_success" not in out:
            verdict = BranchVerdict.failed_apply if "SEARCH-NOT-FOUND" in tail else BranchVerdict.failed_build
            return BranchResult(
                patch_id=patch.get("id", "fix_unknown"),
                verdict=verdict,
                axe_before=axe_before,
                axe_after=axe_before,
                duration_s=time.perf_counter() - t0,
                log_tail=tail,
            )
        payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
        ear = EarResult(
            driver="virtual",
            phrases=[Phrase.model_validate(x) for x in payload["phrases"]],
            aria_yaml=payload.get("aria_yaml", ""),
            reached_success=payload["reached_success"],
        )
        passed = payload["reached_success"]
        heard = " | ".join(str(x.get("phrase", "?")) for x in payload["phrases"][-8:])
        tail = (
            f"nebius sandbox ear: {'success heard' if passed else 'walk ended without success'}"
            f"; last heard: {heard}"
        )
        return BranchResult(
            patch_id=patch.get("id", "fix_unknown"),
            verdict=BranchVerdict.passed if passed else BranchVerdict.failed_ear,
            axe_before=axe_before,
            axe_after=axe_before,
            ear=ear,
            duration_s=time.perf_counter() - t0,
            log_tail=tail,
        )
