/**
 * Content hash normalization for verification items.
 * SHA-256 of normalized markdown to prevent churn from whitespace reformatting.
 */

import { createHash } from 'node:crypto';

/**
 * Normalize and hash a verification item's text content.
 * @param {string} itemText - The raw verification item text including annotations
 * @returns {string} Hex-encoded SHA-256 hash
 */
export function hashItem(itemText) {
  const normalized = normalizeItemText(itemText);
  return createHash('sha256').update(normalized, 'utf8').digest('hex');
}

/**
 * Normalize item text for consistent hashing.
 */
export function normalizeItemText(text) {
  const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
  let result = lines.join('\n');

  // Collapse multiple spaces
  result = result.replace(/ {2,}/g, ' ');

  // Lowercase item IDs (pattern: **ITEM-ID**)
  result = result.replace(/\*\*([A-Z0-9][-A-Z0-9]*)\*\*/g, (_, id) => `**${id.toLowerCase()}**`);

  // Remove HTML comment markers
  result = result.replace(/<!--/g, '').replace(/-->/g, '');

  // Sort annotation fields alphabetically within blocks
  result = sortAnnotationFields(result);

  return result;
}

function sortAnnotationFields(text) {
  const annotationPattern = /^\s*\w[\w_]*:/;
  const lines = text.split('\n');
  const result = [];
  let annotationBuffer = [];
  let inAnnotation = false;

  for (const line of lines) {
    if (annotationPattern.test(line.trim())) {
      inAnnotation = true;
      annotationBuffer.push(line);
    } else {
      if (inAnnotation && annotationBuffer.length > 0) {
        annotationBuffer.sort((a, b) => a.trim().localeCompare(b.trim()));
        result.push(...annotationBuffer);
        annotationBuffer = [];
        inAnnotation = false;
      }
      result.push(line);
    }
  }

  if (annotationBuffer.length > 0) {
    annotationBuffer.sort((a, b) => a.trim().localeCompare(b.trim()));
    result.push(...annotationBuffer);
  }

  return result.join('\n');
}

/**
 * Hash the content of a generated test (between @begin/@end markers).
 * @param {string} testContent - The test code between markers
 * @returns {string} Hex-encoded SHA-256 hash
 */
export function hashGeneratedTest(testContent) {
  return createHash('sha256').update(testContent.trim(), 'utf8').digest('hex');
}
