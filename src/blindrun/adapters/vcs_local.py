"""Local VCS adapter: reads files straight off disk (demo-shop), writes PR artifacts
to .blindrun/ like FakeVCS. The GitHub adapter replaces it for DR-8."""

from pathlib import Path

from blindrun.ports import PRDraft


class LocalVCS:
    def __init__(self, *, base_dir: str):
        self.base = Path(base_dir)

    async def fetch(self, repo: str, ref: str, paths: list[str]) -> dict[str, str]:
        return {p: (self.base / p).read_text() for p in paths if (self.base / p).is_file()}

    async def open_pr(self, repo: str, base: str, draft: PRDraft, diff: str) -> str:
        import time

        out = Path(".blindrun")
        out.mkdir(exist_ok=True)
        stem = time.strftime("%Y%m%d-%H%M%S")
        (out / f"{stem}-{draft.branch.replace('/', '-')}.patch").write_text(diff)
        (out / f"{stem}-pr-body.md").write_text(draft.body_md)
        return f"file://{out.resolve()}/{stem}-pr-body.md"
