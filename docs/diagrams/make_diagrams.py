"""Render the README diagrams: purpose-drawn HTML/CSS -> PNG via headless Chromium.

Two diagrams, each in GitHub light and dark variants (consumed by README <picture>):
  how-it-works  — orchestrator (7 ports) <-> Nebius Token Factory (inference + Sandboxes branches)
  fix-loop      — sequence: walk fails by ear -> audit -> 3 candidates -> parallel sandbox
                  verification -> only the branch whose task completes by ear wins -> PR

Run: uv run python docs/diagrams/make_diagrams.py   (writes docs/diagrams/*.png)
Design: 1200 CSS px wide, deviceScaleFactor 1.8 -> 2160 px output (viewport-safe single pass).
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "diagrams"

THEMES = {
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "panel2": "#eef1f4",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#57606f",
        "accent": "#0f766e",
        "accentsoft": "#ccfbf1",
        "warn": "#9a6700",
        "fail": "#cf222e",
        "failsoft": "#ffebe9",
        "ok": "#1a7f37",
        "oksoft": "#dafbe1",
        "mono": "ui-monospace, SFMono-Regular, Menlo, monospace",
    },
    "dark": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "panel2": "#1c2129",
        "border": "#30363d",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#2dd4bf",
        "accentsoft": "#0d3d38",
        "warn": "#d29922",
        "fail": "#f85149",
        "failsoft": "#3d1d20",
        "ok": "#3fb950",
        "oksoft": "#12261e",
        "mono": "ui-monospace, SFMono-Regular, Menlo, monospace",
    },
}

BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { background:VAR(bg); color:VAR(text); font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;
       width:1200px; padding:34px 38px 30px; }
.h { font-size:21px; font-weight:700; letter-spacing:-.01em; }
.sub { font-size:12.5px; color:VAR(muted); margin-top:3px; line-height:1.45; }
.mono { font-family:VAR(mono); }
.zone { border:1.5px solid VAR(border); border-radius:10px; background:VAR(panel); padding:14px 14px 12px; }
.zone-title { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:VAR(muted); }
.chip { display:inline-block; font-family:VAR(mono); font-size:11.5px; padding:2px 8px; border-radius:6px;
        border:1px solid VAR(border); background:VAR(panel2); color:VAR(text); white-space:nowrap; }
.arrowlab { font-family:VAR(mono); font-size:11px; color:VAR(muted); }
.tag { font-size:10.5px; font-weight:600; padding:1px 7px; border-radius:10px; }
.tag-ok   { color:VAR(ok);   background:VAR(oksoft); }
.tag-fail { color:VAR(fail); background:VAR(failsoft); }
.tag-acc  { color:VAR(accent); background:VAR(accentsoft); }
"""


def _css(t: dict) -> str:
    s = BASE_CSS
    for k, v in t.items():
        s = s.replace(f"VAR({k})", v)
    return s


