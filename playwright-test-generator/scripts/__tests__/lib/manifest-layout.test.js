// Layout 1 (repo-wide items.json / import-index.json / pending-generation.json)
// -> 2.0 (per-doc items/, per-page import-index/). Real files in tmp dirs.
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, readFileSync, writeFileSync, existsSync, readdirSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { migrateManifest, loadManifest, saveManifest, docSlug, MANIFEST_VERSION } from '../../lib/manifest.js';
import { writeItems, writeIndex, writeV1, readItems, FIXED_AT } from '../helpers/manifest-fixtures.js';

const OLDER = '2025-06-01T00:00:00.000Z';
const NEWER = '2026-06-01T00:00:00.000Z';

let root; let dir;
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'ptg-layout-'));
  dir = join(root, 'manifest');
  mkdirSync(dir);
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

const json = (rel) => JSON.parse(readFileSync(join(dir, rel), 'utf8'));
const snapshot = () => {
  const out = {};
  const walk = (d, pre) => {
    for (const f of readdirSync(d, { withFileTypes: true })) {
      if (f.isDirectory()) walk(join(d, f.name), `${pre}${f.name}/`);
      else out[`${pre}${f.name}`] = readFileSync(join(d, f.name), 'utf8');
    }
  };
  walk(root, '');
  return out;
};

const V1_ITEMS = {
  'A-01': { source_doc: 'docs/verification/a.md', content_hash: 'h1', spec_file: 'tests/a.spec.ts', pinned: false, section: 'Intro', tags: ['x', 'y'] },
  'A-02': { source_doc: 'docs/verification/a.md', content_hash: 'h2', status: 'skipped' },
  'B-01': { source_doc: 'docs/verification/pages/b.md', content_hash: 'h3', pinned: true, nested: { deep: [1, { two: 2 }] } },
};
const V1_INDEX = { 'src/a.ts': ['page-a'], 'src/shared.ts': ['page-a', 'page-b'] };

describe('docSlug', () => {
  it('flattens the doc path under docs/verification', () => {
    expect(docSlug('docs/verification/a.md')).toBe('a');
    expect(docSlug('docs/verification/pages/thing.md')).toBe('pages--thing');
  });
});

describe('v1 -> 2.0 migration', () => {
  it('round-trips every item and index fact field for field', () => {
    writeV1(dir, { items: V1_ITEMS, index: V1_INDEX, queue: ['A-02'] });
    const [step] = migrateManifest(dir);

    expect(step).toMatchObject({ from: 1, to: 2, items: 3, queued: 1, droppedQueueIds: [] });
    expect(readdirSync(join(dir, 'items')).sort()).toEqual(['a.json', 'pages--b.json']);
    expect(readdirSync(join(dir, 'import-index')).sort()).toEqual(['page-a.json', 'page-b.json']);

    const a = json('items/a.json');
    expect(a).toMatchObject({ version: MANIFEST_VERSION, hash_version: 1, source_doc: 'docs/verification/a.md', updated_at: FIXED_AT });
    expect(a.items).toEqual({ 'A-01': V1_ITEMS['A-01'], 'A-02': { ...V1_ITEMS['A-02'], pending_generation: true } });
    expect(json('items/pages--b.json').items).toEqual({ 'B-01': V1_ITEMS['B-01'] });
    expect(json('import-index/page-a.json')).toEqual({ version: '2.0', root: 'repo', page: 'page-a', updated_at: FIXED_AT, files: ['src/a.ts', 'src/shared.ts'] });
    expect(json('import-index/page-b.json').files).toEqual(['src/shared.ts']);

    for (const f of ['items.json', 'import-index.json', '../pending-generation.json']) expect(existsSync(join(dir, f))).toBe(false);

    const m = loadManifest(dir);
    const { pending_generation, ...a02 } = m.items['A-02'];
    expect(pending_generation).toBe(true);
    expect({ ...m.items, 'A-02': a02 }).toEqual(V1_ITEMS);
    expect(m.entries).toEqual(V1_INDEX);
  });

  it('treats a file with no version field as 1.0', () => {
    writeFileSync(join(dir, 'items.json'), JSON.stringify({ items: { 'A-01': V1_ITEMS['A-01'] } }));
    expect(migrateManifest(dir)).toHaveLength(1);
    expect(json('items/a.json').version).toBe('2.0');
  });

  it('reads the queue as an envelope or a bare array and reports ids with no entry', () => {
    writeV1(dir, { items: V1_ITEMS, queue: ['B-01', 'GONE-01'], queueEnvelope: false });
    const [step] = migrateManifest(dir);
    expect(step.queued).toBe(1);
    expect(step.droppedQueueIds).toEqual(['GONE-01']);
    expect(json('items/pages--b.json').items['B-01'].pending_generation).toBe(true);
  });

  it('is idempotent: a second run does nothing and rewrites nothing', () => {
    writeV1(dir, { items: V1_ITEMS, index: V1_INDEX });
    migrateManifest(dir);
    const before = snapshot();
    expect(migrateManifest(dir)).toEqual([]);
    expect(loadManifest(dir).migrated).toEqual([]);
    expect(snapshot()).toEqual(before);
  });

  it('keeps 2.0 when the same layout-1 file comes back with an equal timestamp', () => {
    writeV1(dir, { items: V1_ITEMS });
    migrateManifest(dir);
    const before = json('items/a.json');
    writeV1(dir, { items: { ...V1_ITEMS, 'A-01': { ...V1_ITEMS['A-01'], content_hash: 'stale' } } });
    const [step] = migrateManifest(dir);
    expect(step.docsKept).toContain('docs/verification/a.md');
    expect(json('items/a.json')).toEqual(before);
    expect(existsSync(join(dir, 'items.json'))).toBe(false);
  });
});

