#!/usr/bin/env node
/**
 * sync-tests.js - Deterministic manifest sync for verification-to-Playwright pipeline.
 * Exports testable functions. CLI entry point at bottom.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, relative, basename, join, sep } from 'node:path';
import { hashItem, hashGeneratedTest } from './lib/hash.js';
import { acquireLockSync, loadManifest, saveManifest, manifestDirFor } from './lib/manifest.js';
import { isEntryPoint } from './lib/repo.js';

// Format A: - [ ] [depth] **ITEM-ID** action text --- outcome. *Expected: type*
// ID allows uppercase, lowercase, digits, hyphens (e.g., EVT-FRM-01a, ML-ART-30).
// This mirrors verification-writer's FORMAT_A_FULL_REGEX exactly — the two must
// agree or the writer's integrity pass reports a doc clean while the manifest
// silently drops its items. Specifically: `[x]` (already-verified) items count,
// the `[depth]` tag is optional, and the outcome clause need not end in a bare
// period (a closing quote or backtick after it is normal prose).
// The body (action + expected) is captured as ONE group and split on ` --- `
// afterwards. Anchoring on the `Expected: type` trailer rather than requiring a
// ` --- ` separator and a literal `*` emphasis is deliberate: ~100 items across
// 27 docs fuse action and expected into one sentence, 37 end the expected clause
// with a closing quote/paren/backtick, and API items append an annotation after
// the trailer (the trailer is not consumed, so content hashes stay stable).
// Requiring the strict shape silently dropped 138 items — they got
// no manifest entry and therefore no test. This was fixed once (42103db5) and
// reverted by 5e91242d, which copied the skill's stricter regex over this file;
// keep the two copies in sync in THIS direction.
const ITEM_PATTERN_A = /^- \[[ x]\] (?:\[(\w+)\] )?\*\*([A-Za-z0-9][-A-Za-z0-9]*)\*\* ([^\n]+?)\s*[_*]Expected: ([^_*\n]+)[_*]/gm;
// Format B: - [ ] [depth] **Action text** --- expected. _Expected: type_  (no separate ID)
const ITEM_PATTERN_B = /^- \[ \] \[(\w+)\] \*\*(.+?)\*\* --- (.+)\. [_*]Expected: (.+?)[_*]/gm;

/** Parse verification items from markdown content. Supports both ID-based and action-based formats.
 * @param {string} markdown - The verification doc content
 * @param {string} [pageTag=''] - Page tag used to scope auto-generated IDs (prevents cross-doc collisions)
 */
// Fenced code blocks hold *examples* of the item grammar (docs/verification/README.md
// documents Format A with a sample line). Parsing them mints phantom items like
// `ITEM-ID` that no doc owns. scan-versions.py already skips fences; this keeps the
// two parsers agreed. Masking with equal-length blanks preserves every offset the
// Format A/B `consumed` ranges depend on.
function maskFencedBlocks(markdown) {
  let inFence = false;
  return markdown
    .split('\n')
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        inFence = !inFence;
        return ' '.repeat(line.length);
      }
      return inFence ? ' '.repeat(line.length) : line;
    })
    .join('\n');
}

