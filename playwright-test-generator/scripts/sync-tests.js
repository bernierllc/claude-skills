#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { hashItem } from './lib/hash.js';
import { readManifestFile, writeManifestFile, acquireLock, releaseLock } from './lib/manifest.js';

/**
 * Parse verification items from a markdown doc.
 * Pattern: - [ ] [depth] **ID** action --- expected. *Expected: type*
 */
export function parseVerificationItems(markdown) {
  const items = [];
  const lines = markdown.split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const lineMatch = line.match(/^- \[ \] \[(\w+)\] \*\*([A-Z0-9-]+)\*\*\s+(.+)/);
    if (lineMatch) {
      const depth = lineMatch[1];
      const id = lineMatch[2];
      const text = lineMatch[3];

      // Collect continuation lines and annotation blocks
      let fullText = line;
      let j = i + 1;
      while (j < lines.length && !lines[j].match(/^- \[ \]/) && !lines[j].match(/^#/)) {
        fullText += '\n' + lines[j];
        j++;
      }

      // Parse expected type from text
      const expectedMatch = text.match(/\*Expected:\s*(.+?)\*/);
      const expectedType = expectedMatch ? expectedMatch[1].trim() : null;

      // Extract action and expected from --- separator
      const parts = text.split('---');
      const action = parts[0].trim();
      const expected = parts.length > 1 ? parts[1].trim() : '';

      items.push({
        id,
        depth,
        action,
        expected,
        expectedType,
        fullText,
        contentHash: hashItem(id, fullText)
      });
      i = j;
    } else {
      i++;
    }
  }
  return items;
}

/**
 * Detect changes between parsed doc items and the manifest.
 */
export function detectChanges(docItems, manifestItems) {
  const docMap = new Map(docItems.map(item => [item.id, item]));
  const manifestMap = new Map(Object.entries(manifestItems || {}));

  const added = [];
  const removed = [];
  const modified = [];
  const unchanged = [];

  for (const [id, item] of docMap) {
    if (!manifestMap.has(id)) {
      added.push(item);
    } else {
      const mItem = manifestMap.get(id);
      if (mItem.content_hash !== item.contentHash) {
        modified.push({ item, manifestEntry: mItem });
      } else {
        unchanged.push(item);
      }
    }
  }

  for (const [id, mItem] of manifestMap) {
    if (!docMap.has(id)) {
      removed.push({ id, ...mItem });
    }
  }

  return { added, removed, modified, unchanged };
}

/**
 * Classify a modification as minor or substantial.
 * Minor: same depth + same expected type, only description text changed.
 * Substantial: depth or expected type changed.
 */
export function classifyModification(item, manifestEntry) {
  const depthChanged = item.depth !== manifestEntry.depth;
  const typeChanged = item.expectedType !== manifestEntry.expected_type;

  if (depthChanged || typeChanged) {
    return 'substantial';
  }
  return 'minor';
}

/**
 * Remove test code between @begin:ID / @end:ID markers.
 */
export function removeTestBlock(specContent, itemId) {
  const beginMarker = `// @begin:${itemId}`;
  const endMarker = `// @end:${itemId}`;
  const beginIdx = specContent.indexOf(beginMarker);
  const endIdx = specContent.indexOf(endMarker);

  if (beginIdx === -1 || endIdx === -1) return specContent;

  const endOfEndMarker = endIdx + endMarker.length;
  const after = specContent.slice(endOfEndMarker);
  const trimmedAfter = after.startsWith('\n') ? after.slice(1) : after;

  return specContent.slice(0, beginIdx) + trimmedAfter;
}

/**
 * Detect if a test has been manually edited (pinned).
 * Compares the actual test code hash against generated_hash in manifest.
 */
export function detectPinning(specContent, itemId, generatedHash) {
  const beginMarker = `// @begin:${itemId}`;
  const endMarker = `// @end:${itemId}`;
  const beginIdx = specContent.indexOf(beginMarker);
  const endIdx = specContent.indexOf(endMarker);

  if (beginIdx === -1 || endIdx === -1) return false;

  const testCode = specContent.slice(beginIdx, endIdx + endMarker.length);
  const actualHash = hashItem(itemId, testCode);
  return actualHash !== generatedHash;
}

/**
 * Main sync entry point.
 */
export async function syncTests(verificationDocPath, manifestDir) {
  const docContent = await readFile(verificationDocPath, 'utf-8');
  const items = parseVerificationItems(docContent);

  await acquireLock(manifestDir);
  try {
    const itemsManifest = await readManifestFile(join(manifestDir, 'items.json'));
    const manifestItems = itemsManifest?.items || {};

    const changes = detectChanges(items, manifestItems);
    const pendingGeneration = [];

    for (const removed of changes.removed) {
      delete manifestItems[removed.id];
    }

    for (const { item, manifestEntry } of changes.modified) {
      const classification = classifyModification(item, manifestEntry);
      if (classification === 'substantial') {
        pendingGeneration.push(item.id);
      }
      manifestItems[item.id] = {
        ...manifestEntry,
        content_hash: item.contentHash,
        depth: item.depth,
        expected_type: item.expectedType
      };
    }

    for (const item of changes.added) {
      pendingGeneration.push(item.id);
      manifestItems[item.id] = {
        content_hash: item.contentHash,
        depth: item.depth,
        expected_type: item.expectedType,
        status: 'pending',
        pinned: false
      };
    }

    await writeManifestFile(join(manifestDir, 'items.json'), {
      version: '1.0',
      items: manifestItems
    });

    if (pendingGeneration.length > 0) {
      const pendingPath = join(manifestDir, '..', 'pending-generation.json');
      let existing = [];
      try {
        const raw = await readFile(pendingPath, 'utf-8');
        existing = JSON.parse(raw);
      } catch { /* file may not exist */ }

      const merged = [...new Set([...existing, ...pendingGeneration])];
      await writeFile(pendingPath, JSON.stringify(merged, null, 2) + '\n');
    }

    return {
      added: changes.added.length,
      removed: changes.removed.length,
      modified: changes.modified.length,
      unchanged: changes.unchanged.length,
      pendingGeneration: pendingGeneration.length
    };
  } finally {
    await releaseLock(manifestDir);
  }
}
