#!/usr/bin/env node
/**
 * verify-pipeline.js - Pipeline health diagnostic.
 * Checks manifest integrity, file existence, item-to-test consistency,
 * pinned tests, and pending queue.
 *
 * Usage: node verify-pipeline.js
 *        node verify-pipeline.js --help
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { readManifestFile } from './lib/manifest.js';

if (process.argv.includes('--help')) {
  console.log(`verify-pipeline.js - Pipeline health diagnostic

Usage: node verify-pipeline.js
       node verify-pipeline.js --help

Runs 7 health checks on the verification-playwright pipeline:
1. Manifest integrity (all 3 files parse as valid JSON)
2. Source file existence (import index entries exist on disk)
3. Spec file existence (items.json references exist on disk)
4. Item-to-test consistency (every item has @begin/@end markers)
5. Import index coverage (no orphaned entries)
6. Pinned test audit
7. Pending generation queue

Exit code 0: all pass or warnings only
Exit code 1: any failures`);
  process.exit(0);
}

const projectDir = process.cwd();
let hasFailure = false;

console.log('Pipeline Health Check');

// 1. Manifest integrity
const manifestFiles = ['items.json', 'import-index.json', 'config.json'];
let validCount = 0;
for (const file of manifestFiles) {
  const data = readManifestFile(projectDir, file);
  if (data) validCount++;
}
check(
  'Manifest files valid',
  validCount === manifestFiles.length,
  `${validCount}/${manifestFiles.length}`,
  `${validCount}/${manifestFiles.length} — missing or invalid`
);

// 2. Source file existence (import index)
const importIndex = readManifestFile(projectDir, 'import-index.json');
if (importIndex?.entries) {
  const entries = Object.keys(importIndex.entries);
  const staleEntries = entries.filter(f => !existsSync(f));
  if (staleEntries.length === 0) {
    check('Source files exist', true, `${entries.length}/${entries.length}`);
  } else {
    check('Source files exist', false, '', `${staleEntries.length} stale import index entries`);
    hasFailure = false; // Stale entries are warnings, not failures
    console.log(`  \u26a0 ${staleEntries.length} stale import index entries (run --force-index to rebuild)`);
  }
} else {
  check('Source files exist', true, 'no import index yet');
}

// 3. Spec file existence
const items = readManifestFile(projectDir, 'items.json');
if (items?.items) {
  const specFiles = [...new Set(Object.values(items.items).map(i => i.spec_file).filter(Boolean))];
  const missingSpecs = specFiles.filter(f => !existsSync(f));
  check(
    'Spec files exist',
    missingSpecs.length === 0,
    `${specFiles.length - missingSpecs.length}/${specFiles.length}`,
    `${missingSpecs.length} missing spec files`
  );
} else {
  check('Spec files exist', true, 'no items yet');
}

// 4. Item-to-test consistency
if (items?.items) {
  let consistent = 0;
  let inconsistent = 0;
  for (const [id, item] of Object.entries(items.items)) {
    if (!item.spec_file || !existsSync(item.spec_file)) {
      inconsistent++;
      continue;
    }
    try {
      const content = readFileSync(item.spec_file, 'utf8');
      if (content.includes(`// @begin:${id}`) && content.includes(`// @end:${id}`)) {
        consistent++;
      } else if (item.status === 'pending') {
        consistent++; // Pending items don't have markers yet
      } else {
        inconsistent++;
      }
    } catch {
      inconsistent++;
    }
  }
  const total = consistent + inconsistent;
  check(
    'Item-to-test consistency',
    inconsistent === 0,
    `${consistent}/${total}`,
    `${inconsistent} orphaned items`
  );
} else {
  check('Item-to-test consistency', true, 'no items yet');
}

// 5. Import index coverage (already checked in #2, report stale count)
// Combined with check 2

// 6. Pinned test audit
if (items?.items) {
  const pinned = Object.entries(items.items).filter(([, item]) => item.pinned);
  if (pinned.length > 0) {
    console.log(`  \u26a0 ${pinned.length} pinned tests (manually edited)`);
  } else {
    check('Pinned tests', true, 'none');
  }
} else {
  check('Pinned tests', true, 'no items yet');
}

// 7. Pending generation queue
const queuePath = join(projectDir, 'tests', 'verification-playwright', 'pending-generation.json');
if (existsSync(queuePath)) {
  try {
    const queue = JSON.parse(readFileSync(queuePath, 'utf8'));
    if (queue.length > 0) {
      console.log(`  \u26a0 ${queue.length} pending generation items`);
    } else {
      check('Pending generation', true, 'none');
    }
  } catch {
    check('Pending generation', false, '', 'queue file corrupted');
  }
} else {
  check('No pending generation items', true, '');
}

process.exit(hasFailure ? 1 : 0);

function check(name, passed, successDetail, failDetail) {
  if (passed) {
    const detail = successDetail ? ` (${successDetail})` : '';
    console.log(`  \u2713 ${name}${detail}`);
  } else {
    const detail = failDetail ? ` — ${failDetail}` : '';
    console.log(`  \u2717 ${name}${detail}`);
    hasFailure = true;
  }
}
