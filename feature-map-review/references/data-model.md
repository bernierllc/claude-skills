# Data model

Every file lives in `docs/feature-map/` (configurable). The JSON files keep **one record per line**: one
feature, link, gap, plan annotation, external page or reviewed feature per line. A diff then shows exactly
which records changed. A reformat to one key per line turns a one-gap change into thousands of lines, so
write these files with `scripts/gaps.mjs` or with a writer that keeps the layout.

| File | What it is | Required |
|---|---|---|
| `config.json` | Project name, paths, phases, frontmatter field names, external source and tracker labels | yes |
| `features.json` | Areas, features (built and planned), links | yes |
| `gaps.json` | Every known gap under a permanent id | stage 2 |
| `reviews.json` | Per feature: review, workstreams, conflicts, plan changes; plus the synthesis | stage 3 |
| `annotations.json` | Per plan: one-line summary, how much is built, a note per `features:` entry | optional |
| `external-plans.json` | Plans kept outside the repo (for example Notion), and pages that only mirror a repo plan | optional |
| `tracker-snapshot.json` | Status, owner and priority of the tracker rows the map shows | optional |
| `tracker-features.json` | Open tracker rows with no plan, tagged like plans | optional |
| `plan-review-<date>.md` | The written review | stage 4 |
| `work.json` | Per workstream: what it needs first, what it waits on, who can do it; delivery data | stage 8 |
| `work-review-<date>.md` | The written work review | stage 8 |
| `contexts.json` | The context map: the product's independent pieces, what each owns and offers | stage 9 |
| `dist/` | Build output; add it to `.gitignore` | generated |

## config.json

Start from `assets/templates/config.json`; its `$comment` explains every key. The ones you will set:

| Key | Meaning |
|---|---|
| `project` | Name shown on the map |
| `repo_url` | Prefix for plan links, for example `https://github.com/acme/app/blob/main/` |
| `plans_dir` | Where the plans live |
| `plans_exclude` | Files in the plans folder that are not plans (ROADMAP.md, README.md) |
| `archive_dir` | Where archived plans go |
| `plans_exempt` | Plans with no frontmatter that stay that way (charters, decision records) |
| `plan_statuses` | The project's plan statuses |
| `phases` | Timeline columns in order, `{id, label}`. Add `gate: true` for a planning pause between phases. `default_phase` places plans with none |
| `plan_fields` | The frontmatter keys holding a plan's tracker and roadmap row URLs |
| `external` | `{label, key_prefix}` for plans kept outside the repo, for example `{"label": "Notion", "key_prefix": "notion"}`. Drop it if there are none |
| `tracker` | `{label, roadmap_label, id_pattern, closed_statuses, done_status}`. Drop it if there is no tracker |
| `stale_days` | How long an active plan can go without an update before the map flags it |
| `owner_label` | The person whose steps gate work, as the Work view names them ("Waits on Dana"). Default "the owner" |
| `branches` | `{integration, release}`: where work lands and where it is promoted. `release: null` when nothing is promoted; the Work view then hides promotion lag |

## features.json

```json
{"areas": [{"id": "core", "code": "COR", "name": "Core product", "column": 1}],
 "statuses": {"live": {"label": "Live", "tag": ""}, "planned": {"label": "Planned, not built", "tag": "PLANNED"}},
 "features": [
   {"id": "projects", "area": "core", "name": "Projects", "status": "live",
    "description": "One or two plain sentences: what it does for the user.",
    "pages": ["/projects"], "api": ["POST /api/v1/projects"], "jobs": [], "code": ["src/projects/"],
    "introduced_by": null}],
 "links": [{"from": "projects", "to": "permissions", "kind": "gate", "note": "Every project write checks the caller's role first.", "partial": false}]}
```

- **Ids** are kebab-case and permanent. A feature is a capability a customer, operator or integrator would
  recognise, not a module.
- **Areas:** `column` 0 to 3 places an area on the map's grid; `"band"` makes it a full-width band, for
  platform and engineering areas.
- **Statuses:** typical values are live, flagged (built but switched off), beta, api (no UI), internal
  (staff only), ops and planned.
  A `planned` feature names the plan that adds it in `introduced_by` (`plans/<file>.md` or
  `<prefix>:<id>` for an external plan), or a tracker row in `introduced_by_tracker`.
- **Link kinds,** read as "from <kind> to":
  - `needs`: from depends on to.
  - `gate`: from is checked by to.
  - `trigger`: from starts to.
  - `data`: from sends data to to.
  - `exposes`: from makes to available.

  `partial: true` marks a link that is half built.

## Plan frontmatter

```yaml
---
title: "Archive a project"
status: draft
phase: 2
created: 2026-10-27
updated: 2026-10-27
depends_on: []
supersedes: []
features: [adds:project-archive, changes:projects]
gaps: [GAP-0123, GAP-0140]
---
```

