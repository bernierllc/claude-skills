#!/usr/bin/env node
/**
 * verify-pipeline.js - Pipeline health diagnostic.
 * Exports testable functions. CLI entry point at bottom.
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { resolveRepoRoot, isEntryPoint } from './lib/repo.js';
import { isIndexEntryStale, staleIndexMessage } from './lib/index-drift.js';
import {
  loadManifest, manifestDirFor, pendingIds, LEGACY_MANIFEST_FILES, MANIFEST_VERSION,
} from './lib/manifest.js';

// Tool-call artifact tokens that must never appear in a generated spec. A
// malformed generation can leak these trailer tokens into a file; because
// Playwright fails at collection when any spec is unparseable, one corrupted
// file aborts the entire suite. Catch them deterministically at the gate.
const ARTIFACT_TOKENS = [
  'antml:invoke',
  'antml:parameter',
  '<invoke',
  '</invoke>',
  '<parameter',
  '</parameter>',
  '<function_calls>',
  '</function_calls>',
];

const LAYOUT_DIRS = ['items', 'import-index'];

function jsonFilesIn(manifestDir) {
  const files = existsSync(join(manifestDir, 'config.json')) ? ['config.json'] : [];
  for (const sub of LAYOUT_DIRS) {
    const dir = join(manifestDir, sub);
    if (!existsSync(dir)) continue;
    for (const f of readdirSync(dir).sort()) if (f.endsWith('.json')) files.push(`${sub}/${f}`);
  }
  return files;
}

/** Check manifest file integrity: config.json and every per-doc / per-page
 *  file parse as valid JSON. */
export async function checkManifestIntegrity(manifestDir) {
  const results = [];
  if (!existsSync(join(manifestDir, 'config.json'))) {
    results.push({ file: 'config.json', status: 'warn', message: 'Missing manifest file: config.json' });
  }
  for (const file of jsonFilesIn(manifestDir)) {
    try {
      JSON.parse(readFileSync(join(manifestDir, file), 'utf8'));
      results.push({ file, status: 'pass', message: 'Valid JSON' });
    } catch (err) {
      results.push({ file, status: 'fail', message: `Invalid JSON: ${err.message}` });
    }
  }
  return results;
}

/**
 * Load the manifest through the one loader (which migrates an older layout
 * first) and report the layout state. Returns { checks, manifest }; manifest
 * is null when the loader refused.
 *   - loader throws (unmigratable layout 1, newer layout, ID collision) -> fail
 *   - layout-1 files next to per-doc files (a pre-migration branch merged in)
 *     -> fail: the loader folded them locally, but the tree must not carry both
 *   - layout 1 alone -> warn: migrated in the working tree, not yet committed
 */
export async function checkManifestLayout(manifestDir) {
  const legacy = LEGACY_MANIFEST_FILES.filter((f) => existsSync(join(manifestDir, f)));
  const shardCount = (sub) => existsSync(join(manifestDir, sub))
    ? readdirSync(join(manifestDir, sub)).filter((f) => f.endsWith('.json')).length : 0;
  const hadCurrent = LAYOUT_DIRS.some((sub) => shardCount(sub) > 0);
  // A bootstrapped pipeline (config.json present) with no item files at all
  // means manifest/items/ was deleted or emptied: loadManifest would return an
  // empty map and every later check would pass over nothing.
  if (existsSync(join(manifestDir, 'config.json')) && !legacy.length && shardCount('items') === 0) {
    return { manifest: null, checks: [{ file: 'items/', status: 'fail', message:
      'Manifest has config.json but no per-doc item files under manifest/items/. Fix: restore them ' +
      '(git checkout -- manifest/items) or regenerate with --force' }] };
  }
  let manifest;
  try {
    manifest = loadManifest(manifestDir);
  } catch (err) {
    return {
      manifest: null,
      checks: [{ file: 'manifest', status: 'fail', message:
        `Manifest cannot be loaded: ${err.message}. Fix: correct the file named above, then re-run ` +
        '(a refused migration leaves the old files untouched)' }],
    };
  }
  const commit = `commit manifest/items/ and manifest/import-index/, then git rm ${legacy.join(' ')}`;
  if (legacy.length && hadCurrent) {
    return { manifest, checks: [{ file: legacy.join(', '), status: 'fail', message:
      `Layout-1 manifest file(s) committed alongside the ${MANIFEST_VERSION} per-doc layout (folded in locally). Fix: ${commit}` }] };
  }
  if (legacy.length) {
    return { manifest, checks: [{ file: legacy.join(', '), status: 'warn', message:
      `Manifest migrated from layout 1 to ${MANIFEST_VERSION} in the working tree. Fix: ${commit}` }] };
  }
  if (shardCount('import-index') === 0 && Object.keys(manifest.items).length) {
    return { manifest, checks: [{ file: 'import-index/', status: 'warn', message:
      'No import-index pages under manifest/import-index/, so no source change maps to a test. ' +
      'Fix: restore them (git checkout -- manifest/import-index) or regenerate with --force' }] };
  }
  return { manifest, checks: [] };
}

