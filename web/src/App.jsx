import React, { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRun } from "./useRun.js";
import { detectMode } from "./data.js";

const STAGE_ORDER = ["Plan", "Listen", "Audit", "Fix", "Verify", "Report"];

/* ---------- primitives ---------- */

const Panel = ({ title, sub, count, children, id }) => (
  <section className="panel" id={id}>
    <div className="panel-head">
      <div className="titles">
        <h2>{title}</h2>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {count != null && <span className="count">{count}</span>}
    </div>
    <div className="panel-body">{children}</div>
  </section>
);

const Chip = ({ tone, children }) => (
  <span className={`chip ${tone}`}>{children}</span>
);

const useCountUp = (target) => {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (target == null) return;
    const t0 = performance.now();
    const dur = 900;
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      setV(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return v;
};

/* ---------- stage rail ---------- */

function StageRail({ stage, status }) {
  const active = STAGE_ORDER.indexOf(stage);
  const terminal = status === "done" || status === "escalated" || status === "failed";
  return (
    <div className="stages" role="list" aria-label="Pipeline stage">
      {STAGE_ORDER.map((label, i) => {
        const cls = terminal && i === 5 ? "done" : i < active ? "done" : i === active ? "active" : "";
        return (
          <React.Fragment key={label}>
            {i > 0 && <motion.span className="arr" aria-hidden>→</motion.span>}
            <motion.span
              role="listitem"
              className={`stage ${cls}`}
              aria-current={i === active && !terminal ? "step" : undefined}
              animate={{
                scale: i === active && !terminal ? [1, 1.04, 1] : 1,
              }}
              transition={{ repeat: i === active && !terminal ? Infinity : 0, duration: 1.6, ease: "easeInOut" }}
            >
              <span className="n">{i + 1}</span>{label}
              {i === active && !terminal && <span className="pulse" aria-hidden />}
            </motion.span>
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ---------- transcript ---------- */

function Transcript({ phrases }) {
  const boxRef = useRef(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = boxRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [phrases.length]);
  const cls = (t) =>
    /^(button|radio|checkbox|link|radiogroup)/i.test(t) ? "act"
    : /^(end of|document|paragraph)/i.test(t) ? "status" : "";
  const visible = phrases.slice(-160);
  return (
    <div
      className="transcript"
      ref={boxRef}
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      }}
    >
      {visible.map((p, i) => (
        <motion.div
          key={phrases.length - visible.length + i}
          className={`tr-line ${cls(p.text)}`}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <span className="t">{(p.t / 1000).toFixed(1)}s</span>
          <span>{p.text}</span>
        </motion.div>
      ))}
      {phrases.length === 0 && <div className="empty">Listening…</div>}
    </div>
  );
}

/* ---------- findings ---------- */

function Findings({ findings }) {
  const [sev, setSev] = useState("");
  const rows = findings.filter((f) => !sev || f.severity === sev);
  return (
    <>
      <div className="filters">
        <select value={sev} onChange={(e) => setSev(e.target.value)} aria-label="Severity filter">
          <option value="">All severities</option>
          <option value="blocker">Blocker</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
        </select>
        <span className="count">{rows.length} of {findings.length}</span>
      </div>
      <table className="findings">
        <thead>
          <tr>
            <th>Severity</th><th>WCAG</th><th>Heard</th><th>Seen</th><th className="num">Confidence</th><th>Route</th>
          </tr>
        </thead>
        <tbody>
          <AnimatePresence>
            {rows.map((f) => (
              <motion.tr
                key={f.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <td><Chip tone={f.severity}>{f.severity}</Chip></td>
                <td className="wcag">
                  {f.wcag_url
                    ? <a href={f.wcag_url} target="_blank" rel="noopener">{f.wcag_sc}</a>
                    : f.wcag_sc}
                </td>
                <td className="quote">{f.heard}</td>
                <td className="quote">{f.seen}</td>
                <td className="num">
                  <div className="confidence">
                    <span className="bar"><motion.i
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.round((f.confidence ?? 0) * 100)}%` }}
                      transition={{ duration: 0.7, ease: "easeOut" }}
                    /></span>
                    <span className="value">{(f.confidence ?? 0).toFixed(2)}</span>
                  </div>
                </td>
                <td className={`route ${f.route ?? ""}`}>{f.route ?? "—"}</td>
              </motion.tr>
            ))}
          </AnimatePresence>
        </tbody>
      </table>
      {rows.length === 0 && <div className="empty">Findings appear as the auditor reports them.</div>}
    </>
  );
}

/* ---------- branches ---------- */

function Branches({ branches, verified }) {
  const list = Object.values(branches);
  const winner = verified?.passed
    ? list.find((b) => b.verdict === "passed")?.patch_id
    : null;
  return (
    <div className="branches">
      <AnimatePresence>
        {list.map((b, i) => (
          <motion.article
            key={b.patch_id}
            className={`branch ${b.patch_id === winner ? "winner" : ""}`}
            initial={{ opacity: 0, y: 14, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: i * 0.08, type: "spring", stiffness: 260, damping: 22 }}
          >
            <div className="branch-head">
              <span className="badge">{String.fromCharCode(65 + i)}</span>
              <span className="bname">{b.patch_id}</span>
              <Chip tone={b.verdict === "passed" ? "pass" : "fail"}>
                {b.verdict === "passed" ? "verified by ear" : b.verdict.replace("_", " ")}
              </Chip>
            </div>
            <div className="branch-body">{b.tail}</div>
          </motion.article>
        ))}
      </AnimatePresence>
      {list.length === 0 && <div className="empty">Candidates appear once the fixer replies.</div>}
    </div>
  );
}

/* ---------- diff ---------- */

function DiffPanel({ verified }) {
  const lines = useMemo(() => {
    if (!verified?.transcript_diff) return null;
    return verified.transcript_diff
      .split("\n")
      .filter((l) => l && !l.startsWith("@@") && !l.startsWith("---") && !l.startsWith("+++"));
  }, [verified]);
  if (!lines) return <div className="empty">The transcript diff lands here once a fix is verified.</div>;
  const before = lines.filter((l) => l.startsWith("-"));
  const after = lines.filter((l) => l.startsWith("+"));
  return (
    <div className="diff-grid">
      <div className="diff-col">
        <h4>Before — task fails</h4>
        <pre>
          {before.map((l, i) => (
            <motion.div key={i} className="diff-line remove" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.015 }}>
              {l.slice(1) || " "}
            </motion.div>
          ))}
        </pre>
      </div>
      <div className="diff-col">
        <h4>After — task completes by ear</h4>
        <pre>
          {after.map((l, i) => (
            <motion.div key={i} className="diff-line add" initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
              {l.slice(1) || " "}
            </motion.div>
          ))}
        </pre>
      </div>
    </div>
  );
}

/* ---------- benchmark ---------- */

function Benchmark({ bench }) {
  if (!bench) return <div className="empty">Loading benchmark…</div>;
  const rows = [
    bench.axe_only && { name: "axe only", c: bench.axe_only, muted: true },
    bench.ear_auditor && {
      name: "ear + auditor", c: bench.ear_auditor,
      extra: `precision ${bench.ear_auditor.precision ?? "—"} · ${bench.ear_auditor.control_false_positives ?? "—"} FP on controls`,
    },
    bench.combined_axe_plus_ear && { name: "combined (shipped)", c: bench.combined_axe_plus_ear },
  ].filter(Boolean);
  return (
    <table className="findings bench">
      <thead>
        <tr><th>Condition</th><th className="num">Recall</th><th>95% CI</th><th className="num">Axe-invisible recall</th></tr>
      </thead>
      <tbody>
        {rows.map(({ name, c, extra, muted }) => (
          <tr key={name} className={muted ? "muted" : ""}>
            <td>{name}</td>
            <td className="num strong">{(c.recall * 100).toFixed(1)}%</td>
            <td>
              <span className="cibar">
                <span className="ci" style={{
                  left: `${c.recall_ci95[0] * 100}%`,
                  width: `${(c.recall_ci95[1] - c.recall_ci95[0]) * 100}%`,
                }} />
                <span className="dotci" style={{ left: `${c.recall * 100}%` }} />
              </span>
            </td>
            <td className="num">{c.recall_axe_invisible == null ? "—" : `${(c.recall_axe_invisible * 100).toFixed(1)}%`}</td>
            {extra && <td className="extra">{extra}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ---------- app ---------- */

export default function App() {
  const { state, bench, paused, setPaused, speed, setSpeed } = useRun();
  const [theme, setTheme] = useState(() => localStorage.getItem("br-theme") ?? "light");
  const [mode, setModeState] = useState("");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("br-theme", theme);
  }, [theme]);
  useEffect(() => {
    detectMode().then((api) => setModeState(api ? "live" : "static"));
  }, []);
  const tokens = useCountUp(state.tokens);
  const findings = state.findings.length;
  const branches = Object.keys(state.branches).length;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="dot" />Blind-Run<span className="tag">verified by ear</span></div>
        <div className="tools">
          {mode && <span className={`mode-chip ${mode}`}>{mode === "live" ? "● live API" : "◐ static demo"}</span>}
          <span className="controls" role="group" aria-label="Replay controls">
            <button className="btn ghost" aria-pressed={paused} onClick={() => setPaused(!paused)}>
              {paused ? "Resume" : "Pause"}
            </button>
            {[0.5, 1, 2].map((s) => (
              <button key={s} className={`btn ghost speed ${speed === s ? "on" : ""}`} onClick={() => setSpeed(s)}>{s}×</button>
            ))}
          </span>
          <button className="btn ghost icon" aria-label="Toggle theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            {theme === "light" ? "☾" : "☀"}
          </button>
          <a className="btn primary" href="https://github.com/0xv3nm09/blind-run" target="_blank" rel="noopener">GitHub</a>
        </div>
      </header>

      <motion.main className="page" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <h1>Can a web task be completed <em>by ear?</em></h1>
        <p className="lede">
          Blind-Run drives a <strong>virtual screen reader</strong> through a web flow and listens to every phrase it
          announces. If a blind user couldn't finish the task, an AI auditor names the exact barrier, a fixer writes the
          code change — and the fix <strong>only counts when the task can then be finished by ear</strong>.
        </p>
        <div className="meta-row">
          <span className="meta"><b>{state.status}</b></span>
          {state.task && <span className="meta mono">task · {state.task}</span>}
          {state.tokens != null && (
            <span className="meta mono accent">{tokens.toLocaleString()} tokens ≈ $0.01 · Token Factory</span>
          )}
        </div>
        <StageRail stage={state.stage} status={state.status} />

        <div className="grid2">
          <Panel
            title="Transcript — what the screen reader said"
            sub="Exactly what a screen-reader user hears. Highlighted lines are controls the walker acted on."
            count={`${state.phrases.length} phrases`}
          >
            <Transcript phrases={state.phrases} />
          </Panel>

          <div className="col">
            <Panel title="Findings" sub="Every finding quotes the transcript and links the official WCAG doc." count={findings}>
              <Findings findings={state.findings} />
            </Panel>
            <Panel
              title="Fix candidates — verified in parallel"
              sub="Each ran in its own Nebius Sandboxes branch. Only one let the task finish by ear."
              count={branches}
            >
              <Branches branches={state.branches} verified={state.verified} />
            </Panel>
          </div>
        </div>

        <Panel title="What the screen reader announced — before vs after the fix" id="diff">
          <DiffPanel verified={state.verified} />
        </Panel>

        {state.pr && (
          <motion.a
            className="banner"
            href={state.pr.url}
            target="_blank"
            rel="noopener"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Verified fix opened as a pull request — a human reviews and merges. <b>{state.pr.url}</b>
          </motion.a>
        )}

        <Panel title="Detection benchmark — axe vs ear" sub="21 planted bugs + 5 clean controls, Wilson 95% CIs.">
          <Benchmark bench={bench} />
        </Panel>

        <div className="stack">
          <span><b>Nemotron-3 Super</b> · plan + audit</span>
          <span><b>Nemotron-3 Ultra</b> · fix</span>
          <span><b>Nebius Sandboxes</b> · parallel branches</span>
          <span><b>Tavily</b> · live W3C retrieval</span>
        </div>
        <p className="foot">
          The screen reader decides — never a model opinion. Live runs: clone the repo, <code>make setup && make up</code>.
        </p>
      </motion.main>
    </div>
  );
}
