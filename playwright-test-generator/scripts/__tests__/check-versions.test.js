import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  parseFrontmatter,
  parseSpecHeader,
  splitRef,
  compareVersions,
  discoverDocs,
  missingAffectedPaths,
  classifyDoc,
  checkVersions,
} from '../check-versions.js';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('parseFrontmatter', () => {
  it('reads scalars and top-level lists', () => {
    const fm = parseFrontmatter(`---
version: "1.2.0"
generated_by: "verification-writer@3.4.0"
id_namespace: EVT  # trailing comment
affected_paths:
  - src/pages/Event.tsx
  - "src/components/event/**"
---

# Doc
`);
    expect(fm.version).toBe('1.2.0');
    expect(fm.generated_by).toBe('verification-writer@3.4.0');
    expect(fm.id_namespace).toBe('EVT');
    expect(fm.affected_paths).toEqual(['src/pages/Event.tsx', 'src/components/event/**']);
  });

  it('returns null when there is no frontmatter', () => {
    expect(parseFrontmatter('# Just a heading\n')).toBeNull();
  });
});

describe('parseSpecHeader', () => {
  it('reads all four annotations', () => {
    const header = parseSpecHeader(`/**
 * @source docs/verification/pages/event.md@1.0.0
 * @source-generated-by verification-writer@3.4.0
 * @metadata tests/verification-playwright/metadata/event.md@1.1.0
 * @generated-by playwright-test-generator@3.9.0
 */
`);
    expect(header.source).toBe('docs/verification/pages/event.md@1.0.0');
    expect(header.sourceGeneratedBy).toBe('verification-writer@3.4.0');
    expect(header.metadata).toBe('tests/verification-playwright/metadata/event.md@1.1.0');
    expect(header.generatedBy).toBe('playwright-test-generator@3.9.0');
  });
});

describe('splitRef', () => {
  it('splits on the last @ so paths and skill names both work', () => {
    expect(splitRef('docs/verification/pages/a.md@1.0.0')).toEqual({
      name: 'docs/verification/pages/a.md',
      version: '1.0.0',
    });
    expect(splitRef(null)).toEqual({ name: null, version: null });
  });
});

describe('compareVersions', () => {
  it('orders semver numerically, not lexically', () => {
    expect(compareVersions('1.10.0', '1.9.0')).toBe(1);
    expect(compareVersions('1.0.0', '1.0.0')).toBe(0);
    expect(compareVersions(null, '0.0.0')).toBe(0);
  });
});

