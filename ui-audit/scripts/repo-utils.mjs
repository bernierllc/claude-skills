#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { exec } from 'node:child_process';

/**
 * Detect git repository root, handling worktrees.
 * Uses git rev-parse --show-toplevel which works for both regular repos and worktrees.
 */
function getRepoRoot() {
  try {
    const { execSync } = require('child_process');
    const stdout = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' });
    return stdout.trim();
  } catch (e) {
    throw new Error('Not in a git repository. Please run this from within a git repository.');
  }
}

/**
 * Ensure CONTEXT_CACHE directory exists at repo root and is in .gitignore
 */
function ensureContextCache() {
  const repoRoot = getRepoRoot();
  const cacheDir = path.join(repoRoot, 'CONTEXT_CACHE');
  const gitignorePath = path.join(repoRoot, '.gitignore');

  // Create CONTEXT_CACHE directory
  if (!fs.existsSync(cacheDir)) {
    fs.mkdirSync(cacheDir, { recursive: true });
    console.log(`Created CONTEXT_CACHE directory at: ${cacheDir}`);
  } else {
    console.log(`CONTEXT_CACHE directory exists at: ${cacheDir}`);
  }

  // Ensure .gitignore contains CONTEXT_CACHE/
  if (!fs.existsSync(gitignorePath)) {
    fs.writeFileSync(gitignorePath, 'CONTEXT_CACHE/\n', 'utf8');
    console.log(`Created .gitignore with CONTEXT_CACHE/`);
  } else {
    const gi = fs.readFileSync(gitignorePath, 'utf8');
    if (!gi.split(/\r?\n/).some(line => line.trim() === 'CONTEXT_CACHE/')) {
      fs.appendFileSync(gitignorePath, '\nCONTEXT_CACHE/\n', 'utf8');
      console.log(`Added CONTEXT_CACHE/ to .gitignore`);
    } else {
      console.log('.gitignore already contains CONTEXT_CACHE/');
    }
  }

  return { repoRoot, cacheDir };
}

// Run if executed directly
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  const { repoRoot, cacheDir } = ensureContextCache();
  console.log(`Repo root: ${repoRoot}`);
  console.log(`CONTEXT_CACHE: ${cacheDir}`);
}

export { getRepoRoot, ensureContextCache };

