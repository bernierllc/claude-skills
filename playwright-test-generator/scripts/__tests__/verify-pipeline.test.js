import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  checkManifestIntegrity,
  checkSourceFiles,
  checkSpecFiles,
  checkItemConsistency,
  checkSpecArtifacts,
  checkPinnedTests,
  checkPendingGeneration,
  verifyPipeline
} from '../verify-pipeline.js';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('checkManifestIntegrity', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('reports all green when all manifests are valid', async () => {
    await writeFile(join(tempDir, 'items.json'), '{"version":"1.0","items":{}}');
    await writeFile(join(tempDir, 'import-index.json'), '{"version":"1.0","entries":{}}');
    await writeFile(join(tempDir, 'config.json'), '{"version":"1.0","tiers":{}}');

    const results = await checkManifestIntegrity(tempDir);
    expect(results.every(r => r.status === 'pass')).toBe(true);
    expect(results).toHaveLength(3);
  });

  it('detects invalid JSON in manifest files', async () => {
    await writeFile(join(tempDir, 'items.json'), '{invalid');
    await writeFile(join(tempDir, 'import-index.json'), '{"valid":true}');
    await writeFile(join(tempDir, 'config.json'), '{"valid":true}');

    const results = await checkManifestIntegrity(tempDir);
    const failedItem = results.find(r => r.file === 'items.json');
    expect(failedItem.status).toBe('fail');
    expect(failedItem.message).toContain('Invalid JSON');
  });

  it('warns when manifest file is missing', async () => {
    // Create only two of three files
    await writeFile(join(tempDir, 'items.json'), '{}');
    await writeFile(join(tempDir, 'import-index.json'), '{}');

    const results = await checkManifestIntegrity(tempDir);
    const missingConfig = results.find(r => r.file === 'config.json');
    expect(missingConfig.status).toBe('warn');
  });
});

describe('checkSourceFiles', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-src-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('detects missing source files in import index', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });

    await writeFile(join(manifestDir, 'import-index.json'), JSON.stringify({
      version: '1.0',
      entries: {
        'src/ExistingFile.tsx': ['page-a'],
        'src/MissingFile.tsx': ['page-b']
      }
    }));

    // Create only one of the two files
    const srcDir = join(tempDir, 'src');
    await mkdir(srcDir, { recursive: true });
    await writeFile(join(srcDir, 'ExistingFile.tsx'), 'export default function() {}');

    const results = await checkSourceFiles(manifestDir, tempDir);
    const existing = results.find(r => r.file === 'src/ExistingFile.tsx');
    const missing = results.find(r => r.file === 'src/MissingFile.tsx');

    expect(existing.status).toBe('pass');
    expect(missing.status).toBe('fail');
    expect(missing.message).toContain('not found');
  });

  it('resolves repo-root-relative index keys against repoRoot in a monorepo', async () => {
    // Monorepo shape: Playwright project root is a subdirectory; manifest lives
    // under it. Index keys are repo-root-relative and span two packages.
    const projectDir = join(tempDir, 'apps', 'web');
    const manifestDir = join(projectDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });

    await writeFile(join(manifestDir, 'import-index.json'), JSON.stringify({
      version: '1.0',
      entries: {
        'packages/ui/src/Button.tsx': ['page-a'],
        'apps/web/src/Home.tsx': ['page-b']
      }
    }));

    // Sources exist at the REPO ROOT (tempDir), not under projectDir.
    await mkdir(join(tempDir, 'packages', 'ui', 'src'), { recursive: true });
    await writeFile(join(tempDir, 'packages', 'ui', 'src', 'Button.tsx'), 'export const Button = () => {};');
    await mkdir(join(tempDir, 'apps', 'web', 'src'), { recursive: true });
    await writeFile(join(tempDir, 'apps', 'web', 'src', 'Home.tsx'), 'export const Home = () => {};');

    // With repoRoot passed, both resolve and pass.
    const results = await checkSourceFiles(manifestDir, projectDir, tempDir);
    expect(results.every(r => r.status === 'pass')).toBe(true);

    // Regression guard: the old single-base behavior (repoRoot === projectDir)
    // would double the path and falsely report both as not found.
    const buggy = await checkSourceFiles(manifestDir, projectDir);
    expect(buggy.every(r => r.status === 'fail')).toBe(true);
  });
});

describe('checkSpecFiles', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-spec-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('detects missing spec files referenced by items', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {
        'EVT-01': { spec_file: 'tests/page.spec.ts' },
        'EVT-02': { spec_file: 'tests/missing.spec.ts' }
      }
    }));

    // Create only one spec file
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });
    await writeFile(join(testsDir, 'page.spec.ts'), 'test("x", () => {});');

    const results = await checkSpecFiles(manifestDir, tempDir);
    const existing = results.find(r => r.file === 'tests/page.spec.ts');
    const missing = results.find(r => r.file === 'tests/missing.spec.ts');

    expect(existing.status).toBe('pass');
    expect(missing.status).toBe('fail');
  });
});

