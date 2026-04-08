import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  checkManifestIntegrity,
  checkSourceFiles,
  checkSpecFiles,
  checkItemConsistency,
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
