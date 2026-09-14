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

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
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
    const rel = relative(projectDir, file);
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
  const itemsPath = join(projectDir, SPEC_DIR, 'manifest', 'items.json');
  const queuePath = join(projectDir, SPEC_DIR, 'pending-generation.json');
  const { markers, duplicates } = collectMarkers(projectDir);

  const items = JSON.parse(readFileSync(itemsPath, 'utf8'));
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

  const pending = Object.keys(items.items).filter((id) => !markers.has(id));
  const generatedAt = new Date().toISOString().replace(/\.\d+Z$/, 'Z');

  items.generated_at = generatedAt;
  writeFileSync(itemsPath, JSON.stringify(items, null, 2) + '\n', 'utf8');

  const queue = JSON.parse(readFileSync(queuePath, 'utf8'));
  queue.items = pending;
  queue.generated_at = generatedAt;
  writeFileSync(queuePath, JSON.stringify(queue, null, 2) + '\n', 'utf8');

  return { linked, pending: pending.length, orphans, duplicates };
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`link-specs.js - Link generated specs back into manifest/items.json

Usage: node link-specs.js
       node link-specs.js --help`);
    process.exit(0);
  }
  const { linked, pending, orphans, duplicates } = linkSpecs(process.cwd());
  console.log(`Linked ${linked} item(s) to specs; ${pending} still pending generation.`);
  for (const d of duplicates) console.log(`  ✗ ${d}`);
  for (const o of orphans) console.log(`  ⚠ orphan marker (no manifest item): ${o}`);
  // Duplicate/unterminated markers mean two specs claim one item — the manifest
  // cannot record both, so fail rather than record whichever won the walk.
  process.exit(duplicates.length > 0 ? 1 : 0);
}
