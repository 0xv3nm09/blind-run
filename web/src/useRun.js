import { useEffect, useReducer, useRef, useState } from "react";
import { makeRunner, loadBench } from "./data.js";

const initial = () => ({
  status: "connecting", task: null, tokens: null, stage: "",
  phrases: [], findings: [], branches: {}, verified: null, pr: null,
  diff: null,
});

const STAGES = [
  ["planning", "Plan"], ["listening", "Listen"], ["auditing", "Audit"],
  ["fixing", "Fix"], ["verifying", "Verify"], ["done", "Report"],
  ["escalated", "Report"], ["failed", "Report"],
];
const stageOf = (s) => STAGES.find(([k]) => k === s)?.[1] ?? "";

function reducer(state, ev) {
  const d = ev.data ?? {};
  switch (ev.type) {
    case "run.started":
    case "run.status": {
      const to = d.to || d.status || state.status;
      return {
        ...state,
        status: to,
        task: d.task ?? state.task,
        stage: stageOf(to) || state.stage,
      };
    }
    case "ear.phrase":
      return { ...state, phrases: [...state.phrases, { text: d.text, t: d.t_ms ?? 0 }] };
    case "finding.new": {
      if (state.findings.some((f) => f.id === d.id)) return state;
      return { ...state, findings: [...state.findings, d] };
    }
    case "fix.branch":
      return { ...state, branches: { ...state.branches, [d.patch_id]: d } };
    case "fix.verified":
      return { ...state, verified: d };
    case "pr.opened":
      return { ...state, pr: d };
    case "run.finished":
      return { ...state, tokens: d.tokens ?? state.tokens, status: d.status ?? state.status };
    default:
      return state;
  }
}

export function useRun() {
  const [state, dispatch] = useReducer(reducer, initial());
  const [bench, setBench] = useState(null);
  const [mode, setMode] = useState(null); // "live" | "static"
  const [paused, setPaused] = useState(false);
  const [speed, setSpeedState] = useState(1);
  const runnerRef = useRef(null);
  const speedRef = useRef(0.12);

  useEffect(() => {
    const runner = makeRunner({
      onEvent: dispatch,
      onStatus: (s) => dispatch({ type: "run.status", data: { status: s } }),
      onDone: () => {},
      mode: new URLSearchParams(location.search).get("mode") ?? undefined,
    });
    runnerRef.current = runner;
    runner.start();
    loadBench().then(setBench);
    return () => runner.close();
  }, []);

  useEffect(() => {
    if (!runnerRef.current) return;
    const r = runnerRef.current;
    if (paused) r.pause(); else r.resume();
  }, [paused]);

  useEffect(() => {
    speedRef.current = 0.12 / speed;
    runnerRef.current?.setSpeed(speedRef.current);
  }, [speed]);

  return { state, bench, paused, setPaused, speed, setSpeed: setSpeedState, mode };
}
