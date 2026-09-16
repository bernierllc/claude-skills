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

# Build grep pattern from affected tags
# Each tag is followed by whitespace or end-of-title: `@onboarding` must not
# also select `@onboarding-domains` and thirteen other sibling suites, which
# blew a one-file change past the cap and — non-interactively — skipped the
# gate for the tests that were actually affected.
grep_pattern="(?:$(echo "$affected_tags" | tr ' ' '|'))(?:\\s|$)"

# Browsers come from tiers.gate.browsers, the same way pre-push.sh reads its
# tier. Hardcoding --project chromium here once meant adding a browser to the
# config changed pre-push and silently did nothing to the gate. (This block was
# lost in a simplification and project_args expanded empty; restored.)
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

# Depth filter, as a POSITIVE allowlist.
#
# `tiers.gate.depths` was declared in config.json and read by nothing, so the
# commit gate ran every depth including `deep`. The first fix excluded depths
# that OTHER tiers named — which silently let through any depth no tier
# declares. This manifest has four `error` items and one `edge`; none were in a
# tier list, so none were ever excluded.
#
# A gate allows, it does not deny: the selection must match a gate depth AND an
# affected suite tag. Anything wearing an unrecognised depth is out by default,
# which is the safe direction for a check that runs on every commit.
read_gate_depths() {
  node -e '
    const fs = require("node:fs");
    const cfg = JSON.parse(fs.readFileSync("tests/verification-playwright/manifest/config.json", "utf8"));
    process.stdout.write((cfg?.tiers?.gate?.depths ?? []).join("|"));
  ' 2>/dev/null || true
}
gate_depths=$(read_gate_depths)

if [ -n "$gate_depths" ]; then
  # Two lookaheads against the test title: one gate depth, one affected tag.
  # affected_tags already carry their "@", so only the depths need one added.
  grep_pattern="(?=.*@(?:${gate_depths})(?:\\s|$))(?=.*${grep_pattern})"
fi

# Starting the app is Playwright's job: its webServer block has the env and the
# start-if-down logic, and duplicating that here is what produced six review
# findings in two rounds. It never adopts a server it did not start (the config
# sets reuseExistingServer:false, because an unauthenticated probe cannot tell
# a mock-configured server from one pointed at api.sendgrid.com).
#
# Two things Playwright cannot do for us:
#
# 1. Notice that this checkout could never serve the app. A worktree that
#    symlinks node_modules makes Turbopack refuse to start, so every selected
#    test would fail on connection and the operator would learn nothing from a
#    screen of red.
if [ -L node_modules ]; then
  echo "verification gate: skipped — node_modules is a symlink, so the dev server cannot start here."
  echo "  Install deps directly in this worktree to enable the gate: rm node_modules && npm ci"
  exit 0
fi

# 2. Pick a port. Another session usually holds 3400, and with reuse off a
#    busy port ends the run before a single test — a block unrelated to the
#    change. The config reads VERIFICATION_PORT; choose the first free one.
#    The mock SendGrid that globalSetup starts has the same problem on 39876,
#    so it gets the same treatment (MOCK_SENDGRID_PORT).
pick_port() {
  local from="$1" to="$2" p
  command -v lsof >/dev/null 2>&1 || { echo "$from"; return; }
  for p in $(seq "$from" "$to"); do
    lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || { echo "$p"; return; }
  done
  echo ""
}
VERIFICATION_PORT=$(pick_port 3400 3420)
MOCK_SENDGRID_PORT=$(pick_port 39876 39896)
if [ -z "$VERIFICATION_PORT" ] || [ -z "$MOCK_SENDGRID_PORT" ]; then
  echo "verification gate: skipped — no free port for the dev server (3400-3420) or the SendGrid mock (39876-39896)."
  exit 0
fi
export VERIFICATION_PORT MOCK_SENDGRID_PORT

# Ask Playwright what this selection actually resolves to. `|| true` is load
# bearing: --list exits 1 on an empty selection, and `var=$(cmd)` adopts that
# status, so set -e would kill the hook before the zero-check below. Counting tags told
# the operator "2 tests" and then ran 26, and left maxTests comparing against a
# number that was never tests in the first place. Parse the authoritative
# "Total: N tests" line: `grep -c` prints 0 AND exits 1 on no match, so a
# `|| echo "?"` fallback would make the count the two-line string "0\n?".
test_count=$(npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  ${project_args[@]+"${project_args[@]}"} \
  --grep "$grep_pattern" \
  --list 2>/dev/null | sed -n 's/^Total: \([0-9][0-9]*\) test.*/\1/p' | tail -1 || true)
[ -n "${test_count:-}" ] || test_count="?"

# An empty selection is normal once depth filtering is on — a change whose only
# affected tests are @deep resolves to nothing at gate depth. Playwright exits 1
# on "no tests found", which would block the commit for no reason.
if [ "$test_count" = "0" ]; then
  echo "verification gate: no gate-depth tests for these changes — skipping."
  exit 0
fi

if [ "$test_count" != "?" ] && [ "$test_count" -gt "$max_tests" ] 2>/dev/null; then
  echo "verification gate: $test_count tests selected from $tag_count tag(s) — over the $max_tests cap."
  echo "  Tags are suite-level, so a single changed file can pull in a whole suite."
  # stdin is /dev/null under `git commit`, and stdout IS a tty — so testing
  # `-t 1` and calling `read` means EOF, a non-zero status, and `set -e` killing
  # the hook. Blocking a commit is the one thing this gate must never do.
  if [ -r /dev/tty ] && [ -t 1 ]; then
    # -t: a pty-wrapped commit (script, tmux, CI with a tty) would otherwise
    # hang forever, which costs exactly as much as blocking.
    read -t 30 -r -p "  Run anyway? [y/N] " run_anyway </dev/tty || run_anyway=""
    case "$run_anyway" in y|Y) ;; *) echo "  skipped."; exit 0 ;; esac
  else
    echo "  skipped (non-interactive). Raise tiers.gate.maxTests or narrow the tags to run it."
    exit 0
  fi
fi

if [ "$test_count" = "?" ]; then
  echo "Running verification tests (count unavailable) from $tag_count tag(s) (gate tier: ${browser_names:-default}, port $VERIFICATION_PORT, mock $MOCK_SENDGRID_PORT)..."
else
  echo "Running $test_count verification test(s) from $tag_count tag(s) (gate tier: ${browser_names:-default}, port $VERIFICATION_PORT, mock $MOCK_SENDGRID_PORT)..."
fi
test_exit=0
npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  ${project_args[@]+"${project_args[@]}"} \
  --grep "$grep_pattern" \
  --timeout "$timeout_ms" || test_exit=$?

# Ceiling, accepted knowingly: a Playwright failure that is NOT a test failure —
# a missing browser binary, a config error, a port taken between the check
# above and Playwright binding it — also exits non-zero and blocks. Distinguishing those from a real failure means
# parsing reporter output, which is its own source of false confidence. The
# environmental cases this gate can name (no server, no deps, no env, empty
# selection, over cap) are all handled above.
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
