// Command-line flags and <dir>/config.json, with the defaults every script shares.
import { existsSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";

/** `--flag value` and bare `--flag` into an object; positionals under `_`. */
export function parseArgs(argv = process.argv.slice(2)) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) { out._.push(a); continue; }
    const [k, inline] = a.slice(2).split(/=(.*)/s);
    if (inline !== undefined) out[k] = inline;
    else if (i + 1 < argv.length && !argv[i + 1].startsWith("--")) out[k] = argv[++i];
    else out[k] = true;
  }
  return out;
}

export const readJson = (f, fallback) => (existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : fallback);

const DEFAULT_PHASES = [
  { id: "now", label: "Today" },
  { id: "1", label: "Phase 1" },
  { id: "2", label: "Phase 2" },
  { id: "3", label: "Phase 3" },
];

/**
 * Resolves the repo root, the map directory and config.json. Every config key is optional:
 * no `external` means no plans outside the repo; no `tracker` means no tracker rows.
 */
export function loadConfig(args) {
  const root = resolve(args.root ?? process.cwd());
  const dirRel = args.dir ?? "docs/feature-map";
  const dir = resolve(root, dirRel);
  const raw = readJson(join(dir, "config.json"), {});
  const plansDir = raw.plans_dir ?? "plans";
  let phases = Array.isArray(raw.phases) && raw.phases.length ? raw.phases.map((p) => (typeof p === "string" ? { id: p, label: p } : p)) : DEFAULT_PHASES;
  // Done plans sit under "now", so the phase list always starts with it.
  if (!phases.some((p) => p.id === "now")) phases = [{ id: "now", label: "Today" }, ...phases];
  const planPhases = phases.filter((p) => p.id !== "now");
  const repoUrl = raw.repo_url ? String(raw.repo_url).replace(/\/?$/, "/") : null;
  const prRepo = raw.pr_repo ?? repoUrl?.match(/github\.com\/([^/]+\/[^/]+)\//)?.[1] ?? null;
  const external = raw.external
    ? {
        label: raw.external.label ?? "External",
        key_prefix: raw.external.key_prefix ?? "ext",
        id_pattern: raw.external.id_pattern ?? "^[A-Za-z0-9_.-]+$",
        url_id_pattern: raw.external.url_id_pattern ?? null,
        program_label: raw.external.program_label ?? null,
      }
    : null;
  const tracker = raw.tracker
    ? {
        label: raw.tracker.label ?? "Tracker",
        roadmap_label: raw.tracker.roadmap_label ?? "Roadmap",
        id_pattern: raw.tracker.id_pattern ?? "([^/?#]+)/?(?:[?#].*)?$",
        closed_statuses: raw.tracker.closed_statuses ?? ["Done", "Duplicate", "No Op", "Do Not Do", "Closed", "Cancelled", "Canceled"],
        done_status: raw.tracker.done_status ?? "Done",
        url_template: raw.tracker.url_template ?? null,
      }
    : null;
  return {
    root,
    dirRel,
    dir,
    project: raw.project ?? basename(root),
    repo_url: repoUrl,
    pr_repo: prRepo,
    repo_label: raw.repo_label ?? (repoUrl && /github\.com/.test(repoUrl) ? "GitHub" : "Source"),
    plans_dir: plansDir,
    plans_exclude: new Set(raw.plans_exclude ?? ["ROADMAP.md", "README.md"]),
    archive_dir: raw.archive_dir ?? `${plansDir}/archive`,
    plan_statuses: new Set(raw.plan_statuses ?? ["draft", "active", "blocked", "done", "archived"]),
    phases,
    default_phase: raw.default_phase ?? planPhases[planPhases.length - 1]?.id ?? "now",
    plan_fields: { tracker: raw.plan_fields?.tracker ?? "tracker", roadmap: raw.plan_fields?.roadmap ?? "roadmap" },
    external,
    tracker,
    stale_days: raw.stale_days ?? 30,
    default_feature: raw.default_feature ?? null,
    causes: raw.causes ?? null,
    gap_sources: raw.gap_sources ?? null,
    required_fields: raw.required_fields ?? null,
    // The person whose steps gate work (Work view: "Waits on <owner_label>").
    owner_label: raw.owner_label ?? "the owner",
    // Where work lands and where it is promoted to; release null when the project has no promotion step.
    branches: { integration: raw.branches?.integration ?? "main", release: raw.branches?.release ?? null },
  };
}
