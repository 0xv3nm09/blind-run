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
import hashlib
import io
import json
import shlex
import tarfile
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
import sys, re, hashlib
path, edits = sys.argv[1], open(sys.argv[2]).read()
expected_site_md5 = sys.argv[3] if len(sys.argv) > 3 else ""
content = open(path).read()
pristine_md5 = hashlib.md5(content.encode()).hexdigest()
NL = chr(10)

def md5(t):
    return hashlib.md5(t.encode()).hexdigest()

def diag(search, n):
    note = "" if pristine_md5 == expected_site_md5 else " MISMATCH"
    return (
        f"SEARCH-NOT-FOUND (pair {n}): {search[:80]!r}"
        f" | pristine site md5 {pristine_md5} (expected {expected_site_md5 or '?'}{note})"
        f" | edits md5 {md5(edits)}"
    )

pattern = "<<<SEARCH" + NL + "(.*?)" + NL + "===" + NL + "(.*?)" + NL + ">>>"
pairs = re.findall(pattern, edits, re.S)
if not pairs:
    sys.exit("no SEARCH/REPLACE pairs")
for n, (search, replace) in enumerate(pairs, 1):
    if search in content:
        content = content.replace(search, replace)  # ALL occurrences
        continue
    lines = [re.escape(l.strip()) for l in search.split(NL) if l.strip()]
    rx = NL.join(r"[ \t]*" + l for l in lines)
    m = re.search(rx, content)
    if m is None:
        sys.exit(diag(search, n))
    actual = content[m.start():].split(NL, 1)[0]
    indent = actual[: len(actual) - len(actual.lstrip())]
    quoted = search.split(NL, 1)[0]
    old_indent = quoted[: len(quoted) - len(quoted.lstrip())]
    if indent != old_indent:
        replace = NL.join(
            indent + l[len(old_indent):] if l.strip() and l.startswith(old_indent) else l
            for l in replace.split(NL)
        )
    content = content[: m.start()] + replace + content[m.end():]
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
        import uuid

        from contree_sdk import ContreeSync

        client = ContreeSync()
        base = client.images.use(self.ear_image)
        # unique tag: a fixed tag can resolve to an older parent whose filesystem
        # carries stale /site files from debugging runs; never inherit state
        tag = f"blindrun-ear-{uuid.uuid4().hex[:6]}"
        parent = base.run(shell=_PARENT_SETUP, timeout=1800, disposable=False, tag=tag).wait()
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
        # Site goes in as a tarball and is unpacked over a wiped /site: uploading
        # files to /site paths directly proved unreliable (stale copies from the
        # parent's history can shadow the upload), and the tar keeps subdirs intact.
        # files= is the documented upload path (concurrent, sha256-deduped) — no heredocs.
        # Server + replay share ONE run: checkpoints save filesystem, not processes.
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for q in sorted(self.base.rglob("*")):
                if q.is_file() and q.suffix in (".html", ".css", ".js"):
                    info = tf.gettarinfo(str(q), arcname=q.relative_to(self.base).as_posix())
                    with q.open("rb") as fh:
                        tf.addfile(info, fh)
        # binary files= payloads are byte-faithful (verified in-branch by md5);
        # the tar preserves the controls/ subdir the flat-name upload flattened
        # unique edits path per branch: three candidates upload three different
        # files; never let same-path concurrent uploads share a cache entry
        patch_id = "".join(c if c.isalnum() or c == "_" else "_" for c in patch.get("id", "x"))
        edits_path = f"/tmp/edits_{patch_id}"
        expected_site_md5 = hashlib.md5(
            (self.base / page_file).read_text().encode()
        ).hexdigest()
        files_payload: dict[str, bytes] = {
            "/tmp/site.tar": buf.getvalue(),
            edits_path: patch.get("diff", "").encode(),
            "/tmp/apply.py": _APPLY_PY.encode(),
            "/ear/virtual_run.mjs": Path(_EAR_SCRIPT).read_bytes(),
        }
        inner = chr(10).join(
            [
                "set -e",
                "rm -rf /site && mkdir -p /site && tar -xf /tmp/site.tar -C /site",
                f"python3 /tmp/apply.py /site/{page_file} {edits_path} {expected_site_md5}",
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
        heard = " | ".join(str(x.get("text", "?")) for x in payload["phrases"][-8:])
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
