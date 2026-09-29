import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  parseVerificationItems,
  detectChanges,
  classifyModification,
  removeTestBlock,
  detectPinning,
  syncTests,
  resolveDocArg,
  readStdinWithin
} from '../sync-tests.js';
import { spawn } from 'node:child_process';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';
import { hashItem } from '../lib/hash.js';
import { mkdtemp, rm, writeFile, mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { existsSync, readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { writeItems, readItems, readItemFiles, writeV1 } from './helpers/manifest-fixtures.js';

describe('parseVerificationItems', () => {
  it('parses verification items from markdown', () => {
    const markdown = `# Test Doc
- [ ] [standard] **EVT-FRM-01** Enter ticket price --- Validation error. *Expected: client-side validation error*
- [ ] [deep] **EVT-FRM-02** Submit form empty --- Error shown. *Expected: success*
`;
    const items = parseVerificationItems(markdown);
    expect(items).toHaveLength(2);
    expect(items[0].id).toBe('EVT-FRM-01');
    expect(items[0].depth).toBe('standard');
    expect(items[0].action).toContain('Enter ticket price');
    expect(items[1].id).toBe('EVT-FRM-02');
    expect(items[1].depth).toBe('deep');
  });

  it('handles empty verification doc gracefully', () => {
    const items = parseVerificationItems('# Empty Doc\nNo items here.');
    expect(items).toHaveLength(0);
  });

  it('handles malformed items gracefully by skipping them', () => {
    const markdown = `# Test Doc
- [ ] This is malformed no ID no depth
- [ ] [standard] **EVT-FRM-01** Valid item --- Expected result. *Expected: success*
- Some random line
`;
    const items = parseVerificationItems(markdown);
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe('EVT-FRM-01');
  });

  it('extracts expected type from item text', () => {
    const markdown = `- [ ] [standard] **EVT-FRM-01** Do something --- Result. *Expected: client-side validation error*`;
    const items = parseVerificationItems(markdown);
    expect(items[0].expectedType).toBe('client-side validation error');
  });
});

describe('detectChanges', () => {
  it('detects new items not in manifest', () => {
    const docItems = [
      { id: 'NEW-01', contentHash: 'abc123' },
      { id: 'NEW-02', contentHash: 'def456' }
    ];
    const manifestItems = {};
    const changes = detectChanges(docItems, manifestItems);
    expect(changes.added).toHaveLength(2);
    expect(changes.removed).toHaveLength(0);
    expect(changes.modified).toHaveLength(0);
  });

  it('detects removed items in manifest but not in doc', () => {
    const docItems = [];
    const manifestItems = {
      'OLD-01': { content_hash: 'abc123' }
    };
    const changes = detectChanges(docItems, manifestItems);
    expect(changes.removed).toHaveLength(1);
    expect(changes.removed[0].id).toBe('OLD-01');
  });

  it('detects modified items with hash changes', () => {
    const docItems = [
      { id: 'MOD-01', contentHash: 'newhash' }
    ];
    const manifestItems = {
      'MOD-01': { content_hash: 'oldhash' }
    };
    const changes = detectChanges(docItems, manifestItems);
    expect(changes.modified).toHaveLength(1);
  });

  it('identifies unchanged items', () => {
    const docItems = [
      { id: 'SAME-01', contentHash: 'samehash' }
    ];
    const manifestItems = {
      'SAME-01': { content_hash: 'samehash' }
    };
    const changes = detectChanges(docItems, manifestItems);
    expect(changes.unchanged).toHaveLength(1);
    expect(changes.modified).toHaveLength(0);
  });
});

describe('classifyModification', () => {
  it('classifies same depth and type as minor', () => {
    const item = { depth: 'standard', expectedType: 'success' };
    const manifestEntry = { depth: 'standard', expected_type: 'success' };
    expect(classifyModification(item, manifestEntry)).toBe('minor');
  });

  it('classifies changed depth as substantial', () => {
    const item = { depth: 'deep', expectedType: 'success' };
    const manifestEntry = { depth: 'standard', expected_type: 'success' };
    expect(classifyModification(item, manifestEntry)).toBe('substantial');
  });

  it('classifies changed expected type as substantial', () => {
    const item = { depth: 'standard', expectedType: 'validation error' };
    const manifestEntry = { depth: 'standard', expected_type: 'success' };
    expect(classifyModification(item, manifestEntry)).toBe('substantial');
  });
});

describe('removeTestBlock', () => {
  it('removes test code between @begin:ID / @end:ID markers', () => {
    const spec = `// other test
// @begin:EVT-01
test('EVT-01', async () => {
  // test code
});
// @end:EVT-01
// more tests`;

    const result = removeTestBlock(spec, 'EVT-01');
    expect(result).not.toContain('@begin:EVT-01');
    expect(result).not.toContain('@end:EVT-01');
    expect(result).not.toContain('test code');
    expect(result).toContain('// other test');
    expect(result).toContain('// more tests');
  });

  it('returns content unchanged when markers not found', () => {
    const spec = '// no markers here\ntest("something", () => {});';
    const result = removeTestBlock(spec, 'NONEXISTENT');
    expect(result).toBe(spec);
  });
});

describe('detectPinning', () => {
  it('detects when test has been manually edited', () => {
    const specContent = `// @begin:EVT-01
test('original', () => {});
// @end:EVT-01`;
    // The generated hash won't match since we pass a different hash
    const result = detectPinning(specContent, 'EVT-01', 'completely-different-hash');
    expect(result).toBe(true);
  });

  it('returns false when markers are not found', () => {
    const result = detectPinning('no markers', 'EVT-01', 'somehash');
    expect(result).toBe(false);
  });
});

describe('syncTests (integration)', () => {
  let tempDir;
  let manifestDir;

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), 'sync-tests-'));
    // Real layout: sync-tests derives repoRoot as manifestDir/../../.., so a
    // fixture that puts the manifest directly under tempDir makes repoRoot
    // resolve two levels ABOVE the temp dir and source_doc paths come out
    // nonsense. Mirror the shape the code actually assumes.
    manifestDir = join(tempDir, 'tests', 'verification-playwright', 'manifest');
    await mkdir(manifestDir, { recursive: true });
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('queues new items with a pending_generation flag in the doc\'s own file', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# Test
- [ ] [standard] **EVT-01** Do action --- Expected. *Expected: success*
- [ ] [deep] **EVT-02** Another action --- Result. *Expected: validation error*
`);

    const result = await syncTests(docPath, manifestDir);
    expect(result.added).toBe(2);
    expect(result.pendingGeneration).toBe(2);

    expect(readItemFiles(manifestDir)).toEqual(['verification.json']);
    const after = readItems(manifestDir);
    expect(after['EVT-01'].pending_generation).toBe(true);
    expect(after['EVT-02'].pending_generation).toBe(true);
    // No shared queue file any more.
    expect(existsSync(join(manifestDir, '..', 'pending-generation.json'))).toBe(false);
  });

  it('refuses to write when an item ID is already owned by another doc', async () => {
    const docPath = join(tempDir, 'use-cases.md');
    await writeFile(docPath, `# Use Cases
- [ ] [standard] **USC-01** Do action --- Expected. *Expected: success*
`);
    writeItems(manifestDir, {
      'USC-01': { source_doc: 'u-scheduling.md', content_hash: 'abc', depth: 'standard', status: 'active' },
    });
    const before = await readFile(join(manifestDir, 'items', 'u-scheduling.json'), 'utf-8');

    // The owner lives in a different per-doc file; the guard still sees it.
    await expect(syncTests(docPath, manifestDir)).rejects.toThrow(/USC-01 — already owned by u-scheduling\.md/);

    // The other doc's file survives untouched and no file is minted for ours.
    expect(await readFile(join(manifestDir, 'items', 'u-scheduling.json'), 'utf-8')).toBe(before);
    expect(readItemFiles(manifestDir)).toEqual(['u-scheduling.json']);
  });

  it('does not treat another doc\'s same-named file as its own items', async () => {
    // pages/beta-signup.md and flows/beta-signup.md share a basename. Matching
    // ownership on the basename made the flows doc consider all 14 of the pages
    // doc's items removed and delete them from the committed manifest on its
    // first sync. Ownership compares the full repo-relative path.
    const pagesDir = join(tempDir, 'docs', 'verification', 'pages');
    const flowsDir = join(tempDir, 'docs', 'verification', 'flows');
    await mkdir(pagesDir, { recursive: true });
    await mkdir(flowsDir, { recursive: true });

    const flowsDoc = join(flowsDir, 'beta-signup.md');
    await writeFile(flowsDoc, `# Flows\nNo items.`);
    writeItems(manifestDir, {
      'PAGE-01': { source_doc: 'docs/verification/pages/beta-signup.md', content_hash: 'abc', depth: 'standard', status: 'active' },
    });

    const result = await syncTests(flowsDoc, manifestDir);

    expect(result.removed).toBe(0);
    expect(readItems(manifestDir)['PAGE-01']).toBeDefined();
  });

  it('stores source_doc repo-relative, never absolute', async () => {
    // An absolute path is machine-specific: it bakes one developer's home
    // directory into a committed artifact and rewrites every entry the moment
    // anyone syncs from a different checkout.
    const docsDir = join(tempDir, 'docs', 'verification', 'pages');
    await mkdir(docsDir, { recursive: true });
    const docPath = join(docsDir, 'thing.md');
    await writeFile(docPath, `# Thing\n\n- [ ] [standard] **THG-01** click it --- it works. *Expected: state change*\n`);

    await syncTests(docPath, manifestDir);

    expect(readItemFiles(manifestDir)).toEqual(['pages--thing.json']);
    const after = readItems(manifestDir);
    expect(after['THG-01'].source_doc).toBe('docs/verification/pages/thing.md');
    expect(after['THG-01'].source_doc.startsWith('/')).toBe(false);
  });

  it('removes a removed item, its queue flag, and a doc file left empty', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# Empty\nNo items.`);
    writeItems(manifestDir, {
      'OLD-01': { source_doc: 'verification.md', content_hash: 'abc', depth: 'standard', status: 'active', pending_generation: true },
    });

    const result = await syncTests(docPath, manifestDir);
    expect(result.removed).toBe(1);

    expect(readItems(manifestDir)['OLD-01']).toBeUndefined();
    expect(readItemFiles(manifestDir)).toEqual([]);
  });

  it('a no-op sync rewrites nothing', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# T\n- [ ] [standard] **EVT-01** Do action --- Expected. *Expected: success*\n`);
    await syncTests(docPath, manifestDir);
    const before = await readFile(join(manifestDir, 'items', 'verification.json'), 'utf-8');

    await syncTests(docPath, manifestDir);

    expect(await readFile(join(manifestDir, 'items', 'verification.json'), 'utf-8')).toBe(before);
  });

  it('edits to two different docs touch disjoint manifest files', async () => {
    // The point of the per-doc layout: two PRs that edit different docs must
    // not both rewrite a shared file, or every such pair conflicts on merge.
    const docs = join(tempDir, 'docs', 'verification');
    await mkdir(docs, { recursive: true });
    const a = join(docs, 'a.md');
    const b = join(docs, 'b.md');
    await writeFile(a, `# A\n- [ ] [standard] **A-01** act --- ok. *Expected: success*\n`);
    await writeFile(b, `# B\n- [ ] [standard] **B-01** act --- ok. *Expected: success*\n`);
    await syncTests(a, manifestDir);
    await syncTests(b, manifestDir);
    const snapshot = () => Object.fromEntries(
      readItemFiles(manifestDir).map((f) => [f, readFileSync(join(manifestDir, 'items', f), 'utf-8')]));
    const base = snapshot();

    const changed = (after) => Object.keys({ ...base, ...after }).filter((f) => base[f] !== after[f]);

    await writeFile(a, `# A\n- [ ] [deep] **A-01** act --- ok. *Expected: success*\n- [ ] [standard] **A-02** more --- ok. *Expected: success*\n`);
    await syncTests(a, manifestDir);
    const afterA = snapshot();
    expect(changed(afterA)).toEqual(['a.json']);

    // Reset to base and make the other branch's edit.
    for (const [f, body] of Object.entries(base)) writeFileSync(join(manifestDir, 'items', f), body);
    await writeFile(a, `# A\n- [ ] [standard] **A-01** act --- ok. *Expected: success*\n`);
    await writeFile(b, `# B\n- [ ] [deep] **B-01** act --- ok. *Expected: success*\n`);
    await syncTests(b, manifestDir);
    expect(changed(snapshot())).toEqual(['b.json']);

    // No repo-wide file exists for either edit to collide on.
    expect(readdirSync(manifestDir).sort()).toEqual(['items']);
  });

  it('migrates a layout-1 manifest on first sync', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# T\n- [ ] [standard] **EVT-01** Do action --- Expected. *Expected: success*\n`);
    writeV1(manifestDir, { items: {
      'KEEP-01': { source_doc: 'other.md', content_hash: 'x', depth: 'standard', status: 'active' },
    }, queue: ['KEEP-01'] });

    await syncTests(docPath, manifestDir);

    expect(existsSync(join(manifestDir, 'items.json'))).toBe(false);
    const after = readItems(manifestDir);
    expect(after['KEEP-01'].pending_generation).toBe(true);
    expect(after['EVT-01']).toBeDefined();
    expect(readItemFiles(manifestDir)).toEqual(['other.json', 'verification.json']);
  });
});

