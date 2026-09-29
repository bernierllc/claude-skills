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

# The tier's browser list is config, not prose: read tiers.<tier>.browsers from
# config.json and pass each as --project, so a playwright.config.ts with more
# projects than the tier names does not run them all.
config_json="tests/verification-playwright/manifest/config.json"
read_browsers() {
  node -e '
    const fs = require("node:fs");
    const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
    const list = cfg?.tiers?.[process.argv[2]]?.browsers ?? [];
    process.stdout.write(list.map((b) => b + "\n").join(""));
  ' "$config_json" "$1" 2>/dev/null || true
}

project_args=()
browser_names=""
while IFS= read -r browser; do
  [ -n "$browser" ] || continue
  project_args+=(--project "$browser")
  browser_names="${browser_names:+$browser_names, }$browser"
done < <(read_browsers "$tier")

case "$tier" in
  "thorough")
    echo "Running verification tests (thorough tier: ${browser_names:-default}, all depths, changes only)..."
    affected=$(node scripts/verification-playwright/map-changes.js --since-main 2>/dev/null || echo "")
    if [ -z "$affected" ]; then
      echo "No affected tests. Push allowed."
      exit 0
    fi
    grep_pattern=$(echo "$affected" | tr ' ' '|')
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts \
      ${project_args[@]+"${project_args[@]}"} \
      --grep "$grep_pattern"
    ;;
  "full")
    echo "Running verification tests (full tier: ${browser_names:-default}, all tests)..."
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts \
      ${project_args[@]+"${project_args[@]}"}
    ;;
  *)
    exit 0 # Feature branch or no match, skip
    ;;
esac

# END verification-playwright
