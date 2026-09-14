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

# Number of affected TAGS. Not the number of tests: one suite tag can pull in
# dozens. The real count is resolved below, once the grep pattern exists.
tag_count=$(echo "$affected_tags" | wc -w | tr -d ' ')

# Read maxTests and timeoutMs from config (defaults: 30 tests, 60s)
max_tests=$(node -e "try{const c=JSON.parse(require('fs').readFileSync('tests/verification-playwright/manifest/config.json','utf8'));console.log(c.tiers.gate.maxTests||30)}catch(e){console.log(30)}" 2>/dev/null || echo "30")
timeout_ms=$(node -e "try{const c=JSON.parse(require('fs').readFileSync('tests/verification-playwright/manifest/config.json','utf8'));console.log(c.tiers.gate.timeoutMs||60000)}catch(e){console.log(60000)}" 2>/dev/null || echo "60000")

# Cap handling: timeoutMs is the primary constraint, maxTests is the circuit breaker
if [ "$tag_count" -gt "$max_tests" ]; then
  if [ -t 1 ]; then
    echo "Warning: $tag_count tags affected (cap is $max_tests)."
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

# Depth filter. `tiers.gate.depths` was declared in config.json and read by
# nothing, so the commit gate ran every depth including `deep` — which is why a
# handful of affected tags expanded into a three-figure test count. Tags select
# WHAT changed; depth selects HOW MUCH of it is worth a commit's wall time.
read_excluded_depths() {
  node -e '
    const fs = require("node:fs");
    const cfg = JSON.parse(fs.readFileSync("tests/verification-playwright/manifest/config.json", "utf8"));
    const gate = cfg?.tiers?.gate?.depths ?? [];
    if (!gate.length) process.exit(0);
    // Every depth any tier names, minus the ones this tier wants.
    const all = new Set(
      Object.values(cfg?.tiers ?? {}).flatMap((t) => t?.depths ?? []),
    );
    const excluded = [...all].filter((d) => !gate.includes(d));
    process.stdout.write(excluded.map((d) => "@" + d).join("|"));
  ' 2>/dev/null || true
}
excluded_depths=$(read_excluded_depths)
grep_invert_args=()
if [ -n "$excluded_depths" ]; then
  grep_invert_args=(--grep-invert "$excluded_depths")
fi

# Browsers come from tiers.gate.browsers, the same way pre-push.sh reads its
# tier. This hook used to hardcode `--project chromium`, so adding a browser to
# the config changed the pre-push run and silently did nothing to the gate —
# the two hooks disagreed about what the gate tier means.
read_browsers() {
  node -e '
    const fs = require("node:fs");
    const cfg = JSON.parse(fs.readFileSync("tests/verification-playwright/manifest/config.json", "utf8"));
    const list = cfg?.tiers?.gate?.browsers ?? [];
    process.stdout.write(list.map((b) => b + "\n").join(""));
  ' 2>/dev/null || true
}

project_args=()
browser_names=""
while IFS= read -r browser; do
  [ -n "$browser" ] || continue
  project_args+=(--project "$browser")
  browser_names="${browser_names:+$browser_names, }$browser"
done < <(read_browsers)

# Server gate. Playwright's own webServer block has reuseExistingServer, but when
# it cannot bring the app up (a worktree whose node_modules is a symlink makes
# Turbopack refuse to start) every selected test fails on connection, producing a
# wall of red that says nothing about the commit. Probe first, start if down, and
# if it still will not come up, say why in one line and skip rather than reporting
# failures we did not actually test for.
APP_PORT="${VERIFICATION_APP_PORT:-3400}"
APP_URL="http://localhost:${APP_PORT}"

server_up() { curl -sf -o /dev/null --max-time 2 "$APP_URL" 2>/dev/null; }

if ! server_up; then
  if [ -L node_modules ]; then
    # Common in git worktrees that symlink node_modules to a primary checkout.
    # Some dev servers refuse to start against it (Next's Turbopack rejects a
    # node_modules symlink outright), so the gate can never pass here.
    echo "verification gate: skipped — node_modules is a symlink, so the dev server cannot start in this checkout."
    echo "  Install dependencies directly here (e.g. npm ci) to enable the gate."
    exit 0
  fi
  echo "verification gate: app not running on $APP_URL — starting it..."
  npm run dev >/tmp/verification-gate-dev.log 2>&1 &
  gate_server_pid=$!
  # Shut down only what we started; an already-running server is left alone.
  trap 'kill "$gate_server_pid" 2>/dev/null || true' EXIT
  for _ in $(seq 1 60); do
    server_up && break
    sleep 2
  done
  if ! server_up; then
    echo "verification gate: skipped — app did not come up within 120s (see /tmp/verification-gate-dev.log)."
    exit 0
  fi
  echo "verification gate: app is up."
fi

# Ask Playwright what this selection actually resolves to. Counting tags told
# the operator "2 tests" and then ran 26, and left maxTests comparing against a
# number that was never tests in the first place.
test_count=$(npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  ${project_args[@]+"${project_args[@]}"} \
  --grep "$grep_pattern" \
  ${grep_invert_args[@]+"${grep_invert_args[@]}"} \
  --list 2>/dev/null | grep -cE "^\s+\S+.*›" || echo "?")

if [ "$test_count" != "?" ] && [ "$test_count" -gt "$max_tests" ] 2>/dev/null; then
  echo "verification gate: $test_count tests selected from $tag_count tag(s) — over the $max_tests cap."
  echo "  Tags are suite-level, so a single changed file can pull in a whole suite."
  if [ -t 1 ]; then
    read -r -p "Run anyway? [y/N] " run_anyway
    case "$run_anyway" in y|Y) ;; *) echo "  skipped."; exit 0 ;; esac
  else
    echo "  skipped (non-interactive). Raise tiers.gate.maxTests or narrow the tags to run it."
    exit 0
  fi
fi

echo "Running $test_count verification test(s) from $tag_count tag(s) (gate tier: ${browser_names:-default})..."
test_exit=0
npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  ${project_args[@]+"${project_args[@]}"} \
  --grep "$grep_pattern" \
  ${grep_invert_args[@]+"${grep_invert_args[@]}"} \
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
