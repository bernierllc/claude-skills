#!/usr/bin/env node
/**
 * sync-tests.js - Deterministic manifest sync for verification-to-Playwright pipeline.
 * Exports testable functions. CLI entry point at bottom.
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, basename, join } from 'node:path';
import { hashItem, hashGeneratedTest } from './lib/hash.js';
import { readManifestFileSync, writeManifestFileSync, acquireLockSync, appendPendingQueue } from './lib/manifest.js';
import { fileURLToPath } from 'node:url';

// Format A: - [ ] [depth] **ITEM-ID** action text --- expected. *Expected: type*
const ITEM_PATTERN_A = /^- \[ \] \[(\w+)\] \*\*([A-Z0-9][-A-Z0-9]*)\*\* (.+?) --- (.+)\. \*Expected: (.+)\*/gm;
// Format B: - [ ] [depth] **Action text** --- expected. _Expected: type_  (no separate ID)
const ITEM_PATTERN_B = /^- \[ \] \[(\w+)\] \*\*(.+?)\*\* --- (.+)\. [_*]Expected: (.+?)[_*]/gm;

/** Parse verification items from markdown content. Supports both ID-based and action-based formats.
 * @param {string} markdown - The verification doc content
 * @param {string} [pageTag=''] - Page tag used to scope auto-generated IDs (prevents cross-doc collisions)
 */
export function parseVerificationItems(markdown, pageTag = '') {
  const items = [];
  const seen = new Set();

  // Try Format A first (has explicit item IDs)
  const patternA = new RegExp(ITEM_PATTERN_A.source, 'gm');
  let match;
  while ((match = patternA.exec(markdown)) !== null) {
    const [fullMatch, depth, id, action, expected, expectedType] = match;
    if (seen.has(id)) continue;
    seen.add(id);
    const afterMatch = markdown.substring(match.index + fullMatch.length);
    const annotationMatch = afterMatch.match(/\n(<!--[\s\S]*?-->)/);
    const annotation = annotationMatch ? annotationMatch[1] : '';
    const fullText = fullMatch + (annotation ? '\n' + annotation : '');
    items.push({
      id, depth, action, expected, expectedType,
      contentHash: hashItem(id, fullText),
      fullText
    });
  }

  // Try Format B for items not caught by Format A (action-as-bold, no ID)
  const patternB = new RegExp(ITEM_PATTERN_B.source, 'gm');
  while ((match = patternB.exec(markdown)) !== null) {
    const [fullMatch, depth, actionBold, expected, expectedType] = match;
    // Generate a stable ID from the action text (slugify)
    const id = slugifyAction(actionBold, pageTag);
    if (seen.has(id)) continue;
    seen.add(id);
    const afterMatch = markdown.substring(match.index + fullMatch.length);
    const annotationMatch = afterMatch.match(/\n(<!--[\s\S]*?-->)/);
    const annotation = annotationMatch ? annotationMatch[1] : '';
    const fullText = fullMatch + (annotation ? '\n' + annotation : '');
    items.push({
      id, depth, action: actionBold, expected, expectedType,
      contentHash: hashItem(id, fullText),
      fullText
    });
  }

  return items;
}

/** Generate a stable ID from action text, scoped to the doc page tag to prevent collisions. */
function slugifyAction(text, pageTag) {
  const slug = text
    .replace(/`[^`]*`/g, '') // Remove inline code
    .replace(/[^a-zA-Z0-9\s-]/g, '') // Remove special chars
    .trim()
    .replace(/\s+/g, '-') // Spaces to dashes
    .toLowerCase()
    .substring(0, 40) // Cap length
    .replace(/-+$/, ''); // Trim trailing dashes
  // Prefix with page tag to prevent collisions across docs
  return `${pageTag}--${slug}`;
}

/** Detect changes between doc items and manifest items. */
export function detectChanges(docItems, manifestItems) {
  const added = [];
  const removed = [];
  const modified = [];
  const unchanged = [];

  const docMap = new Map(docItems.map(i => [i.id, i]));
  const manifestIds = new Set(Object.keys(manifestItems));

  // Removed: in manifest but not in doc
  for (const id of manifestIds) {
    if (!docMap.has(id)) {
      removed.push({ id, ...manifestItems[id] });
    }
  }

  // Added or modified
  for (const item of docItems) {
    const existing = manifestItems[item.id];
    if (!existing) {
      added.push(item);
    } else if (existing.content_hash !== item.contentHash) {
      modified.push(item);
    } else {
      unchanged.push(item);
    }
  }

  return { added, removed, modified, unchanged };
}

/** Classify a modification as minor or substantial. */
export function classifyModification(item, manifestEntry) {
  if (item.depth !== manifestEntry.depth) return 'substantial';
  if (item.expectedType !== manifestEntry.expected_type) return 'substantial';
  return 'minor';
}

/** Remove a test block between @begin:ID / @end:ID markers from spec content. */
export function removeTestBlock(specContent, itemId) {
  const beginMarker = `// @begin:${itemId}`;
  const endMarker = `// @end:${itemId}`;
  const beginIdx = specContent.indexOf(beginMarker);
  const endIdx = specContent.indexOf(endMarker);
  if (beginIdx === -1 || endIdx === -1) return specContent;
  const before = specContent.substring(0, beginIdx);
  const after = specContent.substring(endIdx + endMarker.length);
  return before + after.replace(/^\n/, '');
}

