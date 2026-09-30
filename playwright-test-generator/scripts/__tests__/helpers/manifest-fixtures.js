// Raw on-disk manifest fixtures, written and read by hand (not through
// lib/manifest.js) so a test pins the file format, not the code's idea of it.
import { mkdirSync, readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

export const DEFAULT_DOC = 'docs/verification/a.md';
export const FIXED_AT = '2026-01-01T00:00:00.000Z';

const slug = (doc) => doc.replace(/^docs\/verification\//, '').replace(/\.md$/, '').split('/').join('--');
const put = (path, data) => { mkdirSync(join(path, '..'), { recursive: true }); writeFileSync(path, JSON.stringify(data, null, 2) + '\n'); };

/** Current layout: one items/<slug>.json per source_doc (default DEFAULT_DOC). */
export function writeItems(manifestDir, items, { updatedAt = FIXED_AT } = {}) {
  const byDoc = {};
  for (const [id, entry] of Object.entries(items)) {
    const e = { source_doc: DEFAULT_DOC, ...entry };
    (byDoc[e.source_doc] ??= {})[id] = e;
  }
  for (const [doc, entries] of Object.entries(byDoc)) {
    put(join(manifestDir, 'items', `${slug(doc)}.json`), { version: '2.0', source_doc: doc, updated_at: updatedAt, items: entries });
  }
}

/** Current layout: {sourceFile: [tags]} written as one import-index/<tag>.json per tag. */
export function writeIndex(manifestDir, entries, { updatedAt = FIXED_AT, root = 'repo' } = {}) {
  const pages = {};
  for (const [file, tags] of Object.entries(entries)) for (const t of tags) (pages[t] ??= []).push(file);
  for (const [page, files] of Object.entries(pages)) {
    put(join(manifestDir, 'import-index', `${page}.json`), { version: '2.0', root, page, updated_at: updatedAt, files: files.sort() });
  }
}

/** Every per-doc items file, flattened to {id: entry}. */
export function readItems(manifestDir) {
  const dir = join(manifestDir, 'items');
  const out = {};
  if (!existsSync(dir)) return out;
  for (const f of readdirSync(dir)) Object.assign(out, JSON.parse(readFileSync(join(dir, f), 'utf8')).items);
  return out;
}

export function readItemFiles(manifestDir) {
  const dir = join(manifestDir, 'items');
  return existsSync(dir) ? readdirSync(dir).sort() : [];
}

/** Layout 1: the three repo-wide files. `queue` may be an array (bare, older runs) or null. */
export function writeV1(manifestDir, { items, index, queue, generatedAt = FIXED_AT, queueEnvelope = true } = {}) {
  if (items) put(join(manifestDir, 'items.json'), { version: '1.0', hash_version: 1, generated_at: generatedAt, items });
  if (index) put(join(manifestDir, 'import-index.json'), { version: '1.0', generated_at: generatedAt, root: 'repo', entries: index });
  if (queue) put(join(manifestDir, '..', 'pending-generation.json'),
    queueEnvelope ? { version: '1.0', generated_at: generatedAt, items: queue } : queue);
}
