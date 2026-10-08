// runner/virtual_run.mjs — the default ear: no audio, just announced text.
// usage: node virtual_run.mjs '{"url":"…","steps":["next","act"],"successPhrase":"Added","maxSteps":40,"bundle":"…/index.browser.js"}'
// stdout: one JSON object {driver, phrases:[{i,text,t_ms,step}], aria_yaml, reached_success}
// stderr: one JSON line per phrase as it is spoken: {"phrase":"…","t_ms":123,"step":0}
import { chromium } from "playwright";
import { readFile } from "node:fs/promises";

const cfg = JSON.parse(process.argv[2] ?? "{}");
const { url, steps = [], successPhrase = "", successPhrases, maxSteps = 40, bundle = "" } = cfg;
const GOALS = (successPhrases?.length ? successPhrases : successPhrase ? [successPhrase] : []);

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(url, { waitUntil: "networkidle" });

// The bundle is an ES module exporting the singleton `virtual`. Modules can't be
// fetched cross-origin from an http page, so load it from a blob URL (same origin)
// and import the named export onto window.
const src = await readFile(bundle, "utf8");
await page.evaluate(async (bundleSrc) => {
  const blob = new Blob([bundleSrc], { type: "text/javascript" });
  const mod = await import(URL.createObjectURL(blob));
  window.__v = mod.virtual;
}, src);

await page.evaluate(() => window.__v.start({ container: document.body }));

// page.evaluate(fn) calls fn with no args, so every step fn reads window.__v itself.
const STEP = (s) => {
  if (s === "next") return () => window.__v.next();
  if (s === "previous") return () => window.__v.previous();
  if (s === "act") return () => window.__v.act();
  if (s === "heading") return () => window.__v.perform("moveToNextHeading");
  if (s === "landmark") return () => window.__v.perform("moveToNextLandmark");
  if (s === "form") return () => window.__v.perform("moveToNextForm");
  if (s.startsWith("type:")) {
    const text = s.slice(5);
    return () => window.__v.type(text);
  }
  if (s.startsWith("press:")) {
    const key = s.slice(6);
    return () => window.__v.press(key);
  }
  return null;
};

const phrases = [];
const t0 = Date.now();
let reached = false;

const emit = (text, step) => {
  const p = { i: phrases.length, text, t_ms: Date.now() - t0, step };
  phrases.push(p);
  console.error(JSON.stringify({ phrase: text, t_ms: p.t_ms, step })); // live stream
};

// Success = feedback AFTER an action, never a control's own name. Once the first
// act fires, any later phrase is eligible: status text is typically announced when
// the cursor moves on to the status region, i.e. during the following steps.
let awaitingFeedback = false;
let windowStart = 0;
const checkSuccess = () => {
  if (!GOALS.length || !awaitingFeedback) return;
  for (let k = windowStart; k < phrases.length; k++) {
    if (GOALS.some((g) => phrases[k].text.includes(g))) {
      reached = true;
      return;
    }
  }
};

// Walker policy: a user who lands on an interactive control operates it. Links are
// skipped (they would navigate away); static text is only read. This is how every
// check run proves — or disproves — that a control actually works by ear.
const INTERACTIVE = /(button|radio|checkbox|combobox|option|menu ?item|tab)/i;
const onControl = (text) => INTERACTIVE.test(text) && !/link|end of/i.test(text);

const startVSR = async () => {
  const src = await readFile(bundle, "utf8");
  await page.evaluate(async (bundleSrc) => {
    const mod = await import(URL.createObjectURL(new Blob([bundleSrc], { type: "text/javascript" })));
    window.__v = mod.virtual;
    await window.__v.start({ container: document.body });
  }, src);
};

// One navigation-aware recovery used by every evaluate in the step loop.
const recoverOrStop = async () => {
  const url2 = page.url();
  if (!url2.startsWith(url.origin)) return false; // left the page: report what we heard
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await startVSR();
  return true;
};

try {  // fatal per-step errors must not lose the transcript: degrade, don't crash
for (const [i, step] of steps.slice(0, maxSteps).entries()) {
  const fn = STEP(step);
  if (!fn) throw new Error(`unknown step: ${step}`);
  try {
    await page.evaluate(fn);
    const log = await page.evaluate(() => window.__v.spokenPhraseLog());
    for (const text of log.slice(phrases.length)) emit(text, i);
    checkSuccess(); // status text often lands on the step AFTER the act (cursor reaches the status region)
    if (reached) break;
    if (phrases.length && onControl(phrases[phrases.length - 1].text)) {
      await page.evaluate(() => window.__v.act());
      awaitingFeedback = true;
      windowStart = phrases.length;
      const log2 = await page.evaluate(() => window.__v.spokenPhraseLog());
      for (const text of log2.slice(phrases.length)) emit(text, i);
      checkSuccess();
      if (reached) break;
    }
  } catch (e) {
    // An act can navigate (links): the context dies mid-step. Recover on the new
    // page, or stop when we left the site entirely — the transcript so far stands.
    try {
      if (!(await recoverOrStop())) break;
    } catch {
      break; // recovery itself failed: report what we heard
    }
  }
}
} catch (fatal) {
  console.error(JSON.stringify({ degraded: true, reason: String(fatal).slice(0, 200) }));
}

let aria_yaml = "";
try {
  aria_yaml = await page.locator("body").ariaSnapshot();
} catch {
  aria_yaml = ""; // snapshot optional
}

console.log(JSON.stringify({ driver: "virtual", phrases, aria_yaml, reached_success: reached, degraded: phrases.length === 0 }));
await page.evaluate(() => window.__v?.stop()).catch(() => {});
await browser.close();