# ---------------------------------------------------------------- architecture
ARCH_BODY = """
<div class="h">Blind-Run: an agent that fixes accessibility by ear</div>
<div class="sub">Every model call runs on the Nebius Token Factory inference API; every candidate fix is
built, served and ear-verified inside its own Token Factory Sandboxes branch.</div>

<table style="width:100%; border-collapse:separate; border-spacing:0 0;"><tr>

<td style="width:33%; vertical-align:top;">
  <div class="zone" style="height:100%;">
    <div class="zone-title">This repo — orchestrator</div>
    <div style="font-size:13.5px; font-weight:600; margin:6px 0 4px;">7 ports, fake ↔ real via <span class="mono">.env</span></div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:5px;">
      <span class="chip">LLM</span><span class="chip">Ear</span>
      <span class="chip">Sandbox</span><span class="chip">Search</span>
      <span class="chip">VCS</span><span class="chip">Store</span>
      <span class="chip">Events</span><span class="chip" style="color:VAR(muted)">state machine</span>
    </div>
    <div class="sub" style="margin-top:10px;">run_flow: plan → listen → audit → fix rounds →
    verify (success phrase must be <i>heard</i>) → PR. Fakes keep the whole pipeline
    runnable offline in tests.</div>
  </div>
</td>

<td style="width:22px; vertical-align:middle; text-align:center; color:VAR(accent);
           font-size:20px; font-weight:700; line-height:1.1;">→<div class="arrowlab"
           style="font-size:9.5px; margin-top:4px;">calls</div></td>

<td style="width:38%; vertical-align:top;">
  <div class="zone" style="height:100%; border-style:dashed; border-color:VAR(accent);">
    <div class="zone-title" style="color:VAR(accent);">Nebius Token Factory</div>
    <div style="border:1px solid VAR(border); border-radius:8px; background:VAR(bg); padding:9px 11px; margin-top:9px;">
      <div style="font-size:13px; font-weight:700;">Inference API <span class="tag tag-acc">every model call</span></div>
      <div class="sub" style="margin-top:4px;">Nemotron-3 Super 120B — planner + auditor ·
      Nemotron-3 Ultra 550B — fixer · 3.5 Lightning / Nano-30B / Qwen3-Embedding-8B</div>
    </div>
    <div style="border:1px solid VAR(border); border-radius:8px; background:VAR(bg); padding:9px 11px; margin-top:9px;">
      <div style="font-size:13px; font-weight:700;">Sandboxes <span class="tag tag-acc">ConTree, beta</span></div>
      <div class="sub" style="margin-top:4px;">Parent checkpoint: Node 22 + Playwright + Chromium +
      Guidepup virtual screen reader. Each candidate = a parallel branch:
      <span class="mono">apply patch → serve :8000 → ear replay</span>. Only a branch whose task
      <b>completes by ear</b> returns <span class="mono">passed</span>.</div>
    </div>
  </div>
</td>

<td style="width:22px; vertical-align:middle; text-align:center; color:VAR(accent);
           font-size:20px; font-weight:700; line-height:1.1;">→<div class="arrowlab"
           style="font-size:9.5px; margin-top:4px;">walks /<br>opens</div></td>

<td style="width:24%; vertical-align:top;">
  <div class="zone" style="height:100%;">
    <div class="zone-title">Edges</div>
    <div style="margin-top:9px; border:1px solid VAR(border); border-radius:8px; background:VAR(bg); padding:9px 11px;">
      <div style="font-size:13px; font-weight:700;">Target web app</div>
      <div class="sub">planted-bug shop (8 pages, 21 bugs, 5 clean controls) — the ear walks it
      like a screen-reader user</div>
    </div>
    <div style="margin-top:9px; border:1px solid VAR(border); border-radius:8px; background:VAR(bg); padding:9px 11px;">
      <div style="font-size:13px; font-weight:700;">Out</div>
      <div class="sub">PR with the before/after transcript diff · SSE event stream →
      judge dashboard · benchmark JSON</div>
    </div>
  </div>
</td>
</tr></table>
"""


# ---------------------------------------------------------------- sequence
SEQ_BODY = """
<div class="h">The fix loop: verification by ear, not by opinion</div>
<div class="sub">Recorded flagship (bench/recorded_run.jsonl): round 1, three candidates, one verified.</div>

<svg width="1124" height="620" style="display:block; margin-top:14px;">
  <defs>
    <marker id="sa" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(text)"/></marker>
    <marker id="sg" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(ok)"/></marker>
    <marker id="sr" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(muted)"/></marker>
    <marker id="sacc" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(accent)"/></marker>
  </defs>

  FOREACH

  <!-- 1. walk (ear -> orch) -->
  <text x="34" y="76" class="mono" font-size="11.5" fill="VAR(muted)">1 · listen</text>
  <line x1="90" y1="112" x2="322" y2="112" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#sa)"/>
  <text x="130" y="102" font-size="11.5" fill="VAR(text)" class="mono">next · next · act …</text>
  <text x="130" y="132" font-size="11" fill="VAR(fail)" class="mono">heard: “S, M, L … button, button” — dead end</text>

  <!-- 2. audit (orch -> tf and back) -->
  <text x="34" y="182" class="mono" font-size="11.5" fill="VAR(muted)">2 · audit</text>
  <line x1="330" y1="216" x2="632" y2="216" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#sa)"/>
  <text x="404" y="206" font-size="11.5" fill="VAR(text)" class="mono">transcript + ARIA snapshot</text>
  <line x1="640" y1="244" x2="338" y2="244" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#sr)"/>
  <text x="392" y="236" font-size="11" fill="VAR(text)" class="mono">findings: WCAG 4.1.2 ×3, evidence-weighted</text>

  <!-- 3. fixer (orch -> tf and back) -->
  <text x="34" y="296" class="mono" font-size="11.5" fill="VAR(muted)">3 · fix</text>
  <line x1="330" y1="330" x2="632" y2="330" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#sa)"/>
  <text x="412" y="320" font-size="11.5" fill="VAR(text)" class="mono">file + finding + APG pattern</text>
  <line x1="640" y1="358" x2="338" y2="358" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#sr)"/>
  <text x="368" y="350" font-size="11.5" fill="VAR(text)" class="mono">3 × &lt;&lt;&lt;SEARCH / === / &gt;&gt;&gt; candidates</text>

  <!-- 4. fan-out (orch -> sandboxes) -->
  <text x="34" y="410" class="mono" font-size="11.5" fill="VAR(muted)">4 · verify in Sandboxes</text>
  <line x1="330" y1="444" x2="882" y2="444" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#sa)"/>
  <text x="484" y="434" font-size="11.5" fill="VAR(text)" class="mono">3 parallel branches: apply → serve :8000 → ear replay</text>

  <!-- verdict card -->
  <rect x="712" y="468" width="356" height="60" rx="8" fill="VAR(bg)" stroke="VAR(border)"/>
  <text x="728" y="492" font-size="12" class="mono" fill="VAR(fail)">fix_r1_02 ✗ failed_ear</text>
  <text x="728" y="512" font-size="12" class="mono" fill="VAR(fail)">fix_r1_03 ✗ failed_ear</text>
  <text x="900" y="492" font-size="12" class="mono" fill="VAR(ok)" font-weight="700">fix_r1_01 ✓</text>
  <text x="884" y="512" font-size="11" class="mono" fill="VAR(ok)">heard “Added to cart”</text>

  <!-- 5. verdicts back (sandboxes -> orch, dashed) -->
  <text x="34" y="556" class="mono" font-size="11.5" fill="VAR(muted)">5 · verdicts</text>
  <line x1="890" y1="566" x2="338" y2="566" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#sr)"/>
  <text x="500" y="584" font-size="11" fill="VAR(text)" class="mono">loser tails feed round 2 — external signal only, never “try harder”</text>

  <!-- round-2 loop-back elbow on the left: verdicts row -> fix row -->
  <path d="M 322 566 L 58 566 L 58 344 L 322 344" fill="none" stroke="VAR(accent)"
        stroke-width="1.3" stroke-dasharray="4 4" marker-end="url(#sacc)"/>
  <text x="40" y="462" font-size="10.5" class="mono" fill="VAR(accent)"
        transform="rotate(-90 40 462)" text-anchor="middle">round 2 (≤ 2 rounds)</text>

  <!-- 6. PR (orch -> tf verify note -> github) -->
  <text x="34" y="600" class="mono" font-size="11.5" fill="VAR(muted)">6 · report</text>
  <line x1="330" y1="530" x2="632" y2="530" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#sa)" opacity="0"/>
  <line x1="330" y1="612" x2="1042" y2="612" stroke="VAR(ok)" stroke-width="1.8" marker-end="url(#sg)"/>
  <text x="560" y="604" font-size="11.5" fill="VAR(ok)" class="mono">winner only → PR with the before/after transcript diff</text>
</svg>
"""

