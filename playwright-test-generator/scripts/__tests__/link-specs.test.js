import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { linkSpecs, collectMarkers } from '../link-specs.js';
import { writeItems, readItems, writeV1 } from './helpers/manifest-fixtures.js';
import { existsSync } from 'node:fs';
import { mkdtemp, rm, writeFile, mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('linkSpecs', () => {
  let dir, specDir, manifestDir;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'link-specs-'));
    specDir = join(dir, 'tests', 'verification-playwright');
    manifestDir = join(specDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
  });
  afterEach(async () => { await rm(dir, { recursive: true, force: true }); });

  const items = (obj) => writeItems(manifestDir, obj);
  const after = () => readItems(manifestDir);
  const queued = () => Object.keys(after()).filter((id) => after()[id].pending_generation).sort();
  const spec = (name, body) => writeFile(join(specDir, name), body);

  it('links a marked item to its spec and records status', async () => {
    items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\ntest('x', async () => {});\n// @end:A-01\n`);

    const res = linkSpecs(dir);

    expect(res.linked).toBe(1);
    expect(after()['A-01'].spec_file).toBe('tests/verification-playwright/a.spec.ts');
    expect(after()['A-01'].status).toBe('active');
  });

  it('stores spec_file with POSIX separators', async () => {
    items({ 'A-01': { content_hash: 'h' } });
    await mkdir(join(specDir, 'pages'), { recursive: true });
    await spec(join('pages', 'a.spec.ts'), `// @begin:A-01\nt\n// @end:A-01\n`);

    linkSpecs(dir);

    // Backslashes here would be read back on Linux/macOS as a literal filename
    // and checkSpecFiles would report the existing spec as missing.
    expect(after()['A-01'].spec_file).not.toContain('\\');
    expect(after()['A-01'].spec_file).toBe('tests/verification-playwright/pages/a.spec.ts');
  });

  it('keeps a queued-but-already-marked item in the queue', async () => {
    // sync-tests queues substantially MODIFIED items; those already have a
    // marker. Deriving the queue from marker presence alone dropped them and
    // the stale test was never regenerated.
    items({ 'A-01': { content_hash: 'h', pending_generation: true } });
    await spec('a.spec.ts', `// @begin:A-01\nstale\n// @end:A-01\n`);

    linkSpecs(dir);

    expect(queued()).toContain('A-01');
  });

  it('queues every item that has no spec yet', async () => {
    items({ 'A-01': { content_hash: 'h' }, 'B-02': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);

    const res = linkSpecs(dir);

    expect(queued()).toEqual(['B-02']);
    expect(res.pending).toBe(1);
  });

  it('migrates a layout-1 manifest and its bare-array queue before linking', async () => {
    // Older runs wrote the queue as a bare array; ids no longer in the
    // manifest (OLD-01) are dropped, as link-specs always dropped them.
    writeV1(manifestDir, {
      items: { 'A-01': { source_doc: 'docs/verification/a.md', content_hash: 'h' },
               'B-02': { source_doc: 'docs/verification/a.md', content_hash: 'h' } },
      queue: ['OLD-01', 'A-01'], queueEnvelope: false,
    });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);

    linkSpecs(dir);

    expect(existsSync(join(manifestDir, 'items.json'))).toBe(false);
    expect(existsSync(join(specDir, 'pending-generation.json'))).toBe(false);
    expect(queued()).toEqual(['A-01', 'B-02']);
    expect(after()['A-01'].spec_file).toBe('tests/verification-playwright/a.spec.ts');
  });

  it('rewrites only the doc files whose items changed', async () => {
    items({
      'A-01': { content_hash: 'h', source_doc: 'docs/verification/a.md', spec_file: 'tests/verification-playwright/a.spec.ts', status: 'active' },
      'B-01': { content_hash: 'h', source_doc: 'docs/verification/b.md' },
    });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);
    await spec('b.spec.ts', `// @begin:B-01\nt\n// @end:B-01\n`);
    const aBefore = await readFile(join(manifestDir, 'items', 'a.json'), 'utf8');

    linkSpecs(dir);

    expect(await readFile(join(manifestDir, 'items', 'a.json'), 'utf8')).toBe(aBefore);
    expect(after()['B-01'].spec_file).toBe('tests/verification-playwright/b.spec.ts');
  });

  it('reports an orphan marker without minting a manifest entry', async () => {
    items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:GHOST-01\nt\n// @end:GHOST-01\n`);

    const res = linkSpecs(dir);

    expect(res.orphans).toEqual(['GHOST-01']);
    expect(after()['GHOST-01']).toBeUndefined();
  });

  it('flags one item marked in two specs rather than picking a winner', async () => {
    items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);
    await spec('b.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);

    const res = linkSpecs(dir);

    expect(res.duplicates).toHaveLength(1);
    expect(res.duplicates[0]).toContain('A-01');
  });

  it('marks a .skip()ped block as skipped', async () => {
    items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\ntest.skip('x', async () => {});\n// @end:A-01\n`);

    linkSpecs(dir);

    expect(after()['A-01'].status).toBe('skipped');
  });

  it('releases the manifest lock even when it throws', async () => {
    // No items at all: the throw must not strand .lock and wedge every
    // later sync-tests run.
    expect(() => linkSpecs(dir)).toThrow(/No manifest items/);
    expect(existsSync(join(manifestDir, '.lock'))).toBe(false);
  });
});

describe('collectMarkers', () => {
  let dir, specDir;
  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'markers-'));
    specDir = join(dir, 'tests', 'verification-playwright');
    await mkdir(specDir, { recursive: true });
  });
  afterEach(async () => { await rm(dir, { recursive: true, force: true }); });

  it('treats an unterminated @begin as unresolvable rather than guessing', async () => {
    await writeFile(join(specDir, 'a.spec.ts'), `// @begin:A-01\nno end marker\n`);
    const { markers, duplicates } = collectMarkers(dir);
    expect(markers.size).toBe(0);
    expect(duplicates[0]).toContain('no matching @end');
  });
});
