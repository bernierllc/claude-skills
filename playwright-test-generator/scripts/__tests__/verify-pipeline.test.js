import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  checkManifestIntegrity,
  checkSourceFiles,
  checkSpecFiles,
  checkItemConsistency,
  checkSpecArtifacts,
  checkPinnedTests,
  checkPendingGeneration,
  checkManifestLayout,
  verifyPipeline
} from '../verify-pipeline.js';
import { loadManifest } from '../lib/manifest.js';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { writeItems, writeIndex, writeV1 } from './helpers/manifest-fixtures.js';

// The checks take the loaded manifest; load real files through the one loader.
const itemsManifest = (dir, items) => { writeItems(dir, items); return loadManifest(dir); };
const indexManifest = (dir, entries) => { writeIndex(dir, entries); return loadManifest(dir); };

describe('checkManifestIntegrity', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'verify-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('reports all green when all manifests are valid', async () => {
    writeItems(tempDir, { 'A-01': { content_hash: 'h' } });
    writeIndex(tempDir, { 'src/a.ts': ['a'] });
    await writeFile(join(tempDir, 'config.json'), '{"version":"1.0","tiers":{}}');

    const results = await checkManifestIntegrity(tempDir);
    expect(results.every(r => r.status === 'pass')).toBe(true);
    expect(results.map(r => r.file)).toEqual(['config.json', 'items/a.json', 'import-index/a.json']);
  });

  it('detects invalid JSON in manifest files', async () => {
    await mkdir(join(tempDir, 'items'));
    await writeFile(join(tempDir, 'items', 'a.json'), '{invalid');
    await writeFile(join(tempDir, 'config.json'), '{"valid":true}');

    const results = await checkManifestIntegrity(tempDir);
    const failedItem = results.find(r => r.file === 'items/a.json');
    expect(failedItem.status).toBe('fail');
    expect(failedItem.message).toContain('Invalid JSON');
  });

  it('warns when manifest file is missing', async () => {
    writeItems(tempDir, { 'A-01': { content_hash: 'h' } });

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

    const manifest = indexManifest(manifestDir, {
      'src/ExistingFile.tsx': ['page-a'],
      'src/MissingFile.tsx': ['page-b']
    });

    // Create only one of the two files
    const srcDir = join(tempDir, 'src');
    await mkdir(srcDir, { recursive: true });
    await writeFile(join(srcDir, 'ExistingFile.tsx'), 'export default function() {}');

    const results = await checkSourceFiles(manifest, tempDir);
    const existing = results.find(r => r.file === 'src/ExistingFile.tsx');
    const missing = results.find(r => r.file === 'src/MissingFile.tsx');

    expect(existing.status).toBe('pass');
    expect(missing.status).toBe('fail');
    // index-drift.js owns this message and makes it actionable rather than
    // merely descriptive — it names the refresh command.
    expect(missing.message).toContain('is stale');
    expect(missing.message).toContain('playwright-test-generator');
  });

  it('resolves repo-root-relative index keys against repoRoot in a monorepo', async () => {
    // Monorepo shape: Playwright project root is a subdirectory; manifest lives
    // under it. Index keys are repo-root-relative and span two packages.
    const projectDir = join(tempDir, 'apps', 'web');
    const manifestDir = join(projectDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });

    const manifest = indexManifest(manifestDir, {
      'packages/ui/src/Button.tsx': ['page-a'],
      'apps/web/src/Home.tsx': ['page-b']
    });

    // Sources exist at the REPO ROOT (tempDir), not under projectDir.
    await mkdir(join(tempDir, 'packages', 'ui', 'src'), { recursive: true });
    await writeFile(join(tempDir, 'packages', 'ui', 'src', 'Button.tsx'), 'export const Button = () => {};');
    await mkdir(join(tempDir, 'apps', 'web', 'src'), { recursive: true });
    await writeFile(join(tempDir, 'apps', 'web', 'src', 'Home.tsx'), 'export const Home = () => {};');

    // With repoRoot passed, both resolve and pass.
    const results = await checkSourceFiles(manifest, projectDir, tempDir);
    expect(results.every(r => r.status === 'pass')).toBe(true);

    // Regression guard: the old single-base behavior (repoRoot === projectDir)
    // would double the path and falsely report both as not found.
    const buggy = await checkSourceFiles(manifest, projectDir);
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

    const manifest = itemsManifest(manifestDir, {
        'EVT-01': { spec_file: 'tests/page.spec.ts' },
        'EVT-02': { spec_file: 'tests/missing.spec.ts' }
      });

    // Create only one spec file
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });
    await writeFile(join(testsDir, 'page.spec.ts'), 'test("x", () => {});');

    const results = await checkSpecFiles(manifest, tempDir);
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

    const manifest = itemsManifest(manifestDir, {
        'EVT-01': { spec_file: 'tests/page.spec.ts' },
        'EVT-02': { spec_file: 'tests/page.spec.ts' }
      });

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:EVT-01
test('EVT-01', async () => {});
// @end:EVT-01
// EVT-02 has no markers
`);

    const results = await checkItemConsistency(manifest, tempDir);
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

    const manifest = itemsManifest(manifestDir, { 'PUB-07': { spec_file: 'tests/page.spec.ts', status: 'skipped' } });

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:PUB-07
test.skip('@PUB-07 article cards visible', async ({ page }) => {});
// @end:PUB-07
`);

    const results = await checkItemConsistency(manifest, tempDir);
    expect(results.find(r => r.itemId === 'PUB-07').status).toBe('pass');
  });

  it('fails a skipped item whose marked block has no .skip()', async () => {
    const manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
    const testsDir = join(tempDir, 'tests');
    await mkdir(testsDir, { recursive: true });

    const manifest = itemsManifest(manifestDir, { 'PUB-07': { spec_file: 'tests/page.spec.ts', status: 'skipped' } });

    await writeFile(join(testsDir, 'page.spec.ts'), `
// @begin:PUB-07
test('@PUB-07 article cards visible', async ({ page }) => {});
// @end:PUB-07
`);

    const results = await checkItemConsistency(manifest, tempDir);
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

    const manifest = itemsManifest(manifestDir, {
        'A': { spec_file: 'tests/clean.spec.ts' },
        'B': { spec_file: 'tests/corrupt.spec.ts' }
      });

    await writeFile(join(testsDir, 'clean.spec.ts'), `test('a', async () => {});`);
    // Build the artifact token at runtime so this test file itself stays clean.
    const tok = '<' + '/invoke>';
    await writeFile(join(testsDir, 'corrupt.spec.ts'), `test('b', async () => {});\n${tok}\n`);

    const results = await checkSpecArtifacts(manifest, tempDir);
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

    const manifest = itemsManifest(manifestDir, { 'A': { spec_file: 'tests/clean.spec.ts' } });
    await writeFile(join(testsDir, 'clean.spec.ts'), `test('a', async () => {});`);

    const results = await checkSpecArtifacts(manifest, tempDir);
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
    const manifest = itemsManifest(tempDir, {
        'EVT-01': { pinned: true },
        'EVT-02': { pinned: false },
        'EVT-03': { pinned: true }
      });

    const results = await checkPinnedTests(manifest);
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

  it('reports items flagged pending_generation across doc files', async () => {
    writeItems(tempDir, {
      'EVT-01': { source_doc: 'docs/verification/a.md', pending_generation: true },
      'EVT-02': { source_doc: 'docs/verification/b.md', pending_generation: true },
      'EVT-03': { source_doc: 'docs/verification/b.md' },
    });

    const results = await checkPendingGeneration(loadManifest(tempDir));
    expect(results.map(r => r.itemId).sort()).toEqual(['EVT-01', 'EVT-02']);
    expect(results.every(r => r.status === 'warn')).toBe(true);
  });

  it('returns empty when nothing is flagged', async () => {
    const results = await checkPendingGeneration(itemsManifest(tempDir, { 'EVT-01': {} }));
    expect(results).toHaveLength(0);
  });
});

