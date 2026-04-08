#!/usr/bin/env node
/**
 * select-tier.js - Select test execution tier based on target branch.
 * Exports testable functions. CLI entry point at bottom.
 */

import { resolve } from 'node:path';
import { readManifestFile as readManifestFileAsync } from './lib/manifest.js';
import { readManifestFileSync } from './lib/manifest.js';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** Match a branch name against a pattern (string or array). */
export function matchBranch(branch, pattern) {
  if (pattern === '*') return true;
  const patterns = Array.isArray(pattern) ? pattern : [pattern];
  return patterns.some(p => {
    if (p.includes('*')) {
      const regex = new RegExp('^' + p.replace(/\*/g, '.*') + '$');
      return regex.test(branch);
    }
    return p === branch;
  });
}

/** Validate that catch-all tiers are last in the order. */
export function validateTierOrder(tiers) {
  const entries = Object.entries(tiers);
  for (let i = 0; i < entries.length - 1; i++) {
    const [name, tier] = entries[i];
    if (tier.branches === '*') {
      throw new Error(`Tier "${name}" has branches: "*" (catch-all) but is not the last tier. Catch-all must be checked last.`);
    }
  }
}

/** Select the appropriate tier for a branch. */
export async function selectTier(branch, projectDir) {
  const manifestDir = join(projectDir, 'tests', 'verification-playwright', 'manifest');
  let config;
  try {
    config = JSON.parse(readFileSync(join(manifestDir, 'config.json'), 'utf8'));
  } catch {
    return '';
  }

  if (!config || !config.tiers) return '';

  validateTierOrder(config.tiers);

  const tierOrder = ['full', 'thorough', 'gate'];
  for (const tierName of tierOrder) {
    const tier = config.tiers[tierName];
    if (!tier) continue;
    if (matchBranch(branch, tier.branches)) return tierName;
  }

  return '';
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help')) {
    console.log(`select-tier.js - Select test execution tier based on target branch

Usage: node select-tier.js <branch-name>
       node select-tier.js --help`);
    process.exit(0);
  }

  const branch = process.argv[2];
  if (!branch) process.exit(0);

  const result = await selectTier(branch, process.cwd());
  if (result) process.stdout.write(result);
}
