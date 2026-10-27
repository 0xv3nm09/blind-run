/* Data layer — two adapters behind one contract: live SSE (FastAPI) and static
   replay (GitHub Pages, fetching bench/recorded_run.jsonl). Same event shapes. */

// root-absolute: works from FastAPI /app AND any static host (404 -> static mode)
const apiProbe = async () => {
  try {
    const r = await fetch("/v1/benchmark/latest");
    return r.ok;
  } catch {
    return false;
  }
};
export const detectMode = apiProbe;

// repo root for static hosts: this app lives at <root>/web/dist/
const staticRoot = () => {
  const p = window.location.pathname;
  const i = p.indexOf("web/dist/");
  return i >= 0 ? p.slice(0, i) : p.endsWith("/") ? p : p + "/";
};

const RECORDINGS = {
  flagship: "recorded_run.jsonl",
  checkout: "recorded_run_checkout.jsonl",
  search: "recorded_run_search.jsonl",
};

const loadStaticEvents = async (source = "flagship") => {
  const root = staticRoot();
  const file = RECORDINGS[source] ?? RECORDINGS.flagship;
  const candidates = [`${root}bench/${file}`, `./bench/${file}`, `/bench/${file}`];
  for (const url of candidates) {
    const r = await fetch(url);
    if (r.ok) {
      return (await r.text()).split("\n").filter(Boolean).map((l) => JSON.parse(l));
    }
  }
  throw new Error("recorded run not found on this host");
};

const loadStaticBench = async () => {
  const root = staticRoot();
  const candidates = [`${root}bench/results.json`, "./bench/results.json"];
  for (const url of candidates) {
    const r = await fetch(url);
    if (r.ok) return r.json();
  }
  return null;
};

const loadApiBench = async () => {
  const r = await fetch("/v1/benchmark/latest");
  if (!r.ok) throw new Error("no api");
  return r.json();
};

/**
 * runEvents({ onEvent, onStatus, speedRef }) -> controller { close, reopen }
 * Streams run 'demo' from the API, or replays the static recording.
 * speedRef.current = seconds between events (static) — live pace is server-side.
 */
export function makeRunner({ onEvent, onStatus, onDone, mode }) {
  let es = null;
  let timer = null;
  let paused = false;
  let source = "flagship";
  let lastSeq = -1;
  let staticEvents = {};
  let interval = 0.12;
  let closed = false;

  const stop = () => {
    if (es) { es.close(); es = null; }
    if (timer) { clearTimeout(timer); timer = null; }
  };

  const runStatic = async () => {
    stop();
    paused = false;
    const cacheKey = source ?? "flagship";
    if (!staticEvents[cacheKey]) {
      try {
        staticEvents[cacheKey] = await loadStaticEvents(cacheKey);
      } catch {
        onStatus?.("recorded run not found on this host");
        return;
      }
    }
    const evs = staticEvents[cacheKey];
    let i = evs.findIndex((e) => e.seq > lastSeq);
    if (lastSeq >= 0 && i < 0) return; // resuming a finished stream
    if (i < 0) i = 0;
    const step = () => {
      if (closed || paused) return;
      if (i >= evs.length) { onDone?.(); return; }
      const ev = evs[i];
      lastSeq = ev.seq;
      onEvent(ev);
      i += 1;
      timer = setTimeout(step, interval * 1000);
    };
    step();
  };

  const runLive = () => {
    stop();
    paused = false;
    const qs = new URLSearchParams();
    if (lastSeq >= 0) qs.set("after_seq", lastSeq);
    es = new EventSource(`/v1/runs/demo/events${qs.toString() ? "?" + qs : ""}`);
    es.addEventListener("update", (e) => {
      const ev = JSON.parse(e.data);
      if (typeof ev.seq === "number") lastSeq = ev.seq;
      onEvent(ev);
      if (ev.type === "run.finished" || ev.type === "run.failed") { es.close(); es = null; onDone?.(); }
    });
    es.onerror = () => {
      if (lastSeq < 0) onStatus?.("not found — start one with curl POST /v1/runs");
      es.close(); es = null; onDone?.();
    };
  };

  return {
    async start(runSource = "flagship") {
      closed = false;
      source = runSource;
      const api = runSource === "search" ? false : mode === "static" ? false : await apiProbe();
      if (api) runLive(); else await runStatic();
    },
    get source() { return source; },
    pause() { paused = true; if (es) { es.close(); es = null; } if (timer) clearTimeout(timer); },
    resume() { if (!paused) return; apiProbe().then((api) => (api ? runLive() : runStatic())); },
    setSpeed(v) { interval = v; if (!paused && staticEvents && !es) runStatic(); }, // static: re-time from lastSeq
    get paused() { return paused; },
    get isStatic() { return !es && !!staticEvents || mode === "static"; },
    close() { closed = true; stop(); },
  };
}

export const loadUseCaseResults = async () => {
  const root = staticRoot();
  const candidates = [`${root}bench/usecase_results.json`, "./bench/usecase_results.json", "/bench/usecase_results.json"];
  for (const url of candidates) {
    const r = await fetch(url);
    if (r.ok) return r.json();
  }
  return [];
};

// per-run record: calls (role/model/tokens/t+/duration), phases, findings —
// computed from the committed recording, exactly what RUN-RECORDS.md documents
export const loadRunRecord = async (source = "flagship") => {
  const root = staticRoot();
  const file = RECORDINGS[source] ?? RECORDINGS.flagship;
  const candidates = [`${root}bench/${file}`, `./bench/${file}`, `/bench/${file}`];
  let text = null;
  for (const url of candidates) {
    const r = await fetch(url);
    if (r.ok) { text = await r.text(); break; }
  }
  if (!text) return null;
  const events = text.split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const t0 = new Date(events[0].at).getTime();
  const at = (e) => Math.round((new Date(e.at).getTime() - t0) / 100) / 10;
  const rec = { events: events.length, artifact: `bench/${file}`, calls: [], phases: {}, findings: [], tokens: null, status: "", seconds: null };
  let prev = 0;
  for (const e of events) {
    const t = at(e);
    if (e.type === "llm.call") {
      rec.calls.push({ role: e.data.role, model: String(e.data.model).split("/").pop(), tokens: e.data.tokens, at_s: t, latency: Math.round((t - prev) * 10) / 10 });
    }
    if (e.type === "search.call") {
      rec.calls.push({ role: "tavily · " + e.data.kind, model: e.data.source, tokens: null, at_s: t, latency: Math.round((t - prev) * 10) / 10 });
    }
    if (e.type === "plan.ready") rec.phases.plan_done_s = t;
    if (e.type === "ear.done") { rec.phases.listen_done_s = t; rec.phrases = e.data.phrases; }
    if (e.type === "finding.new") rec.findings.push({ sev: e.data.severity, wcag: e.data.wcag_sc, heard: e.data.heard });
    if (e.type === "run.finished") { rec.tokens = e.data.tokens; rec.status = e.data.status; rec.seconds = t; }
    prev = t;
  }
  return rec;
};

export const loadBench = async (mode) =>
  mode === "static" ? loadStaticBench() : await loadApiBench().catch(() => loadStaticBench());
