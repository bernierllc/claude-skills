// Best-effort feedback-loop capture: a missing or failing store never affects this hook.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';

export function fbLog(subject, severity, summary) {
  const candidates = [
    process.env.AGENT_FEEDBACK_BIN,
    join(process.env.CLAUDE_PROJECT_DIR || '.', '.claude/skills/feedback-loop/scripts/feedback.py'),
    join(homedir(), '.claude/skills/feedback-loop/scripts/feedback.py'),
  ];
  const bin = candidates.find((c) => c && existsSync(c));
  if (!bin) return;
  // spawnSync never throws on a failed child; its result is ignored by design.
  spawnSync('python3', [bin, 'log', subject, '--reporter', 'hook', '--severity', severity,
    '--summary', summary, '--quiet'], { stdio: 'ignore', timeout: 5000 });
}
