import asyncio

"""Local sandbox: applies candidate patches to a scratch copy of the site, then
re-runs the virtual ear against the modified copy. A fix only passes when the
task completes by ear on the patched copy — same contract as ConTree branches.

This is the dev/demo fallback for SANDBOX_BACKEND=local; the Nebius Sandboxes
adapter (contree) takes the same shape when beta permissions land.
"""

import http.server
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
from functools import partial
from pathlib import Path

from blindrun.errors import SandboxError
from blindrun.ports import BranchResult, SandboxHandle
from blindrun.types import BranchVerdict


class _LocalHandle(SandboxHandle):
    def __init__(self, base_dir: Path):
        self.base = base_dir
        self.id = f"local_{abs(hash(str(base_dir))) % 10**8:08x}"

    async def sh(self, cmd: str, *, timeout_s: int = 300) -> tuple[int, str]:
        r = await asyncio.to_thread(
            subprocess.run,
            cmd,
            shell=True,
            cwd=self.base,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return r.returncode, (r.stdout + r.stderr)[-2000:]

    async def branch(self) -> "_LocalHandle":
        return self  # copies happen per check_branch

    async def close(self) -> None:
        return None


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a) -> None:
            pass

    handler = partial(Quiet, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _normalize_diff_paths(diff: str, target: str) -> str:
    """Models write arbitrary repo-relative paths in diff headers; the scratch site
    is a single-rooted copy, so force every file path to the target file."""
    import re

    lines = []
    for ln in diff.splitlines():
        if ln.startswith("--- "):
            lines.append(f"--- a/{target}")
        elif ln.startswith("+++ "):
            lines.append(f"+++ b/{target}")
        else:
            lines.append(re.sub(r"^(diff --git a/)\S+( b/)\S+$", r"\1" + target + r"\2" + target, ln))
    return "\n".join(lines)


def _apply_pairs(content: str, pairs: list[tuple[str, str]]) -> str | None:
    """Exact replacement when verbatim; indentation-tolerant fallback otherwise
    (models re-indent quoted lines far more often than they alter content)."""
    import re

    for search, replace in pairs:
        if search in content:
            content = content.replace(
                search, replace
            )  # ALL occurrences: one pattern often fixes several call sites
            continue
        lines = [re.escape(l.strip()) for l in search.split("\n") if l.strip()]
        rx = "\n".join(r"[ \t]*" + l for l in lines)
        m = re.search(rx, content)
        if m is None:
            return None
        actual = content[m.start() :].split("\n", 1)[0]
        indent = actual[: len(actual) - len(actual.lstrip())]
        quoted = search.split("\n", 1)[0]
        old_indent = quoted[: len(quoted) - len(quoted.lstrip())]
        if indent != old_indent:
            replace = "\n".join(
                indent + l[len(old_indent) :] if l.strip() and l.startswith(old_indent) else l
                for l in replace.split("\n")
            )
        content = content[: m.start()] + replace + content[m.end() :]
    return content


def _apply_edits(site: Path, target: str, edits: str) -> tuple[int, str]:
    """Apply <<<SEARCH ... === ... >>> blocks: exact match, else indentation-tolerant."""
    import re

    path = site / target
    if not path.is_file():
        return 1, f"target file missing: {target}"
    content = path.read_text()
    pairs = re.findall(r"<<<SEARCH\n(.*?)\n===\n(.*?)\n>>>", edits, re.DOTALL)
    if not pairs:
        return 1, "no SEARCH/REPLACE pairs found"
    applied = _apply_pairs(content, pairs)
    if applied is None:
        return 1, "search text not found in " + target + f": {pairs[0][0][:80]!r}"
    path.write_text(applied)
    return 0, ""


async def _apply(site: Path, patch_file: Path) -> tuple[int, str]:
    """Lenient-apply ladder: models write imprecise hunk headers, so recount lines,
    relax context matching, then fall back to classic patch(1) before giving up."""
    strategies = [
        ["git", "apply", "--recount", "--whitespace=nowarn"],
        ["git", "apply", "--recount", "-C1", "--whitespace=nowarn"],
        ["patch", "-p1", "-F3", "--batch", "-f", "-i"],
    ]
    err = ""
    for argv in strategies:
        r = await asyncio.to_thread(
            subprocess.run, [*argv, str(patch_file)], cwd=site, capture_output=True, text=True, check=False
        )
        if r.returncode == 0:
            return 0, ""
        err = (r.stderr or r.stdout)[-400:]
    return 1, err


class LocalSandbox:
    def __init__(self, *, base_dir: str, world: dict | None = None):
        self.base = Path(base_dir)
        if not self.base.is_dir():
            raise SandboxError(f"local sandbox base dir not found: {self.base}")
        self.world = world or {}

    async def prepare(self, repo: str, ref: str, setup: list[str]) -> _LocalHandle:
        return _LocalHandle(self.base)

    async def check_branch(self, patch: dict, *, axe_before: int = 0, plan=None) -> BranchResult:
        """apply -> serve -> ear replay. plan required (walker needs steps + success phrase)."""
        t0 = time.perf_counter()
        diff = patch.get("diff", "")
        tmp = Path(tempfile.mkdtemp(prefix="blindrun-branch-"))
        try:
            site = tmp / "site"
            shutil.copytree(self.base, site)
            target_name = self.world.get("page_file", "index.html")
            if "<<<SEARCH" in diff:
                rc, err = await asyncio.to_thread(_apply_edits, site, target_name, diff)
            else:
                patch_file = tmp / "candidate.patch"
                patch_file.write_text(_normalize_diff_paths(diff, target_name))
                rc, err = await _apply(site, patch_file)
            if rc != 0:
                return BranchResult(
                    patch_id=patch.get("id", "fix_unknown"),
                    verdict=BranchVerdict.failed_apply,
                    axe_before=axe_before,
                    axe_after=axe_before,
                    duration_s=time.perf_counter() - t0,
                    log_tail=err,
                )
            if plan is None:
                # no plan: build-check only (verdict 'passed' means it applied cleanly)
                return BranchResult(
                    patch_id=patch.get("id", "fix_unknown"),
                    verdict=BranchVerdict.passed,
                    axe_before=axe_before,
                    axe_after=axe_before,
                    duration_s=time.perf_counter() - t0,
                    log_tail="applied; no plan for ear replay",
                )

            httpd, port = _serve(site)
            try:
                from blindrun.adapters.ear_real import VirtualEar
                from blindrun.schemas import Plan as PlanModel

                p = PlanModel.model_validate(plan)
                steps = p.steps + ["next"] * max(0, p.max_steps - len(p.steps))
                walk = p.model_copy(update={"steps": steps})
                url = f"http://127.0.0.1:{port}/{self.world.get('page_file', 'index.html')}"
                ear = await VirtualEar().run(url, walk, timeout_s=120)
                passed = ear.reached_success  # post-act feedback only (node enforces the window)
                tail_phrases = [p_.text for p_ in ear.phrases[-4:]]
                return BranchResult(
                    patch_id=patch.get("id", "fix_unknown"),
                    verdict=BranchVerdict.passed if passed else BranchVerdict.failed_ear,
                    axe_before=axe_before,
                    axe_after=axe_before,
                    ear=ear,
                    duration_s=time.perf_counter() - t0,
                    log_tail="ear replay on patched copy: "
                    + ("success phrase heard" if passed else f"not heard; walker last heard {tail_phrases}"),
                )
            finally:
                httpd.shutdown()
        except SandboxError:
            raise
        except Exception as e:  # noqa: BLE001 - a broken candidate is a verdict, not a crash
            return BranchResult(
                patch_id=patch.get("id", "fix_unknown"),
                verdict=BranchVerdict.failed_build,
                axe_before=axe_before,
                axe_after=axe_before,
                duration_s=time.perf_counter() - t0,
                log_tail=f"{type(e).__name__}: {e}"[:400],
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
