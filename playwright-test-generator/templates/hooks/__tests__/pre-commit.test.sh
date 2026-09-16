#!/usr/bin/env bash
# Harness for the pre-commit verification gate.
#
# The hook no longer starts or manages a dev server — Playwright's webServer
# does that, and the foreign-server guard lives in tests/e2e/global-setup.ts so
# it covers every run. What is left here is selection: which tests this change
# implies, at gate depth, honestly counted. These cases cover that.
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
  local dir="$1" http="$2" test_route_http="$3" list_out="$4"
  mkdir -p "$dir"

  cat > "$dir/curl" <<EOF
#!/usr/bin/env bash
# Distinguish the liveness probe from the /api/test/* trust probe by URL.
for a in "\$@"; do
  case "\$a" in
    */api/test/*) printf '%s' "$test_route_http"; exit 0 ;;
  esac
done
# -w '%{http_code}' callers want a body; -o /dev/null callers ignore it.
printf '%s' "$http"
[ "$http" = "000" ] && exit 7
exit 0
EOF

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
echo "playwright run (stub)"
exit 0
EOF

  chmod +x "$dir/curl" "$dir/npx"
}

# $1 name, $2 expected exit, $3 http, $4 test-route http, $5 --list output,
# $6 substring the output MUST contain ("" to skip), $7.. extra env
#
# The substring matters more than the exit code for the safety cases: a hook
# that wrongly starts an unconfigured server also exits 0. Only the message
# proves it refused.
check() {
  local name="$1" want="$2" http="$3" troute="$4" list="$5" expect="$6"; shift 6
  local stubs; stubs="$(mktemp -d)"
  make_stubs "$stubs" "$http" "$troute" "$list"

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
check "no staged files"            0 "200" "200" "Total: 3 tests in 1 file" ""

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

cp "$REPO_ROOT/$MAPPED_FILE" /tmp/pre-commit-test-fixture.bak
printf '\n// pre-commit harness fixture\n' >> "$REPO_ROOT/$MAPPED_FILE"
git -C "$REPO_ROOT" add "$MAPPED_FILE" >/dev/null 2>&1

restore_fixture() {
  cp /tmp/pre-commit-test-fixture.bak "$REPO_ROOT/$MAPPED_FILE"
  rm -f /tmp/pre-commit-test-fixture.bak "$GIT_INDEX_FILE"
}
trap restore_fixture EXIT

# Sanity: the fixture must actually produce tags, or everything below is vacuous.
if ! git -C "$REPO_ROOT" diff --staged --name-only \
     | xargs node "$REPO_ROOT/scripts/verification-playwright/map-changes.js" 2>/dev/null \
     | grep -q '@'; then
  echo "  FAIL harness fixture resolves to no tags — the cases below would prove nothing"
  exit 1
fi

check "empty selection at depth"   0 "200" "200" "" "no gate-depth tests"
check "over the cap, no tty"       0 "200" "200" "Total: 9999 tests in 1 file" "over the"
check "normal run"                 0 "200" "200" "Total: 3 tests in 1 file" "Running 3"


printf '\n%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
