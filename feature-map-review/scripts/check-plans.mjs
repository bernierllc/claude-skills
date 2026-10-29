#!/usr/bin/env node
// Plan guard: every live plan carries the frontmatter the feature map reads, and every plan
// reference resolves. File-system only. Run it where CI or a pre-commit hook will see it.
//
//   node check-plans.mjs [--root .] [--dir docs/feature-map]
//
// Rules, each one fails the run (exit 1):
//   1. every top-level <plans_dir>/*.md (minus plans_exclude) opens with frontmatter, unless it
//      is listed in config plans_exempt;
//   2. it has every required field (config required_fields; default title, status, phase,
//      features, gaps); list fields are lists;
//   3. status is one of plan_statuses, phase one of the config phases, dates YYYY-MM-DD;
//      done needs a PR in prs (config done_needs_pr, default true); archived plans live in
//      archive_dir;
//   4. features: non-empty `<adds|changes|fixes|removes>:<id>` entries, ids in features.json,
//      no feature twice;
//   5. gaps: GAP-NNNN ids in gaps.json, none twice;
//   6. depends_on / supersedes / blocked_by name live plans (repo-relative paths);
//   7. relative .md links between plans resolve, and every `<plans_dir>/<file>.md` citation in
//      git-tracked text files points at a file that exists, so archiving a plan cannot leave a
//      dangling reference behind.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, normalize, relative } from "node:path";
import { loadConfig, parseArgs, readJson } from "./lib/config.mjs";
import { FEATURE, FEATURE_VERBS, frontmatter, GAP_ID, LISTS } from "./lib/frontmatter.mjs";

const args = parseArgs();
const C = loadConfig(args);
const raw = readJson(join(C.dir, "config.json"), {});
const ROOT = C.root;
const PLANS = C.plans_dir;
const ARCHIVE = C.archive_dir;
const REQUIRED = C.required_fields ?? ["title", "status", "phase", "features", "gaps"];
const PHASES = new Set(C.phases.filter((p) => p.id !== "now").map((p) => p.id));
const EXEMPT = new Set(raw.plans_exempt ?? []);
const DONE_NEEDS_PR = raw.done_needs_pr ?? true;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const errors = [];
const abs = (p) => join(ROOT, p);
const relDir = relative(ROOT, C.dir);

const ids = (file, key) => {
  const f = join(C.dir, file);
  if (!existsSync(f)) { errors.push(`${relDir}/${file}: missing; plan ${key} ids are checked against it`); return null; }
  try { return new Set(JSON.parse(readFileSync(f, "utf8"))[key === "features" ? "features" : "gaps"].map((x) => x.id)); }
  catch (e) { errors.push(`${relDir}/${file}: not readable (${e.message})`); return null; }
};
const featureIds = ids("features.json", "features");
const gapIds = ids("gaps.json", "gaps");

if (!existsSync(abs(PLANS))) { console.error(`check-plans: ${PLANS} does not exist under ${ROOT}`); process.exit(1); }
const files = readdirSync(abs(PLANS)).filter((f) => f.endsWith(".md") && !C.plans_exclude.has(f)).sort();
const live = new Set(files.map((f) => `${PLANS}/${f}`));
const isLive = (p) => /\.md$/.test(p) && !p.includes("..") && live.has(normalize(p));

