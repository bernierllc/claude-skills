#!/usr/bin/env bash
# Point git at the tracked hooks directory so the version-check pre-commit runs.
# Run once per clone.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
git -C "$repo_root" config core.hooksPath .githooks
echo "core.hooksPath set to .githooks"
