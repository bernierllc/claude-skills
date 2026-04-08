#!/usr/bin/env bash
# Verification-Playwright Pipeline: Pre-commit gate
# Runs affected Playwright tests before allowing commit
# Part of the playwright-test-generator skill
#
# BEGIN verification-playwright

set -euo pipefail

# Guard: skip if pipeline not initialized
if [ ! -f "scripts/verification-playwright/map-changes.js" ]; then
  exit 0
fi

# Check for dry-run mode (env var or config)
dry_run="${VERIFICATION_PIPELINE_DRY_RUN:-}"
if [ -z "$dry_run" ]; then
  dry_run=$(node -e "try{const c=JSON.parse(require('fs').readFileSync('tests/verification-playwright/manifest/config.json','utf8'));console.log(c.dry_run||false)}catch(e){console.log(false)}" 2>/dev/null || echo "false")
fi

# Get staged files
staged_files=$(git diff --staged --name-only)
if [ -z "$staged_files" ]; then
  exit 0
fi

# Map to affected test tags
affected_tags=$(echo "$staged_files" | xargs node scripts/verification-playwright/map-changes.js 2>/dev/null || echo "")
if [ -z "$affected_tags" ]; then
  exit 0
fi

# Count affected tests
test_count=$(echo "$affected_tags" | wc -w | tr -d ' ')

# Read maxTests and timeoutMs from config (defaults: 30 tests, 60s)
max_tests=$(node -e "try{const c=JSON.parse(require('fs').readFileSync('tests/verification-playwright/manifest/config.json','utf8'));console.log(c.tiers.gate.maxTests||30)}catch(e){console.log(30)}" 2>/dev/null || echo "30")
timeout_ms=$(node -e "try{const c=JSON.parse(require('fs').readFileSync('tests/verification-playwright/manifest/config.json','utf8'));console.log(c.tiers.gate.timeoutMs||60000)}catch(e){console.log(60000)}" 2>/dev/null || echo "60000")

# Cap handling: timeoutMs is the primary constraint, maxTests is the circuit breaker
if [ "$test_count" -gt "$max_tests" ]; then
  if [ -t 1 ]; then
    echo "Warning: $test_count tests affected (cap is $max_tests)."
    read -r -p "Run [a]ll / [c]apped at $max_tests / [s]kip? " choice
    case "$choice" in
      s|S) exit 0 ;;
      c|C) affected_tags=$(echo "$affected_tags" | tr ' ' '\n' | head -n "$max_tests" | tr '\n' ' ') ;;
      *) ;; # run all
    esac
  else
    # Non-interactive: run capped at maxTests
    affected_tags=$(echo "$affected_tags" | tr ' ' '\n' | head -n "$max_tests" | tr '\n' ' ')
  fi
fi

# Build grep pattern from affected tags
grep_pattern=$(echo "$affected_tags" | tr ' ' '|')

# Run Playwright (chromium only for gate tier)
echo "Running $test_count verification tests (gate tier, chromium)..."
test_exit=0
npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  --project chromium \
  --grep "$grep_pattern" \
  --timeout "$timeout_ms" || test_exit=$?

# Dry-run: report but don't block
if [ "$dry_run" = "true" ]; then
  if [ $test_exit -eq 0 ]; then
    echo "[DRY RUN] Tests passed. Commit would have been allowed."
  else
    echo "[DRY RUN] Tests failed. Commit would have been blocked."
  fi
  exit 0
fi

exit $test_exit

# END verification-playwright