let checked = 0;
for (const f of files) {
  const path = `${PLANS}/${f}`;
  const fm = frontmatter(readFileSync(abs(path), "utf8"));
  if (!fm) { if (!EXEMPT.has(f)) errors.push(`${path}: missing the leading frontmatter block (--- ... ---); add it, or list the file in config plans_exempt`); continue; }
  checked++;
  const missing = REQUIRED.filter((k) => !(k in fm));
  if (missing.length) errors.push(`${path}: frontmatter is missing ${missing.join(", ")}`);
  for (const k of LISTS) if (k in fm && !Array.isArray(fm[k])) errors.push(`${path}: frontmatter ${k} must be a list ([] when empty)`);
  if ("status" in fm && !C.plan_statuses.has(fm.status)) errors.push(`${path}: status "${fm.status}" is not one of ${[...C.plan_statuses].join(" | ")}`);
  if ("phase" in fm && !PHASES.has(fm.phase)) errors.push(`${path}: phase "${fm.phase}" is not one of ${[...PHASES].join(" | ")}`);
  for (const k of ["created", "updated"]) if (k in fm && fm[k] && !DATE.test(fm[k])) errors.push(`${path}: ${k} "${fm[k]}" is not YYYY-MM-DD`);
  for (const k of ["depends_on", "supersedes", "blocked_by"]) {
    for (const p of Array.isArray(fm[k]) ? fm[k] : []) {
      if (k === "blocked_by" && !/\.md$/.test(p)) continue; // blocked_by may name a person or a non-plan blocker
      if (!isLive(p)) errors.push(`${path}: ${k} lists ${p}, which is not a live plan (repo-relative: ${PLANS}/<file>.md)`);
    }
  }
  if (Array.isArray(fm.features)) {
    if (!fm.features.length) errors.push(`${path}: features is empty; name each feature the plan ${FEATURE_VERBS.join(", ")}, as <verb>:<id>`);
    const named = new Set();
    for (const entry of fm.features) {
      const m = entry.match(FEATURE);
      if (!m) errors.push(`${path}: features entry "${entry}" is not <${FEATURE_VERBS.join("|")}>:<feature-id>`);
      else if (featureIds && !featureIds.has(m[2])) errors.push(`${path}: features names "${m[2]}", which is not in features.json (add it there first)`);
      else if (named.has(m[2])) errors.push(`${path}: features names "${m[2]}" twice; keep the one verb that fits best`);
      if (m) named.add(m[2]);
    }
  }
  const seen = new Set();
  for (const id of Array.isArray(fm.gaps) ? fm.gaps : []) {
    if (!GAP_ID.test(id)) errors.push(`${path}: gaps entry "${id}" is not a gap id (GAP-0001)`);
    else if (gapIds && !gapIds.has(id)) errors.push(`${path}: gaps names ${id}, which is not in gaps.json`);
    else if (seen.has(id)) errors.push(`${path}: gaps names ${id} twice`);
    seen.add(id);
  }
  if (DONE_NEEDS_PR && fm.status === "done" && !(Array.isArray(fm.prs) && fm.prs.length)) errors.push(`${path}: status done needs at least one PR in prs`);
  if (fm.status === "archived") errors.push(`${path}: status archived, so git mv it to ${ARCHIVE}/`);
}

// ---- references: plan-to-plan links and repo-wide citations of plan paths
const archived = existsSync(abs(ARCHIVE)) ? readdirSync(abs(ARCHIVE)).filter((n) => n.endsWith(".md")) : [];
const known = new Set([...files, ...archived]);
for (const dir of [PLANS, ARCHIVE].filter((d) => existsSync(abs(d)))) {
  for (const f of readdirSync(abs(dir)).filter((n) => n.endsWith(".md"))) {
    for (const [, link] of readFileSync(abs(join(dir, f)), "utf8").matchAll(/\]\((?!https?:|#|\/)([^)#\s]+\.md)(?:#[^)]*)?\)/g)) {
      if (known.has(basename(link)) && !existsSync(normalize(join(abs(dir), link)))) errors.push(`${join(dir, f)}: links to missing ${link}`);
    }
  }
}
const tracked = spawnSync("git", ["ls-files", "-z"], { cwd: ROOT, encoding: "utf8" });
if (tracked.status === 0) {
  const TEXT = /\.(md|mdx|ts|tsx|js|mjs|cjs|jsx|py|rb|go|rs|java|kt|json|ya?ml|toml|sh|txt)$/;
  const cite = new RegExp(`(?<![\\w/.-])${PLANS.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/((?:${basename(ARCHIVE)}/)?[\\w.-]+\\.md)`, "g");
  const dist = `${relDir}/dist/`;
  for (const f of tracked.stdout.split("\0").filter((x) => x && TEXT.test(x) && !x.startsWith(dist))) {
    if (!existsSync(abs(f)) || !statSync(abs(f)).isFile()) continue;
    for (const [, c] of readFileSync(abs(f), "utf8").matchAll(cite)) {
      if (known.has(basename(c)) && !existsSync(abs(join(PLANS, c)))) errors.push(`${f}: cites ${PLANS}/${c}, which does not exist`);
    }
  }
}

if (errors.length) {
  console.error(`check-plans: ${errors.length} problem(s)\n  ${errors.join("\n  ")}`);
  process.exit(1);
}
console.log(`check-plans: ok (${checked} plans with frontmatter, ${files.length - checked} exempt, ${archived.length} archived)`);