LIFELINES = """
  <rect x="{lx}" y="8" width="124" height="30" rx="7" fill="VAR(panel2)" stroke="VAR(border)"/>
  <text x="{x}" y="27" text-anchor="middle" font-size="12.5" font-weight="700" fill="VAR(text)">{name}</text>
  <line x1="{x}" y1="38" x2="{x}" y2="606" stroke="VAR(border)" stroke-width="1.2" stroke-dasharray="3 3"/>
"""
_SEQ_LIFES = "".join(
    LIFELINES.format(x=x, lx=x - 62, name=n)
    for x, n in [
        (90, "Ear (VSR)"),
        (330, "Orchestrator"),
        (640, "Token Factory"),
        (890, "Sandboxes ×3"),
        (1050, "GitHub PR"),
    ]
)
SEQ_BODY = SEQ_BODY.replace("FOREACH", _SEQ_LIFES)


# ---------------------------------------------------------------- tavily flow
TAV_BODY = """
<div class="h">Tavily — retrieval inside the fix loop</div>
<div class="sub">Two load-bearing runtime calls per run, with a hard degrade to the local cache. No key, no network — the run still completes.</div>

<svg width="1124" height="470" style="display:block; margin-top:14px;">
  <defs>
    <marker id="ta" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(text)"/></marker>
    <marker id="td" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(muted)"/></marker>
    <marker id="to" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="VAR(accent)"/></marker>
  </defs>

  FOREACH

  <!-- 1. pattern() -->
  <text x="34" y="76" class="mono" font-size="11.5" fill="VAR(muted)">1 · before the fixer writes code</text>
  <line x1="90" y1="108" x2="382" y2="108" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#ta)"/>
  <text x="130" y="98" font-size="11.5" fill="VAR(text)" class="mono">pattern("radio")</text>
  <line x1="390" y1="130" x2="752" y2="130" stroke="VAR(accent)" stroke-width="1.6" marker-end="url(#to)"/>
  <text x="470" y="120" font-size="11.5" fill="VAR(text)" class="mono">POST api.tavily.com/search · Bearer · advanced</text>
  <line x1="760" y1="156" x2="398" y2="156" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#td)"/>
  <text x="462" y="148" font-size="11" fill="VAR(text)" class="mono">results + answer — w3.org preferred</text>
  <line x1="390" y1="182" x2="98" y2="182" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#td)"/>
  <text x="150" y="174" font-size="11.5" fill="VAR(text)" class="mono">Pattern(url, summary, source="tavily")</text>
  <line x1="390" y1="206" x2="1042" y2="206" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#ta)"/>
  <text x="520" y="198" font-size="11.5" fill="VAR(text)" class="mono">into the fixer prompt + cited in the PR with its source</text>

  <!-- 2. docs() -->
  <text x="34" y="252" class="mono" font-size="11.5" fill="VAR(muted)">2 · every finding, grounded</text>
  <line x1="90" y1="284" x2="382" y2="284" stroke="VAR(text)" stroke-width="1.6" marker-end="url(#ta)"/>
  <text x="130" y="274" font-size="11.5" fill="VAR(text)" class="mono">docs("4.1.2")</text>
  <line x1="390" y1="306" x2="752" y2="306" stroke="VAR(accent)" stroke-width="1.6" marker-end="url(#to)"/>
  <text x="452" y="296" font-size="11.5" fill="VAR(text)" class="mono">POST /search · "Understanding WCAG 4.1.2 site:w3.org"</text>
  <line x1="760" y1="330" x2="98" y2="330" stroke="VAR(muted)" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#td)"/>
  <text x="140" y="322" font-size="11.5" fill="VAR(text)" class="mono">official Understanding URL → dashboard link on the finding</text>

  <!-- 3. degrade -->
  <text x="34" y="378" class="mono" font-size="11.5" fill="VAR(muted)">3 · any failure</text>
  <line x1="390" y1="410" x2="958" y2="410" stroke="VAR(warn)" stroke-width="1.6" stroke-dasharray="6 4" marker-end="url(#td)"/>
  <text x="480" y="400" font-size="11.5" fill="VAR(text)" class="mono">error · no key · quota</text>
  <rect x="962" y="390" width="150" height="40" rx="8" fill="VAR(bg)" stroke="VAR(border)"/>
  <text x="978" y="408" font-size="12" class="mono" fill="VAR(text)">CachedSearch floor</text>
  <text x="978" y="424" font-size="10.5" class="mono" fill="VAR(muted)">verified slug map</text>
  <text x="96" y="443" font-size="11" fill="VAR(text)" class="mono">the run completes with cached patterns — search is an enhancement, never a dependency</text>
</svg>
"""

