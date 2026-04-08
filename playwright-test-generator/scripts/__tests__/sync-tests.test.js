import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  parseVerificationItems,
  detectChanges,
  classifyModification,
  removeTestBlock,
  detectPinning,
  syncTests
} from '../sync-tests.js';
import { hashItem } from '../lib/hash.js';
import { mkdtemp, rm, writeFile, mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

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
    manifestDir = join(tempDir, 'manifest');
    await mkdir(manifestDir, { recursive: true });
  });

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  it('writes substantial changes to pending-generation.json', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# Test
- [ ] [standard] **EVT-01** Do action --- Expected. *Expected: success*
- [ ] [deep] **EVT-02** Another action --- Result. *Expected: validation error*
`);

    // Empty manifest initially
    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {}
    }));

    const result = await syncTests(docPath, manifestDir);
    expect(result.added).toBe(2);
    expect(result.pendingGeneration).toBe(2);

    const pendingPath = join(tempDir, 'pending-generation.json');
    const pending = JSON.parse(await readFile(pendingPath, 'utf-8'));
    expect(pending).toContain('EVT-01');
    expect(pending).toContain('EVT-02');
  });

  it('detects removed items from manifest', async () => {
    const docPath = join(tempDir, 'verification.md');
    await writeFile(docPath, `# Empty\nNo items.`);

    await writeFile(join(manifestDir, 'items.json'), JSON.stringify({
      version: '1.0',
      items: {
        'OLD-01': { content_hash: 'abc', depth: 'standard', status: 'active' }
      }
    }));

    const result = await syncTests(docPath, manifestDir);
    expect(result.removed).toBe(1);

    const updatedManifest = JSON.parse(await readFile(join(manifestDir, 'items.json'), 'utf-8'));
    expect(updatedManifest.items['OLD-01']).toBeUndefined();
  });
});
