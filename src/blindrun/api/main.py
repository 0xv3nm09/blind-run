"""FastAPI surface. Day 1: in-process worker (no Redis yet) + SSE stream.

POST /v1/runs         -> 202 + run_id (runs run_flow as a background task)
GET  /v1/runs/{id}    -> status + counts
GET  /v1/runs/{id}/events -> text/event-stream (replay + live)
GET  /healthz         -> {"ok": true}
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sse_starlette.sse import EventSourceResponse

from blindrun.config import get_settings
from blindrun.deps import build_deps
from blindrun.pipeline.orchestrator import new_run_id, run_flow
from blindrun.schemas import Event
from blindrun.types import RunId

_DEPS = None


def deps():
    global _DEPS
    if _DEPS is None:
        _DEPS = build_deps(get_settings())
    return _DEPS


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps()  # build (and assert ports) once at startup, not mid-run
    yield
    _DEPS = None


app = FastAPI(title="Blind-Run API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline hardening; the dashboard is same-origin so no CORS is opened."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'"
    )
    return resp


@app.middleware("http")
async def request_id(request, call_next):
    import uuid as _uuid

    rid = request.headers.get("x-request-id", _uuid.uuid4().hex)
    resp = await call_next(request)
    resp.headers["x-request-id"] = rid
    return resp


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    url: HttpUrl
    task: str = Field(min_length=5, max_length=300, examples=["buy the cheapest item"])
    driver: str | None = Field(default=None, pattern=r"^(virtual|voiceover|nvda|fake)$")
    fix: bool = True
    repo: str | None = Field(default=None, pattern=r"^[\w.-]+/[\w.-]+$")


class RunCreated(BaseModel):
    run_id: str
    status: str = "queued"
    events_url: str


@app.post("/v1/runs", status_code=202, response_model=RunCreated)
async def create_run(body: RunRequest) -> RunCreated:
    run_id = new_run_id()
    asyncio.get_running_loop().create_task(run_flow(deps(), RunId(run_id), body.model_dump(mode="json")))
    return RunCreated(run_id=run_id, events_url=f"/v1/runs/{run_id}/events")


@app.get("/v1/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    run = await deps().store.get_run(RunId(run_id))
    if run is None:
        raise HTTPException(404, "run not found")
    return run


_REPLAY_ID = "demo"  # reserved run id: replays the recorded flagship run for judges
_REPLAY_FILE = Path(__file__).resolve().parents[3] / "bench" / "recorded_run.jsonl"
# demo-PR evidence (transcript diff + patch) served so the dashboard's PR banner
# link resolves on the API host; the same path works when the repo is served
# statically (GitHub Pages) because evidence/ sits at the repo root
_EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "evidence"
if _EVIDENCE_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/evidence", StaticFiles(directory=str(_EVIDENCE_DIR)), name="evidence")


def _replay_events() -> list[Event] | None:
    if not _REPLAY_FILE.is_file():
        return None
    events = []
    for line in _REPLAY_FILE.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(Event.model_validate_json(line))
    return events or None


@app.get("/v1/runs/{run_id}/events")
async def run_events(run_id: str, after_seq: int = -1):
    if run_id == _REPLAY_ID:
        events = _replay_events()
        if events is None:
            raise HTTPException(404, "no recorded demo run (bench/recorded_run.jsonl)")

        async def replay_gen():
            import asyncio

            for ev in events:
                if ev.seq <= after_seq:
                    continue
                yield {"event": "update", "id": str(ev.seq), "data": ev.model_dump_json()}
                await asyncio.sleep(0.12)  # let judges watch it stream

        return EventSourceResponse(replay_gen(), ping=15)

    rid = RunId(run_id)

    async def gen():
        async for ev in deps().events.subscribe(rid, after_seq):
            yield {
                "event": "update",
                "id": str(ev.seq),
                "data": ev.model_dump_json(),
            }

    return EventSourceResponse(gen(), ping=15)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/v1/runs/{run_id}/findings")
async def run_findings(run_id: str) -> list[dict]:
    if run_id == _REPLAY_ID:
        events = _replay_events() or []
        return [e.data for e in events if e.type == "finding.new" and "heard" in e.data]
    out = []
    for f in deps().store.findings.get(RunId(run_id), []):
        out.append(
            {
                "id": f.id,
                "wcag_sc": f.wcag_sc,
                "category": f.category.value,
                "severity": f.severity,
                "confidence": f.confidence,
                "heard": f.heard,
                "seen": f.seen,
                "element_hint": f.element_hint,
                "route": f.route.value if f.route else None,
            }
        )
    return out


@app.get("/v1/benchmark/latest")
async def benchmark_latest() -> dict:
    path = Path(__file__).resolve().parents[3] / "bench" / "results.json"
    if not path.is_file():
        raise HTTPException(404, "no benchmark results yet")
    return json.loads(path.read_text())


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "dashboard.html")
