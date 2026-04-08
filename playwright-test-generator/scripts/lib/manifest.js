/**
 * Manifest file operations with lockfile-based concurrency safety.
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, unlinkSync, renameSync } from 'node:fs';
import { join } from 'node:path';

const LOCK_STALE_MS = 10_000;

export function readManifestFile(dir, filename) {
  const filePath = join(dir, 'tests', 'verification-playwright', 'manifest', filename);
  try {
    return JSON.parse(readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

export function writeManifestFile(dir, filename, data) {
  const manifestDir = join(dir, 'tests', 'verification-playwright', 'manifest');
  mkdirSync(manifestDir, { recursive: true });
  const filePath = join(manifestDir, filename);
  const tmpPath = `${filePath}.tmp`;
  writeFileSync(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf8');
  renameSync(tmpPath, filePath);
}

export function acquireLock(dir) {
  const manifestDir = join(dir, 'tests', 'verification-playwright', 'manifest');
  mkdirSync(manifestDir, { recursive: true });
  const lockPath = join(manifestDir, '.lock');

  if (existsSync(lockPath)) {
    try {
      const lockData = JSON.parse(readFileSync(lockPath, 'utf8'));
      const age = Date.now() - lockData.timestamp;
      if (age < LOCK_STALE_MS && isPidAlive(lockData.pid)) {
        const start = Date.now();
        while (Date.now() - start < LOCK_STALE_MS) {
          Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
          if (!existsSync(lockPath)) break;
          try {
            const cur = JSON.parse(readFileSync(lockPath, 'utf8'));
            if (!isPidAlive(cur.pid) || Date.now() - cur.timestamp >= LOCK_STALE_MS) break;
          } catch { break; }
        }
      }
    } catch { /* corrupted lock, override */ }
  }

  writeFileSync(lockPath, JSON.stringify({ pid: process.pid, timestamp: Date.now() }), 'utf8');
  return () => releaseLock(dir);
}

export function releaseLock(dir) {
  const lockPath = join(dir, 'tests', 'verification-playwright', 'manifest', '.lock');
  try { unlinkSync(lockPath); } catch { /* already removed */ }
}

function isPidAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

export function readPendingQueue(dir) {
  const queuePath = join(dir, 'tests', 'verification-playwright', 'pending-generation.json');
  try { return [...new Set(JSON.parse(readFileSync(queuePath, 'utf8')))]; } catch { return []; }
}

export function appendPendingQueue(dir, itemIds) {
  const queuePath = join(dir, 'tests', 'verification-playwright', 'pending-generation.json');
  let existing = [];
  try { existing = JSON.parse(readFileSync(queuePath, 'utf8')); } catch { /* new file */ }
  const merged = [...new Set([...existing, ...itemIds])];
  mkdirSync(join(dir, 'tests', 'verification-playwright'), { recursive: true });
  writeFileSync(queuePath, JSON.stringify(merged, null, 2) + '\n', 'utf8');
}

export function clearPendingQueue(dir) {
  const queuePath = join(dir, 'tests', 'verification-playwright', 'pending-generation.json');
  try { unlinkSync(queuePath); } catch { /* already gone */ }
}
