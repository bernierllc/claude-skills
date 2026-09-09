import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtemp, rm, readFile, writeFile, mkdir, chmod } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const hooksJson = fileURLToPath(new URL('../../hooks.json', import.meta.url));

async function preCommitCommand() {
  const { hooks } = JSON.parse(await readFile(hooksJson, 'utf8'));
  const hook = hooks.find((h) => h.id === 'ptg-check-changed-docs-pre-commit');
  return hook.command;
}

// Runs the hook command in `repo` with a stubbed `aec` that logs its argv.
function runHook(command, repo, bin) {
  const env = { ...process.env, PATH: `${bin}:${process.env.PATH}` };
  execFileSync('bash', ['-c', command], { cwd: repo, env, stdio: 'pipe' });
}

describe('ptg-check-changed-docs-pre-commit', () => {
  let repo, bin, log;

  beforeEach(async () => {
    repo = await mkdtemp(join(tmpdir(), 'ptg-hook-'));
    bin = join(repo, '.bin');
    log = join(repo, 'aec.log');
    await mkdir(bin);
    await writeFile(join(bin, 'aec'), `#!/usr/bin/env bash\necho "$@" >> "${log}"\n`);
    await chmod(join(bin, 'aec'), 0o755);
    const git = (...args) => execFileSync('git', args, { cwd: repo, stdio: 'pipe' });
    git('init', '-q');
    git('config', 'user.email', 't@example.com');
    git('config', 'user.name', 'T');
    await mkdir(join(repo, 'docs', 'verification', 'pages'), { recursive: true });
  });

  afterEach(async () => {
    await rm(repo, { recursive: true, force: true });
  });

  it('is a no-op when no verification docs are staged', async () => {
    await writeFile(join(repo, 'src.ts'), 'export const a = 1;\n');
    execFileSync('git', ['add', 'src.ts'], { cwd: repo, stdio: 'pipe' });

    runHook(await preCommitCommand(), repo, bin); // throws on non-zero exit

    await expect(readFile(log, 'utf8')).rejects.toThrow(/ENOENT/);
  });

  it('matches a verification doc at the root of docs/verification', async () => {
    await writeFile(join(repo, 'docs/verification/home.md'), '# home\n');
    execFileSync('git', ['add', 'docs/verification/home.md'], { cwd: repo, stdio: 'pipe' });

    runHook(await preCommitCommand(), repo, bin);

    const lines = (await readFile(log, 'utf8')).trim().split('\n');
    expect(lines[0]).toContain('sync-tests.js docs/verification/home.md');
    expect(lines[1]).toContain('preflight.sh');
  });

  it('syncs each staged doc and then runs preflight', async () => {
    await writeFile(join(repo, 'docs/verification/pages/home.md'), '# home\n');
    execFileSync('git', ['add', 'docs/verification/pages/home.md'], { cwd: repo, stdio: 'pipe' });

    runHook(await preCommitCommand(), repo, bin);

    const lines = (await readFile(log, 'utf8')).trim().split('\n');
    expect(lines[0]).toContain('sync-tests.js docs/verification/pages/home.md');
    expect(lines[1]).toContain('preflight.sh');
  });
});
