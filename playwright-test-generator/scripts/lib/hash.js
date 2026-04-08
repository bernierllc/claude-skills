/**
 * Content hash normalization for verification items.
 * SHA-256 of normalized markdown to prevent churn from whitespace reformatting.
 */

import { createHash } from 'node:crypto';

/**
 * Normalize and hash a verification item's text content.
 * @param {string} itemId - The item ID (e.g., EVT-FRM-01)
 * @param {string} text - The raw item text including annotations
 * @returns {string} Hex-encoded SHA-256 hash
 */
export function hashItem(itemId, text) {
  const { body, annotations } = parseAnnotations(text);
  let normalized = normalizeText(body);
  // Lowercase the item ID for consistency
  const lowerId = itemId.toLowerCase();
  // Re-join with sorted, stripped annotations
  const sortedAnnotations = annotations.map(a => sortAnnotationFields(stripCommentMarkers(a))).join('\n');
  const fullText = `${lowerId}\n${normalized}\n${sortedAnnotations}`;
  return createHash('sha256').update(fullText.trim(), 'utf8').digest('hex');
}

/**
 * Normalize text: strip whitespace per line, collapse spaces.
 * @param {string} text
 * @returns {string}
 */
export function normalizeText(text) {
  const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
  let result = lines.join('\n');
  result = result.replace(/ {2,}/g, ' ');
  return result;
}

/**
 * Remove HTML comment markers from text.
 * @param {string} text
 * @returns {string}
 */
export function stripCommentMarkers(text) {
  return text.replace(/<!--/g, '').replace(/-->/g, '');
}

/**
 * Sort annotation fields (key: value lines) alphabetically.
 * The first line (header like STATE-DEPENDENCY:) is kept in place.
 * @param {string} text
 * @returns {string}
 */
export function sortAnnotationFields(text) {
  const lines = text.split('\n');
  if (lines.length <= 1) return text;

  // First line is the annotation header
  const header = lines[0];
  const fields = lines.slice(1).filter(l => l.trim());
  fields.sort((a, b) => a.trim().localeCompare(b.trim()));
  return [header, ...fields].join('\n');
}

/**
 * Parse annotation blocks from item text.
 * Extracts <!-- ... --> blocks as annotations, returns body without them.
 * @param {string} text
 * @returns {{ body: string, annotations: string[] }}
 */
export function parseAnnotations(text) {
  const annotations = [];
  const body = text.replace(/<!--[\s\S]*?-->/g, (match) => {
    annotations.push(match);
    return '';
  });
  return { body: body.trim(), annotations };
}

/**
 * Hash the content of a generated test (between @begin/@end markers).
 * @param {string} testContent - The test code between markers
 * @returns {string} Hex-encoded SHA-256 hash
 */
export function hashGeneratedTest(testContent) {
  return createHash('sha256').update(testContent.trim(), 'utf8').digest('hex');
}
