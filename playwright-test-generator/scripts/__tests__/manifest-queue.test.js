import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readPendingQueue, appendPendingQueue, clearPendingQueue, pendingQueuePath } from '../lib/manifest.js';
import { mkdtemp, rm, writeFile, mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

/**
 * The queue file has exactly one reader and one writer, and they agree.
 *
 * They did not always. `sync-tests.js` was fixed to write (and tolerantly
 * read) the `{version, generated_at, items}` envelope while these helpers
 * still assumed a bare array, so `appendPendingQueue` threw
 * "existing is not iterable" on the file `sync-tests.js` had just written —
 * the same crash, one module over.
 */
describe('pending queue helpers', () => {
  let dir;
  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mq-'));
    await mkdir(join(dir, 'tests', 'verification-playwright'), { recursive: true });
  });
  afterEach(async () => { await rm(dir, { recursive: true, force: true }); });

  it('appends onto an envelope written by a previous run', async () => {
    await writeFile(pendingQueuePath(dir), JSON.stringify({
      version: '1.0', generated_at: new Date().toISOString(), items: ['A-01'],
    }));

    appendPendingQueue(dir, ['B-02']);

    expect(readPendingQueue(dir)).toEqual(['A-01', 'B-02']);
  });

  it('appends onto a bare array written by an older run', async () => {
    await writeFile(pendingQueuePath(dir), JSON.stringify(['A-01']));

    appendPendingQueue(dir, ['B-02']);

    expect(readPendingQueue(dir)).toEqual(['A-01', 'B-02']);
  });

  it('always writes the envelope, whatever it read', async () => {
    await writeFile(pendingQueuePath(dir), JSON.stringify(['A-01']));

    appendPendingQueue(dir, ['B-02']);

    const raw = JSON.parse(await readFile(pendingQueuePath(dir), 'utf8'));
    expect(Array.isArray(raw)).toBe(false);
    expect(raw.items).toEqual(['A-01', 'B-02']);
    expect(raw.version).toBe('1.0');
  });

  it('dedupes across runs', async () => {
    appendPendingQueue(dir, ['A-01', 'B-02']);
    appendPendingQueue(dir, ['B-02', 'C-03']);
    expect(readPendingQueue(dir)).toEqual(['A-01', 'B-02', 'C-03']);
  });

  it('reads empty for a missing, empty or corrupt queue', async () => {
    expect(readPendingQueue(dir)).toEqual([]);
    await writeFile(pendingQueuePath(dir), 'not json');
    expect(readPendingQueue(dir)).toEqual([]);
    await writeFile(pendingQueuePath(dir), JSON.stringify({ version: '1.0' }));
    expect(readPendingQueue(dir)).toEqual([]);
  });

  it('creates the directory when the queue is written first', async () => {
    const fresh = await mkdtemp(join(tmpdir(), 'mq-fresh-'));
    appendPendingQueue(fresh, ['A-01']);
    expect(readPendingQueue(fresh)).toEqual(['A-01']);
    await rm(fresh, { recursive: true, force: true });
  });

  it('clear removes the queue', async () => {
    appendPendingQueue(dir, ['A-01']);
    clearPendingQueue(dir);
    expect(readPendingQueue(dir)).toEqual([]);
  });
});
