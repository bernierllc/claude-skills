#!/usr/bin/env node
/**
 * select-tier.js - Select test execution tier based on target branch.
 * Exports testable functions. CLI entry point at bottom.
 */

import { resolve } from 'node:path';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';
import { isEntryPoint } from './lib/repo.js';

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

/**
 * The order tiers are checked in. The first tier whose `branches` matches wins,
 * so the most specific tier has to come first and the catch-all last.
 */
export const TIER_ORDER = ['full', 'thorough', 'gate'];

/**
 * Validate that no catch-all tier shadows a tier checked after it.
 *
 * This walks TIER_ORDER, not the key order of the config object. Key order is
 * whatever JSON.parse preserved and has no bearing on which tier selectTier()
 * picks; validating it rejects a config that lists `gate` first and throws on
 * every branch name, so no tier ever runs.
 */
export function validateTierOrder(tiers, order = TIER_ORDER) {
  const present = order.filter(name => tiers[name]);
  for (let i = 0; i < present.length - 1; i++) {
    const name = present[i];
    const b = tiers[name].branches;
    if (b === '*' || (Array.isArray(b) && b.includes('*'))) {
      throw new Error(`Tier "${name}" has branches: "*" (catch-all) but is checked before ${present.slice(i + 1).map(n => `"${n}"`).join(', ')}, which can therefore never be selected.`);
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

  for (const tierName of TIER_ORDER) {
    const tier = config.tiers[tierName];
    if (!tier) continue;
    if (matchBranch(branch, tier.branches)) return tierName;
  }

  return '';
}

// --- CLI entry point ---
const isMain = isEntryPoint(import.meta.url);
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
