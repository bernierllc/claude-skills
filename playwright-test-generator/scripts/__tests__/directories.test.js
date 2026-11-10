import { it, expect } from 'vitest';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkVersions } from '../check-versions.js';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolveDocArg } from '../sync-tests.js';
import { mapFilesToTags } from '../map-changes.js';

it('uses a saved custom directory for edit hooks and changed-file mapping', async () => {
  const repo = mkdtempSync(join(tmpdir(), 'verification-directory-'));
  try {
    mkdirSync(join(repo, '.aec'));
    writeFileSync(join(repo, '.aec/directories.json'), JSON.stringify({ verification: 'quality docs/checks' }));
    mkdirSync(join(repo, 'quality docs/checks/pages'), { recursive: true });
    const file = join(repo, 'quality docs/checks/pages/home.md');
    writeFileSync(file, '# Home');
    const payload = () => JSON.stringify({ tool_input: { file_path: file } });
    expect(resolveDocArg(['node', 'sync-tests.js'], payload, repo)).toBe(file);
    expect(resolveDocArg(['node', 'sync-tests.js'], () => JSON.stringify({ tool_input: { file_path: join(repo, 'docs/verification/old.md') } }), repo)).toBeNull();
    expect(checkVersions(repo).total).toBe(1);
    const preflight = fileURLToPath(new URL('../preflight.sh', import.meta.url));
    const result = spawnSync('bash', [preflight, '--root', repo], { encoding: 'utf8' });
    expect(result.status).toBe(1);
    expect(result.stdout).toContain('could not detect a Node project');
    expect(result.stdout).not.toContain('requires verification docs');
    expect(await mapFilesToTags(['quality docs/checks/home.md'], { entries: {} }, repo)).toEqual({ tags: ['@home'], warnings: [] });
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