export function parseVerificationItems(markdown, pageTag = '') {
  const scan = maskFencedBlocks(markdown);
  const items = [];
  const seen = new Set();
  // Character ranges already claimed by Format A. Format B's pattern also
  // matches a Format A line (its bold group happily swallows `ID** action`),
  // which would mint a phantom slug-derived duplicate of a real item.
  const consumed = [];

  // Try Format A first (has explicit item IDs)
  const patternA = new RegExp(ITEM_PATTERN_A.source, 'gm');
  let match;
  while ((match = patternA.exec(scan)) !== null) {
    const [fullMatch, depthTag, id, body, expectedType] = match;
    const depth = depthTag || 'standard';
    const sep = body.indexOf(' --- ');
    // No separator: the doc fused action and expected into one statement.
    const action = sep === -1 ? body : body.slice(0, sep);
    const expected = sep === -1 ? body : body.slice(sep + 5);
    if (seen.has(id)) continue;
    seen.add(id);
    consumed.push([match.index, match.index + fullMatch.length]);
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
  while ((match = patternB.exec(scan)) !== null) {
    const [fullMatch, depth, actionBold, expected, expectedType] = match;
    if (consumed.some(([start, end]) => match.index >= start && match.index < end)) continue;
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
  // The one loader: migrates an older manifest layout first, then hands back
  // every per-doc items file as one flat {id: entry} map.
  const manifest = loadManifest(manifestDir);

  // Repo-relative source_doc: an absolute path is machine-specific and
  // rewrites every entry the moment anyone syncs from a different checkout.
  // ponytail: manifestDir is always <repo>/tests/verification-playwright/manifest.
  const repoRoot = join(manifestDir, '..', '..', '..');

  const docContent = readFileSync(docPath, 'utf8');
  const pageTag = basename(docPath, '.md');
  const docFilename = basename(docPath);
  const docItems = parseVerificationItems(docContent, pageTag);

  // Scope: only compare against manifest items belonging to THIS doc.
  // Compare the full repo-relative path, not the basename: pages/ and flows/
  // both contain beta-signup.md, and matching on the basename alone made the
  // flows doc treat all 14 of the pages doc's items as removed and delete them
  // from the committed manifest on its first sync.
  // POSIX separators always: relative() yields backslashes on Windows, which
  // would match nothing against the committed manifest, mark every item as
  // added, and rewrite the paths -- then churn back on the next unix sync.
  const docRel = relative(repoRoot, docPath).split(sep).join('/');
  const scopedManifestItems = {};
  for (const [id, item] of Object.entries(manifest.items)) {
    if (item.source_doc === docRel) {
      scopedManifestItems[id] = item;
    }
  }
  const changes = detectChanges(docItems, scopedManifestItems);

  // Process removals. A queued id leaves the queue with its entry, because
  // the queue is the entry's own pending_generation flag.
  for (const removed of changes.removed) {
    delete manifest.items[removed.id];
  }

  // Refuse to write when an added ID is already owned by a different doc.
  // Item IDs are unique across ALL per-doc files (the loader flattens them),
  // so writing here would silently move the other doc's item into this doc's
  // file and drop its test coverage with no error anywhere. Two docs sharing
  // an id_namespace is the usual cause — verification-writer's integrity pass
  // reports that upstream.
  const collisions = changes.added
    .filter((a) => manifest.items[a.id])
    .map((a) => `  ${a.id} — already owned by ${manifest.items[a.id].source_doc}`);
  if (collisions.length > 0) {
    throw new Error(
      `sync-tests: ${collisions.length} item ID collision(s) syncing ${docFilename}; manifest not written.\n` +
        `${collisions.join('\n')}\n` +
        `Give each verification doc a unique id_namespace, then re-run.`
    );
  }

  // Process additions
  const pendingIds = [];
  for (const added of changes.added) {
    manifest.items[added.id] = {
      source_doc: docRel,
      content_hash: added.contentHash,
      depth: added.depth,
      expected_type: added.expectedType,
      status: 'pending',
      pinned: false,
    };
    pendingIds.push(added.id);
  }

  // Process modifications
  for (const mod of changes.modified) {
    const existing = manifest.items[mod.id];
    const classification = classifyModification(mod, existing);
    manifest.items[mod.id].content_hash = mod.contentHash;
    manifest.items[mod.id].source_doc = docRel;
    manifest.items[mod.id].expected_type = mod.expectedType;
    if (classification === 'substantial' && !existing.pinned) {
      pendingIds.push(mod.id);
    }
  }

  // Queue for LLM generation: the flag lives on the entry, in this doc's file.
  for (const id of pendingIds) manifest.items[id].pending_generation = true;

  // Backfill expected_type on entries that predate the field. Without it
  // classifyModification compares a parsed type against undefined and calls
  // every wording edit substantial, queueing regeneration that isn't needed.
  let backfilled = 0;
  for (const item of changes.unchanged) {
    const entry = manifest.items[item.id];
    if (entry && entry.expected_type === undefined) {
      entry.expected_type = item.expectedType;
      backfilled++;
    }
  }

  // saveManifest rewrites only the per-doc files whose content changed, so a
  // no-op sync leaves the tree clean and an edit to one doc touches one file.
  saveManifest(manifest);

  return {
    added: changes.added.length,
    removed: changes.removed.length,
    modified: changes.modified.length,
    unchanged: changes.unchanged.length,
    pendingGeneration: pendingIds.length,
  };
}

/**
 * Resolve the doc to sync: an explicit argument, else the edited file the
 * postToolUse hook hands us on stdin as `{tool_input: {file_path}}`. That hook
 * has no way to interpolate a path into the command, so without the stdin read
 * it invoked the script with nothing to sync and failed on every doc edit.
 *
 * readStdin() returning undefined means no payload is coming (see
 * readStdinWithin); that returns undefined too, vs null for "hook payload,
 * nothing to sync", so the CLI can fail with usage instead of exiting clean.
 */
export function resolveDocArg(argv, readStdin) {
  if (argv[2] && !argv[2].startsWith('-')) return argv[2];
  const text = readStdin();
  if (text === undefined) return undefined;
  let edited;
  try {
    edited = JSON.parse(text)?.tool_input?.file_path;
  } catch {
    return null;
  }
  // The hook fires on every Edit/Write, not just verification docs — ignore
  // anything that isn't one rather than rewriting the manifest for a stray file.
  return /verification\/.*\.md$/.test(edited ?? '') ? edited : null;
}

/**
 * Read all of stdin, or resolve undefined when nothing is coming: stdin is a
 * terminal (run by hand) or an inherited pipe that stays open without writing
 * (run by an agent). A blocking read hangs forever in both. `ms` is an idle
 * bound, reset by every chunk, so a slow writer is never cut off; if a writer
 * goes quiet without closing, whatever it sent is still returned. Closed with
 * nothing sent (`</dev/null`) is "nothing coming" too.
 */
export function readStdinWithin(stream, ms) {
  if (stream.isTTY) return Promise.resolve(undefined);
  return new Promise(done => {
    let text = '';
    const idle = () => { stream.destroy(); done(text || undefined); };
    let timer = setTimeout(idle, ms);
    stream.setEncoding('utf8');
    stream.on('data', chunk => {
      text += chunk;
      clearTimeout(timer);
      timer = setTimeout(idle, ms);
    });
    stream.on('end', () => { clearTimeout(timer); done(text || undefined); });
    stream.on('error', () => { clearTimeout(timer); done(''); });
  });
}

// --- CLI entry point ---
const isMain = isEntryPoint(import.meta.url);
if (isMain) {
  const hasPathArg = process.argv[2] && !process.argv[2].startsWith('-');
  const stdinText = process.argv.includes('--help') || hasPathArg
    ? ''
    : await readStdinWithin(process.stdin, 2000);
  const docArg = process.argv.includes('--help')
    ? null
    : resolveDocArg(process.argv, () => stdinText);

  if (!docArg) {
    // undefined = run by hand with nothing to sync: an error, not a quiet no-op.
    const log = docArg === undefined ? console.error : console.log;
    log(`sync-tests.js - Sync verification docs to Playwright test manifest

Usage: node sync-tests.js <verification-doc-path>
       node sync-tests.js            # hook form: reads {"tool_input":{"file_path":…}} on stdin
       node sync-tests.js --help`);
    process.exit(docArg === undefined ? 2 : 0);
  }

  const docPath = resolve(docArg);
  const projectDir = process.cwd();

  if (!existsSync(docPath)) {
    console.error(`File not found: ${docPath}`);
    process.exit(1);
  }

  const release = acquireLockSync(projectDir);
  try {
    const manifestDir = manifestDirFor(projectDir);
    const result = await syncTests(docPath, manifestDir);
    const parts = [];
    if (result.added) parts.push(`${result.added} added`);
    if (result.modified) parts.push(`${result.modified} modified`);
    if (result.removed) parts.push(`${result.removed} removed`);
    if (result.unchanged) parts.push(`${result.unchanged} unchanged`);
    if (result.pendingGeneration) parts.push(`${result.pendingGeneration} queued`);
    console.log(`sync-tests: ${basename(docPath, '.md')} — ${parts.join(', ') || 'no changes'}`);
  } catch (err) {
    console.error(err.message);
    process.exitCode = 1;
  } finally {
    release();
  }
}
