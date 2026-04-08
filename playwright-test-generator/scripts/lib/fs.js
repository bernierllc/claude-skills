import { access } from 'node:fs/promises';
import { constants } from 'node:fs';

/**
 * Check if a file exists on disk.
 */
export async function fileExists(filePath) {
  try {
    await access(filePath, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}
