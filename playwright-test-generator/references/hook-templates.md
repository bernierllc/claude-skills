# Hook Templates Reference

Configuration templates for the verification-to-Playwright pipeline hooks.

## postToolUse Hook (.claude/settings.json)

Added to the project's `.claude/settings.json` during skill installation:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "if echo \"$CLAUDE_FILE_PATH\" | grep -q 'docs/verification/'; then node scripts/verification-playwright/sync-tests.js \"$CLAUDE_FILE_PATH\" 2>&1 | tail -5; fi"
          }
        ]
      }
    ]
  }
}
```

**Behavior:** Fires after every Edit or Write tool call. If the edited file is in `docs/verification/`, runs `sync-tests.js` to update the manifest and patch test files. Output is limited to 5 lines via `tail -5` to keep hook output concise.

**Merging:** This hook must be merged with existing PostToolUse hooks, not replace them. If the project already has hooks (e.g., TypeScript type checking), append this entry to the existing array.

## Orphan Marker Pre-Commit Check

A fast, deterministic integrity check that runs before the Playwright test runner gate. Guards against `@begin:ID` markers in test spec files that have no matching item in `docs/verification/`. This catches the failure mode where the generator invented IDs rather than reading them from `parseVerificationItems()`.

**Run:** `node scripts/verification-playwright/verify-pipeline.js --check-orphans`

**Scope:** Only fires when files in `docs/verification/` or `tests/verification-playwright/` are staged. Safe to run on every commit — exits in milliseconds when nothing in scope changed.

### If using the `pre-commit` tool (`.pre-commit-config.yaml`)

```yaml
- repo: local
  hooks:
    - id: verify-playwright-orphan-markers
      name: Check for orphan @begin:ID markers in Playwright tests
      entry: node scripts/verification-playwright/verify-pipeline.js --check-orphans
      language: system
      pass_filenames: false
      files: ^(docs/verification/|tests/verification-playwright/)
      stages: [pre-commit]
```

### If using husky

```bash
# In .husky/pre-commit (before the Playwright gate):
node scripts/verification-playwright/verify-pipeline.js --check-orphans
```

### If using lefthook

```yaml
pre-commit:
  commands:
    verify-playwright-orphan-markers:
      run: node scripts/verification-playwright/verify-pipeline.js --check-orphans
      glob: "{docs/verification/**,tests/verification-playwright/**}"
```

### If using raw `.git/hooks/pre-commit`

```bash
# Before the Playwright test runner section:
if git diff --staged --name-only | grep -qE '^(docs/verification/|tests/verification-playwright/)'; then
  node scripts/verification-playwright/verify-pipeline.js --check-orphans || exit 1