describe('project scans', () => {
  let projectDir;

  const doc = (fm, body = '- [ ] [smoke] **EVT-01** Go --- Ok. *Expected: success*\n') =>
    `---\n${fm}\n---\n\n${body}`;

  beforeEach(async () => {
    projectDir = await mkdtemp(join(tmpdir(), 'check-versions-'));
    await mkdir(join(projectDir, 'docs', 'verification', 'pages'), { recursive: true });
    await mkdir(join(projectDir, 'tests', 'verification-playwright', 'metadata'), { recursive: true });
    await mkdir(join(projectDir, 'tests', 'verification-playwright', 'pages'), { recursive: true });
  });

  afterEach(async () => {
    await rm(projectDir, { recursive: true, force: true });
  });

  it('discovers root-level docs and skips report directories', async () => {
    const root = join(projectDir, 'docs', 'verification');
    await mkdir(join(root, 'findings'), { recursive: true });
    await writeFile(join(root, 'index.md'), 'x');
    await writeFile(join(root, 'shared.md'), 'x');
    await writeFile(join(root, '01-public.md'), 'x');
    await writeFile(join(root, 'pages', 'event.md'), 'x');
    await writeFile(join(root, 'findings', 'report.md'), 'x');

    const found = discoverDocs(root).map((p) => p.slice(root.length + 1));
    expect(found.sort()).toEqual(['01-public.md', join('pages', 'event.md'), 'shared.md']);
  });

  it('flags a doc with no frontmatter', async () => {
    const docPath = join(projectDir, 'docs', 'verification', 'pages', 'event.md');
    await writeFile(docPath, '# Event\n- [ ] item\n');
    expect(classifyDoc(docPath, projectDir).status).toBe('frontmatter-missing');
  });

  it('flags a doc with frontmatter but no generated_by stamp', async () => {
    const docPath = join(projectDir, 'docs', 'verification', 'pages', 'event.md');
    await writeFile(docPath, doc('version: "1.0.0"'));
    expect(classifyDoc(docPath, projectDir).status).toBe('stamp-missing');
  });

  it('walks the chain: metadata-missing -> skill-version-mismatch -> test-missing -> source-updated -> up-to-date', async () => {
    const docPath = join(projectDir, 'docs', 'verification', 'pages', 'event.md');
    const metaPath = join(projectDir, 'tests', 'verification-playwright', 'metadata', 'event.md');
    const specPath = join(projectDir, 'tests', 'verification-playwright', 'pages', 'event.spec.ts');
    const writeSpec = (metaVersion) =>
      writeFile(specPath, `/**
 * @source docs/verification/pages/event.md@1.0.0
 * @source-generated-by verification-writer@3.4.0
 * @metadata tests/verification-playwright/metadata/event.md@${metaVersion}
 * @generated-by playwright-test-generator@3.9.0
 */
`);

    await writeFile(docPath, doc('version: "1.0.0"\ngenerated_by: "verification-writer@3.4.0"'));
    expect(classifyDoc(docPath, projectDir).status).toBe('metadata-missing');

    // Metadata synced against an older verification-writer — hard stop.
    await writeFile(metaPath, doc(`version: "1.0.0"
source: "docs/verification/pages/event.md@1.0.0"
source_generated_by: "verification-writer@3.3.0"`, ''));
    expect(classifyDoc(docPath, projectDir).status).toBe('skill-version-mismatch');

    await writeFile(metaPath, doc(`version: "1.0.0"
source: "docs/verification/pages/event.md@1.0.0"
source_generated_by: "verification-writer@3.4.0"`, ''));
    expect(classifyDoc(docPath, projectDir).status).toBe('test-missing');

    await writeSpec('1.0.0');
    expect(classifyDoc(docPath, projectDir).status).toBe('up-to-date');

    // Doc moves ahead of what the metadata was synced against.
    await writeFile(docPath, doc('version: "1.1.0"\ngenerated_by: "verification-writer@3.4.0"'));
    expect(classifyDoc(docPath, projectDir).status).toBe('source-updated');
  });

  it('flags a spec with no header annotations', async () => {
    const docPath = join(projectDir, 'docs', 'verification', 'pages', 'event.md');
    await writeFile(docPath, doc('version: "1.0.0"\ngenerated_by: "verification-writer@3.4.0"'));
    await writeFile(
      join(projectDir, 'tests', 'verification-playwright', 'metadata', 'event.md'),
      doc(`version: "1.0.0"
source: "docs/verification/pages/event.md@1.0.0"
source_generated_by: "verification-writer@3.4.0"`, '')
    );
    await writeFile(
      join(projectDir, 'tests', 'verification-playwright', 'pages', 'event.spec.ts'),
      "import { test } from '@playwright/test';\n"
    );
    expect(classifyDoc(docPath, projectDir).status).toBe('header-missing');
  });

  it('flags affected_paths that no longer exist on disk', async () => {
    const docPath = join(projectDir, 'docs', 'verification', 'pages', 'event.md');
    await writeFile(
      docPath,
      doc(`version: "1.0.0"
generated_by: "verification-writer@3.4.0"
affected_paths:
  - src/pages/Gone.tsx`)
    );
    await writeFile(
      join(projectDir, 'tests', 'verification-playwright', 'metadata', 'event.md'),
      doc(`version: "1.0.0"
source: "docs/verification/pages/event.md@1.0.0"
source_generated_by: "verification-writer@3.4.0"`, '')
    );
    const result = classifyDoc(docPath, projectDir);
    expect(result.status).toBe('affected-path-missing-on-disk');
    expect(result.missingPaths).toEqual(['src/pages/Gone.tsx']);
  });

  it('counts statuses across the whole project', async () => {
    await writeFile(join(projectDir, 'docs', 'verification', 'pages', 'a.md'), '# no frontmatter\n');
    await writeFile(join(projectDir, 'docs', 'verification', 'pages', 'b.md'), '# no frontmatter\n');
    const report = checkVersions(projectDir);
    expect(report.total).toBe(2);
    expect(report.counts['frontmatter-missing']).toBe(2);
  });
});

describe('missingAffectedPaths', () => {
  it('ignores negation patterns and reports missing literals', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'affected-paths-'));
    await writeFile(join(dir, 'present.ts'), 'x');
    expect(missingAffectedPaths(['present.ts', 'absent.ts', '!ignored.ts'], dir)).toEqual([
      'absent.ts',
    ]);
    await rm(dir, { recursive: true, force: true });
  });
});
