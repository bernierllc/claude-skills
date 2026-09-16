#!/usr/bin/env bash
# Harness for the pre-commit verification gate.
#
# The hook no longer starts or manages a dev server — Playwright's webServer
# does that, and the foreign-server guard is reuseExistingServer:false in
# tests/verification-playwright/playwright.config.ts, so it covers every run.
# What is left here is selection and environment: which tests this change
# implies, at gate depth, honestly counted, on a port nobody else holds.
#
# Why this exists: two review rounds found six Critical issues in this hook and
# every one was a `set -euo pipefail` interaction — `read` hitting EOF, `grep -c`
# exiting 1 on zero matches, a command substitution adopting a non-zero status.
# None were visible by reading; all are visible in one run. The gate's whole
# promise is "never block a commit for an environmental reason", and that is a
# testable claim.
#
# Runs the real script with `npx` and `curl` stubbed on PATH, under the stdin git
# actually gives a hook (/dev/null). No framework.
#
# Usage: bash scripts/verification-playwright/hooks/__tests__/pre-commit.test.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HOOK="$REPO_ROOT/scripts/verification-playwright/hooks/pre-commit.sh"
pass=0
fail=0

# A sandbox with stubbed binaries. Each case declares how the fakes behave.
make_stubs() {
  local dir="$1" list_out="$2"
  mkdir -p "$dir"

  cat > "$dir/npx" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do
  if [ "\$a" = "--list" ]; then
    if [ -z "$list_out" ]; then
      # Real Playwright still prints a Total line, then exits 1.
      printf 'Total: 0 tests in 0 files\n'
      exit 1
    fi
    printf '%s\n' "$list_out"
    exit 0
  fi
done
# Echo the arguments so a case can assert what reached Playwright.
echo "playwright run (stub) \$*"
exit "\${STUB_RUN_EXIT:-0}"
EOF

  # lsof: claim STUB_BUSY_PORTS (colon-separated) are listening, nothing else.
  cat > "$dir/lsof" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    -iTCP:*) port="${a#-iTCP:}" ;;
  esac
done
case ":${STUB_BUSY_PORTS:-}:" in
  *":${port}:"*) exit 0 ;;
  *) exit 1 ;;
esac
EOF

  chmod +x "$dir/npx" "$dir/lsof"
}

# $1 name, $2 expected exit, $3 --list output,
# $4 substring the output MUST contain ("" to skip), $5.. extra env
#
# The substring matters more than the exit code for the safety cases: a hook
# that wrongly starts an unconfigured server also exits 0. Only the message
# proves it refused.
check() {
  local name="$1" want="$2" list="$3" expect="$4"; shift 4
  local stubs; stubs="$(mktemp -d)"
  make_stubs "$stubs" "$list"

  local out status
  out=$(cd "$REPO_ROOT" && PATH="$stubs:$PATH" env "$@" bash "$HOOK" </dev/null 2>&1)
  status=$?
  rm -rf "$stubs"

  if [ -n "$expect" ] && [[ "$out" != *"$expect"* ]]; then
    printf '  FAIL %s — output missing %q\n' "$name" "$expect"
    printf '%s\n' "$out" | sed 's/^/         /' | head -6
    fail=$((fail + 1))
  elif [ "$status" -eq "$want" ]; then
    printf '  ok   %s (exit %s)\n' "$name" "$status"
    pass=$((pass + 1))
  else
    printf '  FAIL %s — wanted exit %s, got %s\n' "$name" "$want" "$status"
    printf '%s\n' "$out" | sed 's/^/         /' | head -6
    fail=$((fail + 1))
  fi
}

echo "pre-commit gate: environmental conditions must never block a commit"

# Nothing staged is the commonest case of all and must be instant and silent.
check "no staged files"            0 "Total: 3 tests in 1 file" ""

# Stage a file map-changes.js actually resolves to tags. Without this the hook
# exits at "no affected tags" and every case below passes without exercising a
# single line of the gate — which is how the first draft of this harness scored
# 7/7 while testing nothing.
# A file map-changes.js resolves to at least one tag. Consumers set this to a
# path in their own tree; the default is the first file the import index knows.
MAPPED_FILE="${PRE_COMMIT_HARNESS_FIXTURE:-$(node -e '
  const idx = require(process.cwd() + "/tests/verification-playwright/manifest/import-index.json");
  const files = Object.keys(idx.files ?? idx);
  process.stdout.write(files[0] ?? "");
