#!/usr/bin/env bash
# preflight.sh — Verify the project is ready for this skill before it runs.
#
# Two checks, in order:
#   1. Verification docs exist at docs/verification/pages/*.md
#   2. Playwright is installed in the target project
#
# Contract: exit 0 silently on success. Exit 1 with a halt message on stdout
# on failure. The agent prints the message verbatim and stops — no recovery,
# no retry, no fallback.
#
# The Playwright check is cached (mtime-based) so repeated runs cost nothing:
# if the project's dependency manifest(s) have not changed since the last
# successful check, the cached result is trusted and the check is skipped.
#
# Run from any working directory; pass --root to point at a different repo.

set -euo pipefail

SKILL_NAME="playwright-test-generator"
ROOT="."

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --root=*)
      ROOT="${1#--root=}"
      shift
      ;;
    *)
      printf 'preflight: unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Check 1 — verification docs exist
# ---------------------------------------------------------------------------

PAGES_DIR="$ROOT/docs/verification/pages"

if [ ! -d "$PAGES_DIR" ]; then
  cat <<EOF
ERROR: $SKILL_NAME requires verification docs at docs/verification/pages/

This skill depends on output from the verification-writer skill, which has
not been run in this repo yet (or the docs were deleted).

To resolve:
  1. If verification-writer is installed, run it now to generate the docs.
  2. If it is not installed, install it via AEC:
     https://github.com/bernierllc/agents-environment-config
  3. Or install manually from:
     https://github.com/bernierllc/claude-skills

After verification docs exist, re-run $SKILL_NAME.
EOF
  exit 1
fi

# Count *.md files in pages/, excluding any dotfiles.
# Using find for portability across macOS/Linux without Bash 4 globstar.
PAGE_COUNT=$(find "$PAGES_DIR" -maxdepth 1 -type f -name '*.md' ! -name '.*' 2>/dev/null | wc -l | tr -d ' ')

if [ "$PAGE_COUNT" -eq 0 ]; then
  cat <<EOF
ERROR: $SKILL_NAME requires at least one verification page doc

The directory docs/verification/pages/ exists but contains no .md files.
This usually means verification-writer started a scaffold but did not finish
generating page docs.

To resolve: run verification-writer to generate page docs, then re-run $SKILL_NAME.
EOF
  exit 1
fi

# ---------------------------------------------------------------------------
# Check 2 — Playwright is installed (mtime-cached)
# ---------------------------------------------------------------------------

CACHE_FILE="$ROOT/.playwright-test-generator.cache"

# Portable file-mtime in epoch seconds (BSD/macOS stat vs GNU/Linux stat).
file_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# Build a signature of every dependency manifest / lockfile that exists in the
# project root. The signature is "<path>:<mtime>" pairs joined by newlines.
# If this matches the cached signature, nothing dependency-related has changed
# and the previous "ok" result is still valid.
MANIFEST_CANDIDATES="
package.json
package-lock.json
pnpm-lock.yaml
yarn.lock
node_modules/.package-lock.json
pyproject.toml
requirements.txt
poetry.lock
pom.xml
build.gradle
build.gradle.kts
"

build_signature() {
  local sig="" f
  for f in $MANIFEST_CANDIDATES; do
    if [ -f "$ROOT/$f" ]; then
      sig="${sig}${f}:$(file_mtime "$ROOT/$f")
"
    fi
  done
  # Include any *.csproj (one level deep) for .NET projects.
  local csproj
  while IFS= read -r csproj; do
    [ -n "$csproj" ] || continue
    sig="${sig}${csproj#"$ROOT/"}:$(file_mtime "$csproj")
"
  done <<EOF2
$(find "$ROOT" -maxdepth 2 -type f -name '*.csproj' 2>/dev/null)
EOF2
  printf '%s' "$sig"
}

CURRENT_SIG="$(build_signature)"

