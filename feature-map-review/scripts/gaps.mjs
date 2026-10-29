#!/usr/bin/env node
// The gap table's command line: hands out permanent ids, closes gaps, keeps every plan's
// `gaps:` in step with the workstream owners, and reports what the gaps teach.
//
//   node gaps.mjs next-id
//   node gaps.mjs add --json new-gaps.json           assign ids (never reused) and append
//   node gaps.mjs close GAP-0123 --status fixed --by plans/x.md|<PR url> [--dup-of GAP-0042]
//   node gaps.mjs sync-plan-gaps [--apply]           plans' gaps: = fixed gaps they list + open
//                                                    gaps of the workstreams they own
//   node gaps.mjs learnings                          open and closed gaps by cause, finder, area
//   node gaps.mjs stats                              status, severity, ownership, workstreams
// Common flags: --root <repo root, default cwd>, --dir <map dir, default docs/feature-map>.
// Data files are rewritten one record per line, so diffs stay one line per gap.
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadConfig, parseArgs, readJson } from "./lib/config.mjs";
import { frontmatter, GAP_ID, gapIdOf, gapNum, setListField } from "./lib/frontmatter.mjs";
import { jl, listItem, writeLines } from "./lib/jsonl.mjs";

const args = parseArgs();
const C = loadConfig(args);
const [cmd, ...rest] = args._;
const GAPS = join(C.dir, "gaps.json");
const REVIEWS = join(C.dir, "reviews.json");
const EXTERNAL = join(C.dir, "external-plans.json");
const OPEN = new Set(["open", "unverified"]);
const CLOSED = new Set(["fixed", "duplicate", "wontfix"]);
const today = () => new Date().toISOString().slice(0, 10);
const die = (msg) => { console.error(`gaps: ${msg}`); process.exit(1); };

const loadGaps = () => {
  if (!existsSync(GAPS)) die(`${GAPS} is missing (copy assets/templates/gaps.json)`);
  const t = JSON.parse(readFileSync(GAPS, "utf8"));
  t.gaps ??= [];
  t.next_id ??= Math.max(0, ...t.gaps.map((g) => gapNum(g.id))) + 1;
  return t;
};
const saveGaps = (t) => {
  const head = Object.fromEntries(Object.entries(t).filter(([k]) => k !== "gaps"));
  writeLines(GAPS, head, [["gaps", t.gaps, listItem]]);
};
const featureIds = () => new Set((readJson(join(C.dir, "features.json"), { features: [] }).features ?? []).map((f) => f.id));

function nextId() {
  console.log(gapIdOf(loadGaps().next_id));
}

function add() {
  if (!args.json) die("add needs --json <file> holding one gap or a list of gaps");
  const t = loadGaps();
  const input = JSON.parse(readFileSync(args.json, "utf8"));
  const list = Array.isArray(input) ? input : [input];
  const feats = featureIds();
  const out = [];
  for (const g of list) {
    for (const f of [g.feature, ...(g.related ?? [])]) if (!feats.has(f)) die(`feature ${f} is not in features.json (add it first): ${jl(g).slice(0, 120)}`);
    if (!g.summary) die(`a gap needs a summary: ${jl(g).slice(0, 120)}`);
    const id = gapIdOf(t.next_id++);
    // Field order matches the table, so a new line reads like the others.
    const rec = {
      id, feature: g.feature, related: g.related ?? [], severity: g.severity ?? "medium", status: g.status ?? "open",
      summary: g.summary, detail: g.detail ?? "", evidence: g.evidence ?? [], cause: g.cause ?? null, duplicate_of: null,
      found_by: g.found_by ?? null, source: g.source ?? null, found_at: g.found_at ?? today(), tracker: g.tracker ?? [],
      closed_at: null, closed_by: null,
    };
    t.gaps.push(rec);
    out.push(id);
  }
  saveGaps(t);
  console.log(`gaps: added ${out.length} (${out[0]}${out.length > 1 ? ` .. ${out[out.length - 1]}` : ""}); next_id ${t.next_id}`);
}

function close() {
  const id = rest[0];
  if (!GAP_ID.test(id ?? "")) die("close needs a gap id: close GAP-0123 --status fixed --by <plan or PR>");
  const status = args.status ?? "fixed";
  if (!CLOSED.has(status)) die(`--status must be one of ${[...CLOSED].join(", ")}`);
  if (!args.by) die("close needs --by <plan path or PR url> so the table says who closed it");
  const t = loadGaps();
  const g = t.gaps.find((x) => x.id === id);
  if (!g) die(`${id} is not in gaps.json`);
  if (status === "duplicate") {
    if (!args["dup-of"] || args["dup-of"] === id || !t.gaps.some((x) => x.id === args["dup-of"])) die("a duplicate needs --dup-of <another existing gap id>");
    g.duplicate_of = args["dup-of"];
  }
  g.status = status;
  g.closed_at = today();
  g.closed_by = args.by;
  saveGaps(t);
  console.log(`gaps: ${id} ${status} by ${args.by}`);
}

