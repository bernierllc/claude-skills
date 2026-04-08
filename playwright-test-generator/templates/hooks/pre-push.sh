#!/usr/bin/env bash
# Verification-Playwright Pipeline: Pre-push tier gate
# Runs tiered Playwright tests based on target branch
# Part of the playwright-test-generator skill
#
# BEGIN verification-playwright

set -euo pipefail

# Guard: skip if pipeline not initialized
if [ ! -f "scripts/verification-playwright/select-tier.js" ]; then
  exit 0
fi

# Parse target branch from stdin refspecs
# Git pre-push hooks receive: <local ref> <local sha> <remote ref> <remote sha>
target_branch=""
while IFS=' ' read -r _local_ref _local_sha remote_ref _remote_sha; do
  target_branch=$(echo "$remote_ref" | sed 's|refs/heads/||')
  break
done

# Fallback to @{push} if stdin was empty
if [ -z "$target_branch" ]; then
  target_branch=$(git rev-parse --abbrev-ref '@{push}' 2>/dev/null || echo "")
fi

if [ -z "$target_branch" ]; then
  exit 0 # Can't determine target, skip
fi

# Select tier based on target branch
tier=$(node scripts/verification-playwright/select-tier.js "$target_branch" 2>/dev/null || echo "")

case "$tier" in
  "thorough")
    echo "Running verification tests (thorough tier: 3 browsers, all depths, changes only)..."
    affected=$(node scripts/verification-playwright/map-changes.js --since-main 2>/dev/null || echo "")
    if [ -z "$affected" ]; then
      echo "No affected tests. Push allowed."
      exit 0
    fi
    grep_pattern=$(echo "$affected" | tr ' ' '|')
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts \
      --grep "$grep_pattern"
    ;;
  "full")
    echo "Running verification tests (full tier: all browsers, all tests)..."
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts
    ;;
  *)
    exit 0 # Feature branch or no match, skip
    ;;
esac

# END verification-playwright