- `features:` (required, never empty): `<verb>:<feature id>`.
  - `adds`: creates a capability. Add it to `features.json` first as `planned`, with `introduced_by`
    naming this plan.
  - `changes`: new or reworked behaviour.
  - `fixes`: closes a defect or hole without changing what the feature is for.
  - `removes`: retires it, or part of it.
- `gaps:` (may be empty): the gaps this plan closes. Open ones come from the workstreams it owns; fixed
  ones stay on the plan that fixed them, as history. **Who fixes a gap lives on the plan, not on the
  gap**, so moving work between plans is one frontmatter edit.
- Keep the project's own fields (tracker links, PRs and so on). The scripts read only what config names.

## gaps.json

```json
{"next_id": 1315, "gaps": [
 {"id": "GAP-0123", "feature": "permissions", "related": ["public-api", "cli"], "severity": "high", "status": "open",
  "summary": "One plain sentence: what is missing or wrong.",
  "detail": "Why it matters (who hits it, what goes wrong) and what fixing it looks like. At most 400 characters.",
  "evidence": ["src/lib/permissions/index.ts:120", "plans/x.md#heading", "https://..."],
  "cause": "parity", "duplicate_of": null, "found_by": "surface audit", "source": "where it was seen",
  "found_at": "2026-10-27", "tracker": [{"url": "https://...", "status": "Backlog"}],
  "closed_at": null, "closed_by": null}]}
```

- **Ids** are `GAP-` plus at least four digits, taken from `next_id`. They are never renumbered or
  reused, because plans, rows and commits cite them.
- **`feature` and `related`:** `feature` is the home feature. `related` lists every other feature the fix
  must touch, and the map shows the gap on all of them. A gap that spans features needs a plan that spans
  them too.
- **severity:**
  - `high`: customer-facing breakage, compliance, data loss, security, or a launch blocker.
  - `medium`: real but contained.
  - `low`: polish.
- **status:**
  - `open`;
  - `unverified`: not yet checked against the code;
  - `fixed`: set `closed_at`, and `closed_by` to a PR, plan or path;
  - `duplicate`: set `duplicate_of`;
  - `wontfix`: give the reason in `detail`.
- **cause:** why the gap exists. The Learnings view counts these, which turns a gap list into process
  feedback.
  - `scoped-out`: a plan deferred it knowingly.
  - `parity`: one surface (UI, API, CLI, SDK, docs, test docs) lacks what another has.
  - `missing-guard`: a permission, gate, validation, rate limit or audit check is missing.
  - `not-built`: planned work that has not been built yet.
  - `drift`: docs, plans or config disagree with the code.
  - `debt`: a known shortcut or baseline exception.
  - `config`: environment or account setup not done.
  - `unplanned`: a need nobody planned for.
  - `regression`: it worked once and broke.
- **found_by:** how the gap was found: plan file, tracker row, external plan, known-debt list, surface
  audit, code review, incident or agent audit. Keep the same set in the tracker's "Found by" property if
  it has one.

## reviews.json

```json
{"reviewed_at": "2026-10-27",
 "features": {
  "reports": {"summary": "...", "health": "at-risk",
   "plans": [{"plan": "plans/x.md", "role": "owns", "note": "..."}],
   "workstreams": [{"id": "WS-017", "title": "Gate the report routes behind reports.manage",
     "why": "What goes wrong today and what done looks like.", "gaps": ["GAP-0244"],
     "features": ["reports", "permissions"], "owner": "plans/x.md", "new_plan": false, "phase": "1", "size": "S",
     "depends_on": [], "row": null, "merged_from": ["WS-018"]}],
   "conflicts": [{"plans": ["plans/a.md", "plans/b.md"], "issue": "...", "resolution": "..."}],
   "plan_changes": [{"plan": "plans/a.md", "change": "re-scope", "target": null, "detail": "..."}],
   "new_plans": []}},
 "synthesis": {"new_plans": [...], "phase1": ["WS-007"], "held_for_user": [...]}}
```

- **health:**
  - `solid`: few or low gaps, owned.
  - `gaps`: real holes, mostly owned.
  - `at-risk`: high-severity holes nobody owns, or plans that conflict.
- **Plan roles:**
  - `owns`: the feature's work should happen here.
  - `touches`: changes it in passing.
  - `stale`: done, superseded, or its scope for this feature is already built.
  - `conflicts`: disagrees with another plan about this feature.
- **Workstreams:**
  - Each one is a unit one person could ship (one PR or a short series).
  - Ids are `WS-` plus three or more digits, permanent.
  - Every open gap is in exactly one workstream.
  - `owner` is a live plan key (`plans/<file>.md` or `<prefix>:<id>`), so `owner: null` only appears
    before synthesis.
  - `size` is `S` (hours), `M` (a day or two) or `L` (more).
  - `row` is the tracker row URL once it exists.
  - `phase` is one of the config phases (not `now`) and `size` is required; the build fails otherwise,
    because either mistake bends every critical path through the workstream.