/** Detect if a test has been manually edited (pinning). */
export function detectPinning(specContent, itemId, generatedHash) {
  const beginMarker = `// @begin:${itemId}`;
  const endMarker = `// @end:${itemId}`;
  const beginIdx = specContent.indexOf(beginMarker);
  const endIdx = specContent.indexOf(endMarker);
  if (beginIdx === -1 || endIdx === -1) return false;
  const block = specContent.substring(beginIdx + beginMarker.length, endIdx);
  const currentHash = hashGeneratedTest(block);
  return currentHash !== generatedHash;
}

/** Run the full sync operation. */
export async function syncTests(docPath, manifestDir) {
  const itemsPath = join(manifestDir, 'items.json');
  let items;
  try {
    items = JSON.parse(readFileSync(itemsPath, 'utf8'));
  } catch {
    items = { version: '1.0', items: {} };
  }

  const docContent = readFileSync(docPath, 'utf8');
  const pageTag = basename(docPath, '.md');
  const docItems = parseVerificationItems(docContent, pageTag);

  // Scope: only compare against manifest items belonging to THIS doc
  const docFilename = basename(docPath);
  const scopedManifestItems = {};
  for (const [id, item] of Object.entries(items.items)) {
    if (item.source_doc && basename(item.source_doc) === docFilename) {
      scopedManifestItems[id] = item;
    }
  }
  const changes = detectChanges(docItems, scopedManifestItems);

  // Process removals
  for (const removed of changes.removed) {
    delete items.items[removed.id];
  }

  // Process additions
  const pendingIds = [];
  for (const added of changes.added) {
    items.items[added.id] = {
      source_doc: docPath,
      content_hash: added.contentHash,
      depth: added.depth,
      status: 'pending',
      pinned: false,
    };
    pendingIds.push(added.id);
  }

  // Process modifications
  for (const mod of changes.modified) {
    const existing = items.items[mod.id];
    const classification = classifyModification(mod, existing);
    items.items[mod.id].content_hash = mod.contentHash;
    if (classification === 'substantial' && !existing.pinned) {
      pendingIds.push(mod.id);
    }
  }

  // Write pending queue
  if (pendingIds.length > 0) {
    const pendingPath = join(manifestDir, '..', 'pending-generation.json');
    let existing = [];
    try { existing = JSON.parse(readFileSync(pendingPath, 'utf8')); } catch {}
    const merged = [...new Set([...existing, ...pendingIds])];
    writeFileSync(pendingPath, JSON.stringify(merged, null, 2) + '\n', 'utf8');
  }

  // Write updated manifest
  items.generated_at = new Date().toISOString();
  writeFileSync(itemsPath, JSON.stringify(items, null, 2) + '\n', 'utf8');

  return {
    added: changes.added.length,
    removed: changes.removed.length,
    modified: changes.modified.length,
    unchanged: changes.unchanged.length,
    pendingGeneration: pendingIds.length,
  };
}

// --- CLI entry point ---
const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  if (process.argv.includes('--help') || process.argv.length < 3) {
    console.log(`sync-tests.js - Sync verification docs to Playwright test manifest

Usage: node sync-tests.js <verification-doc-path>
       node sync-tests.js --help`);
    process.exit(0);
  }

  const docPath = resolve(process.argv[2]);
  const projectDir = process.cwd();

  if (!existsSync(docPath)) {
    console.error(`File not found: ${docPath}`);
    process.exit(1);
  }

  const release = acquireLockSync(projectDir);
  try {
    const manifestDir = join(projectDir, 'tests', 'verification-playwright', 'manifest');
    const result = await syncTests(docPath, manifestDir);
    const parts = [];
    if (result.added) parts.push(`${result.added} added`);
    if (result.modified) parts.push(`${result.modified} modified`);
    if (result.removed) parts.push(`${result.removed} removed`);
    if (result.unchanged) parts.push(`${result.unchanged} unchanged`);
    if (result.pendingGeneration) parts.push(`${result.pendingGeneration} queued`);
    console.log(`sync-tests: ${basename(docPath, '.md')} — ${parts.join(', ') || 'no changes'}`);
  } finally {
    release();
  }
}
