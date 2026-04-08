import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { matchBranch, validateTierOrder, selectTier } from '../select-tier.js';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('matchBranch', () => {
  it('matches exact branch name', () => {
    expect(matchBranch('main', ['main', 'production'])).toBe(true);
  });

  it('matches wildcard pattern', () => {
    expect(matchBranch('feature/foo', ['*'])).toBe(true);
  });

  it('matches glob patterns', () => {
    expect(matchBranch('release/v1.0', ['release/*'])).toBe(true);
  });

  it('returns false for non-matching branch', () => {
    expect(matchBranch('feature/bar', ['main', 'staging'])).toBe(false);
  });

  it('handles string pattern instead of array', () => {
    expect(matchBranch('main', 'main')).toBe(true);
  });
});

describe('validateTierOrder', () => {
  it('allows catch-all tier as the last tier', () => {
    const tiers = {
      full: { branches: ['main', 'production'] },
      thorough: { branches: ['staging', 'develop'] },
      gate: { branches: '*' }
    };
    expect(() => validateTierOrder(tiers)).not.toThrow();
  });

  it('errors if catch-all tier is not last', () => {
    const tiers = {
      gate: { branches: '*' },
      full: { branches: ['main'] }
    };
    expect(() => validateTierOrder(tiers)).toThrow(/catch-all/i);
  });

  it('allows tiers with no catch-all', () => {
    const tiers = {
      full: { branches: ['main'] },
      thorough: { branches: ['staging'] }
    };
    expect(() => validateTierOrder(tiers)).not.toThrow();
  });
});

describe('selectTier', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'select-tier-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('returns "full" for branch matching full tier', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0',
      tiers: {
        full: {
          branches: ['main', 'production'],
          browsers: ['chromium', 'firefox', 'webkit']
        },
        thorough: {
          branches: ['staging'],
          browsers: ['chromium', 'firefox']
        },
        gate: {
          branches: '*',
          browsers: ['chromium']
        }
      }
    }));

    const result = await selectTier('main', tempDir);
    expect(result).toBe('full');
  });

  it('returns "thorough" for staging branch', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0',
      tiers: {
        full: { branches: ['main', 'production'] },
        thorough: { branches: ['staging'] },
        gate: { branches: '*' }
      }
    }));

    const result = await selectTier('staging', tempDir);
    expect(result).toBe('thorough');
  });

  it('returns empty string when config.json is missing', async () => {
    const result = await selectTier('main', tempDir);
    expect(result).toBe('');
  });

  it('returns empty string for feature branch when no catch-all', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0',
      tiers: {
        full: { branches: ['main'] },
        thorough: { branches: ['staging'] }
      }
    }));

    const result = await selectTier('feature/my-branch', tempDir);
    expect(result).toBe('');
  });

  it('handles glob patterns in branch matching', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0',
      tiers: {
        full: { branches: ['release/*'] },
        gate: { branches: '*' }
      }
    }));

    const result = await selectTier('release/v2.0', tempDir);
    expect(result).toBe('full');
  });
});