describe('mixed-state fold (layout-1 file next to 2.0 files)', () => {
  it('per doc: newer layout 1 wins, older layout 1 keeps 2.0, missing 2.0 is taken; flags union', () => {
    writeItems(dir, {
      'A-01': { source_doc: 'docs/verification/a.md', content_hash: 'v2-a', pending_generation: true },
      'C-01': { source_doc: 'docs/verification/c.md', content_hash: 'v2-c' },
    }, { updatedAt: OLDER });
    writeItems(dir, { 'D-01': { source_doc: 'docs/verification/d.md', content_hash: 'v2-d' } }, { updatedAt: NEWER });
    writeV1(dir, {
      generatedAt: '2026-01-01T00:00:00.000Z',
      items: {
        'A-01': { source_doc: 'docs/verification/a.md', content_hash: 'v1-a' },
        'D-01': { source_doc: 'docs/verification/d.md', content_hash: 'v1-d' },
        'E-01': { source_doc: 'docs/verification/e.md', content_hash: 'v1-e' },
      },
      queue: ['D-01'],
    });

    const [step] = migrateManifest(dir);
    expect(step.docsTaken.sort()).toEqual(['docs/verification/a.md', 'docs/verification/e.md']);
    expect(step.docsKept).toEqual(['docs/verification/d.md']);

    const items = readItems(dir);
    expect(items['A-01']).toMatchObject({ content_hash: 'v1-a', pending_generation: true }); // v1 newer, v2 flag kept
    expect(items['C-01'].content_hash).toBe('v2-c'); // untouched: no v1 counterpart
    expect(items['D-01']).toMatchObject({ content_hash: 'v2-d', pending_generation: true }); // v2 newer, v1 queue unioned
    expect(items['E-01'].content_hash).toBe('v1-e'); // no v2 file: taken
    expect(existsSync(join(dir, 'items.json'))).toBe(false);
  });

  it('refuses when a folded doc would put one ID in two docs', () => {
    writeItems(dir, { 'A-01': { source_doc: 'docs/verification/a.md' } }, { updatedAt: NEWER });
    writeV1(dir, { items: { 'A-01': { source_doc: 'docs/verification/b.md' } } });
    const before = snapshot();
    expect(() => migrateManifest(dir)).toThrow(/collision.*A-01/);
    expect(snapshot()).toEqual(before);
  });
});

