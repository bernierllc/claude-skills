/**
 * Repo root resolution for import-index path bases.
 *
 * Two distinct bases exist in this pipeline:
 *  - projectDir: the Playwright project root (holds tests/verification-playwright/
 *    and the manifest). spec_file paths in items.json are relative to this.
 *  - repoRoot: the git toplevel. import-index.json keys are relative to this,
 *    because (a) sources legitimately span more than one package and cannot all
 *    be expressed under a single package dir, and (b) `git diff --name-only`
 *    always emits repo-root-relative paths regardless of cwd.
 *
 * In a single-root project the two are identical, so callers default
 * repoRoot to projectDir and behavior is unchanged.
 */

import { execSync } from 'node:child_process';

/**
 * Resolve the git repository root for a given project directory.
 * Falls back to projectDir when not in a git repo (preserves single-root behavior).
 * @param {string} projectDir - The Playwright project root (cwd for git).
 * @returns {string} The git toplevel, or projectDir if unavailable.
 */
export function resolveRepoRoot(projectDir) {
  try {
    return execSync('git rev-parse --show-toplevel', {
      encoding: 'utf8',
      cwd: projectDir,
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim() || projectDir;
  } catch {
    return projectDir;
  }
}
