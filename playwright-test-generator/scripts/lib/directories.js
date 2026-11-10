import { isEntryPoint } from './repo.js';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve, relative, isAbsolute } from 'node:path';

export function verificationDirectory(repoRoot) {
  const config = join(repoRoot, '.aec', 'directories.json');
  const value = existsSync(config)
    ? JSON.parse(readFileSync(config, 'utf8')).verification ?? 'docs/verification'
    : 'docs/verification';
  const path = resolve(repoRoot, value);
  const rel = relative(resolve(repoRoot), path);
  if (isAbsolute(value) || rel === '..' || rel.startsWith('../')) {
    throw new Error('verification directory must be inside the repository');
  }
  return path;
}

if (isEntryPoint(import.meta.url)) {
  console.log(verificationDirectory(process.argv[2] ?? process.cwd()));
}