# Cache hit: dependency manifests are byte-for-byte unchanged since the last
# successful check. Trust it and exit silently — zero further work.
if [ -f "$CACHE_FILE" ]; then
  CACHED_SIG="$(cat "$CACHE_FILE" 2>/dev/null || true)"
  if [ -n "$CACHED_SIG" ] && [ "$CACHED_SIG" = "ok
$CURRENT_SIG" ]; then
    exit 0
  fi
fi

# Cache miss — run the real check.
#
# This skill emits TypeScript Playwright specs (.spec.ts, playwright.config.ts)
# and Node-based tooling, so a Node project with @playwright/test is required.
# Other ecosystems (Python/Java/.NET) are detected only to give a tailored
# message — the generated artifacts will not run under them as-is.

playwright_ok=0
halt_message=""

if [ -f "$ROOT/package.json" ]; then
  if grep -q '"@playwright/test"' "$ROOT/package.json" 2>/dev/null; then
    if [ -d "$ROOT/node_modules/@playwright/test" ] || [ -x "$ROOT/node_modules/.bin/playwright" ]; then
      playwright_ok=1
    else
      halt_message=$(cat <<EOF
ERROR: $SKILL_NAME requires Playwright to be installed

package.json declares "@playwright/test" but it is not present in node_modules.
Dependencies have not been installed (or were removed).

To resolve:
  npm install
  npx playwright install      # download browser binaries

After Playwright is installed, re-run $SKILL_NAME.
EOF
)
    fi
  else
    halt_message=$(cat <<EOF
ERROR: $SKILL_NAME requires Playwright to be installed

This is a Node project (package.json found) but "@playwright/test" is not a
declared dependency. This skill generates TypeScript Playwright specs and
cannot run them without it.

To resolve:
  npm install -D @playwright/test
  npx playwright install      # download browser binaries

After Playwright is installed, re-run $SKILL_NAME.
EOF
)
  fi
else
  # No package.json — figure out what kind of project this is for a useful message.
  detected="unknown"
  if [ -f "$ROOT/pyproject.toml" ] || [ -f "$ROOT/requirements.txt" ]; then
    detected="Python"
  elif [ -f "$ROOT/pom.xml" ] || [ -f "$ROOT/build.gradle" ] || [ -f "$ROOT/build.gradle.kts" ]; then
    detected="Java"
  elif find "$ROOT" -maxdepth 2 -type f -name '*.csproj' 2>/dev/null | grep -q .; then
    detected=".NET"
  fi

  if [ "$detected" = "unknown" ]; then
    halt_message=$(cat <<EOF
ERROR: $SKILL_NAME could not detect a Node project

No package.json was found at the project root. This skill generates
TypeScript Playwright specs and Node-based tooling, so it requires a Node
project with "@playwright/test" installed.

To resolve:
  npm init -y
  npm install -D @playwright/test
  npx playwright install

After Playwright is installed, re-run $SKILL_NAME.
EOF
)
  else
    halt_message=$(cat <<EOF
ERROR: $SKILL_NAME requires a Node project with Playwright

A $detected project was detected, but this skill generates TypeScript
Playwright specs (.spec.ts) and Node-based tooling — the output will not run
under a $detected Playwright binding as-is.

To resolve, add a Node Playwright setup (it can live alongside the $detected code):
  npm init -y
  npm install -D @playwright/test
  npx playwright install

After Playwright is installed, re-run $SKILL_NAME.
EOF
)
  fi
fi

if [ "$playwright_ok" -ne 1 ]; then
  # Failed check — drop any stale cache so the next run re-checks.
  rm -f "$CACHE_FILE" 2>/dev/null || true
  printf '%s\n' "$halt_message"
  exit 1
fi

# Passed — write the cache so subsequent runs are free until manifests change.
printf 'ok\n%s' "$CURRENT_SIG" > "$CACHE_FILE" 2>/dev/null || true

exit 0