// Each plan's gaps: = the fixed gaps it already names (the record of what it closed) plus the
// open gaps of every workstream it owns. Archived plans keep only their fixed gaps.
function syncPlanGaps() {
  const t = loadGaps();
  const G = new Map(t.gaps.map((g) => [g.id, g]));
  const reviews = readJson(REVIEWS, { features: {} });
  const own = new Map();
  const add = (k, id) => own.set(k, new Set([...(own.get(k) ?? []), id]));
  const unowned = [];
  for (const r of Object.values(reviews.features ?? {})) {
    for (const w of r.workstreams ?? []) {
      for (const id of w.gaps ?? []) {
        if (!OPEN.has(G.get(id)?.status)) continue;
        if (w.owner) add(w.owner, id); else unowned.push(`${w.id}:${id}`);
      }
    }
  }
  const byNum = (a, b) => gapNum(a) - gapNum(b);
  const plansAbs = join(C.root, C.plans_dir);
  const archAbs = join(C.root, C.archive_dir);
  const files = [
    ...(existsSync(plansAbs) ? readdirSync(plansAbs).filter((f) => f.endsWith(".md") && !C.plans_exclude.has(f)).map((f) => [`${C.plans_dir}/${f}`, false]) : []),
    ...(existsSync(archAbs) ? readdirSync(archAbs).filter((f) => f.endsWith(".md")).map((f) => [`${C.archive_dir}/${f}`, true]) : []),
  ];
  const changes = [];
  const seen = new Set();
  for (const [path, archived] of files) {
    const text = readFileSync(join(C.root, path), "utf8");
    const fm = frontmatter(text);
    if (!fm) continue;
    seen.add(path);
    const cur = new Set(Array.isArray(fm.gaps) ? fm.gaps : []);
    const next = new Set([...cur].filter((id) => G.get(id)?.status === "fixed"));
    if (!archived) for (const id of own.get(path) ?? []) next.add(id);
    const a = [...cur].sort(byNum), b = [...next].sort(byNum);
    // An archived plan with no gaps: line and nothing to record is left alone.
    if (jl(a) !== jl(b) || (!("gaps" in fm) && !(archived && !b.length))) changes.push({ key: path, from: a, to: b, apply: () => writeFileSync(join(C.root, path), setListField(text, "gaps", b)) });
  }
  const ext = C.external && existsSync(EXTERNAL) ? JSON.parse(readFileSync(EXTERNAL, "utf8")) : null;
  for (const p of ext?.pages ?? []) {
    const key = `${C.external.key_prefix}:${p.id}`;
    seen.add(key);
    const cur = new Set(p.gaps ?? []);
    const next = new Set([...cur].filter((id) => G.get(id)?.status === "fixed"));
    for (const id of own.get(key) ?? []) next.add(id);
    const a = [...cur].sort(byNum), b = [...next].sort(byNum);
    if (jl(a) !== jl(b)) changes.push({ key, from: a, to: b, apply: () => { p.gaps = b; } });
  }
  const missingOwners = [...own.keys()].filter((k) => !seen.has(k));
  for (const c of changes) {
    const removed = c.from.filter((x) => !c.to.includes(x)), added = c.to.filter((x) => !c.from.includes(x));
    console.log(`${c.key}: -${removed.length} +${added.length}${removed.length ? ` (drop ${removed.slice(0, 6).join(", ")}${removed.length > 6 ? ", ..." : ""})` : ""}${added.length ? ` (add ${added.slice(0, 6).join(", ")}${added.length > 6 ? ", ..." : ""})` : ""}`);
  }
  if (missingOwners.length) console.log(`owners with no plan file or external page: ${missingOwners.join(", ")}`);
  if (unowned.length) console.log(`open gaps in workstreams with no owner: ${unowned.length} (${unowned.slice(0, 8).join(", ")}${unowned.length > 8 ? ", ..." : ""})`);
  if (args.apply) {
    for (const c of changes) c.apply();
    if (ext && changes.some((c) => !c.key.includes("/"))) {
      const head = Object.fromEntries(Object.entries(ext).filter(([k]) => k !== "pages" && k !== "mirrors"));
      writeLines(EXTERNAL, head, [["pages", ext.pages, listItem], ["mirrors", ext.mirrors ?? {}, jl]]);
    }
    console.log(`gaps: synced ${changes.length} plan(s)`);
  } else {
    console.log(`gaps: ${changes.length} plan(s) would change${changes.length ? "; rerun with --apply" : ""}`);
  }
  if (missingOwners.length) process.exitCode = 1;
}

