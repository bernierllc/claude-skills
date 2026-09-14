import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { linkSpecs, collectMarkers } from '../link-specs.js';
import { readPendingIds, pendingQueuePath } from '../lib/manifest.js';
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

  const items = (obj) => writeFile(
    join(manifestDir, 'items.json'),
    JSON.stringify({ version: '1.0', items: obj }),
  );
  const spec = (name, body) => writeFile(join(specDir, name), body);

  it('links a marked item to its spec and records status', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\ntest('x', async () => {});\n// @end:A-01\n`);

    const res = linkSpecs(dir);

    expect(res.linked).toBe(1);
    const after = JSON.parse(await readFile(join(manifestDir, 'items.json'), 'utf8'));
    expect(after.items['A-01'].spec_file).toBe('tests/verification-playwright/a.spec.ts');
    expect(after.items['A-01'].status).toBe('active');
  });

  it('stores spec_file with POSIX separators', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await mkdir(join(specDir, 'pages'), { recursive: true });
    await spec(join('pages', 'a.spec.ts'), `// @begin:A-01\nt\n// @end:A-01\n`);

    linkSpecs(dir);

    const after = JSON.parse(await readFile(join(manifestDir, 'items.json'), 'utf8'));
    // Backslashes here would be read back on Linux/macOS as a literal filename
    // and checkSpecFiles would report the existing spec as missing.
    expect(after.items['A-01'].spec_file).not.toContain('\\');
    expect(after.items['A-01'].spec_file).toBe('tests/verification-playwright/pages/a.spec.ts');
  });

  it('keeps a queued-but-already-marked item in the queue', async () => {
    // sync-tests queues substantially MODIFIED items; those already have a
    // marker. Deriving the queue from marker presence alone dropped them and
    // the stale test was never regenerated.
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nstale\n// @end:A-01\n`);
    await writeFile(pendingQueuePath(dir), JSON.stringify({
      version: '1.0', generated_at: 'x', items: ['A-01'],
    }));

    linkSpecs(dir);

    expect(readPendingIds(pendingQueuePath(dir))).toContain('A-01');
  });

  it('drops queued ids that have left the manifest', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);
    await writeFile(pendingQueuePath(dir), JSON.stringify({
      version: '1.0', generated_at: 'x', items: ['A-01', 'GONE-99'],
    }));

    linkSpecs(dir);

    expect(readPendingIds(pendingQueuePath(dir))).not.toContain('GONE-99');
  });

  it('writes the queue when the file does not exist yet', async () => {
    // Previously this threw AFTER items.json had already been rewritten,
    // leaving the manifest updated and the queue never written.
    await items({ 'A-01': { content_hash: 'h' }, 'B-02': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);

    linkSpecs(dir);

    expect(readPendingIds(pendingQueuePath(dir))).toEqual(['B-02']);
  });

  it('records pending ids when the queue is a legacy bare array', async () => {
    // `queue.items = pending` on an Array sets a named property that
    // JSON.stringify drops — the ids vanished silently.
    await items({ 'A-01': { content_hash: 'h' }, 'B-02': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);
    await writeFile(pendingQueuePath(dir), JSON.stringify(['OLD-01']));

    linkSpecs(dir);

    const ids = readPendingIds(pendingQueuePath(dir));
    expect(Array.isArray(ids)).toBe(true);
    expect(ids).toContain('B-02');
  });

  it('reports an orphan marker without minting a manifest entry', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:GHOST-01\nt\n// @end:GHOST-01\n`);

    const res = linkSpecs(dir);

    expect(res.orphans).toEqual(['GHOST-01']);
    const after = JSON.parse(await readFile(join(manifestDir, 'items.json'), 'utf8'));
    expect(after.items['GHOST-01']).toBeUndefined();
  });

  it('flags one item marked in two specs rather than picking a winner', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);
    await spec('b.spec.ts', `// @begin:A-01\nt\n// @end:A-01\n`);

    const res = linkSpecs(dir);

    expect(res.duplicates).toHaveLength(1);
    expect(res.duplicates[0]).toContain('A-01');
  });

  it('marks a .skip()ped block as skipped', async () => {
    await items({ 'A-01': { content_hash: 'h' } });
    await spec('a.spec.ts', `// @begin:A-01\ntest.skip('x', async () => {});\n// @end:A-01\n`);

    linkSpecs(dir);

    const after = JSON.parse(await readFile(join(manifestDir, 'items.json'), 'utf8'));
    expect(after.items['A-01'].status).toBe('skipped');
  });

  it('releases the manifest lock even when it throws', async () => {
    // No items.json at all: the throw must not strand .lock and wedge every
    // later sync-tests run.
    await expect(() => linkSpecs(dir)).toThrow();
    const { existsSync } = await import('node:fs');
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
