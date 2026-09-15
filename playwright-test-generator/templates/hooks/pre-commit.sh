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

# Any HTTP response means something is serving. `curl -f` would call a 401/403
# root — or a 500 while Next compiles the first request — "down", and the hook
# would start a second server on an occupied port, time out, and skip silently.
server_up() { curl -s -o /dev/null --max-time 2 "$APP_URL" >/dev/null 2>&1; }

if ! server_up; then
  if [ -L node_modules ]; then
    echo "verification gate: skipped — node_modules is a symlink, so the dev server cannot start here."
    echo "  Install deps directly in this worktree to enable the gate: rm node_modules && npm ci"
    exit 0
  fi

  # Same env Playwright's webServer uses. reuseExistingServer means Playwright
  # adopts whatever is already listening, so a server started here without
  # SENDGRID_API_BASE_URL would point the suite at the real SendGrid account.
  # Optional tests/verification-playwright/dev-server-env.json: the same env the
  # Playwright config passes to its webServer. Keep them in one file and have
  # the config import it — otherwise the hook starts a differently-configured
  # server and reuseExistingServer makes the suite adopt it. A suite that points
  # at a mock API will silently reach the real one.
  gate_env=()
  if [ -f tests/verification-playwright/dev-server-env.json ]; then
    while IFS= read -r kv; do
      [ -n "$kv" ] && gate_env+=("$kv")
    done < <(node -e '
      const e = require("./tests/verification-playwright/dev-server-env.json");
      for (const [k, v] of Object.entries(e)) process.stdout.write(k + "=" + v + "\n");
    ' 2>/dev/null || true)
  fi

  gate_log=$(mktemp -t verification-gate-dev)
  echo "verification gate: app not running on $APP_URL — starting it..."
  # Own process group: `npm run dev` forks `next dev`, which forks Turbopack
  # workers. Killing only npm orphans the server on the port, which poisons
  # every later run.
  set -m
  env ${gate_env[@]+"${gate_env[@]}"} npm run dev >"$gate_log" 2>&1 &
  gate_server_pid=$!
  set +m
  trap 'kill -TERM -"$gate_server_pid" 2>/dev/null || true' EXIT INT TERM

  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    server_up && break
    sleep 2
  done
  if ! server_up; then
    echo "verification gate: skipped — app did not come up within 120s (see $gate_log)."
    exit 0
  fi
  echo "verification gate: app is up."
fi

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
  ${grep_invert_args[@]+"${grep_invert_args[@]}"} \
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
    read -r -p "  Run anyway? [y/N] " run_anyway </dev/tty || run_anyway=""
    case "$run_anyway" in y|Y) ;; *) echo "  skipped."; exit 0 ;; esac
  else
    echo "  skipped (non-interactive). Raise tiers.gate.maxTests or narrow the tags to run it."
    exit 0
  fi
fi

if [ "$test_count" = "?" ]; then
  echo "Running verification tests (count unavailable) from $tag_count tag(s) (gate tier: ${browser_names:-default})..."
else
  echo "Running $test_count verification test(s) from $tag_count tag(s) (gate tier: ${browser_names:-default})..."
fi
test_exit=0
npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  ${project_args[@]+"${project_args[@]}"} \
  --grep "$grep_pattern" \
  ${grep_invert_args[@]+"${grep_invert_args[@]}"} \
  --pass-with-no-tests \
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
