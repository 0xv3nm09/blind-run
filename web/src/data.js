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

const loadStaticEvents = async () => {
  const root = staticRoot();
  const candidates = [`${root}bench/recorded_run.jsonl`, "./bench/recorded_run.jsonl"];
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
  let lastSeq = -1;
  let staticEvents = null;
  let interval = 0.12;
  let closed = false;

  const stop = () => {
    if (es) { es.close(); es = null; }
    if (timer) { clearTimeout(timer); timer = null; }
  };

  const runStatic = async () => {
    stop();
    paused = false;
    if (!staticEvents) {
      try {
        staticEvents = await loadStaticEvents();
      } catch {
        onStatus?.("recorded run not found on this host");
        return;
      }
    }
    let i = staticEvents.findIndex((e) => e.seq > lastSeq);
    if (i < 0) i = 0;
    const step = () => {
      if (closed || paused) return;
      if (i >= staticEvents.length) { onDone?.(); return; }
      const ev = staticEvents[i];
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
    async start() {
      closed = false;
      const api = mode === "static" ? false : await apiProbe();
      api ? runLive() : await runStatic();
    },
    pause() { paused = true; if (es) { es.close(); es = null; } if (timer) clearTimeout(timer); },
    resume() { if (!paused) return; apiProbe().then((api) => (api ? runLive() : runStatic())); },
    setSpeed(v) { interval = v; if (!paused && staticEvents && !es) runStatic(); }, // static: re-time from lastSeq
    get paused() { return paused; },
    get isStatic() { return !es && !!staticEvents || mode === "static"; },
    close() { closed = true; stop(); },
  };
}

export const loadBench = async (mode) =>
  mode === "static" ? loadStaticBench() : await loadApiBench().catch(() => loadStaticBench());
