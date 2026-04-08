#!/usr/bin/env node
/**
 * sync-tests.js - Deterministic manifest sync for verification-to-Playwright pipeline.
 * Called by the postToolUse hook when verification docs are edited.
 * No LLM involvement - handles mechanical operations only.
 *
 * Usage: node sync-tests.js <changed-verification-doc-path>
 *        node sync-tests.js --help
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { hashItem, hashGeneratedTest } from './lib/hash.js';
import { readManifestFile, writeManifestFile, acquireLock, appendPendingQueue } from './lib/manifest.js';

const ITEM_PATTERN = /^- \[ \] \[(\w+)\] \*\*([A-Z0-9][-A-Z0-9]*)\*\* (.+?) --- (.+)\. \*Expected: (.+)\*/gm;

if (process.argv.includes('--help') || process.argv.length < 3) {
  console.log(`sync-tests.js - Sync verification docs to Playwright test manifest

Usage: node sync-tests.js <verification-doc-path>
       node sync-tests.js --help

Reads the verification doc, computes content hashes, and updates the manifest.
New or substantially changed items are queued in pending-generation.json
for the LLM-powered skill to process.`);
  process.exit(0);
}

const docPath = resolve(process.argv[2]);
const projectDir = process.cwd();

if (!existsSync(docPath)) {
  console.error(`File not found: ${docPath}`);
  process.exit(1);
}

// Acquire lock
const release = acquireLock(projectDir);

try {
  const items = readManifestFile(projectDir, 'items.json') || { version: '1.0', generated_at: new Date().toISOString(), items: {} };
  const docContent = readFileSync(docPath, 'utf8');
  const pageTag = basename(docPath, '.md');

  // Parse items from the doc
  const docItems = new Map();
  let match;
  while ((match = ITEM_PATTERN.exec(docContent)) !== null) {
    const [fullMatch, depth, id, action, expected, expectedType] = match;
    // Capture annotation block if present (lines after the item until next item or section)
    const afterMatch = docContent.substring(match.index + fullMatch.length);
    const annotationMatch = afterMatch.match(/\n(<!--[\s\S]*?-->)/);
    const annotation = annotationMatch ? annotationMatch[1] : '';
    const fullText = fullMatch + (annotation ? '\n' + annotation : '');

    docItems.set(id, { depth, action, expected, expectedType, hash: hashItem(fullText), fullText });
  }

  // Find items in manifest belonging to this doc
  const manifestItemsForDoc = new Map();
  for (const [id, item] of Object.entries(items.items)) {
    if (item.source_doc && item.source_doc.endsWith(basename(docPath))) {
      manifestItemsForDoc.set(id, item);
    }
  }

  let added = 0, removed = 0, modified = 0, unchanged = 0, queued = 0;
  const pendingIds = [];

  // Process removals (in manifest but not in doc)
  for (const [id, item] of manifestItemsForDoc) {
    if (!docItems.has(id)) {
      // Remove from manifest
      delete items.items[id];
      // Remove from spec file if it exists
      if (item.spec_file && existsSync(item.spec_file)) {
        removeTestBlock(item.spec_file, id);
      }
      removed++;
    }
  }

  // Process additions and modifications
  for (const [id, docItem] of docItems) {
    const existing = items.items[id];

    if (!existing) {
      // New item — queue for LLM generation
      items.items[id] = {
        source_doc: docPath,
        spec_file: `tests/verification-playwright/pages/${pageTag}.spec.ts`,
        content_hash: docItem.hash,
        generated_hash: null,
        depth: docItem.depth,
        status: 'pending',
        pinned: false,
        testids_required: [],
        testids_missing: [],
      };
      pendingIds.push(id);
      added++;
      queued++;
    } else if (existing.content_hash !== docItem.hash) {
      // Changed — determine if minor or substantial
      const isMinor = existing.depth === docItem.depth && isStructureSame(existing, docItem);

      if (isMinor) {
        // Minor text change — update hash, update comment in test
        items.items[id].content_hash = docItem.hash;
        modified++;
      } else {
        // Substantial change — queue for LLM regeneration
        items.items[id].content_hash = docItem.hash;
        items.items[id].depth = docItem.depth;
        if (!existing.pinned) {
          pendingIds.push(id);
          queued++;
        }
        modified++;
      }
    } else {
      unchanged++;
    }
  }

  // Check for pinning (manual edits to generated tests)
  for (const [id, item] of Object.entries(items.items)) {
    if (item.generated_hash && item.spec_file && existsSync(item.spec_file) && !item.pinned) {
      const currentTestHash = getTestBlockHash(item.spec_file, id);
      if (currentTestHash && currentTestHash !== item.generated_hash) {
        items.items[id].pinned = true;
      }
    }
  }

  // Queue pending items
  if (pendingIds.length > 0) {
    appendPendingQueue(projectDir, pendingIds);
  }

  // Update manifest
  items.generated_at = new Date().toISOString();
  writeManifestFile(projectDir, 'items.json', items);

  // Summary
  const parts = [];
  if (added) parts.push(`${added} added`);
  if (modified) parts.push(`${modified} modified`);
  if (removed) parts.push(`${removed} removed`);
  if (unchanged) parts.push(`${unchanged} unchanged`);
  if (queued) parts.push(`${queued} queued for generation`);
  console.log(`sync-tests: ${pageTag} — ${parts.join(', ') || 'no changes'}`);
} finally {
  release();
}

function isStructureSame(existing, docItem) {
  // Same depth and same general structure = minor change
  return existing.depth === docItem.depth;
}

function removeTestBlock(specFile, itemId) {
  try {
    const content = readFileSync(specFile, 'utf8');
    const beginMarker = `// @begin:${itemId}`;
    const endMarker = `// @end:${itemId}`;
    const beginIdx = content.indexOf(beginMarker);
    const endIdx = content.indexOf(endMarker);
    if (beginIdx !== -1 && endIdx !== -1) {
      const before = content.substring(0, beginIdx);
      const after = content.substring(endIdx + endMarker.length);
      writeFileSync(specFile, before + after.replace(/^\n/, ''), 'utf8');
    }
  } catch { /* spec file issues are non-fatal */ }
}

function getTestBlockHash(specFile, itemId) {
  try {
    const content = readFileSync(specFile, 'utf8');
    const beginMarker = `// @begin:${itemId}`;
    const endMarker = `// @end:${itemId}`;
    const beginIdx = content.indexOf(beginMarker);
    const endIdx = content.indexOf(endMarker);
    if (beginIdx !== -1 && endIdx !== -1) {
      const block = content.substring(beginIdx + beginMarker.length, endIdx);
      return hashGeneratedTest(block);
    }
  } catch { /* non-fatal */ }
  return null;
}