- **Plan change kinds:** `merge-into`, `split`, `re-scope`, `close`, `move-phase`, `add-gaps`. Once a
  change is applied and its plan is archived, drop the entry; the written report keeps the history.

## external-plans.json

```json
{"taken_at": "2026-10-27T16:54Z",
 "pages": [{"id": "<page id>", "url": "https://...", "title": "...", "path": "Roadmap / Platform / ...",
   "kind": "program | sub-plan | design | runbook | draft", "phase": "2", "program_phase": "P3", "status": "draft",
   "summary": "...", "features": ["adds:audit-log"], "notes": {"adds:audit-log": "..."},
   "gaps": ["GAP-0201"],
   "repo_plans": [{"plan": "plans/x.md", "relation": "extends | implements | supersedes | related"}],
   "tracker_rows": ["https://..."], "depends_on": ["notion:<id>", "plans/x.md"]}],
 "mirrors": {"<page id>": {"url": "https://...", "title": "...", "plan": "plans/x.md", "drift": "what is out of date, or null"}}}
```

`phase` is the project's phase; `program_phase` is optional, the step in a wider program the page belongs to. A page that only mirrors a repo plan goes under `mirrors`. It shows as a link on that plan, and if its
`drift` is set, the plan is flagged out of date. Runbooks stay hidden on the map until the viewer turns
them on.

## annotations.json

```json
{"plans": {"plans/x.md": {"summary": "One plain sentence.", "built": "none | partial | most | all | unknown",
  "built_evidence": "PRs or the code path checked", "notes": {"changes:projects": "What it changes there."}}}}
```

A plan whose `built` is `all` but whose status is not done is flagged **out of date** on the map, and so is
an active plan that has not been updated for a long time. Close it with evidence, or update it.

## tracker-snapshot.json and tracker-features.json

`tracker-snapshot.json` holds `{taken_at, tracker: [{id, url, item, status, owner, priority, type, due}],
roadmap: [{id, url, name, status, stage, kind, severity, plan_file}]}`, read-only from the tracker.

`tracker-features.json` holds `{rows: {"<row id>": {features: ["fixes:x"], note}}}` for open rows that
have no plan. A tagged row missing from the snapshot fails `--check`; refresh the snapshot or drop the row.

## work.json

The Work view's input (stage 8). Every workstream in `reviews.json` needs a record, because a workstream
with none would read as ready with nothing before it. One workstream per line.

```json
{"taken_at": "2026-10-28",
 "size_days": {"S": 1, "M": 3, "L": 8},
 "size_days_basis": "Anchored on done plans: median 5 days from created to last PR merge.",
 "wait_days": {"human": 2, "external": 5, "decision": 3},
 "milestones": [{"id": "launch", "label": "Launch", "phases": ["1"]}, {"id": "scale", "label": "Scale", "phases": ["1", "2"]}],
 "git": null,
 "workstreams": {
  "WS-248": {"who": "agent+human", "needs": [{"ws": "WS-095", "kind": "blocks", "why": "Bulk export reuses the job queue table WS-095 adds."}], "waits": [{"kind": "human", "what": "Confirm the largest project size to support", "ref": ""}], "notes": ""}}}
```

- **needs:** `{ws, kind, why}`. The edge runs from `ws` to the workstream: `ws` lands first.
  - `blocks`: this one cannot be built, or cannot ship correctly, before `ws` lands.
  - `enables`: this one could ship first, but is cheaper or safer after `ws`.
  - `why` names the concrete thing (a table, route, function, decision or plan section). Shared topic,
    shared feature or the same plan is not a reason.
- **waits:** `{kind, what, ref}`, things outside the graph.
  - `human`: a step only `owner_label` can take (a console action, a signature, a promotion, a call).
  - `external`: a vendor, a customer or another third party.
  - `date`: cannot start before a date.
  - `decision`: an open question; `ref` points at it (`plans/<file>.md#heading`).
- **who:** `agent` (an agent builds, tests and opens the PR end to end), `agent+human` (an agent, with
  one step from the owner) or `human`.
- **size_days, wait_days:** a workstream's duration is its size in days plus one allowance per distinct
  wait kind (a date adds none). Anchor `size_days` on the project's own done plans, and say how in
  `size_days_basis`.
- **milestones:** `{id, label, phases}`, with phase ids from `config.json`. The critical path of each
  milestone runs over its phases' workstreams plus every workstream they need first.
