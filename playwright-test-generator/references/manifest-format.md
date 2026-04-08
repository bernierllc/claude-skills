# Manifest Format Reference

The manifest is split into three independent files in `tests/verification-playwright/manifest/`. Each can fail and be rebuilt independently.

## manifest/items.json

Tracks the mapping between verification items and generated Playwright tests.

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T18:00:00Z",
  "items": {
    "EVT-FRM-TKT-03": {
      "source_doc": "docs/verification/pages/admin-event-form.md",
      "spec_file": "tests/verification-playwright/pages/admin-event-form.spec.ts",
      "content_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
      "generated_hash": "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5",
      "depth": "standard",
      "status": "active",
      "pinned": false,
      "testids_required": ["ticket-price-min", "ticket-price-max", "submit-event", "ticket-price-error"],
      "testids_missing": ["ticket-price-error"]
    }
  }
}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `source_doc` | string | Path to the verification doc this item came from |
| `spec_file` | string | Path to the generated .spec.ts file |
| `content_hash` | string | SHA-256 of the normalized verification item text (see hash normalization) |
| `generated_hash` | string | SHA-256 of the generated test code between `@begin`/`@end` markers |
| `depth` | string | `smoke`, `standard`, or `deep` |
| `status` | string | `active` (test runs), `skipped` (missing testids), `pinned` (manually edited) |
| `pinned` | boolean | When `true`, skill will not overwrite this test |
| `testids_required` | string[] | All data-testid values this test needs |
| `testids_missing` | string[] | testids not found in the codebase |

### Rebuild

`--force-items` rebuilds this file by re-scanning all verification docs and regenerating all tests. Pinned tests are overwritten only with `--force`.

## manifest/import-index.json

Maps source files to the verification page docs they affect. Used by `map-changes.js` for change-scoped test execution.

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T18:00:00Z",
  "entries": {
    "admin/static/admin/src/components/EventForm.tsx": ["admin-event-form"],
    "admin/static/admin/src/components/ArtistSection.tsx": ["admin-event-form", "admin-artist-form"],
    "admin/app/routers/events.py": ["admin-event-form", "admin-event-detail", "admin-event-list"]
  }
}
```

### Construction

Built during skill invocation (not by `sync-tests.js`):

1. **From verification docs outward:** each page doc covers specific routes (listed in its header). Trace routes to component files via the project's routing structure.
2. **From components inward:** for each component, follow its import tree (1 level deep) to capture shared components, hooks, utilities.
3. **From API routes:** verification items referencing API behavior are mapped to backend route handlers.

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

## Concurrency Safety

Multiple Claude sessions editing different verification docs simultaneously can both trigger `sync-tests.js`.

**Lockfile:** `manifest/.lock` — contains PID and timestamp. `sync-tests.js` acquires before reading/writing any manifest file. Stale locks (>10 seconds or dead PID) are overridden.

**Atomic writes:** All manifest updates write to `<file>.tmp`, then rename atomically.

**Queue deduplication:** The skill deduplicates item IDs in `pending-generation.json` before processing.
