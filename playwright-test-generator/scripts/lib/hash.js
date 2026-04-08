import { createHash } from 'node:crypto';

/**
 * Normalize text for hashing:
 * 1. Strip leading/trailing whitespace per line
 * 2. Collapse multiple consecutive spaces to a single space
 */
export function normalizeText(text) {
  return text
    .split('\n')
    .map(line => line.trim())
    .join('\n')
    .replace(/ {2,}/g, ' ')
    .trim();
}

/**
 * Remove HTML comment markers from annotation text.
 */
export function stripCommentMarkers(text) {
  return text.replace(/<!--/g, '').replace(/-->/g, '');
}

/**
 * Sort annotation fields alphabetically within an annotation block.
 * Fields are key: value lines after the header line.
 */
export function sortAnnotationFields(annotationBlock) {
  const lines = annotationBlock.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length <= 1) return lines.join('\n');
  const header = lines[0];
  const fields = lines.slice(1);
  fields.sort((a, b) => a.localeCompare(b));
  return [header, ...fields].join('\n');
}

/**
 * Parse annotation blocks (<!-- ... -->) from item text.
 */
export function parseAnnotations(text) {
  const annotations = [];
  let body = text;
  const annotationRegex = /<!--\s*([\s\S]*?)\s*-->/g;
  let match;
  while ((match = annotationRegex.exec(text)) !== null) {
    annotations.push(match[1]);
    body = body.replace(match[0], '');
  }
  return { body: body.trim(), annotations };
}

/**
 * Hash a verification item producing a consistent SHA-256 hex string.
 * @param {string} itemId - The item ID (e.g., "EVT-FRM-TKT-03")
 * @param {string} itemText - The full item text including annotations
 * @returns {string} Hex SHA-256 hash
 */
export function hashItem(itemId, itemText) {
  const normalizedId = itemId.toLowerCase();
  const { body, annotations } = parseAnnotations(itemText);
  const normalizedBody = normalizeText(body);

  const sortedAnnotations = annotations
    .map(a => stripCommentMarkers(a))
    .map(a => sortAnnotationFields(a))
    .sort()
    .join('\n');

  const content = `${normalizedId}\n${normalizedBody}\n${sortedAnnotations}`;
  return createHash('sha256').update(content).digest('hex');
}
