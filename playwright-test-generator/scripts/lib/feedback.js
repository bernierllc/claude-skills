// Best-effort feedback-loop capture: a missing or failing store never affects this hook.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { spawn } from 'node:child_process';

export function fbLog(subject, severity, summary) {
  const candidates = [
    process.env.AGENT_FEEDBACK_BIN,
    join(process.env.CLAUDE_PROJECT_DIR || '.', '.claude/skills/feedback-loop/scripts/feedback.py'),
    join(homedir(), '.claude/skills/feedback-loop/scripts/feedback.py'),
  ];
  const bin = candidates.find((c) => c && existsSync(c));
  if (!bin) return;
  try {
    // Detached and unref'd: the hook never waits on the store; a spawn failure is ignored by design.
    const child = spawn('python3', [bin, 'log', subject, '--reporter', 'hook', '--severity', severity,
      '--summary', summary, '--quiet'], { stdio: 'ignore', detached: true });
    child.on('error', () => {}); // best-effort: a missing python3 must never break the hook
    child.unref();
  } catch {
    // best-effort by design: feedback must never break the hook
  }
}
