#!/usr/bin/env node
import { join, basename, extname } from 'node:path';
import { execSync } from 'node:child_process';
import { readManifestFile } from './lib/manifest.js';
import { fileExists } from './lib/fs.js';

/**
 * Map changed files to affected page tags using the import index.
 * @param {string[]} files - Changed file paths
 * @param {object} importIndex - The import-index.json data
 * @param {string} projectRoot - Project root directory
 * @returns {Promise<{ tags: string[], warnings: string[] }>}
 */
export async function mapFilesToTags(files, importIndex, projectRoot) {
  const tags = new Set();
  const warnings = [];

  if (!importIndex || !importIndex.entries) {
    return { tags: [], warnings: [] };
  }

  for (const file of files) {
    // Verification docs map directly via filename
    if (file.startsWith('docs/verification/')) {
      const tag = basename(file, extname(file));
      tags.add(`@${tag}`);
      continue;
    }

    // Source files: look up in import index
    if (importIndex.entries[file]) {
      // Validate the file still exists
      const fullPath = join(projectRoot, file);
      const exists = await fileExists(fullPath);
      if (!exists) {
        warnings.push(`Index entry '${file}' is stale (file no longer exists)`);
        continue;
      }

      for (const pageTag of importIndex.entries[file]) {
        tags.add(`@${pageTag}`);
      }
    } else {
      warnings.push(`File '${file}' not in import index — run playwright-test-generator to refresh`);
    }
  }

  return { tags: [...tags], warnings };
}

/**
 * Get changed files since branching from main.
 */
export function getChangedFilesSinceMain() {
  const mergeBase = execSync('git merge-base HEAD main', { encoding: 'utf-8' }).trim();
  const output = execSync(`git diff --name-only ${mergeBase}..HEAD`, { encoding: 'utf-8' });
  return output.trim().split('\n').filter(Boolean);
}

/**
 * Main entry point for map-changes.
 */
export async function main(args, projectRoot) {
  const manifestDir = join(projectRoot, 'tests', 'verification-playwright', 'manifest');
  const importIndex = await readManifestFile(join(manifestDir, 'import-index.json'));

  if (!importIndex) {
    return { tags: [], warnings: [] };
  }

  let files;
  if (args.includes('--since-main')) {
    files = getChangedFilesSinceMain();
  } else {
    files = args.filter(a => !a.startsWith('--'));
  }

  return mapFilesToTags(files, importIndex, projectRoot);
}
