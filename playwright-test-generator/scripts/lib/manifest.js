import { readFile, writeFile, mkdir, rename, unlink } from 'node:fs/promises';
import { join, dirname } from 'node:path';

/**
 * Read and parse a manifest JSON file.
 * Returns null if file doesn't exist (no throw).
 */
export async function readManifestFile(filePath) {
  try {
    const content = await readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (err) {
    if (err.code === 'ENOENT') {
      return null;
    }
    throw err;
  }
}

/**
 * Write a manifest JSON file atomically (write to .tmp, then rename).
 * Creates the parent directory if it doesn't exist.
 */
export async function writeManifestFile(filePath, data) {
  const dir = dirname(filePath);
  await mkdir(dir, { recursive: true });
  const tmpPath = `${filePath}.tmp`;
  await writeFile(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
  await rename(tmpPath, filePath);
}

const LOCK_STALE_MS = 10_000;

/**
 * Acquire a lockfile for manifest operations.
 * Uses PID-based staleness detection — locks older than 10s are overridden.
 */
export async function acquireLock(manifestDir, options = {}) {
  const { retryMs = 200, maxWaitMs = 15_000 } = options;
  const lockPath = join(manifestDir, '.lock');
  const startTime = Date.now();

  while (true) {
    try {
      await writeFile(lockPath, JSON.stringify({ pid: process.pid, time: Date.now() }), {
        flag: 'wx'
      });
      return; // Lock acquired
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;

      // Lock exists — check staleness
      try {
        const lockContent = await readFile(lockPath, 'utf-8');
        const lockData = JSON.parse(lockContent);
        const age = Date.now() - lockData.time;

        if (age > LOCK_STALE_MS) {
          await unlink(lockPath);
          continue;
        }
      } catch {
        // Lock file disappeared or is corrupt — retry
        continue;
      }

      if (Date.now() - startTime > maxWaitMs) {
        throw new Error(`Failed to acquire lock after ${maxWaitMs}ms`);
      }
      await new Promise(resolve => setTimeout(resolve, retryMs));
    }
  }
}

/**
 * Release the lockfile.
 */
export async function releaseLock(manifestDir) {
  const lockPath = join(manifestDir, '.lock');
  try {
    await unlink(lockPath);
  } catch (err) {
    if (err.code !== 'ENOENT') throw err;
  }
}