/** Check that all source files in the import index exist on disk.
 * import-index paths are repo-root-relative, so they resolve against repoRoot,
 * which defaults to projectDir for single-root projects. */
export async function checkSourceFiles(manifest, projectDir, repoRoot = projectDir) {
  const results = [];
  for (const file of Object.keys(manifest.entries)) {
    // Failing here is the other half of the split documented in
    // lib/index-drift.js: drift that reaches CI means nobody refreshed.
    if (isIndexEntryStale(file, repoRoot)) {
      results.push({ file, status: 'fail', message: staleIndexMessage(file) });
    } else {
      results.push({ file, status: 'pass' });
    }
  }
  return results;
}

/** Check that all spec files referenced in items exist on disk. */
export async function checkSpecFiles(manifest, projectDir) {
  const specFiles = [...new Set(Object.values(manifest.items).map(i => i.spec_file).filter(Boolean))];
  const results = [];
  for (const file of specFiles) {
    const fullPath = join(projectDir, file);
    if (existsSync(fullPath)) {
      results.push({ file, status: 'pass' });
    } else {
      results.push({ file, status: 'fail', message: `Spec file not found: ${file}` });
    }
  }
  return results;
}

/** Check that every item ID has @begin/@end markers in its spec file. */
export async function checkItemConsistency(manifest, projectDir) {
  const results = [];
  for (const [id, item] of Object.entries(manifest.items)) {
    if (!item.spec_file) {
      // Items without spec_file are pending generation or have minimal config — skip, don't fail
      continue;
    }
    const fullPath = join(projectDir, item.spec_file);
    if (!existsSync(fullPath)) {
      results.push({ itemId: id, status: 'fail', message: `Orphaned: spec file missing` });
      continue;
    }
    const content = readFileSync(fullPath, 'utf8');
    const beginMarker = `// @begin:${id}`;
    const endMarker = `// @end:${id}`;
    const beginIdx = content.indexOf(beginMarker);
    const endIdx = content.indexOf(endMarker);
    if (beginIdx !== -1 && endIdx !== -1) {
      // Skip stubs are NOT marker-less — they carry @begin/@end like any other
      // test (sync-tests.js relies on the markers to locate, patch, and un-skip
      // them). A 'skipped' item whose marked block has no .skip() is a
      // status/spec mismatch, not a valid stub.
      if (item.status === 'skipped') {
        const block = content.substring(beginIdx, endIdx);
        if (!block.includes('.skip(')) {
          results.push({ itemId: id, status: 'fail', message: `Status 'skipped' but spec block for ${id} has no .skip()` });
          continue;
        }
      }
      results.push({ itemId: id, status: 'pass' });
    } else if (item.status === 'pending') {
      results.push({ itemId: id, status: 'pass' }); // Pending items don't have markers yet
    } else {
      results.push({ itemId: id, status: 'fail', message: `Orphaned: no @begin/@end markers for ${id}` });
    }
  }
  return results;
}

/** Check that no spec file contains leaked tool-call artifact tokens.
 * A single corrupted spec aborts the whole Playwright run at collection time,
 * so reject artifacts deterministically rather than waiting for a SyntaxError. */
export async function checkSpecArtifacts(manifest, projectDir) {
  const specFiles = [...new Set(Object.values(manifest.items).map(i => i.spec_file).filter(Boolean))];
  const results = [];
  for (const file of specFiles) {
    const fullPath = join(projectDir, file);
    if (!existsSync(fullPath)) continue; // missing-spec is reported by checkSpecFiles
    const content = readFileSync(fullPath, 'utf8');
    const found = ARTIFACT_TOKENS.filter(tok => content.includes(tok));
    if (found.length > 0) {
      results.push({ file, status: 'fail', message: `Tool-call artifact token(s) in spec: ${found.join(', ')}` });
    } else {
      results.push({ file, status: 'pass' });
    }
  }
  return results;
}