describe('checkItemConsistency', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-cons-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('detects orphaned items with no @begin/@end block', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {
        'EVT-01': { spec_file: 'tests/page.spec.ts' },
        'EVT-02': { spec_file: 'tests/page.spec.ts' }
      }
    }));

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:EVT-01
test('EVT-01', async () => {});
// @end:EVT-01
// EVT-02 has no markers
`);

    const results = await checkItemConsistency(manifestDir, tempDir);
    const evt01 = results.find(r => r.itemId === 'EVT-01');
    const evt02 = results.find(r => r.itemId === 'EVT-02');

    expect(evt01.status).toBe('pass');
    expect(evt02.status).toBe('fail');
    expect(evt02.message).toContain('Orphaned');
  });

  it('passes a skipped item whose marked block is a real .skip() stub', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: { 'PUB-07': { spec_file: 'tests/page.spec.ts', status: 'skipped' } }
    }));

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:PUB-07
test.skip('@PUB-07 article cards visible', async ({ page }) => {});
// @end:PUB-07
`);

    const results = await checkItemConsistency(manifestDir, tempDir);
    expect(results.find(r => r.itemId === 'PUB-07').status).toBe('pass');
  });

  it('fails a skipped item whose marked block has no .skip()', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: { 'PUB-07': { spec_file: 'tests/page.spec.ts', status: 'skipped' } }
    }));

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:PUB-07
test('@PUB-07 article cards visible', async ({ page }) => {});
// @end:PUB-07
`);

    const results = await checkItemConsistency(manifestDir, tempDir);
    const r = results.find(r => r.itemId === 'PUB-07');
    expect(r.status).toBe('fail');
    expect(r.message).toContain('no .skip()');
  });
});

describe('checkSpecArtifacts', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-artifact-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('fails specs containing leaked tool-call artifact tokens', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {
        'A': { spec_file: 'tests/clean.spec.ts' },
        'B': { spec_file: 'tests/corrupt.spec.ts' }
      }
    }));

    await writeFile(join(testsDir, 'clean.spec.ts'), `test('a', async () => {});`);
    // Build the artifact token at runtime so this test file itself stays clean.
    const tok = '<' + '/invoke>';
    await writeFile(join(testsDir, 'corrupt.spec.ts'), `test('b', async () => {});\n${tok}\n`);

    const results = await checkSpecArtifacts(manifestDir, tempDir);
    expect(results.find(r => r.file === 'tests/clean.spec.ts').status).toBe('pass');
    const bad = results.find(r => r.file === 'tests/corrupt.spec.ts');
    expect(bad.status).toBe('fail');
    expect(bad.message).toContain('artifact');
  });

  it('passes when all specs are clean', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: { 'A': { spec_file: 'tests/clean.spec.ts' } }
    }));
    await writeFile(join(testsDir, 'clean.spec.ts'), `test('a', async () => {});`);

    const results = await checkSpecArtifacts(manifestDir, tempDir);
    expect(results.every(r => r.status === 'pass')).toBe(true);
  });
});

describe('checkPinnedTests', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-pin-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('reports pinned tests', async () => {
    await writeFile(join(tempDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {
        'EVT-01': { pinned: true },
        'EVT-02': { pinned: false },
        'EVT-03': { pinned: true }
      }
    }));

    const results = await checkPinnedTests(tempDir);
    expect(results).toHaveLength(2);
    expect(results.every(r => r.status === 'warn')).toBe(true);
  });
});

describe('checkPendingGeneration', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-pend-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('reports pending generation items', async () => {
    const verDir = join(tempDir, 'tests', 'verification-playwright');
    await mkdir(verDir, { recursive: true });
    await writeFile(join(verDir, 'pending-generation.json'), JSON.stringify(['EVT-01', 'EVT-02']));

    const results = await checkPendingGeneration(tempDir);
    expect(results).toHaveLength(2);
    expect(results[0].itemId).toBe('EVT-01');
    expect(results[0].status).toBe('warn');
  });

  it('returns empty when no pending file exists', async () => {
    const results = await checkPendingGeneration(tempDir);
    expect(results).toHaveLength(0);
  });
});

describe('verifyPipeline', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-full-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('reports all green when everything is valid', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0', items: {}
    }));
    await writeFile(join(manifestDir, 'import-index.json'), JSON.stringify({
      version: '1.0', entries: {}
    }));
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0', tiers: {}
    }));

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(0);
  });

  it('returns exit code 1 for failures', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });

    // Write invalid JSON to trigger failure
    await writeFile(join(manifestDir, 'items.json'), '{bad json');
    await writeFile(join(manifestDir, 'import-index.json'), '{}');
    await writeFile(join(manifestDir, 'config.json'), '{}');

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(1);
  });

  it('returns exit code 0 when there are only warnings', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: { 'EVT-01': { pinned: true } }
    }));
    await writeFile(join(manifestDir, 'import-index.json'), JSON.stringify({
      version: '1.0', entries: {}
    }));
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0', tiers: {}
    }));

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(0);
  });
});
