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

## Pre-Commit Hook (Git Hook)

Template at `templates/hooks/pre-commit.sh`. Installed into the project's git hooks via the project's hook framework (husky, lefthook, or raw `.git/hooks/`).

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
