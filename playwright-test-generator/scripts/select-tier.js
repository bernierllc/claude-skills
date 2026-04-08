#!/usr/bin/env node
import { readManifestFile } from './lib/manifest.js';
import { join } from 'node:path';

/**
 * Match a branch name against a pattern (glob-like).
 * Supports '*' as wildcard for all branches.
 */
export function matchBranch(branch, patterns) {
  if (!Array.isArray(patterns)) {
    patterns = [patterns];
  }
  for (const pattern of patterns) {
    if (pattern === '*') return true;
    if (pattern === branch) return true;
    // Simple glob: convert * to regex
    const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
    if (regex.test(branch)) return true;
  }
  return false;
}

/**
 * Validate that catch-all tier (*) is last in the tier order.
 * Tiers are checked in the order: full, thorough, gate.
 */
export function validateTierOrder(tiers) {
  const tierNames = Object.keys(tiers);
  for (let i = 0; i < tierNames.length - 1; i++) {
    const tier = tiers[tierNames[i]];
    const branches = Array.isArray(tier.branches) ? tier.branches : [tier.branches];
    if (branches.includes('*')) {
      throw new Error(
        `Catch-all tier '${tierNames[i]}' must be last, but it appears before '${tierNames[i + 1]}'`
      );
    }
  }
}

/**
 * Select the tier for a given branch.
 * Checks tiers in order: full -> thorough -> gate (most restrictive first).
 * Returns tier name or empty string if no match.
 */
export async function selectTier(branch, projectRoot) {
  const configPath = join(projectRoot, 'tests', 'verification-playwright', 'manifest', 'config.json');
  const config = await readManifestFile(configPath);

  if (!config || !config.tiers) {
    return '';
  }

  validateTierOrder(config.tiers);

  // Check tiers in defined order
  for (const [tierName, tierConfig] of Object.entries(config.tiers)) {
    if (matchBranch(branch, tierConfig.branches)) {
      return tierName;
    }
  }

  return '';
}
