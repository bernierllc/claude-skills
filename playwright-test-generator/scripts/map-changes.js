#!/usr/bin/env node
/**
 * map-changes.js - Map changed files to affected verification test tags.
 * Used by pre-commit and pre-push hooks to scope Playwright test execution.
 *
 * Usage: node map-changes.js [file1.tsx file2.py ...]
 *        node map-changes.js --since-main
 *        node map-changes.js --help
 */

import { existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { basename } from 'node:path';
import { readManifestFile } from './lib/manifest.js';

if (process.argv.includes('--help')) {
  console.log(`map-changes.js - Map changed files to affected test tags

Usage: node map-changes.js [file1.tsx file2.py ...]
       node map-changes.js --since-main
       node map-changes.js --help

Maps source files and verification docs to @page-tag values via the import index.
Output: space-separated @tags to stdout.`);
  process.exit(0);
}

const projectDir = process.cwd();
const importIndex = readManifestFile(projectDir, 'import-index.json');

if (!importIndex) {
  // Pipeline not initialized — output nothing, exit clean
  process.exit(0);
}

// Get file list
let files;
if (process.argv.includes('--since-main')) {
  try {
    const mergeBase = execSync('git merge-base HEAD main', { encoding: 'utf8' }).trim();
    const diff = execSync(`git diff --name-only ${mergeBase}..HEAD`, { encoding: 'utf8' });
    files = diff.trim().split('\n').filter(Boolean);
  } catch {
    // Can't determine merge base — output nothing
    process.exit(0);
  }
} else {
  files = process.argv.slice(2).filter(f => f !== '--since-main');
}

if (files.length === 0) {
  process.exit(0);
}

const tags = new Set();

for (const file of files) {
  // Verification docs map directly to page tags
  if (file.startsWith('docs/verification/')) {
    const tag = basename(file, '.md');
    tags.add(`@${tag}`);
    continue;
  }

  // Source files — look up in import index
  const entries = importIndex.entries || {};
  const pageTags = entries[file];

  if (pageTags) {
    // Validate the source file still exists
    if (!existsSync(file)) {
      process.stderr.write(`Warning: Index entry "${file}" is stale (file no longer exists)\n`);
      continue;
    }
    for (const tag of pageTags) {
      tags.add(`@${tag}`);
    }
  } else {
    // File not in index — warn but don't fail
    if (!file.startsWith('tests/verification-playwright/') && !file.startsWith('.')) {
      process.stderr.write(`Warning: File "${file}" not in import index — run playwright-test-generator to refresh\n`);
    }
  }
}

if (tags.size > 0) {
  process.stdout.write([...tags].join(' '));
}
