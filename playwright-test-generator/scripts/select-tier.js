#!/usr/bin/env node
/**
 * select-tier.js - Select test execution tier based on target branch.
 * Reads manifest/config.json and matches branch to tier configuration.
 *
 * Usage: node select-tier.js <branch-name>
 *        node select-tier.js --help
 */

import { readManifestFile } from './lib/manifest.js';

if (process.argv.includes('--help')) {
  console.log(`select-tier.js - Select test execution tier based on target branch

Usage: node select-tier.js <branch-name>
       node select-tier.js --help

Reads manifest/config.json and matches the branch against tier configurations.
Tiers are checked in order: full -> thorough -> gate.
Output: tier name to stdout, or empty string if no match.`);
  process.exit(0);
}

const branch = process.argv[2];
if (!branch) {
  process.exit(0);
}

const projectDir = process.cwd();
const config = readManifestFile(projectDir, 'config.json');

if (!config || !config.tiers) {
  process.exit(0);
}

// Validate: catch-all tier must be last
const tierNames = Object.keys(config.tiers);
const tierOrder = ['full', 'thorough', 'gate'];

// Check for catch-all not in last position
for (let i = 0; i < tierNames.length - 1; i++) {
  const tier = config.tiers[tierNames[i]];
  if (tier.branches === '*') {
    process.stderr.write(`Error: Tier "${tierNames[i]}" has branches: "*" (catch-all) but is not the last tier. Catch-all must be checked last.\n`);
    process.exit(1);
  }
}

// Check tiers in order: most restrictive first
for (const tierName of tierOrder) {
  const tier = config.tiers[tierName];
  if (!tier) continue;

  if (matchesBranch(branch, tier.branches)) {
    process.stdout.write(tierName);
    process.exit(0);
  }
}

// No match
process.exit(0);

function matchesBranch(branch, pattern) {
  if (pattern === '*') return true;

  const patterns = Array.isArray(pattern) ? pattern : [pattern];
  return patterns.some(p => {
    // Simple glob matching: * matches any string
    if (p.includes('*')) {
      const regex = new RegExp('^' + p.replace(/\*/g, '.*') + '$');
      return regex.test(branch);
    }
    return p === branch;
  });
}