fi
```

**On failure:** The check prints each orphan marker with its file path. Fix: either add the missing item to the verification doc, or remove the `@begin`/`@end` marker from the spec file. The generator's pre-flight validation (step 7b in the skill checklist) should have prevented this — an orphan at the commit gate means the pre-flight was bypassed or skipped.

**Flow-scoped IDs:** `FLOW-<PREFIX>-NN` IDs in `/flows/` spec files are exempt from the orphan check if a corresponding flow doc exists in `docs/verification/flows/`. This allows flow tests to use IDs minted in their flow doc.

---

## Pre-Commit Hook (Git Hook)

Template at `templates/hooks/pre-commit.sh`. Installed into the project's git hooks via the project's hook framework (husky, lefthook, or raw `.git/hooks/`). **Runs after the orphan marker check** (see above) — the orphan check is faster and should fail first if markers are invalid.

### Behavior

1. Guard clause: exit 0 if pipeline not initialized
2. Read dry-run mode from config or env var
3. Get staged files from git
4. Map to affected test tags via `map-changes.js`
5. Cap at `maxTests` if threshold exceeded (interactive prompt if TTY, silent cap otherwise)
6. Run Playwright with `--grep` on affected tags, chromium only
7. In dry-run mode: report but exit 0

### Configuration read from manifest/config.json

- `tiers.gate.maxTests` — test count circuit breaker (default: 30)
- `tiers.gate.timeoutMs` — primary time constraint (default: 60000ms)
- `dry_run` — report-only mode (default: false)

### Environment variables

- `VERIFICATION_PIPELINE_DRY_RUN=1` — override dry-run mode regardless of config

## Pre-Push Hook (Git Hook)

Template at `templates/hooks/pre-push.sh`. Branch-aware tiered test execution.

### Behavior

1. Guard clause: exit 0 if pipeline not initialized
2. Parse target branch from stdin refspecs (reliable) with `@{push}` fallback
3. Select tier via `select-tier.js` based on target branch
4. Execute:
   - **thorough:** 3 browsers, all depths, changes-only (`--grep`)
   - **full:** all browsers, all tests (no `--grep`)
   - **no match:** exit 0 (feature branch push, skip)

### Branch-to-tier mapping (from config.json)

| Branch pattern | Tier | Default |
|---|---|---|
| `main`, `production` | full | All browsers + mobile, all tests |
| `staging`, `develop` | thorough | 3 desktop browsers, changed tests only |
| `*` | gate | Handled by pre-commit, not pre-push |

## Hook Management Strategy

### If husky is present

Detected by `.husky/` directory or `husky` in devDependencies. Add verification-playwright as a sourced script:

```bash
# In .husky/pre-commit (append):
source scripts/verification-playwright/hooks/pre-commit.sh
```

Uninstall: remove the source line.

### If lefthook/lint-staged is present

Add entries to the existing config file:

```yaml
# In .lefthookrc.yml:
pre-commit:
  commands:
    verification-playwright:
      run: bash scripts/verification-playwright/hooks/pre-commit.sh
```

Uninstall: remove the entries.

### If no hook framework

Install directly in `.git/hooks/` with comment markers:

```bash
# In .git/hooks/pre-commit:
# BEGIN verification-playwright
source scripts/verification-playwright/hooks/pre-commit.sh
# END verification-playwright
```

Uninstall: remove only the marked section. Content outside the markers is preserved.

## Dry-Run Mode

For the first weeks of adoption. Enable via:

1. Set `"dry_run": true` in `manifest/config.json`
2. Or set `VERIFICATION_PIPELINE_DRY_RUN=1` environment variable

In dry-run mode:
- Pre-commit and pre-push hooks run tests but always exit 0
- Output prefixed with `[DRY RUN]`
- Commit/push is never blocked

Disable by setting `dry_run: false` in config or removing the env var.

## Coordinator / Parallel-Agent Post-Merge Gate

When multiple parallel agents generate tests (e.g., one agent per page doc), they work in isolated worktrees. Worktree merge is last-write-wins for shared files — `items.json`, `import-index.json`, and `pending-generation.json` will reflect only the last agent's state unless a coordinator rebuilds them.

**After merging parallel agent work, before committing:**

```bash
# 1. Run the full pipeline health check
node scripts/verification-playwright/verify-pipeline.js

# 2. Run the orphan marker check
node scripts/verification-playwright/verify-pipeline.js --check-orphans

# 3. If either check fails, DO NOT commit — fix the issues first
```

This is a **mandatory gate**, not optional. The failure mode: 5 parallel agents each write `items.json` with their page's items only; the final merge state has only the last agent's page items; all other pages show `test-missing` on the next `check-versions.js` run; if committed, the gap is invisible until someone runs `check-versions.js`.

**Coordinator agent responsibilities:**
- Own `items.json`, `import-index.json`, and `pending-generation.json` exclusively — worker agents must NOT write these files
- Cherry-pick only each agent's spec files, metadata docs, and test helpers — not shared manifest files
- Run `check-versions.js` and rebuild the index after all worker branches are merged
- Run `verify-pipeline.js` before the final commit

**Absolute path prevention:**
All paths written to manifest files must be project-relative (e.g., `tests/verification-playwright/pages/event-detail.spec.ts`), never absolute (e.g., `/Users/matt/.claude/worktrees/agent-abc123/tests/...`). Absolute paths that include worktree names break on any machine other than where they were written, and permanently after worktree cleanup. If `verify-pipeline.js` reports missing source or spec files that look like worktree paths, rebuild the manifest from scratch with `--force-index` and `--force-items`.
