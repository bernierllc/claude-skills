import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readManifestFile, writeManifestFile, acquireLock, releaseLock } from '../../lib/manifest.js';
import { mkdtemp, rm, readFile, writeFile, stat, access } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { constants } from 'node:fs';

describe('manifest', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'manifest-test-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  describe('readManifestFile', () => {
    it('returns parsed JSON when file exists', async () => {
      const filePath = join(tempDir, 'test.json');
      await writeFile(filePath, JSON.stringify({ version: '1.0', items: {} }));

      const result = await readManifestFile(filePath);
      expect(result).toEqual({ version: '1.0', items: {} });
    });

    it('returns null when file is missing', async () => {
      const result = await readManifestFile(join(tempDir, 'nonexistent.json'));
      expect(result).toBeNull();
    });

    it('throws on invalid JSON', async () => {
      const filePath = join(tempDir, 'bad.json');
      await writeFile(filePath, '{invalid json');

      await expect(readManifestFile(filePath)).rejects.toThrow();
    });
  });

  describe('writeManifestFile', () => {
    it('creates the manifest directory if needed', async () => {
      const nestedPath = join(tempDir, 'sub', 'dir', 'manifest.json');
      await writeManifestFile(nestedPath, { version: '1.0' });

      const content = await readFile(nestedPath, 'utf-8');
      expect(JSON.parse(content)).toEqual({ version: '1.0' });
    });

    it('uses atomic write via tmp file and rename', async () => {
      const filePath = join(tempDir, 'atomic.json');
      await writeManifestFile(filePath, { data: 'test' });

      // The .tmp file should not exist after write (it was renamed)
      let tmpExists = true;
      try {
        await access(`${filePath}.tmp`, constants.F_OK);
      } catch {
        tmpExists = false;
      }
      expect(tmpExists).toBe(false);

      // The actual file should exist with correct content
      const content = await readFile(filePath, 'utf-8');
      expect(JSON.parse(content)).toEqual({ data: 'test' });
    });

    it('overwrites existing file', async () => {
      const filePath = join(tempDir, 'overwrite.json');
      await writeManifestFile(filePath, { version: '1.0' });
      await writeManifestFile(filePath, { version: '2.0' });

      const content = await readFile(filePath, 'utf-8');
      expect(JSON.parse(content)).toEqual({ version: '2.0' });
    });
  });

  describe('acquireLock', () => {
    it('creates a lockfile with PID', async () => {
      await acquireLock(tempDir);

      const lockPath = join(tempDir, '.lock');
      const content = await readFile(lockPath, 'utf-8');
      const lockData = JSON.parse(content);
      expect(lockData.pid).toBe(process.pid);
      expect(lockData.time).toBeTypeOf('number');

      await releaseLock(tempDir);
    });

    it('overrides stale lock older than 10 seconds', async () => {
      const lockPath = join(tempDir, '.lock');
      // Write a stale lock (15 seconds old)
      await writeFile(lockPath, JSON.stringify({
        pid: 99999,
        time: Date.now() - 15_000
      }));

      // Should acquire successfully by overriding stale lock
      await acquireLock(tempDir, { retryMs: 50, maxWaitMs: 2000 });

      const content = await readFile(lockPath, 'utf-8');
      const lockData = JSON.parse(content);
      expect(lockData.pid).toBe(process.pid);

      await releaseLock(tempDir);
    });

    it('waits for a fresh lock held by another process', async () => {
      const lockPath = join(tempDir, '.lock');
      // Write a fresh lock
      await writeFile(lockPath, JSON.stringify({
        pid: process.pid,
        time: Date.now()
      }), { flag: 'wx' });

      // Try to acquire with short timeout — should fail
      await expect(
        acquireLock(tempDir, { retryMs: 50, maxWaitMs: 300 })
      ).rejects.toThrow(/Failed to acquire lock/);

      await releaseLock(tempDir);
    });
  });

  describe('releaseLock', () => {
    it('removes the lockfile', async () => {
      await acquireLock(tempDir);
      await releaseLock(tempDir);

      let exists = true;
      try {
        await access(join(tempDir, '.lock'), constants.F_OK);
      } catch {
        exists = false;
      }
      expect(exists).toBe(false);
    });

    it('does not throw if lockfile already removed', async () => {
      await expect(releaseLock(tempDir)).resolves.not.toThrow();
    });
  });
});
