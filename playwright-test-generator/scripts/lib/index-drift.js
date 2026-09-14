/**
 * Stale import-index detection — one implementation, two severities.
 *
 * An import-index entry keyed on a file that no longer exists is drift: the
 * index was generated against a tree that has since moved on. Both
 * map-changes.js and verify-pipeline.js used to detect this independently and
 * reach different verdicts, which read as one of them being wrong. The split
 * is deliberate, and it belongs to the tools' roles, not to the detection:
 *
 *  - map-changes.js SELECTS test tags for a run. It cannot regenerate the
 *    index, and a deleted source file is exactly what a developer's own commit
 *    produces, so blocking there would block the commit that legitimately
 *    removed the file. It warns, skips the entry, and names the remedy.
 *  - verify-pipeline.js is the GATE. Drift that survives to CI means nobody
 *    refreshed the index, so it fails.
 *
 * Keeping the predicate here is what stops those two verdicts from drifting
 * apart again on top of each other.
 */

import { existsSync } from 'node:fs';
import { join } from 'node:path';

/** The one remedy both tools point at. */
export const STALE_INDEX_REMEDY =
  'run playwright-test-generator to refresh import-index.json';

/**
 * True when an import-index key names a file that is no longer on disk.
 * @param {string} file - Repo-root-relative path (an import-index key).
 * @param {string} repoRoot - Git toplevel; import-index keys are relative to it.
 */
export function isIndexEntryStale(file, repoRoot) {
  return !existsSync(join(repoRoot, file));
}

/** Message shared by both tools so one defect reads as one defect. */
export function staleIndexMessage(file) {
  return `Import-index entry "${file}" is stale (file no longer exists) — ${STALE_INDEX_REMEDY}`;
}
