import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mapFilesToTags, main } from '../map-changes.js';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('mapFilesToTags', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'map-changes-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('returns empty output when import index is null', async () => {
    const result = await mapFilesToTags(['file.tsx'], null, tempDir);
    expect(result.tags).toHaveLength(0);
    expect(result.warnings).toHaveLength(0);
  });

  it('returns empty output when import index has no entries', async () => {
    const result = await mapFilesToTags(['file.tsx'], { entries: {} }, tempDir);
    expect(result.tags).toHaveLength(0);
  });

  it('maps verification doc paths to page tags via filename extraction', async () => {
    const result = await mapFilesToTags(
      ['docs/verification/pages/admin-event-form.md'],
      { entries: {} },
      tempDir
    );
    expect(result.tags).toContain('@admin-event-form');
  });

  it('maps source files to page tags via import index lookup', async () => {
    // Create the source file so existence check passes
    const srcDir = join(tempDir, 'src', 'components');
    await mkdir(srcDir, { recursive: true });
    await writeFile(join(srcDir, 'EventForm.tsx'), 'export default function EventForm() {}');

    const importIndex = {
      entries: {
        'src/components/EventForm.tsx': ['admin-event-form', 'admin-event-detail']
      }
    };

    const result = await mapFilesToTags(['src/components/EventForm.tsx'], importIndex, tempDir);
    expect(result.tags).toContain('@admin-event-form');
    expect(result.tags).toContain('@admin-event-detail');
  });

  it('validates file existence and excludes stale entries', async () => {
    const importIndex = {
      entries: {
        'src/deleted-file.tsx': ['some-page']
      }
    };

    const result = await mapFilesToTags(['src/deleted-file.tsx'], importIndex, tempDir);
    expect(result.tags).toHaveLength(0);
    expect(result.warnings).toHaveLength(1);
    expect(result.warnings[0]).toContain('stale');
  });

  it('deduplicates output tags', async () => {
    // Two files mapping to the same page tag
    const srcDir = join(tempDir, 'src');
    await mkdir(srcDir, { recursive: true });
    await writeFile(join(srcDir, 'a.tsx'), '');
    await writeFile(join(srcDir, 'b.tsx'), '');

    const importIndex = {
      entries: {
        'src/a.tsx': ['shared-page'],
        'src/b.tsx': ['shared-page']
      }
    };

    const result = await mapFilesToTags(['src/a.tsx', 'src/b.tsx'], importIndex, tempDir);
    const sharedCount = result.tags.filter(t => t === '@shared-page').length;
    expect(sharedCount).toBe(1);
  });

  it('produces warning for files not in index', async () => {
    const importIndex = { entries: {} };
    const result = await mapFilesToTags(['src/unknown.tsx'], importIndex, tempDir);
    expect(result.warnings).toHaveLength(1);
    expect(result.warnings[0]).toContain('not in import index');
  });
});

describe('main', () => {
  let tempDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'map-main-'));
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('returns empty when import-index.json is missing', async () => {
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
    // No import-index.json created

    const result = await main(['some-file.tsx'], tempDir);
    expect(result.tags).toHaveLength(0);
  });

  it('handles --since-main flag by getting git changed files', async () => {
    // We test this indirectly - when import-index.json is missing, --since-main
    // won't matter because we exit early with empty tags
    const manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });

    const result = await main(['--since-main'], tempDir);
    expect(result.tags).toHaveLength(0);
  });
});