describe('refusal on a lossy migration', () => {
  it.each([
    ['an item with no source_doc', { items: { 'A-01': { content_hash: 'h' } } }, /no source_doc.*A-01/],
    ['an index entry with no page', { items: V1_ITEMS, index: { 'src/a.ts': [] } }, /map to no page.*src\/a\.ts/],
    ['a page tag that is not a safe file name', { index: { 'src/a.ts': ['../escape'] } }, /not a safe file name/],
    ['a corrupt queue', { items: V1_ITEMS, queue: { nope: true }, queueEnvelope: false }, /neither an id array/],
  ])('refuses %s and leaves the old files byte-identical', (_name, v1, msg) => {
    writeV1(dir, v1);
    const before = snapshot();
    expect(() => loadManifest(dir)).toThrow(msg);
    expect(snapshot()).toEqual(before);
    expect(Object.keys(snapshot()).some((f) => f.endsWith('.tmp'))).toBe(false);
  });
});

describe('version guard', () => {
  it('refuses a per-doc file newer than the skill and never rewrites it', () => {
    writeItems(dir, { 'A-01': {} });
    const path = join(dir, 'items', 'a.json');
    const future = { ...JSON.parse(readFileSync(path, 'utf8')), version: '3.0' };
    writeFileSync(path, JSON.stringify(future));
    const before = snapshot();
    expect(() => loadManifest(dir)).toThrow(/newer than this playwright-test-generator writes \(2\.0\) — upgrade the skill/);
    expect(snapshot()).toEqual(before);
  });

  it('refuses a layout-1 path claiming a later version', () => {
    writeFileSync(join(dir, 'items.json'), JSON.stringify({ version: '2.0', items: {} }));
    expect(() => migrateManifest(dir)).toThrow(/only layout 1 used that path/);
  });

  it('refuses a per-doc file claiming layout 1', () => {
    writeItems(dir, { 'A-01': {} });
    const path = join(dir, 'items', 'a.json');
    writeFileSync(path, JSON.stringify({ ...JSON.parse(readFileSync(path, 'utf8')), version: '1.0' }));
    expect(() => loadManifest(dir)).toThrow(/claims manifest version 1\.x/);
  });
});

describe('per-doc files', () => {
  it('refuses to load an ID present in two doc files', () => {
    writeItems(dir, { 'A-01': { source_doc: 'docs/verification/a.md' } });
    writeItems(dir, { 'A-01': { source_doc: 'docs/verification/b.md' } });
    expect(() => loadManifest(dir)).toThrow(/collision.*A-01/);
  });

  it('refuses two shards that declare the same source_doc', () => {
    writeItems(dir, { 'A-01': { source_doc: 'docs/verification/a.md' } });
    writeFileSync(join(dir, 'items', 'a-copy.json'), readFileSync(join(dir, 'items', 'a.json')));
    expect(() => loadManifest(dir)).toThrow(/a-copy\.json and items\/a\.json both declare source_doc/);
  });

  it('refuses two index shards that declare the same page', () => {
    writeItems(dir, { 'A-01': { source_doc: 'docs/verification/a.md' } });
    writeIndex(dir, { 'src/a.ts': ['page-a'] });
    writeFileSync(join(dir, 'import-index', 'page-a-copy.json'), readFileSync(join(dir, 'import-index', 'page-a.json')));
    expect(() => loadManifest(dir)).toThrow(/both declare page page-a/);
  });

  it('saves only the doc files whose items changed', () => {
    writeItems(dir, {
      'A-01': { source_doc: 'docs/verification/a.md', content_hash: 'h' },
      'B-01': { source_doc: 'docs/verification/b.md', content_hash: 'h' },
    });
    const before = snapshot();
    const m = loadManifest(dir);
    m.items['B-01'].content_hash = 'changed';
    expect(saveManifest(m)).toBe(1);
    const after = snapshot();
    expect(after['manifest/items/a.json']).toBe(before['manifest/items/a.json']);
    expect(json('items/b.json')).toMatchObject({ version: '2.0', items: { 'B-01': { content_hash: 'changed' } } });
    expect(json('items/b.json').updated_at).not.toBe(FIXED_AT);
  });
});
