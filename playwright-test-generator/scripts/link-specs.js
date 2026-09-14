#!/usr/bin/env node
/**
 * link-specs.js - Reconcile items.json against the generated specs on disk.
 *
 * Specs are written by the playwright-test-generator skill, not by
 * sync-tests.js, and nothing else writes `spec_file` back onto the manifest.
 * Without that link three of verify-pipeline.js's checks (checkSpecFiles,
 * checkSpecArtifacts, and the marker half of checkItemConsistency) silently
 * iterate an empty set — the gate passes because it inspects nothing. Run this
 * after any generation pass, then run verify-pipeline.js.
 *
 * Reads:  tests/verification-playwright/*.spec.ts  (// @begin:<ID> markers)
 * Writes: manifest/items.json      — spec_file + status on every matched item
 *         pending-generation.json  — the items that still have no spec
 */

import { readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import {
  readManifestFileSync, writeManifestFileSync,
  acquireLockSync, releaseLockSync,
  pendingQueuePath, readPendingIds, writePendingIds,
} from './lib/manifest.js';
import { fileURLToPath } from 'node:url';

const SPEC_DIR = join('tests', 'verification-playwright');

function walkSpecs(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'manifest' || entry.name === 'node_modules') continue;
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walkSpecs(p, out);
    else if (entry.name.endsWith('.spec.ts')) out.push(p);
  }
  return out;
}

/** Map every @begin/@end-marked item ID to its spec file and whether the
 *  marked block is skipped. `spec_file` is repo-relative, matching the shape
 *  in references/manifest-format.md and how verify-pipeline.js resolves it. */
export function collectMarkers(projectDir) {
  const markers = new Map();
  const duplicates = [];
  for (const file of walkSpecs(join(projectDir, SPEC_DIR))) {
    // POSIX separators always: relative() yields backslashes on Windows, and a
    // committed spec_file with backslashes is read back on Linux/macOS as a
    // literal filename, so checkSpecFiles reports an existing spec as missing.
    // sync-tests.js normalises source_doc the same way and for the same reason.
    const rel = relative(projectDir, file).split(sep).join('/');
    const content = readFileSync(file, 'utf8');
    const re = /\/\/ @begin:([A-Za-z0-9_-]+)/g;
    let m;
    while ((m = re.exec(content)) !== null) {
      const id = m[1];
      const endIdx = content.indexOf(`// @end:${id}`, m.index);
      // An unterminated block has no reliable extent, so its .skip() state is
      // unknowable — leave the item pending rather than guess its status.
      if (endIdx === -1) {
        duplicates.push(`${id}: @begin in ${rel} has no matching @end`);
        continue;
      }
      if (markers.has(id)) {
        duplicates.push(`${id}: marked in both ${markers.get(id).spec_file} and ${rel}`);
        continue;
      }
      markers.set(id, {
        spec_file: rel,
        skipped: content.substring(m.index, endIdx).includes('.skip('),
      });
    }
  }
  return { markers, duplicates };
}

export function linkSpecs(projectDir) {
  const queuePath = pendingQueuePath(projectDir);
  const { markers, duplicates } = collectMarkers(projectDir);

  // Lock across the whole read-modify-write. sync-tests.js writes items.json
  // under this same lock, so without it a concurrent sync lands between our
  // read and our write and this stale snapshot erases its new entries.
  acquireLockSync(projectDir);
  try {
    const items = readManifestFileSync(projectDir, 'items.json');
    if (!items) throw new Error(`No manifest at ${join(projectDir, SPEC_DIR, 'manifest', 'items.json')}`);

    const orphans = [];
    let linked = 0;
    for (const [id, info] of markers) {
      const item = items.items[id];
      // A marker with no manifest entry is a spec for an item the docs no longer
      // describe. Report it; never mint a manifest entry from a spec, or the
      // docs stop being the source of truth.
      if (!item) { orphans.push(id); continue; }
      item.spec_file = info.spec_file;
      item.status = info.skipped ? 'skipped' : 'active';
      linked++;
    }

    // Marker presence cannot distinguish "regenerated this pass" from "stale
    // spec left over from before". An item sync-tests queued as SUBSTANTIALLY
    // MODIFIED already has a marker, so deriving the queue from markers alone
    // drops it and the outdated test is never regenerated — silently.
    // So: union the ids already queued with the ids that have no spec at all,
    // and only drop an id when it has left the manifest entirely. This can
    // leave an id queued after it was regenerated, which surfaces as a
    // "Pending generation" warning; the alternative loses a stale test with no
    // signal at all. Prefer the loud failure.
    const stillInManifest = (id) => Boolean(items.items[id]);
    const unmarked = Object.keys(items.items).filter((id) => !markers.has(id));
    const pending = [...new Set([...readPendingIds(queuePath), ...unmarked])]
      .filter(stillInManifest)
      .sort();

    items.generated_at = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
    writeManifestFileSync(projectDir, 'items.json', items);
    writePendingIds(queuePath, pending);

    return { linked, pending: pending.length, orphans, duplicates };
  } finally {
    releaseLockSync(projectDir);
  }
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`link-specs.js - Link generated specs back into manifest/items.json

Usage: node <skill>/scripts/link-specs.js [projectDir]
       node <skill>/scripts/link-specs.js --help

projectDir defaults to the current working directory.`);
    process.exit(0);
  }
  // Explicit project dir, because the skill's scripts are not inside the target
  // project: invoked by absolute path, process.cwd() is the only other signal
  // and it is wrong whenever the caller runs from the skill directory.
  const dirArg = process.argv.slice(2).find((a) => !a.startsWith('-'));
  const projectDir = resolve(dirArg ?? process.cwd());

  const { linked, pending, orphans, duplicates } = linkSpecs(projectDir);
  console.log(`Linked ${linked} item(s) to specs; ${pending} still pending generation.`);
  for (const d of duplicates) console.log(`  ✗ ${d}`);
  for (const o of orphans) console.log(`  ✗ orphan marker (no manifest item): ${o}`);
  // Duplicate/unterminated markers mean two specs claim one item — the manifest
  // cannot record both, so fail rather than record whichever won the walk.
  // Orphans fail too: verify-pipeline.js discovers specs through manifest
  // spec_file fields, so a spec whose item is gone is invisible to every one of
  // its checks and the gate reports green with stale Playwright code on disk.
  // Consequence, deliberate: deleting an item from a doc fails this step until
  // the spec block is removed as well. That is the intended prompt, not a
  // regression — nothing removes those blocks automatically.
  process.exit(duplicates.length + orphans.length > 0 ? 1 : 0);
}