describe('resolveDocArg', () => {
  const stdin = payload => () => JSON.stringify(payload);

  it('prefers an explicit path argument', () => {
    expect(resolveDocArg(['node', 'sync-tests.js', 'docs/verification/pages/a.md'], stdin({})))
      .toBe('docs/verification/pages/a.md');
  });

  it('falls back to the hook payload on stdin', () => {
    const argv = ['node', 'sync-tests.js'];
    const payload = { tool_input: { file_path: '/repo/docs/verification/pages/a.md' } };
    expect(resolveDocArg(argv, stdin(payload))).toBe('/repo/docs/verification/pages/a.md');
  });

  it('ignores edits to files that are not verification docs', () => {
    const payload = { tool_input: { file_path: '/repo/src/app/page.tsx' } };
    expect(resolveDocArg(['node', 'sync-tests.js'], stdin(payload))).toBeNull();
  });

  it('returns null when stdin is empty or unparseable', () => {
    expect(resolveDocArg(['node', 'sync-tests.js'], () => '')).toBeNull();
  });
  it('returns undefined when no stdin payload is coming', () => {
    expect(resolveDocArg(['node', 'sync-tests.js'], () => undefined)).toBeUndefined();
  });
});

describe('readStdinWithin', () => {
  it('returns what the hook wrote once it closes stdin', async () => {
    const stream = new PassThrough();
    stream.end('{"tool_input":{}}');
    expect(await readStdinWithin(stream, 1000)).toBe('{"tool_input":{}}');
  });

  it('keeps waiting while a slow writer is still sending', async () => {
    const stream = new PassThrough();
    // Each gap (30ms) is inside the 50ms idle bound; the total (120ms) is not.
    const chunks = ['{"tool', '_input"', ':{', '}}'];
    chunks.forEach((c, i) => setTimeout(() => stream.write(c), 30 * i));
    setTimeout(() => stream.end(), 30 * chunks.length);
    expect(await readStdinWithin(stream, 50)).toBe('{"tool_input":{}}');
  });

  it('returns what was sent when the writer goes quiet without closing', async () => {
    const stream = new PassThrough();
    stream.write('{"tool_input":{}}');
    expect(await readStdinWithin(stream, 50)).toBe('{"tool_input":{}}');
  });

  it('gives up on a pipe that stays open without writing', async () => {
    expect(await readStdinWithin(new PassThrough(), 50)).toBeUndefined();
  });

  it('never reads a terminal', async () => {
    const stream = Object.assign(new PassThrough(), { isTTY: true });
    expect(await readStdinWithin(stream, 10_000)).toBeUndefined();
  });

  it('CLI with no argument and a never-closing stdin exits 2 with usage instead of hanging', async () => {
    const script = fileURLToPath(new URL('../sync-tests.js', import.meta.url));
    const child = spawn(process.execPath, [script], { stdio: ['pipe', 'pipe', 'pipe'] });
    try {
      let stderr = '';
      child.stderr.on('data', d => { stderr += d; });
      const code = await new Promise(res => child.on('exit', res));
      expect(code).toBe(2);
      expect(stderr).toMatch(/Usage: node sync-tests\.js <verification-doc-path>/);
    } finally {
      child.kill();
    }
  }, 10_000);
});
