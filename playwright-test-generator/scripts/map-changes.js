#!/usr/bin/env node
/**
 * map-changes.js - Map changed files to affected verification test tags.
 * Exports testable functions. CLI entry point at bottom.
 */

import { existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { basename, join, resolve } from 'node:path';
import { readManifestFileSync } from './lib/manifest.js';
import { fileURLToPath } from 'node:url';

/** Map file list to affected page tags using an import index. */
export async function mapFilesToTags(files, importIndex, projectDir) {
  const tags = new Set();
  const warnings = [];

  if (!importIndex) return { tags: [], warnings: [] };

  for (const file of files) {
    if (file.startsWith('docs/verification/')) {
      tags.add(`@${basename(file, '.md')}`);
      continue;
    }

    const entries = importIndex.entries || {};
    const pageTags = entries[file];

    if (pageTags) {
      const fullPath = join(projectDir, file);
      if (!existsSync(fullPath)) {
        warnings.push(`Index entry "${file}" is stale (file no longer exists)`);
        continue;
      }
      for (const tag of pageTags) {
        tags.add(`@${tag}`);
      }
    } else if (!file.startsWith('tests/verification-playwright/') && !file.startsWith('.')) {
      warnings.push(`File "${file}" not in import index — run playwright-test-generator to refresh`);
    }
  }

  return { tags: [...tags], warnings };
}

/** Main entry for CLI and testing. */
export async function main(args, projectDir) {
  const importIndex = readManifestFileSync(projectDir, 'import-index.json');
  if (!importIndex) return { tags: [], warnings: [] };

  let files;
  if (args.includes('--since-main')) {
    try {
      const mergeBase = execSync('git merge-base HEAD main', { encoding: 'utf8', cwd: projectDir }).trim();
      const diff = execSync(`git diff --name-only ${mergeBase}..HEAD`, { encoding: 'utf8', cwd: projectDir });
      files = diff.trim().split('\n').filter(Boolean);
    } catch {
      return { tags: [], warnings: [] };
    }
  } else {
    files = args.filter(f => f !== '--since-main' && f !== '--help');
  }

  return mapFilesToTags(files, importIndex, projectDir);
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`map-changes.js - Map changed files to affected test tags

Usage: node map-changes.js [file1.tsx file2.py ...]
       node map-changes.js --since-main
       node map-changes.js --help`);
    process.exit(0);
  }

  const result = await main(process.argv.slice(2), process.cwd());
  for (const w of result.warnings) process.stderr.write(`Warning: ${w}\n`);
  if (result.tags.length > 0) process.stdout.write(result.tags.join(' '));
}
