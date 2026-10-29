#!/usr/bin/env node
// Feature map build: joins the feature registry, every live plan's frontmatter, the gap table,
// the feature reviews, plan annotations, plans that live outside the repo and a tracker
// snapshot into the data the page template renders. File-system only.
//
//   node build-map.mjs [--root .] [--dir docs/feature-map] [--out <dir>/dist] [--template <file>]
//   node build-map.mjs --check      validate the inputs only; exit 1 on any problem
//
// Inputs under --dir (all optional except features.json):
//   config.json            project name, plans dir, phases, labels (see assets/templates/config.json)
//   features.json          the registry: statuses, areas, features (built and planned), links
//   gaps.json              every known gap, one per line, by permanent id (GAP-0001)
//   reviews.json           per feature: plans' roles, open gaps grouped into workstreams (WS-001)
//   annotations.json       per plan: one-line summary, how much is built, a note per feature entry
//   external-plans.json    plans that live outside the repo (pages) and pages that mirror a repo plan
//   tracker-snapshot.json  tracker and roadmap rows (read-only copy of the tracker)
//   tracker-features.json  open tracker rows with no plan, tagged with features
//   plan-review-<date>.md  the latest written plan review, shown in the page's reader
//   work.json              per workstream: what it needs first, what it waits on, who can do it (Work view)
//   work-review-<date>.md  the latest written work review, shown in the page's reader
//   contexts.json          the context map: the product's independent pieces, what each owns and
//                          offers; the code under its scope is walked and its imports read (Contexts view)
// Template: <dir>/feature-map.html when present, else this skill's assets/feature-map.html.
//
// --check fails on anything the page would render wrong or not at all, so a green check means
// the published map works.
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadConfig, parseArgs, readJson } from "./lib/config.mjs";
import { FEATURE, FEATURE_ID, FEATURE_VERBS, frontmatter, GAP_ID } from "./lib/frontmatter.mjs";
import { computeWork, validateWork } from "./lib/work.mjs";
import { computeContexts, DEFAULT_TABLE_PATTERN, scanImports, tablesOf, validateContexts } from "./lib/contexts.mjs";

const args = parseArgs();
const C = loadConfig(args);
const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = C.dir;
const DIST = args.out ? resolve(C.root, args.out) : join(DIR, "dist");
const TEMPLATE = args.template ? resolve(C.root, args.template) : existsSync(join(DIR, "feature-map.html")) ? join(DIR, "feature-map.html") : join(HERE, "..", "assets", "feature-map.html");
const PLACEHOLDER = '<script id="fm-data" type="application/json">__FEATURE_MAP_DATA__</script>';
const PLANS = C.plans_dir;
const PHASES = C.phases;
// What the page knows how to draw. Anything else is a --check problem, not a silent gap.
const LINK_KINDS = new Set(["needs", "gate", "trigger", "data", "exposes"]);
const SEVERITIES = new Set(["high", "medium", "low"]);
// A gap's status, and what the page's open/closed views read from it.
const GAP_STATUS = { open: "yes", unverified: "unknown", fixed: "no", duplicate: "no", wontfix: "no" };
// Why a gap happened, so plans can learn from them.
const CAUSES = new Set(["scoped-out", "parity", "missing-guard", "not-built", "drift", "debt", "config", "unplanned", "regression"]);
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const PLAN_STATUS = new Set([...C.plan_statuses, "superseded"]);
const EXT = C.external;
const EXT_ID = EXT ? new RegExp(EXT.id_pattern) : null;
const EXT_KEY = (id) => `${EXT.key_prefix}:${id}`;
const TRACKER = C.tracker;
const TRACKER_ID = TRACKER ? new RegExp(TRACKER.id_pattern) : null;
const COLUMNS = new Set([0, 1, 2, 3, "band"]);
const OPEN_TRACKER = (s) => !(TRACKER?.closed_statuses ?? []).includes(s ?? "");
const ARCHIVE_HINT = `(archived? repoint it to ${C.archive_dir}/ or drop it)`;