_LIFES = """
  <rect x="{lx}" y="8" width="124" height="30" rx="7" fill="VAR(panel2)" stroke="VAR(border)"/>
  <text x="{x}" y="27" text-anchor="middle" font-size="12.5" font-weight="700" fill="VAR(text)">{name}</text>
  <line x1="{x}" y1="38" x2="{x}" y2="456" stroke="VAR(border)" stroke-width="1.2" stroke-dasharray="3 3"/>
"""
_TAV_LIFES = "".join(
    _LIFES.replace("{x}", str(x)).replace("{lx}", str(x - 62)).replace("{name}", name)
    for x, name in [(90, "Orchestrator"), (390, "TavilySearch"), (760, "api.tavily.com"), (1035, "Consumers")]
)
TAV_BODY = TAV_BODY.replace("FOREACH", _TAV_LIFES)


async def render(theme: str, body: str, name: str) -> None:
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + _css(THEMES[theme])
        + "</style></head><body>"
        + body
        + "</body></html>"
    )
    # substitute theme vars across the WHOLE document — inline SVG attributes
    # (fill/stroke="VAR(...)") must resolve too, or they render black-on-black
    for k, v in THEMES[theme].items():
        html = html.replace(f"VAR({k})", v)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=1.8)
        await page.set_content(html, wait_until="networkidle")
        overflow = await page.evaluate(
            "() => Math.max(document.body.scrollWidth, document.body.scrollHeight)"
            " - Math.max(document.body.clientWidth, document.body.clientHeight)"
        )
        w = await page.evaluate("() => document.body.scrollWidth")
        h = await page.evaluate("() => document.body.scrollHeight")
        # element screenshot of <body>: clips exactly to content. full_page is
        # max(scroll, viewport) — anything shorter than 900px padded with empty
        # canvas (looked like a half-black image in dark mode)
        await page.locator("body").screenshot(path=str(OUT / f"{name}-{theme}.png"))
        await browser.close()
        print(f"{name}-{theme}.png  {w}x{h} css-px  overflow={overflow > 2}")


async def main() -> None:
    for theme in ("light", "dark"):
        await render(theme, ARCH_BODY, "how-it-works")
        await render(theme, SEQ_BODY, "fix-loop")
        await render(theme, TAV_BODY, "tavily-flow")


if __name__ == "__main__":
    asyncio.run(main())