const CAUSE_CHECK = {
  "scoped-out": "Every deferral in a plan names its gap id or tracker row.",
  parity: "A plan lists each surface (UI, API, SDK, CLI, docs, tests) and says which it covers.",
  "missing-guard": "Every new route or action names its permission check, safety gates and audit trail.",
  "not-built": "Planned work carries its gap ids, so the map shows what is still owed.",
  drift: "A behavior change updates the docs, plans and copy that describe it in the same PR.",
  debt: "Every shortcut or baseline exception names the plan that removes it.",
  config: "Env, infra and account steps get a runbook and a verification item before the code lands.",
  unplanned: "Planning starts from the feature map: the features a change touches and their open gaps.",
  regression: "A fixed gap gets a test that pins it.",
};

function table(title, rows) {
  const w = Math.max(title.length, ...rows.map((r) => String(r[0]).length));
  console.log(`\n${title.padEnd(w)}  open  closed`);
  for (const [k, o, c] of rows) console.log(`${String(k).padEnd(w)}  ${String(o).padStart(4)}  ${String(c).padStart(6)}`);
}
function tally(gaps, keyOf) {
  const m = new Map();
  for (const g of gaps) {
    const k = keyOf(g) ?? "(none)";
    const e = m.get(k) ?? [k, 0, 0];
    if (OPEN.has(g.status)) e[1]++; else if (g.status === "fixed") e[2]++;
    m.set(k, e);
  }
  return [...m.values()].sort((a, b) => b[1] - a[1] || b[2] - a[2]);
}

function learnings() {
  const t = loadGaps();
  const areaOf = new Map((readJson(join(C.dir, "features.json"), { features: [] }).features ?? []).map((f) => [f.id, f.area]));
  const checks = { ...CAUSE_CHECK, ...Object.fromEntries(Object.entries(C.causes ?? {}).filter(([, v]) => v?.check).map(([k, v]) => [k, v.check])) };
  console.log(`${t.gaps.filter((g) => OPEN.has(g.status)).length} open, ${t.gaps.filter((g) => g.status === "fixed").length} fixed, ${t.gaps.filter((g) => g.status === "duplicate").length} duplicates, ${t.gaps.filter((g) => g.status === "wontfix").length} won't fix`);
  const byCause = tally(t.gaps, (g) => g.cause);
  table("cause", byCause);
  console.log("\nThe check a plan should carry, by cause (most open first):");
  for (const [k, o] of byCause) if (checks[k] && o) console.log(`  ${k}: ${checks[k]}`);
  table("found by", tally(t.gaps, (g) => g.found_by));
  table("area", tally(t.gaps, (g) => areaOf.get(g.feature)));
}

function stats() {
  const t = loadGaps();
  const reviews = readJson(REVIEWS, { features: {} });
  const count = (f) => t.gaps.filter(f).length;
  const named = new Set();
  const plansAbs = join(C.root, C.plans_dir);
  for (const f of existsSync(plansAbs) ? readdirSync(plansAbs).filter((x) => x.endsWith(".md")) : []) {
    for (const id of frontmatter(readFileSync(join(plansAbs, f), "utf8"))?.gaps ?? []) named.add(id);
  }
  for (const p of readJson(EXTERNAL, { pages: [] }).pages ?? []) for (const id of p.gaps ?? []) named.add(id);
  const open = t.gaps.filter((g) => OPEN.has(g.status));
  const ws = Object.values(reviews.features ?? {}).flatMap((r) => r.workstreams ?? []);
  console.log(`gaps: ${t.gaps.length} (next id ${gapIdOf(t.next_id)})`);
  for (const s of ["open", "unverified", "fixed", "duplicate", "wontfix"]) console.log(`  ${s}: ${count((g) => g.status === s)}`);
  console.log(`open by severity: ${["high", "medium", "low"].map((s) => `${s} ${open.filter((g) => g.severity === s).length}`).join(", ")}`);
  console.log(`open with a plan: ${open.filter((g) => named.has(g.id)).length}; with a tracker row: ${open.filter((g) => (g.tracker ?? []).length).length}; with neither: ${open.filter((g) => !named.has(g.id) && !(g.tracker ?? []).length).length}`);
  console.log(`workstreams: ${ws.length}; no owner: ${ws.filter((w) => !w.owner).length}; no row: ${ws.filter((w) => !w.row).length}`);
}

const COMMANDS = { "next-id": nextId, add, close, "sync-plan-gaps": syncPlanGaps, learnings, stats };
if (!COMMANDS[cmd]) die(`usage: gaps.mjs <${Object.keys(COMMANDS).join("|")}> [--root .] [--dir docs/feature-map]`);
COMMANDS[cmd]();
