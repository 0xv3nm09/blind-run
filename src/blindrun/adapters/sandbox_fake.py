"""FakeSandbox: deterministic branch verdicts without any cloud.

Patch markers (see FakeLLM's fixer replies):
  native-radio-group  -> passed (the branch the workbook's example run picks)
  aria-label-only     -> failed_ear   (applies, builds, but the ear still says 'button')
  listbox-missing-keys-> failed_ear   (announces, but arrow keys do nothing)
Anything else          -> failed_build
"""

import asyncio

from blindrun.ports import BranchResult, SandboxHandle
from blindrun.types import BranchVerdict


class _FakeHandle(SandboxHandle):
    def __init__(self, sid: str):
        self.id = sid
        self.commands: list[str] = []

    async def sh(self, cmd: str, *, timeout_s: int = 300) -> tuple[int, str]:
        self.commands.append(cmd)
        return 0, f"fake ok: {cmd[:60]}"

    async def branch(self) -> "_FakeHandle":
        return _FakeHandle(f"{self.id}-b{len(self.commands)}")

    async def close(self) -> None:
        return None


class FakeSandbox:
    def __init__(self, *, world: dict | None = None):
        self.world = world or {}
        self.prepared: list[str] = []

    async def prepare(self, repo: str, ref: str, setup: list[str]) -> _FakeHandle:
        await asyncio.sleep(0)  # keep it a coroutine like the real one
        h = _FakeHandle(f"sbx_{abs(hash((repo, ref))) % 10**8:08x}")
        self.prepared.append(h.id)
        return h

    async def check_branch(self, patch: dict, *, axe_before: int = 0, plan=None) -> BranchResult:
        """Simulated apply -> build -> axe -> virtual-ear ladder for one candidate."""
        diff = patch.get("diff", "")
        if "native-radio-group" in diff:
            verdict, axe_after, tail = (
                BranchVerdict.passed,
                axe_before,
                "ear: 'Size, M, radio button, 2 of 3, selected'",
            )
        elif "aria-label-only" in diff:
            verdict, axe_after, tail = (
                BranchVerdict.failed_ear,
                axe_before,
                "ear: still 'button', no keyboard",
            )
        elif "listbox-missing-keys" in diff:
            verdict, axe_after, tail = BranchVerdict.failed_ear, axe_before, "ear: announces, arrow keys dead"
        else:
            verdict, axe_after, tail = BranchVerdict.failed_build, axe_before, "build failed: unknown marker"
        await asyncio.sleep(0)
        return BranchResult(
            patch_id=patch.get("id", "fix_unknown"),
            verdict=verdict,
            axe_before=axe_before,
            axe_after=axe_after,
            duration_s=0.05,
            log_tail=tail,
        )
