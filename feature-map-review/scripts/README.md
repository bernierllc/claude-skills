# Scripts

Node 18+, no dependencies. Run them from the target repo's root, or pass `--root`. Every script
reads `<dir>/config.json` (default dir `docs/feature-map`; override with `--dir`). Start a new
project by copying `../assets/templates/` into that dir and a plan into `plans/`.

| Script | What it does | Exit |
| --- | --- | --- |
| `build-map.mjs` | Validates the registry, gap table, reviews, annotations, external plans, tracker snapshot, every plan's frontmatter and, when present, `work.json` and `contexts.json` (walking the code under its scope), then writes `<dir>/dist/index.html` (data inlined) plus a copy of each plan and the latest plan and work reviews for the page's reader. | 0 ok, 1 on any problem (listed) |
| `build-map.mjs --check` | Validation only, nothing written. Put it in CI or lint. | 0 / 1 |
| `check-plans.mjs` | Plan frontmatter guard: required fields, status and phase enums, `features:` and `gaps:` ids exist and are not repeated, `depends_on`/`supersedes` name live plans, done plans name a PR, plan links and repo-wide `plans/<file>.md` citations resolve. | 0 / 1 |
| `gaps.mjs next-id` | Prints the next free gap id. | 0 |
| `gaps.mjs add --json <file>` | Appends one gap or a list, assigning permanent ids from `next_id` (never reused) and filling defaults. Refuses unknown feature ids. | 0 / 1 |
| `gaps.mjs close <id> --status fixed\|duplicate\|wontfix --by <plan or PR> [--dup-of <id>]` | Closes a gap with `closed_at` and `closed_by`. | 0 / 1 |
| `gaps.mjs sync-plan-gaps [--apply]` | Sets each plan's `gaps:` to the fixed gaps it already lists plus the open gaps of the workstreams it owns (archived plans keep only fixed ones); also `external-plans.json` pages. Dry run without `--apply`. | 1 when a workstream owner names no plan |
| `gaps.mjs learnings` | Open and fixed gaps by cause, by how they were found and by area, with the check a plan should carry for each cause. | 0 |
| `gaps.mjs stats` | Counts by status and severity, how many open gaps have a plan or a tracker row, workstreams without an owner or row. | 0 |

Common flags: `--root <repo root>` (default: current directory), `--dir <map dir>` (relative to
the root, default `docs/feature-map`). `build-map.mjs` also takes `--out <dir>` (default
`<dir>/dist`) and `--template <file>` (default `<dir>/feature-map.html` if present, else
`../assets/feature-map.html`).

`lib/` holds the shared pieces: `frontmatter.mjs` (the one plan frontmatter parser, plus
`setListField` for rewriting a list line), `config.mjs` (flags, config defaults) and
`jsonl.mjs` (one-record-per-line writers whose output matches Python's `json.dumps` separators,
so files edited by either language diff cleanly), `work.mjs` (the Work view: work.json checks, durations,
critical paths per milestone, classes) and `contexts.mjs` (the Contexts view: glob ownership, import
scanning for JS and TS, reach-ins, table use, lanes). Both are pure functions over data the build reads.

Data files the scripts read, all optional except `features.json`: `gaps.json`, `reviews.json`,
`annotations.json`, `external-plans.json`, `tracker-snapshot.json`, `tracker-features.json`,
`plan-review-<date>.md`, `work.json`, `work-review-<date>.md`, `contexts.json`. Their shapes are described in each template's `$comment` and in
`../references/`.
