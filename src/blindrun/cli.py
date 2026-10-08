"""CLI: `blindrun run` (UC-01) and `blindrun serve` (the API + dashboard)."""

import asyncio
import json

import typer

from blindrun.config import get_settings
from blindrun.deps import build_deps
from blindrun.pipeline.orchestrator import new_run_id, run_flow
from blindrun.types import RunStatus

app = typer.Typer(no_args_is_help=True, help="Blind-Run: prove a web flow can be completed by ear.")


@app.command()
def run(
    url: str = typer.Option(..., "--url", help="page or flow start URL"),
    task: str = typer.Option(..., "--task", help='plain-English task, e.g. "buy the cheapest item"'),
    repo: str = typer.Option(None, "--repo", help="owner/name; needed for fix + PR"),
    no_fix: bool = typer.Option(False, "--no-fix", help="report only"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="print events live"),
    record: str = typer.Option(None, "--record", help="write the full event stream to this JSONL path"),
) -> None:
    """Run one flow end-to-end and print the event stream (DR-7 on fakes by default)."""
    settings = get_settings()
    deps = build_deps(settings)
    run_id = new_run_id()
    sink = open(record, "w") if record else None  # noqa: SIM115 - closed after the run completes

    async def _recorder() -> None:
        async for ev in deps.events.subscribe(run_id):
            if sink:
                sink.write(ev.model_dump_json() + "\n")
                sink.flush()

    async def _run() -> RunStatus:
        tasks = [asyncio.get_running_loop().create_task(_recorder())]
        if watch:
            tasks.append(asyncio.get_running_loop().create_task(_printer(deps, run_id)))
        status = await run_flow(
            deps,
            run_id,
            {"project_id": "demo-shop", "url": url, "task": task, "repo": repo, "fix": not no_fix},
        )
        # give the printers a beat to drain the last events
        await asyncio.sleep(0.3)
        if sink:
            sink.close()
        return status

    status = asyncio.run(_run())
    findings = deps.store.findings.get(run_id, [])
    if findings:
        print("\n--- findings:")
        for f in findings:
            print(
                f"  [{f.severity:>7}] WCAG {f.wcag_sc:<6} conf {f.confidence:.2f} route={f.route.value if f.route else '-':<12} {f.element_hint or ''}"
            )
            print(f"            heard: {f.heard!r}")
            print(f"            seen:  {f.seen!r}")
    print(f"\nrun {run_id}: {status.value}, {len(findings)} finding(s)")
    raise typer.Exit(code=0 if status == RunStatus.done else 1)


async def _printer(deps, run_id) -> None:
    async for ev in deps.events.subscribe(run_id):
        if ev.type == "ear.phrase":
            print(f"  seq {ev.seq:>3} ear.phrase      {ev.data['text']!r}")
        else:
            print(f"  seq {ev.seq:>3} {ev.type:<15} {json.dumps(ev.data, ensure_ascii=False)[:110]}")


@app.command()
def serve(host: str = typer.Option("127.0.0.1"), port: int = typer.Option(8000)) -> None:
    """Start the API (SSE event stream at /v1/runs/{id}/events)."""
    import uvicorn

    uvicorn.run("blindrun.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
