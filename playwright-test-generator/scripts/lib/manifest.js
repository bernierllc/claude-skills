/**
 * Manifest file operations with lockfile-based concurrency safety.
 * Low-level functions operate on direct file paths.
 * CLI scripts construct the full paths (tests/verification-playwright/manifest/).
 */

import { readFile, writeFile, mkdir, unlink, rename, access, stat } from 'node:fs/promises';
import { readFileSync, writeFileSync, mkdirSync, existsSync, unlinkSync, renameSync } from 'node:fs';
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

// --- Sync convenience wrappers for CLI scripts ---

/**
 * Read manifest file synchronously (for CLI scripts).
 * @param {string} projectDir - Project root
 * @param {string} filename - e.g., 'items.json'
 */
export function readManifestFileSync(projectDir, filename) {
  const filePath = join(projectDir, 'tests', 'verification-playwright', 'manifest', filename);
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

export function writeManifestFileSync(projectDir, filename, data) {
  const manifestDir = join(projectDir, 'tests', 'verification-playwright', 'manifest');
  mkdirSync(manifestDir, { recursive: true });
  const filePath = join(manifestDir, filename);
  const tmpPath = `${filePath}.tmp`;
  writeFileSync(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf8');
  renameSync(tmpPath, filePath);
}

export function acquireLockSync(projectDir) {
  const manifestDir = join(projectDir, 'tests', 'verification-playwright', 'manifest');
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
  const lockPath = join(projectDir, 'tests', 'verification-playwright', 'manifest', '.lock');
  try { unlinkSync(lockPath); } catch { /* already removed */ }
}

function queuePath(projectDir) {
  return join(projectDir, 'tests', 'verification-playwright', 'pending-generation.json');
}

/**
 * The canonical on-disk queue is a bare array of item IDs. The skill's drain
 * pass has historically rewritten it as `{ version, generated_at, items }`,
 * so accept that shape too rather than treating it as corruption. Anything
 * else throws — a queue we can't read must not look like an empty one.
 */
export function normalizePendingQueue(parsed) {
  const ids = Array.isArray(parsed) ? parsed
    : Array.isArray(parsed?.items) ? parsed.items
      : null;
  if (!ids) {
    throw new Error('pending-generation.json: expected an array of item IDs or { items: [...] }');
  }
  return [...new Set(ids)];
}

/** Throws if the file exists but is unreadable/unrecognized; [] if absent. */
export function readPendingQueue(projectDir) {
  const path = queuePath(projectDir);
  if (!existsSync(path)) return [];
  return normalizePendingQueue(JSON.parse(readFileSync(path, 'utf8')));
}

export function appendPendingQueue(projectDir, itemIds) {
  const path = queuePath(projectDir);
  const merged = [...new Set([...readPendingQueue(projectDir), ...itemIds])];
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(merged, null, 2) + '\n', 'utf8');
}

export function clearPendingQueue(projectDir) {
  try { unlinkSync(queuePath(projectDir)); } catch { /* already gone */ }
}
