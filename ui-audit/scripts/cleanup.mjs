#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { getRepoRoot } from './repo-utils.mjs';

/**
 * Cleanup script to safely remove CONTEXT_CACHE/UI_AUDIT/* after audit cycle
 * Preserves bootstrap files (bootstrap.mjs, schema.sql)
 */
function cleanupAuditCache() {
  const repoRoot = getRepoRoot();
  const auditDir = path.join(repoRoot, 'CONTEXT_CACHE', 'UI_AUDIT');

  if (!fs.existsSync(auditDir)) {
    console.log('No CONTEXT_CACHE/UI_AUDIT directory found. Nothing to clean up.');
    return;
  }

  console.log(`Cleaning up ${auditDir}...`);

  // Remove all contents of UI_AUDIT directory
  const entries = fs.readdirSync(auditDir, { withFileTypes: true });
  let removedCount = 0;

  for (const entry of entries) {
    const entryPath = path.join(auditDir, entry.name);
    try {
      if (entry.isDirectory()) {
        fs.rmSync(entryPath, { recursive: true, force: true });
        removedCount++;
        console.log(`Removed directory: ${entry.name}`);
      } else {
        fs.unlinkSync(entryPath);
        removedCount++;
        console.log(`Removed file: ${entry.name}`);
      }
    } catch (e) {
      console.error(`Failed to remove ${entryPath}: ${e.message}`);
    }
  }

  console.log(`Cleanup complete. Removed ${removedCount} items.`);
  console.log(`Note: Bootstrap files (ui_audit.db, schema.sql) are preserved in CONTEXT_CACHE/`);
}

// Run if executed directly
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  cleanupAuditCache();
}

export { cleanupAuditCache };