describe('checkManifestLayout', () => {
  let tempDir;
  beforeEach(async () => { tempDir = await mkdtemp(join(tmpdir(), 'vp-layout-')); });
  afterEach(async () => { await rm(tempDir, { recursive: true, force: true }); });

  it('passes silently on the current layout', async () => {
    writeItems(tempDir, { 'A-01': {} });
    writeIndex(tempDir, { 'src/a.ts': ['a'] });
    const { checks, manifest } = await checkManifestLayout(tempDir);
    expect(checks).toEqual([]);
    expect(Object.keys(manifest.items)).toEqual(['A-01']);
  });

  it('warns and names the fix after migrating a pure layout-1 manifest', async () => {
    writeV1(tempDir, { items: { 'A-01': { source_doc: 'docs/verification/a.md' } } });
    const { checks, manifest } = await checkManifestLayout(tempDir);
    expect(checks).toHaveLength(1);
    expect(checks[0].status).toBe('warn');
    expect(checks[0].message).toMatch(/migrated from layout 1.*git rm items\.json/s);
    expect(Object.keys(manifest.items)).toEqual(['A-01']);
  });

  it('fails when a layout-1 file sits next to the per-doc files, after folding it in', async () => {
    writeItems(tempDir, { 'A-01': {} });
    writeV1(tempDir, { items: { 'B-01': { source_doc: 'docs/verification/b.md' } } });
    const { checks, manifest } = await checkManifestLayout(tempDir);
    expect(checks[0].status).toBe('fail');
    expect(checks[0].message).toMatch(/committed alongside.*Fix: commit manifest\/items\/.*git rm items\.json/s);
    expect(Object.keys(manifest.items).sort()).toEqual(['A-01', 'B-01']);
  });

  it('fails when a bootstrapped manifest has no item files (items/ deleted or emptied)', async () => {
    await writeFile(join(tempDir, 'config.json'), '{}');
    await mkdir(join(tempDir, 'items'));
    const { checks, manifest } = await checkManifestLayout(tempDir);
    expect(manifest).toBeNull();
    expect(checks[0]).toMatchObject({ file: 'items/', status: 'fail' });
    expect(checks[0].message).toMatch(/no per-doc item files.*Fix: restore/s);
  });

  it('warns when items exist but import-index/ is empty', async () => {
    writeItems(tempDir, { 'A-01': {} });
    const { checks } = await checkManifestLayout(tempDir);
    expect(checks).toEqual([expect.objectContaining({ file: 'import-index/', status: 'warn' })]);
  });

  it('fails loudly and leaves the old files when layout 1 cannot be migrated', async () => {
    writeV1(tempDir, { items: { 'A-01': {} } });
    const { checks, manifest } = await checkManifestLayout(tempDir);
    expect(manifest).toBeNull();
    expect(checks[0].status).toBe('fail');
    expect(checks[0].message).toMatch(/no source_doc.*A-01.*Fix:/s);
    expect(existsSync(join(tempDir, 'items.json'))).toBe(true);
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

    writeItems(manifestDir, { 'A-01': { content_hash: 'h' } });
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
    await mkdir(join(manifestDir, 'items'));
    await writeFile(join(manifestDir, 'items', 'a.json'), '{bad json');
    await writeFile(join(manifestDir, 'config.json'), '{}');

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(1);
  });

  it('returns exit code 0 when there are only warnings', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });

    writeItems(manifestDir, { 'EVT-01': { pinned: true } });
    await writeFile(join(manifestDir, 'config.json'), JSON.stringify({
      version: '1.0', tiers: {}
    }));

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(0);
  });

  it('returns exit code 1 when a layout-1 file sits next to the per-doc layout', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    writeItems(manifestDir, { 'A-01': { content_hash: 'h' } });
    writeV1(manifestDir, { index: { 'src/a.ts': ['a'] } });

    const result = await verifyPipeline(tempDir);
    expect(result.exitCode).toBe(1);
    expect(result.checks.some(c => /committed alongside/.test(c.message ?? ''))).toBe(true);
  });
});
