"""FakeVCS: writes the patch + PR body to .blindrun/ so you can inspect them,
and returns a file:// URL standing in for the pull request."""

import time
from pathlib import Path

from blindrun.ports import PRDraft


class FakeVCS:
    def __init__(self, out_dir: str | None = None):
        self.out = Path(out_dir or ".blindrun")
        self.out.mkdir(exist_ok=True)

    async def fetch(self, repo: str, ref: str, paths: list[str]) -> dict[str, str]:
        return {p: f"// fake {repo}@{ref} contents of {p}" for p in paths}

    async def open_pr(self, repo: str, base: str, draft: PRDraft, diff: str) -> str:
        stem = time.strftime("%Y%m%d-%H%M%S")
        (self.out / f"{stem}-{draft.branch.replace('/', '-')}.patch").write_text(diff)
        (self.out / f"{stem}-pr-body.md").write_text(draft.body_md)
        return f"file://{(self.out).resolve()}/{stem}-pr-body.md"
