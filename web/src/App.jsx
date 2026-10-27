import React, { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRun } from "./useRun.js";
import { detectMode } from "./data.js";

const ROOT = window.location.pathname.includes("web/dist/")
  ? window.location.pathname.replace(/web\/dist\/.*$/, "")
  : "/";

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

const Chip = ({ tone, children }) => <span className={`chip ${tone}`}>{children}</span>;
const Eyebrow = ({ children }) => <span className="eyebrow">{children}</span>;

const useCountUp = (target) => {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (target == null) return;
    const t0 = performance.now();
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / 900);
      setV(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return v;
};

/* ---------- navbar ---------- */

const NAV = [["#/console", "Console"], ["#/results", "Results"], ["#/use-cases", "Use cases"], ["#/stack", "Stack"], ["#/about", "About"]];

function Navbar({ route, theme, setTheme, mode, paused, setPaused, speed, setSpeed }) {
  return (
    <header className="topbar">
      <a className="brand" href="#/console"><span className="dot" />Blind-Run<span className="tag">verified by ear</span></a>
      <nav className="nav" aria-label="Primary">
        {NAV.map(([href, label]) => (
          <a key={href} href={href} className={`nav-link ${route === href ? "on" : ""}`}>{label}</a>
        ))}
      </nav>
      <div className="tools">
        {mode && <span className={`mode-chip ${mode}`}>{mode === "live" ? "● live API" : "◐ static demo"}</span>}
        {route === "#/console" && (
          <span className="controls" role="group" aria-label="Replay controls">
            <button className="btn ghost" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? "Resume" : "Pause"}</button>
            {[0.5, 1, 2].map((s) => (
              <button key={s} className={`btn ghost speed ${speed === s ? "on" : ""}`} onClick={() => setSpeed(s)}>{s}×</button>
            ))}
          </span>
        )}
        <button className="btn ghost icon" aria-label="Toggle theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          {theme === "light" ? "☾" : "☀"}
        </button>
        <a className="btn primary" href="https://github.com/0xv3nm09/blind-run" target="_blank" rel="noopener">GitHub</a>
      </div>
    </header>
  );
}

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
              animate={{ scale: i === active && !terminal ? [1, 1.04, 1] : 1 }}
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
          <tr><th>Severity</th><th>WCAG</th><th>Heard</th><th>Seen</th><th className="num">Confidence</th><th>Route</th></tr>
        </thead>
        <tbody>
          <AnimatePresence>
            {rows.map((f) => (
              <motion.tr key={f.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <td><Chip tone={f.severity}>{f.severity}</Chip></td>
                <td className="wcag">
                  {f.wcag_url ? <a href={f.wcag_url} target="_blank" rel="noopener">{f.wcag_sc}</a> : f.wcag_sc}
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
  const winner = verified?.passed ? list.find((b) => b.verdict === "passed")?.patch_id : null;
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

/* ---------- benchmark table (shared) ---------- */

function BenchmarkTable({ bench, compact }) {
  if (!bench) return <div className="empty">Loading benchmark…</div>;
  const ofTen = (v) => `${Math.round((v ?? 0) * 10)} of 10`;
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
        <tr><th>Condition</th><th className="num">Recall</th><th>95% CI</th>{compact ? null : <th className="num">Axe-invisible recall</th>}</tr>
      </thead>
      <tbody>
        {rows.map(({ name, c, extra, muted }) => (
          <tr key={name} className={muted ? "muted" : ""}>
            <td>{name}</td>
            <td className="num strong">{(c.recall * 100).toFixed(1)}%</td>
            <td>
              <span className="cibar">
                <span className="ci" style={{ left: `${c.recall_ci95[0] * 100}%`, width: `${(c.recall_ci95[1] - c.recall_ci95[0]) * 100}%` }} />
                <span className="dotci" style={{ left: `${c.recall * 100}%` }} />
              </span>
            </td>
            {compact ? null : <td className="num">{c.recall_axe_invisible == null ? "—" : ofTen(c.recall_axe_invisible)}</td>}
            {extra && <td className="extra">{extra}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ---------- views ---------- */

function CallsPanel({ state }) {
  const calls = state.calls ?? [];
  const boxRef = useRef(null);
  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [calls.length]);
  return (
    <Panel
      title="Live API calls — Token Factory"
      sub="Every inference call as the pipeline makes it: role, model, tokens. This is the real traffic, not a mock."
      count={`${calls.length} calls`}
    >
      <div className="calls" ref={boxRef}>
        {calls.length === 0 && <div className="empty">Calls appear here as the models are invoked.</div>}
        {calls.map((c, i) => c.search ? (
          <motion.div key={i} className="call-line search" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}>
            <span className="c-role">tavily</span>
            <span className="c-model">{c.kind} · {String(c.query)}</span>
            <span className="c-tokens">{c.source}</span>
            <span className="c-url">api.tavily.com</span>
          </motion.div>
        ) : (
          <motion.div key={i} className="call-line" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}>
            <span className="c-role">{c.role}</span>
            <span className="c-model">{String(c.model).split("/").pop()}</span>
            <span className="c-tokens">{(c.tokens ?? 0).toLocaleString()} tok</span>
            <span className="c-url">api.tokenfactory.nebius.com</span>
          </motion.div>
        ))}
        {calls.length > 0 && (
          <div className="call-foot">recorded traffic · POST /v1/chat/completions · OpenAI-compatible SDK</div>
        )}
      </div>
    </Panel>
  );
}

function ConsoleView({ state, bench, selectDemo, demo, setDemo }) {
  const tokens = useCountUp(state.tokens);
  return (
    <>
      <div className="page-head">
        <div>
          <Eyebrow>Console</Eyebrow>
          <h1>Recorded run — <span className="mono-h">{demo === "search" ? "search for running shoes" : "buy the cheapest item"}</span></h1>
          <p className="pagesub">A real run against the planted-bug shop, streaming exactly as it happened. Pause it, slow it down, read what the screen reader heard.</p>
        </div>
        <div className="meta-row">
          <span className="meta"><b>{state.status}</b></span>
          {state.tokens != null && <span className="meta mono accent">{tokens.toLocaleString()} tokens ≈ $0.01 · Token Factory</span>}
          <span className="meta">watching a recorded run — <b>to go live</b>: clone the repo, add your Nebius key (<code>docs/RUN-GUIDE.md</code>), paste your run id above; the pipeline streams identically</span>
        </div>
      </div>
      <div className="chips-row demo-picker" role="group" aria-label="Choose recorded run">
        <button className={`meta mono demo-chip ${demo === "flagship" ? "on" : ""}`} onClick={() => { if (demo !== "flagship") { setDemo("flagship"); selectDemo("flagship"); } }}>
          ① checkout — fix verified by ear
        </button>
        <button className={`meta mono demo-chip ${demo === "search" ? "on" : ""}`} onClick={() => { if (demo !== "search") { setDemo("search"); selectDemo("search"); } }}>
          ② search — field typing, live
        </button>
      </div>
      <StageRail stage={state.stage} status={state.status} />
      <div className="grid2">
        <Panel
          title="Transcript"
          sub="What the screen reader announced, timestamped. Teal lines are controls the walker acted on."
          count={`${state.phrases.length} phrases`}
        >
          <Transcript phrases={state.phrases} />
        </Panel>
        <div className="col">
          <Panel title="Findings" sub="Each finding quotes the transcript and links the official WCAG doc." count={state.findings.length}>
            <Findings findings={state.findings} />
          </Panel>
          <Panel
            title="Fix candidates"
            sub="Each ran in its own Nebius Sandboxes branch — applied, served, re-listened. Only one completed the task by ear."
            count={Object.keys(state.branches).length}
          >
            <Branches branches={state.branches} verified={state.verified} />
          </Panel>
        </div>
      </div>
      <CallsPanel state={state} />
      <Panel title="Transcript diff" sub="The winner's evidence: what changed for a screen-reader user, line by line.">
        <DiffPanel verified={state.verified} />
      </Panel>
      {state.pr && (
        <motion.a className="banner" href={state.pr.url.startsWith("/") ? ROOT + state.pr.url.slice(1) : state.pr.url} target="_blank" rel="noopener" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          Verified fix opened as a pull request — a human reviews and merges. <b>{state.pr.url}</b>
        </motion.a>
      )}
      <Panel title="Benchmark summary" sub="How the detection lanes compare over the planted-bug shop — full data on the Results page.">
        <BenchmarkTable bench={bench} compact />
      </Panel>
    </>
  );
}

function ResultsView({ bench }) {
  return (
    <>
      <div className="page-head">
        <div>
          <Eyebrow>Results</Eyebrow>
          <h1>Benchmark &amp; evidence</h1>
          <p className="pagesub">Detection was measured, not claimed: 21 planted bugs across 8 pages plus 5 clean control pages, Wilson 95% confidence intervals on every estimate.</p>
        </div>
      </div>
      <Panel title="Detection benchmark" sub="Recall = share of planted bugs found. The last column counts the 10 bugs rule engines structurally cannot see (they render fine — they just can't be operated by ear). 0 of 10 there is the finding, not a fault: it is why the ear exists.">
        <BenchmarkTable bench={bench} />
        <p className="helper">The <b>fix loop is the third lane</b> the table can't capture: on the flagship page it caught the exact blocker axe scored 0 on, fixed it, and proved the fix by ear inside a Sandboxes branch — <a href="#/console">recorded run R-001</a>.</p>
      </Panel>
      <div className="grid2">
        <Panel title="How to read this" sub="Three lanes, one verdict.">
          <ul className="prose">
            <li><b>axe only</b> — the rule-engine baseline. Strong on cosmetic issues, silent on task blockers.</li>
            <li><b>ear + auditor</b> — deliberately conservative: fewer findings, but every one is real (100% precision, 0 false positives on controls).</li>
            <li><b>combined (shipped)</b> — the union of both lanes is what production runs use.</li>
          </ul>
        </Panel>
        <Panel title="Beyond the planted shop" sub="Detection on pages we did not author.">
          <ul className="prose">
            <li><b>books.toscrape.com</b> — real product page: <b>2 genuine blockers</b> found (nameless buttons announced as silence). Recording in <code>evidence/real-sites/</code>.</li>
            <li><b>Wikipedia</b> — accessibility article: <b>0 findings, twice</b> (41–42 phrases, no degradation). Precision holds on a real, mostly-accessible page.</li>
          </ul>
        </Panel>
      </div>
      <Panel title="Method" sub="For reviewers who want the setup.">
        <ul className="prose">
          <li>Bugs were planted first, then audited blind — no detector saw the truth table.</li>
          <li>10 of the 21 bugs are <b>axe-invisible by construction</b>: they render fine, they just can't be operated by ear.</li>
          <li>Wilson intervals handle the small-n honesty problem — wide CIs are shown, not hidden.</li>
          <li>Truth table: <code>bench/truth.json</code> · harness: <code>make bench</code>.</li>
        </ul>
      </Panel>
      <Panel
        title="Run record R-001 — flagship fix run (Oct 26)"
        sub="Every event from the recorded stream, in order. Raw artifact: bench/recorded_run.jsonl (59 events, committed)."
        count="59 events"
      >
        <div className="records">
          <div className="rec-row"><span className="rec-t">t+11.1s</span><span className="rec-e">llm.call</span><span className="rec-d">planner · nemotron-3-super-120b-a12b · 1,100 tok</span></div>
          <div className="rec-row"><span className="rec-t">t+11.1s</span><span className="rec-e">plan.ready</span><span className="rec-d">walk plan + success phrase set</span></div>
          <div className="rec-row"><span className="rec-t">t+13.1s</span><span className="rec-e">ear.done</span><span className="rec-d">40 phrases — task did NOT complete by ear (silent size picker, nameless buttons)</span></div>
          <div className="rec-row"><span className="rec-t">t+14.4s</span><span className="rec-e">llm.call</span><span className="rec-d">auditor · nemotron-3-super-120b-a12b · 505 tok</span></div>
          <div className="rec-row"><span className="rec-t">t+20.6s</span><span className="rec-e">finding.new ×2</span><span className="rec-d">blocker 4.1.2 (no announcement) · minor 4.1.2 (nameless buttons)</span></div>
          <div className="rec-row"><span className="rec-t">t+127.9s</span><span className="rec-e">llm.call</span><span className="rec-d">fixer · Nemotron-3-Ultra-550b-a55b · 9,353 tok</span></div>
          <div className="rec-row"><span className="rec-t">t+137.8s</span><span className="rec-e">fix.branch ×2</span><span className="rec-d">fix_r1_01 passed · fix_r1_02 failed_ear — in-branch ear replays</span></div>
          <div className="rec-row"><span className="rec-t">t+137.8s</span><span className="rec-e">fix.verified</span><span className="rec-d">passed — transcript diff produced</span></div>
          <div className="rec-row"><span className="rec-t">t+137.8s</span><span className="rec-e">pr.opened</span><span className="rec-d">artifact preserved in evidence/</span></div>
          <div className="rec-row"><span className="rec-t">t+137.8s</span><span className="rec-e">run.finished</span><span className="rec-d">done · 10,958 tokens ≈ $0.01</span></div>
        </div>
      </Panel>
      <div className="grid2">
        <Panel title="Run record R-005 — live Tavily sweep (Oct 27)" sub="7 runs with SEARCH_BACKEND=tavily: 30 runtime calls recorded, all source=tavily. Fullest take: 24 events.">
          <div className="records">
            <div className="rec-row"><span className="rec-e">search.call ×5</span><span className="rec-d">4× docs("WCAG 4.1.2") + 1× pattern("radio") — every fixer prompt fed by live retrieval, every finding grounded</span></div>
            <div className="rec-row"><span className="rec-e">llm.call ×4</span><span className="rec-d">planner / auditor / fixer×2 — interleaved with the Tavily calls in the same stream</span></div>
            <div className="rec-row"><span className="rec-e">fix.branch ×6</span><span className="rec-d">2 fix rounds — escalated (the documented sampling variance; verified-PR proof is R-001)</span></div>
            <div className="rec-row"><span className="rec-e">artifact</span><span className="rec-d">evidence/real-sites/tavily-run-R005.jsonl</span></div>
          </div>
        </Panel>
        <Panel title="Raw artifacts" sub="Everything on this page links to committed files.">
          <ul className="prose">
            <li><code>bench/recorded_run.jsonl</code> — flagship event stream (R-001)</li>
            <li><code>bench/usecase_results.json</code> — the 8-task measured table (Use cases page)</li>
            <li><code>bench/results.json</code> + <code>bench/truth.json</code> — benchmark + truth table</li>
            <li><code>evidence/real-sites/*.jsonl</code> — 15 recordings: 8 use-case runs, real-site detection, 7 Tavily runs</li>
            <li><code>evidence/*.md, *.patch</code> — the PR body and fix the flagship opened</li>
            <li>Full ledger with per-call tables: <code>docs/RUN-RECORDS.md</code></li>
          </ul>
        </Panel>
      </div>
    </>
  );
}

function StackView() {
  return (
    <>
      <div className="page-head">
        <div>
          <Eyebrow>Stack</Eyebrow>
          <h1>Nebius Token Factory + NVIDIA Nemotron</h1>
          <p className="pagesub">Every model call is a runtime call to the Token Factory inference API — there is no local model anywhere in the repo. Per-call logs print role, model and tokens while it runs.</p>
        </div>
      </div>
      <Panel title="Model matrix" sub="The recorded flagship's hot path in bold.">
        <table className="findings">
          <thead><tr><th>Role</th><th>Model</th><th>Sampling</th><th>Observed live</th></tr></thead>
          <tbody>
            <tr><td><b>Planner</b></td><td className="mono-h">Nemotron-3 Super 120B-A12B</td><td>temp 1.0 · top_p 0.95 · thinking on</td><td>~14s, ~1K tokens per plan</td></tr>
            <tr><td><b>Auditor</b></td><td className="mono-h">Nemotron-3 Super 120B-A12B</td><td>temp 0.2 · thinking off</td><td>quote-grounded findings; confidence computed in code</td></tr>
            <tr><td><b>Fixer</b></td><td className="mono-h">Nemotron-3 Ultra 550B-A55B</td><td>max_tokens 16384 · reasoning_budget 4096</td><td>landed the flagship W3C fix round-1</td></tr>
            <tr className="muted"><td>Fast lane</td><td className="mono-h">Nemotron 3.5 Lightning</td><td>temp 0.3</td><td>1.8s warm (measured)</td></tr>
            <tr className="muted"><td>Guard / Embeddings</td><td className="mono-h">Nano-30B / Qwen3-Embedding-8B</td><td>—</td><td>routed in config</td></tr>
          </tbody>
        </table>
      </Panel>
      <div className="grid2">
        <Panel title="Sandboxes — the verification lane" sub="Nebius Sandboxes (ConTree), Token Factory's code-execution product.">
          <ul className="prose">
            <li><b>Parent checkpoint</b> built once per process: python + Node 22 + Playwright + Chromium + Guidepup (~2–4 min).</li>
            <li>Each fix candidate = a <b>parallel disposable branch</b> (~3–6s): apply patch → serve on :8000 inside the branch → replay the ear there → verdict.</li>
            <li>The flagship's winning branch heard <code>"radio, S, not checked … Added to cart"</code> — verification physically inside Token Factory.</li>
          </ul>
        </Panel>
        <Panel title="Tavily — two load-bearing runtime calls" sub="Retrieval inside the fix loop, not a bolt-on.">
          <ul className="prose">
            <li><code>pattern(widget)</code> — before the fixer writes code, Tavily retrieves the current W3C ARIA APG pattern; the PR cites the fetched URL with its source.</li>
            <li><code>docs(wcag_sc)</code> — every finding links the official WCAG Understanding document, retrieved live.</li>
            <li>Any failure degrades to the bundled cache — a run never crashes because search did.</li>
          </ul>
        </Panel>
      </div>
      <Panel title="Cost & operations" sub="Measured, per run.">
        <div className="chips-row">
          <span className="meta mono accent">10,958 tokens ≈ $0.01 full loop</span>
          <span className="meta mono">21-page benchmark costs cents</span>
          <span className="meta mono">60 RPM / 400K TPM — never a factor</span>
          <span className="meta mono">every call logged: role · model · tokens</span>
        </div>
        <p className="helper">Example log line: <code>llm.call role=fixer model=nvidia/Nemotron-3-Ultra-550b-a55b tokens=9712 base_url=api.tokenfactory.nebius.com</code></p>
      </Panel>
    </>
  );
}

function UseCaseRow({ task, ex, r }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className={`uc-row ${open ? "open" : ""}`} onClick={() => setOpen(!open)}>
        <td className="mono-h">{task.page}</td>
        <td className="strong">"{task.task}"</td>
        <td className="extra">{ex}</td>
        <td className="num">{r ? r.findings_count : "—"}</td>
        <td className="num">{r && r.tokens != null ? r.tokens.toLocaleString() : "—"}</td>
        <td className="num">{r ? `${r.seconds}s` : "—"}</td>
        <td className="num chev">{open ? "▾" : "▸"}</td>
      </tr>
      {open && r && (
        <tr className="uc-detail">
          <td colSpan={7}>
            <div className="uc-proof">
              <div className="uc-block">
                <h5>Real API calls <span>— latency from the event stream timestamps</span></h5>
                {r.calls.map((c, i) => (
                  <div key={i} className="call-line">
                    <span className="c-role">{c.role}</span>
                    <span className="c-model">{c.model}</span>
                    <span className="c-tokens">{c.tokens.toLocaleString()} tok</span>
                    <span className="c-url">t+{c.at_s}s · {c.latency_s}s call</span>
                  </div>
                ))}
                <div className="uc-phases">
                  plan done t+{r.phases.plan_done_s}s
                  {r.phases.listen_done_s != null && <> · ear finished t+{r.phases.listen_done_s}s ({r.phases.phrases} phrases)</>}
                  · total {r.seconds}s
                </div>
              </div>
              <div className="uc-block">
                <h5>What the auditor reported <span>— quoted from the transcript</span></h5>
                {r.findings.length === 0 && <div className="uc-none">0 findings — the task completed by ear on the first call; there was nothing to audit.</div>}
                {r.findings.map((f, i) => (
                  <div key={i} className="uc-find">
                    <Chip tone={f.sev}>{f.sev}</Chip>
                    <span className="mono-h">{f.wcag}</span>
                    <span className="quote">heard {f.heard}</span>
                  </div>
                ))}
              </div>
              <div className="uc-block">
                <h5>Full recording</h5>
                <code className="uc-rec">{r.record}</code>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function UseCasesView({ results }) {
  const cases = [
    {
      who: "Engineering teams — the PR gate",
      run: "blindrun run --url <staging-url> --task \"complete checkout\" in CI",
      get: "Only ear-verified fixes land. Each PR carries the before/after screen-reader transcript as reviewable evidence — no rule-engine noise, no model opinions.",
    },
    {
      who: "E-commerce & checkout owners",
      run: "Task audits on staging: \"add to cart\", \"complete checkout\", \"apply the discount code\"",
      get: "The blockers that rule engines miss (our benchmark: 0 of 10) — found before customers and plaintiffs do. ~70% of accessibility lawsuits target e-commerce.",
    },
    {
      who: "Teams shipping AI-written UI",
      run: "A pre-deploy gate on vibe-coded pages before every deploy",
      get: "Catches what code review and linters structurally cannot: a control that renders and looks fine but cannot be operated by ear. WebAIM 2026 links rising failures to AI-generated code.",
    },
    {
      who: "Accessibility leads & auditors",
      run: "Detection sweep with --no-fix for findings-only reports",
      get: "WCAG-labeled findings with quoted transcript lines, confidence from evidence, and honest routing — auto_fix vs human. The transcript diff is output a reviewer can sign.",
    },
  ];
  const tasks = [
    ["product.html", "buy the cheapest item", "the recorded flagship — silent size picker, nameless buttons"],
    ["catalog.html", "find the cheapest trail shoe and open it", "navigation across a grid of links"],
    ["checkout.html", "complete the checkout", "multi-step form flow"],
    ["search.html", "search for running shoes", "type into a field and read results"],
    ["controls/dialog.html", "open the dialog and submit it", "focus trap + confirmation"],
    ["controls/tabs.html", "read what is on the shipping tab", "tab semantics"],
    ["controls/combobox.html", "select a country from the dropdown", "combobox pattern"],
    ["controls/live-cart.html", "add an item and hear the cart update", "live-region announcements"],
  ];
  return (
    <>
      <div className="page-head">
        <div>
          <Eyebrow>Use cases</Eyebrow>
          <h1>Where Blind-Run fits</h1>
          <p className="pagesub">One loop — task → experience → fix → prove — serving four teams today. Every case runs the same verified pipeline; only the task changes.</p>
        </div>
      </div>
      <div className="cases">
        {cases.map((c) => (
          <article className="case-card" key={c.who}>
            <h3>{c.who}</h3>
            <p className="case-run"><span>run</span><code>{c.run}</code></p>
            <p className="case-get">{c.get}</p>
          </article>
        ))}
      </div>
      <Panel
        title="Try it now — with real measured results"
        sub="Each task below was actually run against the live pipeline (real Nemotron planner + auditor, real virtual screen reader). Status, findings, tokens and duration are the measured values; recordings live in evidence/real-sites/."
        count={tasks.length}
      >
        <table className="findings uc-table">
          <thead><tr><th>Page</th><th>Task (plain English)</th><th>What it exercises</th><th className="num">Findings</th><th className="num">Tokens</th><th className="num">Total</th><th></th></tr></thead>
          <tbody>
            {tasks.map(([page, task, ex]) => {
              const r = (results ?? []).find((x) => x.page === page || x.page === page.replace("/", "-"));
              return <UseCaseRow key={page} task={{ page, task }} ex={ex} r={r} />;
            })}
          </tbody>
        </table>
        <p className="helper">
          {results?.length ? `All ${results.length} tasks completed on live backends (Nemotron planner + auditor, virtual screen reader). Click any row for its real API calls, latencies and findings. ${results.filter((r) => r.findings_count === 0).length} finished by ear with nothing to audit.` : "Loading measured results…"}
          {" "}Reproduce: <code>git clone github.com/0xv3nm09/blind-run && make setup && make serve-shop</code> then <code>uv run python -m blindrun run --url http://127.0.0.1:8932/product.html --task "&lt;task&gt;" --no-fix</code> — the 127.0.0.1:8932 above is the local demo shop the tasks ran against; the pipeline itself ran on Nebius.
        </p>
      </Panel>
      <Panel title="On the roadmap" sub="Where the same loop goes next.">
        <div className="chips-row">
          <span className="meta">multi-page flows — one task across catalog → product → cart → checkout</span>
          <span className="meta">nightly monitoring — "last deploy made checkout silent again"</span>
          <span className="meta">MCP server — coding agents check their own UI</span>
          <span className="meta">VoiceOver / NVDA confirmation lane</span>
          <span className="meta">ADA Title II compliance reporting (Apr 2027/28)</span>
        </div>
      </Panel>
    </>
  );
}

function AboutView() {
  return (
    <>
      <div className="page-head">
        <div>
          <Eyebrow>About</Eyebrow>
          <h1>Can a web task be completed by ear?</h1>
          <p className="pagesub">That question is the product. 95.9% of the top million homepages fail accessibility checks; the tools everyone relies on catch about half, and almost none of the failures that actually block a task. Blind-Run's test is what a blind user experiences: can the task be finished by ear?</p>
        </div>
      </div>
      <div className="grid2">
        <Panel title="The thesis" sub="Why verification — not generation — is the hard part.">
          <ul className="prose">
            <li>An LLM that writes the fix will also "confirm" the fix. The oracle has to be something that can't hallucinate: <b>a string check on the screen-reader transcript</b>.</li>
            <li>Models draft; <b>code verifies</b>. That's what makes agentic fixing safe to automate — and at ≈$0.01 a run, cheap enough for every PR.</li>
            <li>An honest escalate ("no candidate passed") is a feature: the system refusing to ship an unverified fix is the whole point.</li>
          </ul>
        </Panel>
        <Panel title="Safety invariants" sub="Hold everywhere, enforced in code.">
          <ul className="prose">
            <li>The screen reader decides pass/fail — never a model opinion.</li>
            <li>Page text is untrusted data, never instructions; findings must quote real transcript lines.</li>
            <li>Models never run commands; worker code does, under policy. <b>Nothing auto-merges.</b></li>
          </ul>
        </Panel>
      </div>
      <Panel title="Documentation" sub="Everything is checkable in the repo.">
        <div className="chips-row">
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/docs/RUN-RECORDS.md" target="_blank" rel="noopener">Run records</a>
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/docs/TAVILY.md" target="_blank" rel="noopener">Tavily deep-dive</a>
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/docs/COMPLIANCE.md" target="_blank" rel="noopener">Compliance map</a>
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noopener">Architecture deep-dive</a>
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/FEEDBACK.md" target="_blank" rel="noopener">Platform feedback</a>
          <a className="meta mono accent" href="https://github.com/0xv3nm09/blind-run/blob/main/SYSTEM_CARD.md" target="_blank" rel="noopener">System card</a>
        </div>
        <p className="helper">Live runs: clone the repo, <code>make setup && make up</code>, then paste a run id on the Console. Built for the Nebius × NVIDIA Global AI Hackathon 2026 — Coding &amp; Agentic Engineering track.</p>
      </Panel>
    </>
  );
}

/* ---------- app + hash router ---------- */

export default function App() {
  const { state, bench, ucResults, paused, setPaused, speed, setSpeed, selectDemo } = useRun();
  const [demo, setDemo] = useState("flagship");
  const [theme, setTheme] = useState(() => localStorage.getItem("br-theme") ?? "dark");
  const [mode, setModeState] = useState("");
  const [route, setRoute] = useState(() => window.location.hash || "#/console");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("br-theme", theme);
  }, [theme]);
  useEffect(() => { detectMode().then((api) => setModeState(api ? "live" : "static")); }, []);
  useEffect(() => {
    const onHash = () => setRoute(window.location.hash || "#/console");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const view = route.startsWith("#/results") ? "results"
    : route.startsWith("#/use-cases") ? "use-cases"
    : route.startsWith("#/stack") ? "stack"
    : route.startsWith("#/about") ? "about" : "console";

  return (
    <div className="shell">
      <Navbar
        route={route} theme={theme} setTheme={setTheme} mode={mode}
        paused={paused} setPaused={setPaused} speed={speed} setSpeed={setSpeed}
      />
      <AnimatePresence mode="wait">
        <motion.main
          key={view}
          className="page"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.22 }}
        >
          {view === "console" && <ConsoleView state={state} bench={bench} selectDemo={selectDemo} demo={demo} setDemo={setDemo} />}
          {view === "results" && <ResultsView bench={bench} />}
          {view === "use-cases" && <UseCasesView results={ucResults} />}
          {view === "stack" && <StackView />}
          {view === "about" && <AboutView />}
          <p className="foot">The screen reader decides — never a model opinion. <code>github.com/0xv3nm09/blind-run</code></p>
        </motion.main>
      </AnimatePresence>
    </div>
  );
}
