"""In-process store: runs and findings in dicts. Same port as SQLite/Postgres."""

from blindrun.ports import Finding, RunId, RunStatus


class MemoryStore:
    def __init__(self) -> None:
        self.runs: dict[RunId, dict] = {}
        self.findings: dict[RunId, list[Finding]] = {}

    async def save_run(self, run: dict) -> None:
        self.runs[run["run_id"]] = run

    async def set_status(self, run_id: RunId, status: RunStatus, reason: str = "") -> None:
        run = self.runs.setdefault(run_id, {"run_id": run_id})
        run["status"] = status
        if reason:
            run["reason"] = reason

    async def add_findings(self, items: list[Finding]) -> None:
        for f in items:
            self.findings.setdefault(f.run_id, []).append(f)

    async def get_run(self, run_id: RunId) -> dict | None:
        return self.runs.get(run_id)
