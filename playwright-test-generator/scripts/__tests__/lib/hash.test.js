import { describe, it, expect } from 'vitest';
import { hashItem, normalizeText, stripCommentMarkers, sortAnnotationFields, parseAnnotations } from '../../lib/hash.js';

describe('normalizeText', () => {
  it('strips leading and trailing whitespace per line', () => {
    const input = '  hello world  \n  goodbye  ';
    const result = normalizeText(input);
    expect(result).toBe('hello world\ngoodbye');
  });

  it('collapses multiple consecutive spaces to a single space', () => {
    const input = 'hello    world   foo';
    const result = normalizeText(input);
    expect(result).toBe('hello world foo');
  });

  it('strips leading/trailing whitespace from the entire result', () => {
    const input = '\n  hello  \n';
    const result = normalizeText(input);
    expect(result).toBe('hello');
  });
});

describe('stripCommentMarkers', () => {
  it('removes <!-- markers', () => {
    expect(stripCommentMarkers('<!-- hello -->')).toBe(' hello ');
  });

  it('removes multiple markers', () => {
    expect(stripCommentMarkers('<!-- a --> <!-- b -->')).toBe(' a   b ');
  });
});

describe('sortAnnotationFields', () => {
  it('sorts fields alphabetically after the header line', () => {
    const input = 'STATE-DEPENDENCY:\nzebra: 1\nalpha: 2\nmiddle: 3';
    const result = sortAnnotationFields(input);
    expect(result).toBe('STATE-DEPENDENCY:\nalpha: 2\nmiddle: 3\nzebra: 1');
  });

  it('handles single-line annotation with no fields', () => {
    const input = 'SIMPLE-ANNOTATION';
    const result = sortAnnotationFields(input);
    expect(result).toBe('SIMPLE-ANNOTATION');
  });
});

describe('parseAnnotations', () => {
  it('extracts annotation blocks from text', () => {
    const text = 'Some body text\n<!-- STATE-DEPENDENCY:\nfield: value\n-->\nMore text';
    const { body, annotations } = parseAnnotations(text);
    expect(annotations).toHaveLength(1);
    expect(annotations[0]).toContain('STATE-DEPENDENCY:');
    expect(body).not.toContain('<!--');
  });

  it('returns empty annotations for text without comments', () => {
    const { body, annotations } = parseAnnotations('just plain text');
    expect(annotations).toHaveLength(0);
    expect(body).toBe('just plain text');
  });
});

describe('hashItem', () => {
  it('produces consistent SHA-256 hex output', () => {
    const hash1 = hashItem('EVT-FRM-01', 'Test action --- expected result');
    const hash2 = hashItem('EVT-FRM-01', 'Test action --- expected result');
    expect(hash1).toBe(hash2);
    expect(hash1).toMatch(/^[a-f0-9]{64}$/);
  });

  it('lowercases item ID in hash computation', () => {
    const hash1 = hashItem('EVT-FRM-01', 'Test action');
    const hash2 = hashItem('evt-frm-01', 'Test action');
    expect(hash1).toBe(hash2);
  });

  it('removes HTML comment markers from annotations before hashing', () => {
    const textWithMarkers = 'Action\n<!-- STATE-DEPENDENCY:\nfield: value\n-->';
    const hash = hashItem('ID-01', textWithMarkers);
    expect(hash).toMatch(/^[a-f0-9]{64}$/);
  });

  it('sorts annotation fields alphabetically', () => {
    const text1 = 'Action\n<!-- TYPE:\nalpha: 1\nbeta: 2\n-->';
    const text2 = 'Action\n<!-- TYPE:\nbeta: 2\nalpha: 1\n-->';
    const hash1 = hashItem('ID-01', text1);
    const hash2 = hashItem('ID-01', text2);
    expect(hash1).toBe(hash2);
  });

  it('produces same hash for semantically identical content with different whitespace', () => {
    const text1 = '  Action   text  \n  Expected   result  ';
    const text2 = 'Action text\nExpected result';
    const hash1 = hashItem('ID-01', text1);
    const hash2 = hashItem('ID-01', text2);
    expect(hash1).toBe(hash2);
  });

  it('produces different hash for different content', () => {
    const hash1 = hashItem('ID-01', 'Action A');
    const hash2 = hashItem('ID-01', 'Action B');
    expect(hash1).not.toBe(hash2);
  });

  it('produces different hash for different item IDs', () => {
    const hash1 = hashItem('ID-01', 'Same action');
    const hash2 = hashItem('ID-02', 'Same action');
    expect(hash1).not.toBe(hash2);
  });
});
