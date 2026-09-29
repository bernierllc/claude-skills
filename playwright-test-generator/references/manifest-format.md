# Manifest Format Reference

The manifest lives in `tests/verification-playwright/manifest/`:

```
manifest/
├── config.json                     # tier config (hand-edited, not versioned by layout)
├── items/
│   ├── pages--admin-event-form.json   # one file per verification doc
│   └── flows--checkout.json
├── import-index/
│   ├── admin-event-form.json          # one file per page tag
│   └── admin-event-list.json
└── .lock                           # transient lockfile
```

Layout **2.0** (skill 4.0.0+). There is **no repo-wide file and no repo-wide
timestamp**: an edit to one verification doc rewrites only that doc's
`items/<doc-slug>.json`, so parallel branches editing different docs touch
disjoint files and merge without conflict.

**Read and write only through `scripts/lib/manifest.js`** — `loadManifest(dir)`
and `saveManifest(manifest)`. No script parses these files directly; the loader
is also where migration happens (see [Versions and migration](#versions-and-migration)).

## `manifest/items/<doc-slug>.json`

One file per verification doc. `<doc-slug>` is the doc path with
`docs/verification/` and `.md` stripped and `/` replaced by `--`
(`docs/verification/pages/admin-event-form.md` → `pages--admin-event-form.json`).

```json
{
  "version": "2.0",
  "hash_version": 1,
  "source_doc": "docs/verification/pages/admin-event-form.md",
  "updated_at": "2026-09-28T18:00:00.000Z",
  "items": {
    "EVT-FRM-TKT-03": {
      "source_doc": "docs/verification/pages/admin-event-form.md",
      "spec_file": "tests/verification-playwright/pages/admin-event-form.spec.ts",
      "content_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
      "generated_hash": "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5",
      "depth": "standard",
      "status": "active",
      "pinned": false,
      "pending_generation": true,
      "testids_required": ["ticket-price-min", "ticket-price-max", "submit-event", "ticket-price-error"],
      "testids_missing": ["ticket-price-error"]
    }
  }
}
```

### File fields

| Field | Type | Description |
|---|---|---|
| `version` | string | Manifest layout version, `"2.0"`. See [Versions and migration](#versions-and-migration). |
| `hash_version` | number | Normalization algorithm version for this doc's hashes (see SKILL.md → hash_version) |
| `source_doc` | string | The doc this file holds. Every entry's `source_doc` equals it. |
| `updated_at` | string | When this file's items last changed. Only rewritten when the items change. |

### Item fields

| Field | Type | Description |
|---|---|---|
| `source_doc` | string | Path to the verification doc this item came from (project-relative) |
| `spec_file` | string | Path to the generated .spec.ts file (project-relative) |
| `content_hash` | string | SHA-256 of the normalized verification item text (see hash normalization) |
| `generated_hash` | string | SHA-256 of the generated test code between `@begin`/`@end` markers |
| `depth` | string | `smoke`, `standard`, or `deep` |
| `status` | string | `active` (test runs), `skipped` (missing testids), `pinned` (manually edited) |
| `pinned` | boolean | When `true`, skill will not overwrite this test |
| `pending_generation` | boolean | Present and `true` when the item is queued for LLM generation (replaces `pending-generation.json`) |
| `testids_required` | string[] | All data-testid values this test needs |
| `testids_missing` | string[] | testids not found in the codebase |

### ID uniqueness

Item IDs are **globally unique across all doc files**. `loadManifest` refuses to
load a manifest where one ID appears in two files, and `sync-tests.js` refuses
(naming the owning doc) to add an item whose ID another doc already owns.

### Rebuild

`--force-items` rebuilds every `items/*.json` file by re-scanning all verification docs and regenerating all tests. Pinned tests are overwritten only with `--force`.

## `manifest/import-index/<page>.json`

Maps source files to the verification page they affect, one file per page tag. Used by `map-changes.js` for change-scoped test execution; the loader inverts the files into `{sourceFile: [pageTags]}` in memory.

Paths are **repo-root-relative** (the git toplevel), not relative to the Playwright project dir. This lets entries span multiple packages in a monorepo and match `git diff --name-only` output, which is always repo-root-relative. `map-changes.js` and `verify-pipeline.js` resolve the repo root with `git rev-parse --show-toplevel` and fall back to the project dir outside a git repo, so single-root projects (where the two bases coincide) are unaffected. The example below lists `admin/static/admin/src/...` and `admin/app/...` — two packages under one repo root.

```json
{
  "version": "2.0",
  "root": "repo",
  "page": "admin-event-form",
  "updated_at": "2026-09-28T18:00:00.000Z",
  "files": [
    "admin/app/routers/events.py",
    "admin/static/admin/src/components/ArtistSection.tsx",
    "admin/static/admin/src/components/EventForm.tsx"
  ]
}
```

The page tag is the file name, so it must match `^[A-Za-z0-9][\w.-]*$`.

### Construction

Built during skill invocation (not by `sync-tests.js`):

1. **From verification docs outward:** each page doc covers specific routes (listed in its header). Trace routes to component files via the project's routing structure.
2. **From components inward:** for each component, follow its import tree (1 level deep) to capture shared components, hooks, utilities.
3. **From API routes:** verification items referencing API behavior are mapped to backend route handlers.

Write one `import-index/<page>.json` per page, touching only the pages you rebuilt.

### Staleness

`map-changes.js` validates file existence on each lookup. Stale entries (pointing to deleted/moved files) are excluded and warned. Rebuild with `--force-index`.

## manifest/config.json

Tier configuration, dry-run mode, and test isolation strategy.

```json
{
  "version": "1.0",
  "dry_run": false,
  "tiers": {
    "gate": {
      "trigger": "pre-commit",
      "branches": "*",
      "browsers": ["chromium"],
      "depths": ["smoke", "standard"],
      "maxTests": 30,
      "timeoutMs": 60000
    },
    "thorough": {
      "trigger": "pre-push",
      "branches": ["staging", "develop"],
      "browsers": ["chromium", "firefox", "webkit"],
      "depths": ["smoke", "standard", "deep"],
      "maxTests": 100,
      "timeoutMs": 300000
    },
    "full": {
      "trigger": "pre-push",
      "branches": ["main", "production"],
      "browsers": ["chromium", "firefox", "webkit", "Mobile Chrome", "Mobile Safari"],
      "depths": ["smoke", "standard", "deep"],
      "maxTests": null,
      "timeoutMs": null
    }
  },
  "test_isolation": {
    "strategy": "per-test-user",
    "cleanup": "after-each",
    "notes": "Project-specific. Set during init."
  }
}
```

### Tier fields

| Field | Type | Description |
|---|---|---|
| `trigger` | string | `pre-commit` or `pre-push` |
| `branches` | string or string[] | Branch patterns to match. `*` matches all. |
| `browsers` | string[] | Playwright project names to run |
| `depths` | string[] | Which depth tags to include in `--grep` |
| `maxTests` | number or null | Circuit breaker. `null` = no limit. |
| `timeoutMs` | number or null | Primary time constraint. `null` = no limit. |

### Test isolation strategies

| Strategy | Description |
|---|---|
| `per-test-user` | Each test uses a unique test user account |
| `per-test-seed` | Each test seeds data in `beforeEach`, cleans in `afterEach` |
| `serial` | Tests run sequentially, no parallelism |
| `database-reset` | Reset to seed state before each test file |

All values are user-configurable during skill initialization and can be changed directly in config.json.

## Content Hash Normalization

All content hashes use SHA-256 of a normalized representation to prevent churn from whitespace reformatting:

1. Strip leading/trailing whitespace per line
2. Collapse multiple consecutive spaces to a single space
3. Lowercase the item ID (e.g., `EVT-FRM-TKT-03` becomes `evt-frm-tkt-03`)
4. Remove HTML comment markers (`<!--`, `-->`) from annotations before hashing
5. Sort annotation fields alphabetically within each annotation block
6. Encode as UTF-8, compute SHA-256, output as hex string

## Versions and migration

Every layout file carries a top-level `version`. Layout 1 (skill ≤ 3.x) kept
everything in three repo-wide files — `manifest/items.json`,
`manifest/import-index.json` and `tests/verification-playwright/pending-generation.json` —
at `"1.0"`. Layout 2.0 is the per-doc / per-page layout above.

**Detection.** `loadManifest` reads the `version` of every manifest file present
(a missing field counts as `1.0`; `config.json` is the tier config's own schema
and is not part of the layout). It runs, in order, every step in `LAYOUT_STEPS`
(`[{from, to, migrate}]`) from the oldest major version found. A file at the
current version is never rewritten by migration. A file **newer** than the skill
writes stops everything with "upgrade the skill" — the loader never reads a
newer layout as an older one, and never downgrades. A layout-1 path claiming a
later version, or a per-doc file claiming 1.x, is refused as hand-edited.

**Migration 1 → 2.0** (automatic, on the first load by any script):

1. Group `items.json` entries by `source_doc` into `items/<doc-slug>.json`; group
   `import-index.json` entries by page tag into `import-index/<page>.json`.
   `updated_at` = the layout-1 `generated_at`; other top-level metadata
   (`hash_version`, `root`) is carried into each file.
2. Every queued ID in `pending-generation.json` (envelope or bare array) gets
   `pending_generation: true`. Queued IDs with no item entry are dropped and
   reported in the migration report — no reader ever acted on them.
3. Write every new file to `<file>.tmp`, read the tmps back and compare every
   carried item field for field and every index membership. Only then rename
   the tmps into place and delete the three layout-1 files.

It **refuses** (throws, non-zero exit, layout-1 files untouched, no tmps left)
when it would lose anything: an item with no `source_doc`, an ID landing in two
docs, an index entry with no page, a page tag that is not a safe file name, an
unreadable queue, or a read-back mismatch. Fix the file named in the error and
re-run. Running it again after success is a no-op.

**Mixed state** — a branch cut before the migration merges back a layout-1 file
next to 2.0 files. The same step folds it in, **per doc and per page**: the
layout-1 entries win only when the 2.0 file is missing or the layout-1
`generated_at` is strictly newer than that file's `updated_at`; otherwise the
2.0 file is kept. Queued IDs are unioned (flags are only ever added). Layout 1
has one repo-wide timestamp, so every doc in it looks equally new: a stale
branch that touched one doc but was regenerated after another doc's 2.0 file
will also win for that other doc. `verify-pipeline.js` fails in this state,
because the layout-1 file is still committed: commit `manifest/items/` and
`manifest/import-index/`, then `git rm` the layout-1 files it names.

`check-versions.js` also runs the migration (under the lock) and reports it as
`manifest_migration`; it exits 2 with the loader's message if migration refuses.

## Concurrency Safety

Multiple Claude sessions editing different verification docs simultaneously can both trigger `sync-tests.js`.

**Lockfile:** `manifest/.lock` — contains PID and timestamp. Every writer acquires it before loading and holds it until the save. Stale locks (>10 seconds or dead PID) are overridden.

**Atomic writes:** every file is written to `<file>.tmp`, then renamed.

**Disjoint writes:** `saveManifest` rewrites only the doc files whose items changed (and deletes a doc file whose last item was removed), so two edits to different docs never write the same file — in one working tree or across branches.

**Merging:** mark the per-doc files `-merge` in the consuming repo's `.gitattributes` so a conflicting merge leaves them for regeneration instead of producing a spliced JSON file:

```
tests/verification-playwright/manifest/items/*.json -merge
tests/verification-playwright/manifest/import-index/*.json -merge
```

On a conflict, take either side and re-run `sync-tests.js` for that doc (items) or rebuild that page's index (`--force-index`).

## The pending-generation queue

There is no queue file. An item is queued when its entry carries
`pending_generation: true`; `pendingIds(manifest)` lists them. `sync-tests.js`
sets the flag on new items and substantial unpinned changes; `link-specs.js`
sets it on every item it links.

**Draining:** after generating an item's test, delete `pending_generation` from
its entry in `items/<doc-slug>.json` (through `saveManifest` in scripts). An ID
also leaves the queue when its item is removed. Nothing else clears the flag.
