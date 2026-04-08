#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { readManifestFile } from './lib/manifest.js';
import { fileExists } from './lib/fs.js';

/**
 * Safely read a manifest file, returning null on any error.
 */
async function safeReadManifest(filePath) {
  try {
    return await readManifestFile(filePath);
  } catch {
    return null;
  }
}

/**
 * Check that all manifest files are valid JSON.
 */
export async function checkManifestIntegrity(manifestDir) {
  const files = ['items.json', 'import-index.json', 'config.json'];
  const results = [];

  for (const file of files) {
    const filePath = join(manifestDir, file);
    try {
      const content = await readFile(filePath, 'utf-8');
      JSON.parse(content);
      results.push({ file, status: 'pass' });
    } catch (err) {
      if (err.code === 'ENOENT') {
        results.push({ file, status: 'warn', message: 'File not found' });
      } else {
        results.push({ file, status: 'fail', message: `Invalid JSON: ${err.message}` });
      }
    }
  }

  return results;
}

/**
 * Check that all source files in import-index.json exist on disk.
 */
export async function checkSourceFiles(manifestDir, projectRoot) {
  const index = await safeReadManifest(join(manifestDir, 'import-index.json'));
  if (!index || !index.entries) return [];

  const results = [];
  for (const filePath of Object.keys(index.entries)) {
    const fullPath = join(projectRoot, filePath);
    const exists = await fileExists(fullPath);
    results.push({
      file: filePath,
      status: exists ? 'pass' : 'fail',
      message: exists ? undefined : 'Source file not found'
    });
  }
  return results;
}

/**
 * Check that all spec files referenced by items exist.
 */
export async function checkSpecFiles(manifestDir, projectRoot) {
  const items = await safeReadManifest(join(manifestDir, 'items.json'));
  if (!items || !items.items) return [];

  const results = [];
  const specFiles = new Set();

  for (const [itemId, data] of Object.entries(items.items)) {
    if (data.spec_file) {
      specFiles.add(data.spec_file);
    }
  }

  for (const specFile of specFiles) {
    const fullPath = join(projectRoot, specFile);
    const exists = await fileExists(fullPath);
    results.push({
      file: specFile,
      status: exists ? 'pass' : 'fail',
      message: exists ? undefined : 'Spec file not found'
    });
  }
  return results;
}

/**
 * Check that every item has a corresponding @begin/@end block in its spec file.
 */
export async function checkItemConsistency(manifestDir, projectRoot) {
  const items = await safeReadManifest(join(manifestDir, 'items.json'));
  if (!items || !items.items) return [];

  const results = [];
  const specCache = new Map();

  for (const [itemId, data] of Object.entries(items.items)) {
    if (!data.spec_file) continue;

    const fullPath = join(projectRoot, data.spec_file);
    let specContent;
    if (specCache.has(fullPath)) {
      specContent = specCache.get(fullPath);
    } else {
      try {
        specContent = await readFile(fullPath, 'utf-8');
        specCache.set(fullPath, specContent);
      } catch {
        results.push({ itemId, status: 'fail', message: 'Spec file unreadable' });
        continue;
      }
    }

    const hasBegin = specContent.includes(`// @begin:${itemId}`);
    const hasEnd = specContent.includes(`// @end:${itemId}`);

    if (hasBegin && hasEnd) {
      results.push({ itemId, status: 'pass' });
    } else {
      results.push({ itemId, status: 'fail', message: 'Orphaned item (no @begin/@end block)' });
    }
  }
  return results;
}

/**
 * Report pinned tests.
 */
export async function checkPinnedTests(manifestDir) {
  const items = await safeReadManifest(join(manifestDir, 'items.json'));
  if (!items || !items.items) return [];

  const results = [];
  for (const [itemId, data] of Object.entries(items.items)) {
    if (data.pinned) {
      results.push({ itemId, status: 'warn', message: 'Test is pinned (manually edited)' });
    }
  }
  return results;
}

/**
 * Report pending generation items.
 */
export async function checkPendingGeneration(projectRoot) {
  const pendingPath = join(projectRoot, 'tests', 'verification-playwright', 'pending-generation.json');
  try {
    const content = await readFile(pendingPath, 'utf-8');
    const items = JSON.parse(content);
    if (items.length > 0) {
      return items.map(id => ({ itemId: id, status: 'warn', message: 'Pending generation' }));
    }
    return [];
  } catch {
    return []; // No pending items
  }
}

/**
 * Run all pipeline health checks.
 * Returns { checks: [...], exitCode: 0|1 }
 */
export async function verifyPipeline(projectRoot) {
  const manifestDir = join(projectRoot, 'tests', 'verification-playwright', 'manifest');
  const checks = [];
  let hasFailures = false;

  const manifestResults = await checkManifestIntegrity(manifestDir);
  checks.push({ name: 'Manifest files valid', results: manifestResults });
  if (manifestResults.some(r => r.status === 'fail')) hasFailures = true;

  const sourceResults = await checkSourceFiles(manifestDir, projectRoot);
  checks.push({ name: 'Source files exist', results: sourceResults });
  if (sourceResults.some(r => r.status === 'fail')) hasFailures = true;

  const specResults = await checkSpecFiles(manifestDir, projectRoot);
  checks.push({ name: 'Spec files exist', results: specResults });
  if (specResults.some(r => r.status === 'fail')) hasFailures = true;

  const consistencyResults = await checkItemConsistency(manifestDir, projectRoot);
  checks.push({ name: 'Item-to-test consistency', results: consistencyResults });
  if (consistencyResults.some(r => r.status === 'fail')) hasFailures = true;

  const pinnedResults = await checkPinnedTests(manifestDir);
  checks.push({ name: 'Pinned tests', results: pinnedResults });

  const pendingResults = await checkPendingGeneration(projectRoot);
  checks.push({ name: 'Pending generation', results: pendingResults });

  return {
    checks,
    exitCode: hasFailures ? 1 : 0
  };
}
