import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { resolveRepoRoot } from '../../lib/repo.js';
import { mkdtemp, rm, mkdir } from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('resolveRepoRoot', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'repo-root-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('returns the git toplevel when called from a subdirectory of a repo', async () => {
    execSync('git init -q', { cwd: tempDir });
    const subdir = join(tempDir, 'apps', 'web');
    await mkdir(subdir, { recursive: true });

    // git resolves symlinks (e.g. macOS /var → /private/var), so compare realpaths.
    expect(resolveRepoRoot(subdir)).toBe(realpathSync(tempDir));
  });

  it('falls back to projectDir when git is unavailable (not a repo / invalid cwd)', () => {
    const bogus = join(tempDir, 'does-not-exist');
    expect(resolveRepoRoot(bogus)).toBe(bogus);
  });
});
