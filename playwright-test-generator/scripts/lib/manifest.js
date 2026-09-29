/**
 * Manifest file operations with lockfile-based concurrency safety, and the
 * ONE loader/saver for the on-disk manifest layout (see "Manifest layout"
 * below). No script reads or writes items / import-index / queue state by
 * path; they all go through loadManifest() / saveManifest(), which run the
 * layout migration first.
 */

import { readFile, writeFile, mkdir, unlink, rename, access, stat } from 'node:fs/promises';
import { readFileSync, writeFileSync, mkdirSync, existsSync, unlinkSync, renameSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { constants } from 'node:fs';

const LOCK_STALE_MS = 10_000;
const DEFAULT_RETRY_MS = 100;
const DEFAULT_MAX_WAIT_MS = 10_000;

/**
 * Read and parse a JSON manifest file.
 * @param {string} filePath - Direct path to the JSON file
 * @returns {Promise<object|null>} Parsed JSON or null if missing
 */
export async function readManifestFile(filePath) {
  try {
    const content = await readFile(filePath, 'utf8');
    return JSON.parse(content);
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err; // Re-throw parse errors and other failures
  }
}

/**
 * Write a manifest file atomically (tmp + rename).
 * Creates parent directories if needed.
 * @param {string} filePath - Direct path to write
 * @param {object} data - JSON-serializable data
 */
export async function writeManifestFile(filePath, data) {
  await mkdir(dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.tmp`;
  await writeFile(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf8');
  await rename(tmpPath, filePath);
}

/**
 * Acquire a lockfile for manifest operations.
 * @param {string} dir - Directory to create .lock in
 * @param {object} [options]
 * @param {number} [options.retryMs=100] - Retry interval
 * @param {number} [options.maxWaitMs=10000] - Max wait before failure
 */
export async function acquireLock(dir, options = {}) {
  const { retryMs = DEFAULT_RETRY_MS, maxWaitMs = DEFAULT_MAX_WAIT_MS } = options;
  const lockPath = join(dir, '.lock');
  const start = Date.now();

  while (true) {
    // Try to read existing lock
    try {
      const content = await readFile(lockPath, 'utf8');
      const lockData = JSON.parse(content);
      const age = Date.now() - (lockData.time || lockData.timestamp || 0);

      if (age >= LOCK_STALE_MS || !isPidAlive(lockData.pid)) {
        // Stale lock — override it
        break;
      }

      // Lock is fresh and held by a live process
      if (Date.now() - start >= maxWaitMs) {
        throw new Error(`Failed to acquire lock after ${maxWaitMs}ms — held by PID ${lockData.pid}`);
      }

      await sleep(retryMs);
    } catch (err) {
      if (err.code === 'ENOENT') break; // No lock file, proceed
      if (err.message?.includes('Failed to acquire lock')) throw err;
      break; // Corrupted lock, override
    }
  }

  // Write our lock
  await writeFile(lockPath, JSON.stringify({ pid: process.pid, time: Date.now() }), 'utf8');
}

/**
 * Release the lockfile.
 * @param {string} dir - Directory containing .lock
 */
export async function releaseLock(dir) {
  const lockPath = join(dir, '.lock');
  try { await unlink(lockPath); } catch { /* already removed */ }
}

function isPidAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// --- Lock (sync, for CLI scripts) ---

export function manifestDirFor(projectDir) {
  return join(projectDir, 'tests', 'verification-playwright', 'manifest');
}

export function acquireLockSync(projectDir) {
  const manifestDir = manifestDirFor(projectDir);
  mkdirSync(manifestDir, { recursive: true });
  const lockPath = join(manifestDir, '.lock');

  if (existsSync(lockPath)) {
    try {
      const lockData = JSON.parse(readFileSync(lockPath, 'utf8'));
      const age = Date.now() - (lockData.time || lockData.timestamp || 0);
      if (age < LOCK_STALE_MS && isPidAlive(lockData.pid)) {
        // Wait briefly
        const start = Date.now();
        while (Date.now() - start < LOCK_STALE_MS) {
          const end = Date.now() + 100;
          while (Date.now() < end) { /* spin */ }
          if (!existsSync(lockPath)) break;
        }
      }
    } catch { /* corrupted, override */ }
  }

  writeFileSync(lockPath, JSON.stringify({ pid: process.pid, time: Date.now() }), 'utf8');
  return () => releaseLockSync(projectDir);
}

export function releaseLockSync(projectDir) {
  const lockPath = join(manifestDirFor(projectDir), '.lock');
  try { unlinkSync(lockPath); } catch { /* already removed */ }
}

// --- Manifest layout ---------------------------------------------------------
//
// Layout 2 (current), under tests/verification-playwright/manifest/:
//
//   config.json               tier config (unchanged; its own version is the
//                             config schema's, not the layout's)
//   items/<doc-slug>.json     one file per source verification doc, "version": "2.0"
//   import-index/<page>.json  one file per page tag, "version": "2.0"
//
// The layout is read from the `version` field every manifest file already
// carries (missing = "1.0"); there is no separate marker file. Layout 1 kept everything in three repo-wide files (items.json,
// import-index.json, ../pending-generation.json), each with a top-level
// generated_at. Any two PRs touching different docs rewrote all of them and
// conflicted on the whole file. In layout 2 two PRs touching different docs
// touch disjoint files, and nothing carries a repo-wide timestamp.
//
// The pending-generation queue is no longer a file: an item is queued when its
// entry carries `pending_generation: true`, so the queue lives in the same
// per-doc file as the item and a removed item leaves the queue by construction.

/** The manifest layout this skill writes. Bump the major and add a
 *  LAYOUT_STEPS entry when the on-disk shape changes. */
export const MANIFEST_VERSION = '2.0';
const CURRENT_MAJOR = 2;
const ITEMS_DIR = 'items';
const INDEX_DIR = 'import-index';
const V1_ITEMS = 'items.json';
const V1_INDEX = 'import-index.json';
const V1_QUEUE = join('..', 'pending-generation.json');
/** Where layout-1 aggregate files live, relative to the manifest dir. */
export const LEGACY_MANIFEST_FILES = [V1_ITEMS, V1_INDEX, V1_QUEUE];

/** File-name slug for a source doc: docs/verification/pages/a.md -> pages--a.
 *  The file also stores source_doc, which is what ownership is keyed on; the
 *  slug is only a name, and a slug clash between two docs is refused on save. */
export function docSlug(sourceDoc) {
  return sourceDoc.replace(/^docs\/verification\//, '').replace(/\.md$/, '').split('/').join('--');
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw new Error(`Cannot parse ${path}: ${err.message}`);
  }
}

/** Major layout version of a parsed manifest file; a missing field is 1.0. */
function majorOf(data, where) {
  const v = Array.isArray(data) ? undefined : data?.version;
  if (v === undefined || v === null) return 1;
  const major = Number.parseInt(String(v), 10);
  if (!Number.isInteger(major) || major < 1) throw new Error(`${where}: unreadable manifest version ${JSON.stringify(v)}`);
  return major;
}

function refuseNewer(major, where) {
  if (major > CURRENT_MAJOR) {
    throw new Error(`${where} is manifest version ${major}.x, newer than this playwright-test-generator writes (${MANIFEST_VERSION}) — upgrade the skill; refusing to read or rewrite it`);
  }
}

function writeJsonAtomic(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(data, null, 2) + '\n', 'utf8');
  renameSync(tmp, path);
}

function jsonFiles(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
}

const sortKeys = (obj) => Object.fromEntries(Object.entries(obj).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
/** File content minus its own timestamp — what "changed" is judged on. */
const body = ({ updated_at, ...rest }) => JSON.stringify(rest);

function readItemDocs(dir) {
  const docs = new Map();
  for (const f of jsonFiles(join(dir, ITEMS_DIR))) {
    const doc = readJson(join(dir, ITEMS_DIR, f));
    const major = majorOf(doc, `${ITEMS_DIR}/${f}`);
    refuseNewer(major, `${ITEMS_DIR}/${f}`);
    if (major < CURRENT_MAJOR) throw new Error(`${ITEMS_DIR}/${f} claims manifest version ${major}.x but sits in the ${MANIFEST_VERSION} per-doc layout; fix its "version" field`);
    if (!doc?.source_doc || typeof doc.items !== 'object') {
      throw new Error(`Manifest file ${ITEMS_DIR}/${f} has no source_doc/items — not a per-doc item file`);
    }
    // Two shards for one doc (a stale copy, a rename) would silently drop one.
    if (docs.has(doc.source_doc)) throw new Error(`${ITEMS_DIR}/${docs.get(doc.source_doc).file} and ${ITEMS_DIR}/${f} both declare source_doc ${doc.source_doc} — delete the stale one`);
    docs.set(doc.source_doc, { file: f, doc });
  }
  return docs;
}

function readIndexPages(dir) {
  const pages = new Map();
  for (const f of jsonFiles(join(dir, INDEX_DIR))) {
    const page = readJson(join(dir, INDEX_DIR, f));
    const major = majorOf(page, `${INDEX_DIR}/${f}`);
    refuseNewer(major, `${INDEX_DIR}/${f}`);
    if (major < CURRENT_MAJOR) throw new Error(`${INDEX_DIR}/${f} claims manifest version ${major}.x but sits in the ${MANIFEST_VERSION} per-doc layout; fix its "version" field`);
    if (!page?.page || !Array.isArray(page.files)) {
      throw new Error(`Manifest file ${INDEX_DIR}/${f} has no page/files — not a per-page index file`);
    }
    if (pages.has(page.page)) throw new Error(`${INDEX_DIR}/${pages.get(page.page).file} and ${INDEX_DIR}/${f} both declare page ${page.page} — delete the stale one`);
    pages.set(page.page, { file: f, page });
  }
  return pages;
}

/** The legacy queue, either shape older runs wrote (envelope or bare array). */
function readLegacyQueue(path) {
  const raw = readJson(path);
  if (raw === null) return [];
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.items)) return raw.items;
  throw new Error(`Cannot read ${path}: neither an id array nor a {items: [...]} envelope`);
}

/**
 * Layout 1 -> 2. Also the mixed-state fold: a branch cut before the migration
 * and merged after brings a layout-1 file back next to layout-2 files. Rule:
 *   - per doc (items) / per page (index): an existing layout-2 file always
 *     wins; layout-1 entries fill only docs/pages with no layout-2 file.
 *     Layout 1 has one repo-wide generated_at, so it cannot say which doc is
 *     newer. A kept doc that the stale branch really did change is re-flagged
 *     by sync-tests on its next run, since its content_hash no longer matches.
 *   - queue: union. Every queued id that still has an entry gets
 *     pending_generation: true. Ids with no entry anywhere are dropped and
 *     reported — every reader already ignored them (link-specs dropped them).
 * Lossless: refuses (throws, nothing renamed, legacy files untouched) if an
 * item has no source_doc, an ID lands in two docs, an index entry maps to no
 * page, or the written files do not read back field-for-field.
 */
function migrateV1ToV2(dir) {
  const v1Items = readJson(join(dir, V1_ITEMS));
  const v1Index = readJson(join(dir, V1_INDEX));
  const queue = new Set(readLegacyQueue(join(dir, V1_QUEUE)));
  const now = new Date().toISOString();
  const writes = []; // [relPath, data]
  const report = { items: 0, docsTaken: [], docsKept: [], pagesTaken: [], pagesKept: [], queued: 0, droppedQueueIds: [] };

  // ---- items
  const v2Docs = readItemDocs(dir);
  const { items: v1Entries = {}, generated_at: v1ItemsAt, ...itemsMeta } = v1Items ?? {};
  const noDoc = Object.keys(v1Entries).filter((id) => !v1Entries[id]?.source_doc);
  if (noDoc.length) {
    throw new Error(`${noDoc.length} item(s) in ${V1_ITEMS} have no source_doc, so they cannot be placed in a per-doc file: ${noDoc.slice(0, 10).join(', ')}`);
  }
  const byDoc = new Map();
  for (const [id, entry] of Object.entries(v1Entries)) {
    if (!byDoc.has(entry.source_doc)) byDoc.set(entry.source_doc, {});
    byDoc.get(entry.source_doc)[id] = entry;
  }
  const finalDocs = new Map([...v2Docs].map(([d, { file, doc }]) => [d, { file, doc, changed: false }]));
  for (const [sourceDoc, entries] of byDoc) {
    // A 2.0 file always wins: layout 1 has one repo-wide timestamp, so a stale
    // branch re-saving it would look newer than every doc it never touched.
    if (v2Docs.has(sourceDoc)) { report.docsKept.push(sourceDoc); continue; }
    report.docsTaken.push(sourceDoc);
    const doc = { ...itemsMeta, version: MANIFEST_VERSION, source_doc: sourceDoc, updated_at: v1ItemsAt ?? now, items: sortKeys(structuredClone(entries)) };
    finalDocs.set(sourceDoc, { file: `${docSlug(sourceDoc)}.json`, doc, changed: true });
  }
  const owner = new Map();
  const collisions = [];
  for (const [sourceDoc, { doc }] of finalDocs) {
    for (const id of Object.keys(doc.items)) {
      if (owner.has(id)) collisions.push(`${id} (${owner.get(id)} and ${sourceDoc})`);
      else owner.set(id, sourceDoc);
    }
  }
  if (collisions.length) throw new Error(`Item ID collision(s) across docs: ${collisions.join(', ')}`);
  for (const id of queue) {
    const sourceDoc = owner.get(id);
    if (!sourceDoc) { report.droppedQueueIds.push(id); continue; }
    const target = finalDocs.get(sourceDoc);
    if (!target.doc.items[id].pending_generation) {
      if (!target.changed) target.doc = { ...structuredClone(target.doc), updated_at: now };
      target.doc.items[id].pending_generation = true;
      target.changed = true;
    }
    report.queued++;
  }
  const slugs = new Map();
  for (const [sourceDoc, { file, doc, changed }] of finalDocs) {
    if (slugs.has(file)) throw new Error(`Docs ${slugs.get(file)} and ${sourceDoc} both map to ${ITEMS_DIR}/${file}`);
    slugs.set(file, sourceDoc);
    if (changed) writes.push([join(ITEMS_DIR, file), doc]);
  }

  // ---- import index
  const v2Pages = readIndexPages(dir);
  const { entries: v1Map = {}, generated_at: v1IndexAt, ...indexMeta } = v1Index ?? {};
  const unmapped = Object.keys(v1Map).filter((f) => !Array.isArray(v1Map[f]) || v1Map[f].length === 0);
  if (unmapped.length) {
    throw new Error(`${unmapped.length} ${V1_INDEX} entr(ies) map to no page, so a per-page index cannot hold them: ${unmapped.slice(0, 10).join(', ')} — remove them or give them a page`);
  }
  const byPage = new Map();
  for (const [file, tags] of Object.entries(v1Map)) {
    for (const tag of tags) {
      if (!/^[A-Za-z0-9][\w.-]*$/.test(tag)) throw new Error(`${V1_INDEX}: page tag "${tag}" is not a safe file name`);
      if (!byPage.has(tag)) byPage.set(tag, new Set());
      byPage.get(tag).add(file);
    }
  }
  for (const [tag, files] of byPage) {
    if (v2Pages.has(tag)) { report.pagesKept.push(tag); continue; }
    report.pagesTaken.push(tag);
    writes.push([join(INDEX_DIR, `${tag}.json`),
      { ...indexMeta, version: MANIFEST_VERSION, page: tag, updated_at: v1IndexAt ?? now, files: [...files].sort() }]);
  }

  // ---- write tmp, verify read-back, then rename, then delete legacy files
  for (const [rel, data] of writes) {
    const path = join(dir, rel);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(`${path}${MIGRATE_TMP}`, JSON.stringify(data, null, 2) + '\n', 'utf8');
  }
  const lost = verifyV1Carried(dir, writes, v1Entries, v1Map, report);
  if (lost.length) {
    for (const [rel] of writes) { try { unlinkSync(join(dir, `${rel}${MIGRATE_TMP}`)); } catch { /* gone */ } }
    throw new Error(`migration would lose data, refusing: ${lost.slice(0, 10).join('; ')}`);
  }
  for (const [rel] of writes) renameSync(join(dir, `${rel}${MIGRATE_TMP}`), join(dir, rel));
  for (const f of LEGACY_MANIFEST_FILES) { try { unlinkSync(join(dir, f)); } catch { /* not present */ } }

  report.items = Object.values(v1Entries).length;
  return report;
}

// Migration runs from read-only callers without the lock, so two first loads
// can race; a per-process tmp name keeps one from renaming the other's file
// away. Both publish identical content from the same legacy input.
const MIGRATE_TMP = `.${process.pid}.tmp`;

/** Read the .tmp files back and check every taken layout-1 fact survived. */
function verifyV1Carried(dir, writes, v1Entries, v1Map, report) {
  const lost = [];
  const written = new Map(writes.map(([rel]) => [rel, JSON.parse(readFileSync(join(dir, `${rel}${MIGRATE_TMP}`), 'utf8'))]));
  const docs = new Map([...written.values()].filter((d) => d.source_doc).map((d) => [d.source_doc, d]));
  const pages = new Map([...written.values()].filter((p) => p.page).map((p) => [p.page, p]));
  const taken = new Set(report.docsTaken);
  let expected = 0; let carried = 0;
  for (const [id, entry] of Object.entries(v1Entries)) {
    if (!taken.has(entry.source_doc)) continue;
    expected++;
    const { pending_generation, ...got } = docs.get(entry.source_doc)?.items[id] ?? {};
    const { pending_generation: _p, ...want } = entry;
    if (JSON.stringify(sortKeys(got)) === JSON.stringify(sortKeys(want))) carried++;
    else lost.push(`item ${id} differs after migration`);
  }
  if (expected !== carried) lost.push(`${expected} items expected, ${carried} carried`);
  const takenPages = new Set(report.pagesTaken);
  for (const [file, tags] of Object.entries(v1Map)) {
    for (const tag of tags) {
      if (takenPages.has(tag) && !pages.get(tag)?.files.includes(file)) lost.push(`index ${file} -> ${tag} missing`);
    }
  }
  return lost;
}

/** Ordered upgrade steps, keyed on the major version they read. Layout 3
 *  adds one {from: 2, to: 3} entry; the dispatch below does not change. */
const LAYOUT_STEPS = [
  { from: 1, to: 2, migrate: migrateV1ToV2 },
];

/**
 * Major version of every layout file present: the layout-1 aggregate paths
 * plus the per-doc / per-page files. Refuses anything newer than we write,
 * so a newer layout is never read as, or rewritten into, an older one.
 * An aggregate file is layout 1 by its version field (missing = 1.0); one
 * claiming a later version was never written by any release, so it refuses.
 */
export function manifestVersions(manifestDir) {
  const found = [];
  for (const rel of LEGACY_MANIFEST_FILES) {
    const data = readJson(join(manifestDir, rel));
    if (data === null) continue;
    const major = majorOf(data, rel);
    refuseNewer(major, rel);
    if (major !== 1) throw new Error(`${rel} claims manifest version ${major}.x, but only layout 1 used that path — remove it or restore its 1.0 content`);
    found.push({ file: rel, major });
  }
  for (const sub of [ITEMS_DIR, INDEX_DIR]) {
    for (const f of jsonFiles(join(manifestDir, sub))) {
      const rel = `${sub}/${f}`;
      const major = majorOf(readJson(join(manifestDir, rel)), rel);
      refuseNewer(major, rel);
      found.push({ file: rel, major });
    }
  }
  return found;
}

/**
 * Upgrade the manifest dir to MANIFEST_VERSION. Idempotent: with every file
 * already current it does nothing. Runs, in order, each step from the oldest
 * version found upward. Returns the steps applied (empty when none).
 * ponytail: no lock here. Writers call it inside their own lock (via
 * loadManifest); read-only callers can race another migration, and both
 * produce identical files from identical input.
 */
export function migrateManifest(manifestDir) {
  const found = manifestVersions(manifestDir);
  if (!found.length) return [];
  const oldest = Math.min(...found.map((f) => f.major));
  const applied = [];
  for (const step of LAYOUT_STEPS) {
    if (step.from < oldest) continue;
    applied.push({ from: step.from, to: step.to, ...step.migrate(manifestDir) });
  }
  return applied;
}

/**
 * THE loader. Runs the migration, then returns:
 *   items   - flat {id: entry}; mutate this, saveManifest() regroups by source_doc
 *   entries - {sourceFile: [pageTags]}, built in memory from the per-page index
 *   pages   - {pageTag: [sourceFiles]}
 *   migrated- the steps migrateManifest() applied on this load
 * Throws on unparseable files and on an item ID present in two doc files.
 */
export function loadManifest(manifestDir) {
  const migrated = migrateManifest(manifestDir);
  const docs = readItemDocs(manifestDir);
  const items = {};
  const collisions = [];
  for (const [sourceDoc, { doc }] of docs) {
    for (const [id, entry] of Object.entries(doc.items)) {
      if (items[id]) collisions.push(`${id} (${items[id].source_doc} and ${sourceDoc})`);
      else items[id] = { ...entry, source_doc: entry.source_doc ?? sourceDoc };
    }
  }
  if (collisions.length) throw new Error(`Item ID collision(s) across manifest ${ITEMS_DIR}/ files: ${collisions.join(', ')}`);

  const pages = {};
  const entries = {};
  for (const [tag, { page }] of readIndexPages(manifestDir)) {
    pages[tag] = [...page.files];
    for (const file of page.files) (entries[file] ??= []).push(tag);
  }
  return { dir: manifestDir, items, entries, pages, migrated, _docs: docs };
}

/**
 * THE writer for items (and so for the queue). Regroups `manifest.items` by
 * source_doc and rewrites only the doc files whose content changed; a doc left
 * with no items has its file removed. Atomic per file (tmp + rename).
 * Callers hold the manifest lock across load -> save.
 */
export function saveManifest(manifest) {
  const dir = manifest.dir;
  const groups = new Map();
  for (const [id, entry] of Object.entries(manifest.items)) {
    if (!entry.source_doc) throw new Error(`Manifest item ${id} has no source_doc; cannot place it in a per-doc file`);
    if (!groups.has(entry.source_doc)) groups.set(entry.source_doc, {});
    groups.get(entry.source_doc)[id] = entry;
  }
  const docs = manifest._docs;
  // Meta for a doc file that does not exist yet: copy what the others carry
  // (version, hash_version), since those describe the manifest, not the doc.
  const { source_doc: _s, items: _i, updated_at: _u, ...defaultMeta } = docs.values().next().value?.doc ?? {};
  const files = new Map([...docs].map(([d, { file }]) => [file, d]));
  let written = 0;
  for (const [sourceDoc, entries] of groups) {
    const prev = docs.get(sourceDoc);
    const file = prev?.file ?? `${docSlug(sourceDoc)}.json`;
    if (!prev && files.has(file)) throw new Error(`Docs ${files.get(file)} and ${sourceDoc} both map to ${ITEMS_DIR}/${file}`);
    const { source_doc: _a, items: _b, updated_at: _c, ...meta } = prev?.doc ?? defaultMeta;
    const next = { ...meta, version: MANIFEST_VERSION, source_doc: sourceDoc, updated_at: prev?.doc.updated_at, items: sortKeys(entries) };
    if (prev && body(next) === body(prev.doc)) continue;
    next.updated_at = new Date().toISOString();
    writeJsonAtomic(join(dir, ITEMS_DIR, file), next);
    docs.set(sourceDoc, { file, doc: next });
    files.set(file, sourceDoc);
    written++;
  }
  for (const [sourceDoc, { file }] of [...docs]) {
    if (groups.has(sourceDoc)) continue;
    try { unlinkSync(join(dir, ITEMS_DIR, file)); } catch { /* gone */ }
    docs.delete(sourceDoc);
    written++;
  }
  return written;
}

/** Queued item IDs: entries carrying pending_generation: true. */
export function pendingIds(manifest) {
  return Object.keys(manifest.items).filter((id) => manifest.items[id].pending_generation).sort();
}
