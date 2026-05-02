#!/usr/bin/env bash
# preflight.sh — Verify verification docs exist before this skill runs.
#
# Contract: exit 0 silently on success. Exit 1 with a halt message on stdout
# on failure. The agent prints the message verbatim and stops — no recovery,
# no retry, no fallback. The user must run verification-writer before retrying.
#
# Run from any working directory; pass --root to point at a different repo.

set -euo pipefail

SKILL_NAME="playwright-test-runner"
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

exit 0