- **git:** optional delivery data measured from the repo, its PRs and CI (the delivery brief):
  `taken_at`, `window` (`integration_head`, `release_head`, `followup_days`, dates), `size_days` (measured
  PR days per size), `features` (per feature: commits, fixes, reverts, files, agent share, rework,
  follow-up fix rate), `prs`, `ci`, `iteration_sample`, `promotion` (`lag_days`, `unpromoted_commits`,
  `oldest_unpromoted_days`), `plans` (`lead_days`), `notes`. Every field is optional; the page shows what
  is there.

The build checks: every workstream has a record and nothing else does; `who` and the edge and wait kinds
are valid; no workstream needs itself or names one twice; `blocks` edges form no cycle; milestones name
config phases. It then computes, per workstream:
- duration, the workstreams it unlocks (through `blocks`, transitively), its `enables` reach;
- earliest start, finish and slack on each milestone's critical path;
- its classes, first one wins for the card colour: `long-pole` (no slack on a milestone), `linchpin-blocker`
  (unlocks three or more), `linchpin-enabler` (enables three or more), `convergence` (needs three or more
  first), `human`, `external`, `decision`, `date`, `phase-inversion` (needs something from a later phase),
  `agent-ready` (nothing before it, no wait, `who: agent`), `ready`, `leaf` (no edges, no waits).

## contexts.json

The Contexts view's input (stage 9): the product's independent pieces, what each owns and what it
offers the others. The code's imports are read from JS and TS files under `scope`; other languages still
get ownership and its checks, but no reach-ins.

```json
{"taken_at": "2026-10-28",
 "scope": ["src/"],
 "aliases": {"@/": "src/"},
 "schema": {"file": "src/lib/db/schema.ts"},
 "contexts": [
  {"id": "kernel", "name": "Shared kernel", "kind": "shared", "summary": "DB client, env, logging, UI kit.", "areas": [], "owns": {"code": ["src/lib/db/**", "src/components/ui/**"], "tables": []}, "interfaces": []},
  {"id": "core", "name": "Core product", "kind": "domain", "summary": "Projects and everything done inside one.", "areas": ["core"], "features": ["comments"],
   "owns": {"code": ["src/projects/**"], "tables": ["projects"]},
   "interfaces": [{"path": "src/projects/index.ts", "status": "defined", "what": "getProject(): the one way to read a project."},
                  {"status": "missing", "what": "exportProject(): the one way to read a whole project out.", "ref": "plans/2026-01-01-project-export.md"}]}]}
```

- **kind:** `domain` (a piece of the product), `shared` (the kernel: every context may import it, and it
  imports no context), `none` (tooling outside the product, such as scripts).
- **areas, features:** every `features.json` area sits in exactly one context; `features` moves a single
  feature out of its area's context.
- **owns.code:** globs (`**` any depth, `*` inside one segment). The most specific match owns a file: a path
  with no `*` beats any pattern, then more literal characters win. Two contexts tying on a file is an error.
- **owns.tables:** table names as the schema declares them. `schema.file` is the one module that declares
  tables, and `schema.table_pattern` a regex with one capture group for a table's name (the default
  reads Drizzle's `pgTable`, `mysqlTable` and `sqliteTable`). Table use is read from named imports of the
  schema module, including destructured `await import()`. Leave `schema` null when the code does not
  import tables by name; tables are then ownership only.
- **interfaces:** `{path, status: "defined", what}` for a file other contexts may import, or
  `{status: "missing", what, ref}` for one a plan must build, `ref` being that plan (a plan path or an
  external plan's key or URL, optionally with `#heading`).
- **scope, aliases, extensions, exclude, skip:** what to walk. Defaults: `["src/"]`; no aliases;
  `.ts .tsx .js .jsx .mjs .cjs`; files matching `\.(test|spec|stories)\.` excluded; `node_modules`,
  `__tests__`, `dist`, `build`, `coverage`, `.next` and dot folders skipped.

The rules the build applies:
- An import from context A into a file of context B is a **reach-in** unless that file is one of B's
  declared interfaces or B is the kernel. Type-only imports (`import type`, or a clause of `type`
  specifiers only) count apart.
- A file other contexts import that is not declared is an **implicit interface**: either declare it or
  stop the imports.
- Two domain contexts are **independent** when no reach-in runs between them either way.
- A workstream's contexts come from the code paths its gaps' evidence names, else from its features.
- **Lanes:** agent-ready workstreams that change disjoint contexts, picked greedily in phase order then by
  how much they unlock, each with the reach-ins that still couple it to the other lanes.

`--check` fails on: an area or feature in two contexts, or an area in none; a table owned twice, or not in
the schema; a glob that matches no file; a defined interface whose file is missing or owned by another
context; a missing interface whose `ref` is not a live plan; a file two contexts claim equally; a source
file or a schema table no context owns. So a new folder, a new table or a moved file fails lint instead of
drifting.