' 2>/dev/null)}"
[ -n "$MAPPED_FILE" ] || { echo "  FAIL no fixture file — set PRE_COMMIT_HARNESS_FIXTURE to a mapped path"; exit 1; }

# Stage into a THROWAWAY index, never the real one. Staging the fixture in the
# repo index and then unstaging it afterwards would silently discard whatever
# the developer already had staged for that file — the harness would quietly
# destroy work it was never asked to touch.
#
# GIT_INDEX_FILE redirects every git read and write below, including the hook's
# own `git diff --staged`, so the real index is never opened.
export GIT_INDEX_FILE
# Portable template: GNU mktemp requires at least three X's and treats -t as
# deprecated, so `-t name` fails there and leaves GIT_INDEX_FILE empty — after
# which `git diff --staged` reads an empty index as "every file deleted".
GIT_INDEX_FILE=$(mktemp "${TMPDIR:-/tmp}/pre-commit-harness-index.XXXXXX")
[ -n "$GIT_INDEX_FILE" ] || { echo "  FAIL could not create a temp index"; exit 1; }
rm -f "$GIT_INDEX_FILE"                   # git wants to create it itself
git -C "$REPO_ROOT" read-tree HEAD        # seed it from HEAD

# Stage the fixture as a blob straight into that index. The working tree is
# never written: an earlier version appended to the real file and restored it
# on EXIT, and a killed run left a `// probe` line that reached a commit.
blob=$(printf '// pre-commit harness fixture\n' | git -C "$REPO_ROOT" hash-object -w --stdin)
git -C "$REPO_ROOT" update-index --add --cacheinfo "100644,$blob,$MAPPED_FILE"
trap 'rm -f "$GIT_INDEX_FILE"' EXIT

# Sanity: the fixture must actually produce tags, or everything below is vacuous.
if ! git -C "$REPO_ROOT" diff --staged --name-only \
     | xargs node "$REPO_ROOT/scripts/verification-playwright/map-changes.js" 2>/dev/null \
     | grep -q '@'; then
  echo "  FAIL harness fixture resolves to no tags — the cases below would prove nothing"
  exit 1
fi

check "empty selection at depth"   0 "" "no gate-depth tests"
check "over the cap, no tty"       0 "Total: 9999 tests in 1 file" "over the"
check "normal run"                 0 "Total: 3 tests in 1 file" "Running 3"
check "browsers reach playwright"  0 "Total: 3 tests in 1 file" "--project chromium"
check "port 3400 held elsewhere"   0 "Total: 3 tests in 1 file" "port 3401" STUB_BUSY_PORTS=3400
check "no free port"               0 "Total: 3 tests in 1 file" "no free port" STUB_BUSY_PORTS=$(seq -s: 3400 3420)
check "dry run reports a failure"  0 "Total: 3 tests in 1 file" "[DRY RUN] Tests failed" STUB_RUN_EXIT=1 VERIFICATION_PIPELINE_DRY_RUN=true
check "failure blocks when live"   1 "Total: 3 tests in 1 file" "" STUB_RUN_EXIT=1 VERIFICATION_PIPELINE_DRY_RUN=false

# A checkout whose node_modules is a symlink can never serve the app. Run the
# hook from a sandbox that looks like such a worktree: every top-level entry is
# a symlink to the real one (node_modules included), git is pointed back here.
sandbox=$(mktemp -d)
for entry in "$REPO_ROOT"/* "$REPO_ROOT"/.[!.]*; do
  [ -e "$entry" ] && ln -s "$entry" "$sandbox/$(basename "$entry")"
done
stubs="$(mktemp -d)"; make_stubs "$stubs" "Total: 3 tests in 1 file"
out=$(cd "$sandbox" && GIT_DIR="$(git -C "$REPO_ROOT" rev-parse --absolute-git-dir)" GIT_WORK_TREE="$sandbox" \
      PATH="$stubs:$PATH" bash "$HOOK" </dev/null 2>&1); status=$?
rm -rf "$stubs" "$sandbox"
if [ "$status" -eq 0 ] && [[ "$out" == *"node_modules is a symlink"* ]]; then
  echo "  ok   symlinked node_modules skips (exit 0)"; pass=$((pass + 1))
else
  echo "  FAIL symlinked node_modules skips — exit $status"; printf '%s\n' "$out" | sed 's/^/         /' | head -6; fail=$((fail + 1))
fi


printf '\n%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
