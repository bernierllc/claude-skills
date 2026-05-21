#!/usr/bin/env node
/**
 * verify-pipeline.js - Pipeline health diagnostic.
 * Exports testable functions. CLI entry point at bottom.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveRepoRoot } from './lib/repo.js';

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

/** Check manifest file integrity (all 3 files parse as valid JSON). */
export async function checkManifestIntegrity(manifestDir) {
  const files = ['items.json', 'import-index.json', 'config.json'];
  const results = [];
  for (const file of files) {
    const filePath = join(manifestDir, file);
    if (!existsSync(filePath)) {
      results.push({ file, status: 'warn', message: `Missing manifest file: ${file}` });
      continue;
    }
    try {
      JSON.parse(readFileSync(filePath, 'utf8'));
      results.push({ file, status: 'pass', message: 'Valid JSON' });
    } catch (err) {
      results.push({ file, status: 'fail', message: `Invalid JSON: ${err.message}` });
    }
  }
  return results;
}

/** Check that all source files in the import index exist on disk.
 * import-index keys are repo-root-relative, so they resolve against repoRoot,
 * which defaults to projectDir for single-root projects. */
export async function checkSourceFiles(manifestDir, projectDir, repoRoot = projectDir) {
  const indexPath = join(manifestDir, 'import-index.json');
  if (!existsSync(indexPath)) return [];
  const index = JSON.parse(readFileSync(indexPath, 'utf8'));
  const results = [];
  for (const file of Object.keys(index.entries || {})) {
    const fullPath = join(repoRoot, file);
    if (existsSync(fullPath)) {
      results.push({ file, status: 'pass' });
    } else {
      results.push({ file, status: 'fail', message: `Source file not found: ${file}` });
    }
  }
  return results;
}

/** Check that all spec files referenced in items exist on disk. */
export async function checkSpecFiles(manifestDir, projectDir) {
  const itemsPath = join(manifestDir, 'items.json');
  if (!existsSync(itemsPath)) return [];
  let items;
  try {
    items = JSON.parse(readFileSync(itemsPath, 'utf8'));
  } catch {
    return [{ file: 'items.json', status: 'fail', message: 'Cannot parse items.json' }];
  }
  const specFiles = [...new Set(Object.values(items.items || {}).map(i => i.spec_file).filter(Boolean))];
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
export async function checkItemConsistency(manifestDir, projectDir) {
  const itemsPath = join(manifestDir, 'items.json');
  if (!existsSync(itemsPath)) return [];
  let items;
  try {
    items = JSON.parse(readFileSync(itemsPath, 'utf8'));
  } catch {
    return [{ itemId: 'N/A', status: 'fail', message: 'Cannot parse items.json' }];
  }
  const results = [];
  for (const [id, item] of Object.entries(items.items || {})) {
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
export async function checkSpecArtifacts(manifestDir, projectDir) {
  const itemsPath = join(manifestDir, 'items.json');
  if (!existsSync(itemsPath)) return [];
  let items;
  try {
    items = JSON.parse(readFileSync(itemsPath, 'utf8'));
  } catch {
    return [];
  }
  const specFiles = [...new Set(Object.values(items.items || {}).map(i => i.spec_file).filter(Boolean))];
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
export async function checkPinnedTests(manifestDir) {
  const itemsPath = join(manifestDir, 'items.json');
  if (!existsSync(itemsPath)) return [];
  let items;
  try {
    items = JSON.parse(readFileSync(itemsPath, 'utf8'));
  } catch {
    return [];
  }
  const results = [];
  for (const [id, item] of Object.entries(items.items || {})) {
    if (item.pinned) {
      results.push({ itemId: id, status: 'warn', message: `Pinned (manually edited)` });
    }
  }
  return results;
}

/** Report pending generation items. */
export async function checkPendingGeneration(projectDir) {
  const queuePath = join(projectDir, 'tests', 'verification-playwright', 'pending-generation.json');
  if (!existsSync(queuePath)) return [];
  try {
    const queue = JSON.parse(readFileSync(queuePath, 'utf8'));
    return queue.map(id => ({ itemId: id, status: 'warn', message: 'Pending generation' }));
  } catch {
    return [{ status: 'fail', message: 'Queue file corrupted' }];
  }
}

/** Run full pipeline verification. */
export async function verifyPipeline(projectDir) {
  const manifestDir = join(projectDir, 'tests', 'verification-playwright', 'manifest');
  const repoRoot = resolveRepoRoot(projectDir);
  const checks = [];
  let hasFailure = false;

  const integrity = await checkManifestIntegrity(manifestDir);
  checks.push(...integrity);
  if (integrity.some(r => r.status === 'fail')) hasFailure = true;

  const sources = await checkSourceFiles(manifestDir, projectDir, repoRoot);
  checks.push(...sources);
  if (sources.some(r => r.status === 'fail')) hasFailure = true;

  const specs = await checkSpecFiles(manifestDir, projectDir);
  checks.push(...specs);
  if (specs.some(r => r.status === 'fail')) hasFailure = true;

  const artifacts = await checkSpecArtifacts(manifestDir, projectDir);
  checks.push(...artifacts);
  if (artifacts.some(r => r.status === 'fail')) hasFailure = true;

  const consistency = await checkItemConsistency(manifestDir, projectDir);
  checks.push(...consistency);
  if (consistency.some(r => r.status === 'fail')) hasFailure = true;

  const pinned = await checkPinnedTests(manifestDir);
  checks.push(...pinned);

  const pending = await checkPendingGeneration(projectDir);
  checks.push(...pending);

  return { exitCode: hasFailure ? 1 : 0, checks };
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
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

  const failChecks = result.checks.filter(c => c.status === 'fail');
  const warnChecks = result.checks.filter(c => c.status === 'warn');

  if (failChecks.length === 0 && warnChecks.length === 0) {
    console.log('  \u2713 All checks passed');
  }
  for (const c of failChecks) console.log(`  \u2717 ${c.message || c.file || c.itemId}`);
  for (const c of warnChecks) console.log(`  \u26a0 ${c.message || c.file || c.itemId}`);

  process.exit(result.exitCode);
}