const rel = (p) => relative(C.root, p) || ".";
const at = (f) => join(DIR, f);
const trackerId = (url) => (TRACKER_ID && typeof url === "string" ? url.match(TRACKER_ID)?.[1] ?? null : null);
// Links the page renders are https only; a bare number in `prs` is a PR in this repo.
const httpsOrNull = (url) => (typeof url === "string" && /^https:\/\//.test(url) ? url : null);
function prLink(raw) {
  const url = /^#?\d+$/.test(raw) ? (C.pr_repo ? `https://github.com/${C.pr_repo}/pull/${raw.replace("#", "")}` : null) : httpsOrNull(raw);
  if (!url) return null;
  const m = url.match(/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/);
  return { url, label: m ? (m[1] === C.pr_repo ? `#${m[2]}` : `${m[1]}#${m[2]}`) : url };
}

if (!existsSync(at("features.json"))) {
  console.error(`feature-map: ${rel(at("features.json"))} is missing (start from the skill's assets/templates/)`);
  process.exit(1);
}
const registry = readJson(at("features.json"));
const gapTable = readJson(at("gaps.json"), { next_id: 1, gaps: [] });
const reviewFile = readJson(at("reviews.json"), { features: {} });
// The latest dated review of a kind (plan-review-<date>.md, work-review-<date>.md), or null.
const latestDoc = (kind) => (existsSync(DIR) ? readdirSync(DIR).filter((f) => new RegExp(`^${kind}-review-\\d{4}-\\d{2}-\\d{2}\\.md$`).test(f)).sort().pop() ?? null : null);
const reviewDoc = latestDoc("plan");
const workReviewDoc = latestDoc("work");
const annotations = readJson(at("annotations.json"), { plans: {} }).plans ?? {};
const snapshot = readJson(at("tracker-snapshot.json"), { tracker: [], roadmap: [] });
const trackerTags = readJson(at("tracker-features.json"), { rows: {} }).rows ?? {};
const extPlans = readJson(at("external-plans.json"), { pages: [], mirrors: {} });
const problems = [];
if (!TRACKER && Object.keys(trackerTags).length) problems.push("tracker-features.json: has rows but config.json has no tracker section");
if (!EXT && (extPlans.pages ?? []).length) problems.push("external-plans.json: has pages but config.json has no external section");

// ---- registry shape: what the page needs to render every feature, link and gap
registry.statuses ??= { live: { label: "Live", tag: "" }, planned: { label: "Planned, not built", tag: "PLANNED" } };
registry.links ??= [];
const areaIds = new Set();
for (const a of registry.areas ?? []) {
  if (areaIds.has(a.id)) problems.push(`features.json: area ${a.id} is listed twice`);
  areaIds.add(a.id);
  if (!COLUMNS.has(a.column)) problems.push(`features.json: area ${a.id} has column ${JSON.stringify(a.column)}; use 0-3 or "band"`);
}
const featureIds = new Set();
for (const f of registry.features ?? []) {
  if (!FEATURE_ID.test(f.id ?? "")) problems.push(`features.json: feature id ${JSON.stringify(f.id)} is not kebab-case (a-z, 0-9, -)`);
  if (featureIds.has(f.id)) problems.push(`features.json: feature ${f.id} is listed twice`);
  featureIds.add(f.id);
  if (!areaIds.has(f.area)) problems.push(`features.json: feature ${f.id} is in area ${f.area}, which is not in areas`);
  if (!(f.status in registry.statuses)) problems.push(`features.json: feature ${f.id} has status ${f.status}, which is not in statuses`);
  if ("gaps" in f) problems.push(`features.json: feature ${f.id} carries gaps; they live in gaps.json`);
}
if (!featureIds.size) problems.push("features.json: no features");
if (C.default_feature && !featureIds.has(C.default_feature)) problems.push(`config.json: default_feature ${C.default_feature} is not in features.json`);
// ---- gap table
const gapIds = new Set();
for (const g of gapTable.gaps ?? []) {
  const where = `gaps.json: ${g.id}`;
  if (!GAP_ID.test(g.id ?? "")) problems.push(`gaps.json: gap id ${JSON.stringify(g.id)} is not GAP-NNNN`);
  else if (Number(g.id.slice(4)) >= (gapTable.next_id ?? Infinity)) problems.push(`${where}: id is not below next_id ${gapTable.next_id}; raise next_id`);
  if (gapIds.has(g.id)) problems.push(`${where}: listed twice (ids are permanent; never reuse one)`);
  gapIds.add(g.id);
  if (!featureIds.has(g.feature)) problems.push(`${where}: feature ${g.feature} is not in features.json`);
  for (const r of g.related ?? []) if (!featureIds.has(r)) problems.push(`${where}: related feature ${r} is not in features.json`);
  if (!SEVERITIES.has(g.severity)) problems.push(`${where}: severity ${g.severity}; use high, medium or low`);
  if (!(g.status in GAP_STATUS)) problems.push(`${where}: status ${g.status}; use ${Object.keys(GAP_STATUS).join(", ")}`);
  if (g.cause != null && !CAUSES.has(g.cause)) problems.push(`${where}: cause ${g.cause}; use ${[...CAUSES].join(", ")} or null`);
  if (g.found_at != null && !DATE.test(g.found_at)) problems.push(`${where}: found_at ${g.found_at} is not YYYY-MM-DD`);
  if (!Array.isArray(g.tracker)) problems.push(`${where}: tracker must be a list ([] for no row)`);
  else for (const t of g.tracker) if (!httpsOrNull(t?.url)) problems.push(`${where}: tracker row ${JSON.stringify(t)} needs an https url`);
  if (!Array.isArray(g.evidence)) problems.push(`${where}: evidence must be a list`);
}
for (const g of gapTable.gaps ?? []) {
  if (g.status === "duplicate" && !gapIds.has(g.duplicate_of)) problems.push(`gaps.json: ${g.id} is a duplicate of ${g.duplicate_of}, which is not a gap`);
}
for (const l of registry.links) {
  if (!featureIds.has(l.from) || !featureIds.has(l.to)) problems.push(`features.json: link ${l.from} -> ${l.to} names an unknown feature`);
  if (!LINK_KINDS.has(l.kind)) problems.push(`features.json: link ${l.from} -> ${l.to} has kind ${l.kind}; use ${[...LINK_KINDS].join(", ")}`);
}

// `<verb>:<feature id>`, as plan frontmatter and tracker-features.json both write it.
const entryOf = (entry, where) => {
  const m = String(entry).match(FEATURE);
  if (!m) { problems.push(`${where}: "${entry}" is not <${FEATURE_VERBS.join("|")}>:<feature-id>`); return null; }
  if (!featureIds.has(m[2])) { problems.push(`${where}: "${entry}" names unknown feature ${m[2]}`); return null; }
  return { verb: m[1], id: m[2] };
};

// ---- plans
const tracker = new Map((snapshot.tracker ?? []).map((r) => [r.id, r]));
const roadmap = new Map((snapshot.roadmap ?? []).map((r) => [r.id, r]));
const plans = [];
const plansAbs = join(C.root, PLANS);
if (!existsSync(plansAbs)) problems.push(`config.json: plans_dir ${PLANS} does not exist under ${C.root}`);
for (const file of existsSync(plansAbs) ? readdirSync(plansAbs).filter((f) => f.endsWith(".md") && !C.plans_exclude.has(f)).sort() : []) {
  const fm = frontmatter(readFileSync(join(plansAbs, file), "utf8"));
  if (!fm) continue; // no frontmatter: an exempt plan (check-plans.mjs reports a live one)
  const path = `${PLANS}/${file}`;
  const note = annotations[path] ?? {};
  const features = (Array.isArray(fm.features) ? fm.features : []).flatMap((entry) => {
    const e = entryOf(entry, path);
    return e ? [{ ...e, note: note.notes?.[entry] ?? "" }] : [];
  });
  const tUrl = fm[C.plan_fields.tracker];
  const rUrl = fm[C.plan_fields.roadmap];
  const tId = trackerId(tUrl);
  const rId = trackerId(rUrl);
  const t = tId ? tracker.get(tId) : null;
  const r = rId ? roadmap.get(rId) : null;
  const tasks = tId ? (snapshot.tracker ?? []).filter((row) => (row.plan ?? []).includes(tId)) : [];
  for (const id of Array.isArray(fm.gaps) ? fm.gaps : []) if (!gapIds.has(id)) problems.push(`${path}: gaps names ${id}, which is not in gaps.json`);
  const phase = fm.phase ?? C.default_phase;
  if (fm.status !== "done" && !PHASES.some((ph) => ph.id === phase)) problems.push(`${path}: phase ${phase} is not one of ${PHASES.map((ph) => ph.id).join(", ")} (config.json phases)`);
  plans.push({
    source: "repo",
    key: path,
    gaps: Array.isArray(fm.gaps) ? fm.gaps.filter((id) => gapIds.has(id)) : [],
    file: path,
    title: fm.title ?? file,
    status: fm.status ?? "draft",
    phase: fm.status === "done" ? "now" : phase,
    listed_phase: fm.phase ?? null,
    created: fm.created ?? null,
    updated: fm.updated ?? null,
    depends_on: fm.depends_on ?? [],
    blocked_by: fm.blocked_by ?? [],
    supersedes: fm.supersedes ?? [],
    prs: (fm.prs ?? []).map(prLink).filter(Boolean),
    github: C.repo_url ? `${C.repo_url}${path}` : null,
    summary: note.summary ?? "",
    built: note.built ?? "unknown",
    built_evidence: note.built_evidence ?? "",
    features,
    tracker: tId && httpsOrNull(tUrl) ? { id: tId, url: tUrl, item: t?.item ?? null, status: t?.status ?? null, owner: t?.owner ?? null, priority: t?.priority ?? null, due: t?.due ?? null } : null,
    roadmap: rId && httpsOrNull(rUrl) ? { id: rId, url: rUrl, name: r?.name ?? null, status: r?.status ?? null, stage: r?.stage ?? null, kind: r?.kind ?? null, severity: r?.severity ?? null } : null,
    tasks: { open: tasks.filter((x) => OPEN_TRACKER(x.status)).length, done: tasks.filter((x) => x.status === TRACKER?.done_status).length },
  });
}
const planFiles = new Set(plans.map((p) => p.file));
const planPathExists = (p) => planFiles.has(p) || (p.startsWith(`${PLANS}/`) && existsSync(join(C.root, p)));

// ---- plans that live outside the repo (a wiki, Notion, a docs site)
const extIds = new Set((extPlans.pages ?? []).map((n) => n.id));
const extKeyOk = (k) => !!EXT && typeof k === "string" && k.startsWith(`${EXT.key_prefix}:`) && extIds.has(k.slice(EXT.key_prefix.length + 1));
for (const n of EXT ? extPlans.pages ?? [] : []) {
  const where = `external-plans.json: ${n.id}`;
  if (!EXT_ID.test(n.id ?? "")) problems.push(`${where}: id does not match external.id_pattern ${EXT.id_pattern}`);
  if (!httpsOrNull(n.url)) problems.push(`${where}: url must be https`);
  if (!PHASES.some((ph) => ph.id === n.phase)) problems.push(`${where}: phase ${n.phase} is not one of ${PHASES.map((ph) => ph.id).join(", ")}`);
  if (!PLAN_STATUS.has(n.status)) problems.push(`${where}: status ${n.status} is not one of ${[...PLAN_STATUS].join(", ")}`);
  for (const r of n.repo_plans ?? []) if (!planPathExists(r.plan)) problems.push(`${where}: repo plan ${r.plan} does not exist ${ARCHIVE_HINT}`);
  for (const d of n.depends_on ?? []) {
    const ok = d.startsWith(`${EXT.key_prefix}:`) ? extKeyOk(d) : planPathExists(d);
    if (!ok) problems.push(`${where}: depends_on ${d} is neither an external plan here nor a plan file`);
  }
  const features = (n.features ?? []).flatMap((entry) => {
    const e = entryOf(entry, where);
    return e ? [{ ...e, note: n.notes?.[entry] ?? "" }] : [];
  });
  for (const id of n.gaps ?? []) if (!gapIds.has(id)) problems.push(`${where}: gaps names ${id}, which is not in gaps.json`);
  plans.push({
    source: "external",
    key: EXT_KEY(n.id),
    gaps: (n.gaps ?? []).filter((id) => gapIds.has(id)),
    file: null,
    title: n.title,
    status: n.status,
    phase: n.status === "done" ? "now" : n.phase,
    listed_phase: n.phase,
    created: null,
    updated: null,
    depends_on: n.depends_on ?? [],
    blocked_by: [],
    supersedes: [],
    prs: [],
    github: null,
    external_url: httpsOrNull(n.url),
    path: n.path ?? "",
    kind: n.kind ?? "sub-plan",
    program_phase: n.program_phase ?? n.nevar_phase ?? null,
    summary: n.summary ?? "",
    built: n.status === "done" ? "all" : "unknown",
    built_evidence: "",
    features,
    repo_plans: n.repo_plans ?? [],
    tracker_rows: (n.tracker_rows ?? []).map(httpsOrNull).filter(Boolean),
    tracker: null,
    roadmap: null,
    tasks: { open: 0, done: 0 },
  });
}
// External pages on a repo plan: mirrors of it, and external plans that extend it.
const mirrors = EXT ? extPlans.mirrors ?? {} : {};
for (const [id, m] of Object.entries(mirrors)) {
  if (!planPathExists(m.plan)) problems.push(`external-plans.json: mirror ${id} points at ${m.plan}, which does not exist ${ARCHIVE_HINT}`);
}
// Why a plan looks out of date: built but not closed, active but untouched, or an external copy that drifted.
const today = new Date().toISOString().slice(0, 10);
const daysSince = (d) => (Date.parse(today) - Date.parse(d)) / 86400000;
for (const p of plans) {
  p.stale = [];
  if (p.source !== "repo") continue;
  if (p.built === "all" && ["draft", "active", "blocked"].includes(p.status)) p.stale.push(`The feature-map review found it fully built, but it is marked ${p.status}.`);
  if (p.status === "active" && DATE.test(p.updated ?? "") && daysSince(p.updated) > C.stale_days) p.stale.push(`Active, but last updated ${p.updated}.`);
  for (const m of Object.values(mirrors)) if (m.plan === p.file && m.drift) p.stale.push(`Its ${EXT.label} copy (${m.title}) is out of date: ${m.drift}`);
}
for (const p of plans) {
  if (p.source !== "repo") continue;
  p.external_pages = [
    ...Object.values(mirrors).filter((m) => m.plan === p.file && httpsOrNull(m.url)).map((m) => ({ url: m.url, title: m.title, relation: "mirrors" })),
    ...(EXT ? extPlans.pages ?? [] : []).flatMap((n) => (n.repo_plans ?? []).filter((r) => r.plan === p.file).map((r) => ({ key: EXT_KEY(n.id), url: n.url, title: n.title, relation: r.relation }))),
  ];
}

for (const f of registry.features ?? []) {
  if (f.status === "planned" && !(f.introduced_by && planFiles.has(f.introduced_by)) && !extKeyOk(f.introduced_by) && !f.introduced_by_tracker) {
    problems.push(`features.json: planned feature ${f.id} names no live plan, external plan (introduced_by) or tracker row (introduced_by_tracker) ${ARCHIVE_HINT}`);
  }
}
// What the page draws for a gap: its owners (the plans that name it, then its tracker rows) and
// whether it is still open. A gap sits on its feature and on every related feature.
const ownersOf = new Map();
for (const p of plans) for (const id of p.gaps) ownersOf.set(id, [...(ownersOf.get(id) ?? []), p.key]);
const pageGaps = new Map();
for (const g of gapTable.gaps ?? []) {
  // The snapshot's status wins over the one recorded when the row was linked.
  const rows = (Array.isArray(g.tracker) ? g.tracker : []).filter((t) => httpsOrNull(t?.url)).map((t) => {
    const row = tracker.get(trackerId(t.url));
    return { url: t.url, status: row?.status ?? t.status ?? null };
  });
  const out = { ...g, tracker: rows, covered_by: [...(ownersOf.get(g.id) ?? []), ...rows.map((t) => t.url)], still_open: GAP_STATUS[g.status] ?? "unknown" };
  for (const fid of [g.feature, ...(g.related ?? [])]) if (featureIds.has(fid)) pageGaps.set(fid, [...(pageGaps.get(fid) ?? []), out]);
}
// ---- feature reviews: workstreams are the unit of work a row tracks; each open gap is in at most one.
const HEALTH = new Set(["solid", "gaps", "at-risk"]);
const ROLES = new Set(["owns", "touches", "stale", "conflicts"]);
const CHANGES = new Set(["merge-into", "split", "re-scope", "close", "move-phase", "add-gaps"]);
const planKeys = new Set(plans.map((p) => p.key));
const gapStatus = new Map((gapTable.gaps ?? []).map((g) => [g.id, g.status]));
const wsOfGap = new Map();
const wsIds = new Set();
for (const [fid, r] of Object.entries(reviewFile.features ?? {})) {
  const where = `reviews.json: ${fid}`;
  if (!featureIds.has(fid)) problems.push(`${where}: not a feature in features.json`);
  if (!HEALTH.has(r.health)) problems.push(`${where}: health ${r.health}; use ${[...HEALTH].join(", ")}`);
  for (const p of r.plans ?? []) {
    if (!planKeys.has(p.plan)) problems.push(`${where}: plan ${p.plan} is not a live plan ${ARCHIVE_HINT}`);
    if (!ROLES.has(p.role)) problems.push(`${where}: plan ${p.plan} has role ${p.role}`);
  }
  for (const w of r.workstreams ?? []) {
    if (!/^WS-\d{3,}$/.test(w.id ?? "")) problems.push(`${where}: workstream id ${JSON.stringify(w.id)} is not WS-NNN`);
    if (wsIds.has(w.id)) problems.push(`${where}: workstream ${w.id} is listed twice`);
    wsIds.add(w.id);
    if (w.owner && !planKeys.has(w.owner)) problems.push(`${where}: ${w.id} owner ${w.owner} is not a live plan`);
    for (const f of w.features ?? []) if (!featureIds.has(f)) problems.push(`${where}: ${w.id} names unknown feature ${f}`);
    if (w.row != null && !httpsOrNull(w.row)) problems.push(`${where}: ${w.id} row must be an https URL`);
    if (!PHASES.some((ph) => ph.id !== "now" && ph.id === String(w.phase))) problems.push(`${where}: ${w.id} phase ${JSON.stringify(w.phase)}; use one of ${PHASES.filter((ph) => ph.id !== "now").map((ph) => ph.id).join(", ")} (config.json phases)`);
    // An unknown size would count as 0 days and shorten every critical path through it.
    if (!["S", "M", "L"].includes(w.size)) problems.push(`${where}: ${w.id} size ${JSON.stringify(w.size)}; use "S", "M" or "L"`);
    for (const id of w.gaps ?? []) {
      if (!gapStatus.has(id)) problems.push(`${where}: ${w.id} names ${id}, which is not in gaps.json`);
      else if (wsOfGap.has(id)) problems.push(`${where}: ${id} is in ${wsOfGap.get(id)} and ${w.id}; a gap belongs to one workstream`);
      else wsOfGap.set(id, w.id);
    }
  }
  for (const c of r.plan_changes ?? []) {
    if (!planKeys.has(c.plan)) problems.push(`${where}: plan change names ${c.plan}, which is not a live plan`);
    if (!CHANGES.has(c.change)) problems.push(`${where}: plan change ${c.change}; use ${[...CHANGES].join(", ")}`);
  }
}
// A workstream is named on every gap it holds and on the plan that carries it.
for (const list of pageGaps.values()) for (const g of list) g.workstream = wsOfGap.get(g.id) ?? null;
const workstreamsOf = new Map();
for (const [fid, r] of Object.entries(reviewFile.features ?? {})) for (const w of r.workstreams ?? []) if (w.owner) workstreamsOf.set(w.owner, [...(workstreamsOf.get(w.owner) ?? []), { id: w.id, title: w.title, feature: fid }]);
for (const p of plans) p.workstreams = workstreamsOf.get(p.key) ?? [];
const allWorkstreams = Object.values(reviewFile.features ?? {}).flatMap((r) => r.workstreams ?? []);

// ---- work graph (optional): computed only from a work.json that passes, so the page never draws a
// cycle or an edge to a workstream that is gone.
const workFile = readJson(at("work.json"), null);
let work = null;
if (workFile) {
  const phaseIds = PHASES.map((ph) => ph.id);
  const workProblems = validateWork(workFile, wsIds, phaseIds);
  problems.push(...workProblems);
  if (!workProblems.length) work = computeWork(workFile, allWorkstreams, phaseIds);
}

// ---- context map (optional): who owns each file and table, and which imports reach into another
// context's internals. The code is scanned only where it exists, so a tree with no source still builds.
const contextsFile = readJson(at("contexts.json"), null);
let contexts = null;
if (contextsFile) {
  const skip = new Set(contextsFile.skip ?? ["node_modules", "__tests__", "dist", "build", "coverage", ".next"]);
  const exts = contextsFile.extensions ?? [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];
  const exclude = new RegExp(contextsFile.exclude ?? "\\.(test|spec|stories)\\.");
  const walk = (d) => readdirSync(join(C.root, d), { withFileTypes: true }).flatMap((n) => {
    if (skip.has(n.name) || n.name.startsWith(".")) return [];
    const p = `${d}/${n.name}`;
    return n.isDirectory() ? walk(p) : [p];
  });
  const scope = contextsFile.scope ?? ["src/"];
  const files = scope.filter((s) => existsSync(join(C.root, s))).flatMap((s) => walk(s.replace(/\/$/, "")))
    .filter((f) => exts.some((e) => f.endsWith(e)) && !exclude.test(f)).sort();
  const schemaFile = contextsFile.schema?.file ?? null;
  if (schemaFile && !existsSync(join(C.root, schemaFile))) problems.push(`contexts.json: schema.file ${schemaFile} does not exist`);
  const tables = schemaFile && existsSync(join(C.root, schemaFile)) ? tablesOf(readFileSync(join(C.root, schemaFile), "utf8"), contextsFile.schema?.table_pattern ?? DEFAULT_TABLE_PATTERN) : [];
  // Mirrors the page's planKey(): a plan key or path, an external plan's URL, with an optional #fragment.
  const extUrlRe = EXT?.url_id_pattern ? new RegExp(EXT.url_id_pattern) : null;
  const isPlan = (ref) => {
    const k = String(ref).split("#")[0];
    if (planKeys.has(k) || plans.some((p) => p.external_url === k)) return true;
    const m = extUrlRe ? extUrlRe.exec(k) : null;
    return !!m && planKeys.has(EXT_KEY(m[1]));
  };
  const contextProblems = validateContexts(contextsFile, { areaIds, featureIds, tables, files, isPlan, schemaFile });
  problems.push(...contextProblems);
  if (!contextProblems.length) {
    contexts = computeContexts(contextsFile, {
      files, imports: scanImports(files, (f) => readFileSync(join(C.root, f), "utf8"), contextsFile.aliases ?? {}), tables, schemaFile,
      features: registry.features, workstreams: allWorkstreams,
      gapEvidence: new Map((gapTable.gaps ?? []).map((g) => [g.id, g.evidence])), work,
    });
  }
}

for (const path of Object.keys(annotations)) {
  if (!planFiles.has(path)) problems.push(`annotations.json: ${path} is not a live plan ${ARCHIVE_HINT}`);
}

// ---- tracker rows with no plan
const trackerItems = Object.entries(trackerTags).flatMap(([id, tag]) => {
  const row = tracker.get(id);
  // A row the snapshot lacks has no status to judge, so it is a problem, never a guessed open row.
  if (!row) { problems.push(`tracker-features.json: row ${id} is not in tracker-snapshot.json (refresh the snapshot or drop the row)`); return []; }
  const features = (tag.features ?? []).map((entry) => entryOf(entry, `tracker-features.json: ${id}`)).filter(Boolean);
  if (!OPEN_TRACKER(row.status)) return [];
  return [{
    id, url: httpsOrNull(row.url) ?? (TRACKER.url_template ? TRACKER.url_template.replace("{id}", id) : null), item: row.item ?? tag.item ?? "", status: row.status ?? null,
    owner: row.owner ?? null, priority: row.priority ?? null, type: row.type ?? null,
    features, note: tag.note ?? "",
  }];
});

if (problems.length) {
  console.error(`feature-map: ${problems.length} problem(s)\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
const extCount = plans.filter((p) => p.source === "external").length;
const staleCount = plans.filter((p) => p.stale.length).length;
const summary = [
  `${registry.features.length} features`, `${(gapTable.gaps ?? []).length} gaps`, `${wsIds.size} workstreams`, `${plans.length - extCount} repo plans`,
  ...(EXT ? [`${extCount} ${EXT.label} plans`] : []), ...(TRACKER ? [`${trackerItems.length} open ${TRACKER.label} rows`] : []), `${staleCount} plans out of date`,
].join(", ");
const extra = (work ? `; work: ${work.edges.blocks} blocks and ${work.edges.enables} enables edges, ${work.milestones.map((m) => `${m.id} ${m.days} days`).join(", ") || "no milestones"}` : "")
  + (contexts ? `; contexts: ${contexts.counts.contexts}, ${contexts.counts.owned} of ${contexts.counts.files} files owned, ${contexts.counts.reach_ins} reach-ins, ${contexts.counts.independent_pairs} of ${contexts.counts.domain_pairs} pairs independent` : "");
if (args.check) {
  console.log(`feature-map: ok (${summary})${extra}`);
} else {
  const template = readFileSync(TEMPLATE, "utf8");
  if (!template.includes(PLACEHOLDER)) { console.error(`feature-map: ${TEMPLATE} has no ${PLACEHOLDER} placeholder`); process.exit(1); }
  const docRef = (file, title) => (file ? { file, title: `${title} ${file.slice(-13, -3)}`, github: C.repo_url && !relative(C.root, DIR).startsWith("..") ? `${C.repo_url}${relative(C.root, DIR)}/${file}` : null } : null);
  const git = (a) => spawnSync("git", a, { cwd: C.root, encoding: "utf8" }).stdout?.trim() || null;
  const data = {
    $comment: "Generated by build-map.mjs. Do not edit by hand.",
    config: {
      project: C.project,
      repo_url: C.repo_url,
      repo_label: C.repo_label,
      plans_dir: PLANS,
      default_feature: C.default_feature,
      external: EXT ? { label: EXT.label, key_prefix: EXT.key_prefix, url_id_pattern: EXT.url_id_pattern, program_label: EXT.program_label } : null,
      tracker: TRACKER ? { label: TRACKER.label, roadmap_label: TRACKER.roadmap_label } : null,
      causes: C.causes,
      gap_sources: C.gap_sources,
      owner_label: C.owner_label,
      branches: C.branches,
    },
    source: { repo: C.pr_repo, branch: git(["rev-parse", "--abbrev-ref", "HEAD"]), sha: git(["rev-parse", "--short", "HEAD"]), tracker_snapshot_taken_at: snapshot.taken_at ?? null, external_plans_taken_at: extPlans.taken_at ?? null, registry_generated_from: registry.generated_from ?? null },
    phases: PHASES,
    statuses: registry.statuses,
    areas: registry.areas,
    features: registry.features.map((f) => ({ ...f, gaps: pageGaps.get(f.id) ?? [], review: reviewFile.features?.[f.id] ?? null })),
    reviewed_at: reviewFile.reviewed_at ?? null,
    review_doc: docRef(reviewDoc, "Plan review"),
    work_review_doc: docRef(workReviewDoc, "Work review"),
    gap_count: (gapTable.gaps ?? []).length,
    links: registry.links,
    plans,
    tracker_items: trackerItems,
    work,
    contexts,
  };
  // `<` is escaped so no string in the data can close the inline <script> early.
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  rmSync(DIST, { recursive: true, force: true });
  mkdirSync(join(DIST, PLANS), { recursive: true });
  writeFileSync(join(DIST, "index.html"), template.replace(PLACEHOLDER, () => `<script id="fm-data" type="application/json">${json}</script>`));
  const repoPlans = plans.filter((p) => p.file);
  for (const p of repoPlans) copyFileSync(join(C.root, p.file), join(DIST, p.file));
  for (const doc of [reviewDoc, workReviewDoc]) if (doc) copyFileSync(at(doc), join(DIST, doc));
  console.log(`feature-map: wrote ${rel(join(DIST, "index.html"))} and ${repoPlans.length} plan files (${summary})${extra}`);
}