/** Report pinned tests. */
export async function checkPinnedTests(manifest) {
  const results = [];
  for (const [id, item] of Object.entries(manifest.items)) {
    if (item.pinned) {
      results.push({ itemId: id, status: 'warn', message: `Pinned (manually edited)` });
    }
  }
  return results;
}

/** Report pending generation items (entries flagged pending_generation). */
export async function checkPendingGeneration(manifest) {
  return pendingIds(manifest).map(id => ({ itemId: id, status: 'warn', message: 'Pending generation' }));
}

/** Run full pipeline verification. */
export async function verifyPipeline(projectDir) {
  const manifestDir = manifestDirFor(projectDir);
  const repoRoot = resolveRepoRoot(projectDir);
  const checks = [];
  let hasFailure = false;

  const integrity = await checkManifestIntegrity(manifestDir);
  checks.push(...integrity);
  if (integrity.some(r => r.status === 'fail')) hasFailure = true;

  const layout = await checkManifestLayout(manifestDir);
  checks.push(...layout.checks);
  if (layout.checks.some(r => r.status === 'fail')) hasFailure = true;
  const manifest = layout.manifest;
  if (!manifest) return { exitCode: 1, checks };

  const sources = await checkSourceFiles(manifest, projectDir, repoRoot);
  checks.push(...sources);
  if (sources.some(r => r.status === 'fail')) hasFailure = true;

  const specs = await checkSpecFiles(manifest, projectDir);
  checks.push(...specs);
  if (specs.some(r => r.status === 'fail')) hasFailure = true;

  const artifacts = await checkSpecArtifacts(manifest, projectDir);
  checks.push(...artifacts);
  if (artifacts.some(r => r.status === 'fail')) hasFailure = true;

  const consistency = await checkItemConsistency(manifest, projectDir);
  checks.push(...consistency);
  if (consistency.some(r => r.status === 'fail')) hasFailure = true;

  const pinned = await checkPinnedTests(manifest);
  checks.push(...pinned);

  const pending = await checkPendingGeneration(manifest);
  checks.push(...pending);

  return { exitCode: hasFailure ? 1 : 0, checks };
}

/**
 * Render checks for the CLI, one line per distinct message.
 *
 * Checks that share a constant message — every pending item reports
 * 'Pending generation', every pinned one reports the same — used to print one
 * indistinguishable line each, because the printer preferred `message` and so
 * discarded the only field that identified them. A 611-item generation queue
 * turned the report into 611 identical lines with nothing to act on. Group by
 * message instead, and carry the subjects on the line.
 */
export function formatChecks(checks, maxSubjects = 10) {
  const groups = new Map();
  for (const c of checks) {
    const key = c.message || c.file || c.itemId || 'Unknown check';
    const subject = c.itemId || c.file;
    if (!groups.has(key)) groups.set(key, []);
    if (subject && subject !== key) groups.get(key).push(subject);
  }
  return [...groups].map(([message, subjects]) => {
    if (subjects.length === 0) return message;
    if (subjects.length === 1) return `${message}: ${subjects[0]}`;
    const shown = subjects.slice(0, maxSubjects).join(', ');
    const rest = subjects.length - maxSubjects;
    return `${message} (${subjects.length}): ${shown}${rest > 0 ? `, +${rest} more` : ''}`;
  });
}

// --- CLI entry point ---
const isMain = isEntryPoint(import.meta.url);
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`verify-pipeline.js - Pipeline health diagnostic

Usage: node verify-pipeline.js
       node verify-pipeline.js --help`);
    process.exit(0);
  }

  const result = await verifyPipeline(process.cwd());

  console.log('Pipeline Health Check');
  const byStatus = { pass: 0, warn: 0, fail: 0 };
  for (const check of result.checks) {
    byStatus[check.status] = (byStatus[check.status] || 0) + 1;
  }
  console.log(`  ${byStatus.pass} passed, ${byStatus.warn} warned, ${byStatus.fail} failed`);

  const failChecks = result.checks.filter(c => c.status === 'fail');
  const warnChecks = result.checks.filter(c => c.status === 'warn');

  if (failChecks.length === 0 && warnChecks.length === 0) {
    console.log('  \u2713 All checks passed');
  }
  for (const line of formatChecks(failChecks)) console.log(`  \u2717 ${line}`);
  for (const line of formatChecks(warnChecks)) console.log(`  \u26a0 ${line}`);

  process.exit(result.exitCode);
}
