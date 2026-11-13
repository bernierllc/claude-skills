# Adopting the feedback loop in an item

The capture point lives **inside the item**, because friction is noticed while the item runs.
Never add feedback instructions to a project's `AGENTS.md` / `CLAUDE.md` or to an installer: the
item carries its own loop and works the same wherever it is installed.

Do **not** list `feedback-loop` under the item's `dependencies:`. The loop is optional: an item
whose user has not installed it (or has turned it off) must run exactly as before.

## Skills and agents: the standard section

Append this block as the item's last section, with `<kind>` (`skill` or `agent`) and `<name>`
filled in. The HTML comments delimit it so upstream merges and future updates to the block stay
mechanical: replace everything between the markers, never edit around them.

```markdown
<!-- feedback-loop:begin -->
## Feedback

If the `feedback-loop` skill is installed, use it to improve this <kind> over time:

- When this <kind>'s own instructions cause rework, a wrong default, a missed case or a needless
  pause, log it as it happens: subject `<kind>:<name>`, with the phase or section at fault and the
  concrete fix to these instructions.
- At the end of a run, check `<kind>:<name>`; if a review is due, make the feedback-loop offer.

If `feedback-loop` is not installed, ignore this section.
<!-- feedback-loop:end -->
```

An item that owns a moment in the development process (shipping, CI, test runs, planning,
review, deploy) adds one more bullet inside the block:

```markdown
- When the project's own process causes friction during this <kind>'s work (for example a flaky
  or slow CI job, a test that missed a regression, a plan that was wrong about the code), log it
  as subject `process:<project>` with `--area <ci|test|plan|review|deploy|dev>`.
```

Bump the item's `version` (minor) when adding or changing the block.

## Hooks: capture in the script

A hook cannot read a markdown section, so it logs from code, and only when **the hook itself**
is at fault: it crashed, timed out, needed a tool that is missing, or could not parse its input.
A hook that correctly blocks something is working and logs nothing.

Rules:

- Best-effort and silent: dispatch the logger in the background and never wait on it, never
  print its output, and return success from the logging function on every path, so a hook
  running under `set -e` or checking `$?` is unaffected.
- Subject: `hook:<owning-item>/<hook-id>` (for example `hook:my-skill/post-edit`), reporter
  `hook`.
- Summary names the failure, never file contents, arguments or environment values.

Shell:

```bash
fb_log() {  # fb_log <severity> <summary>: backgrounded, always returns 0
  local c
  for c in "${AGENT_FEEDBACK_BIN:-}" "${CLAUDE_PROJECT_DIR:-.}/.claude/skills/feedback-loop/scripts/feedback.py" \
           "$HOME/.claude/skills/feedback-loop/scripts/feedback.py"; do
    if [ -n "$c" ] && [ -f "$c" ]; then
      ( python3 "$c" log "hook:my-skill/post-edit" --reporter hook \
          --severity "$1" --summary "$2" --quiet </dev/null >/dev/null 2>&1 & ) 2>/dev/null
      return 0
    fi
  done
  return 0
}
command -v tsc >/dev/null || fb_log medium "tsc not found; type-check skipped"
```

Python:

```python
def fb_log(severity: str, summary: str) -> None:
    """Best-effort and detached: the hook never waits on, or fails because of, the feedback store."""
    import os, subprocess
    from pathlib import Path
    candidates = [os.environ.get("AGENT_FEEDBACK_BIN"),
                  Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude/skills/feedback-loop/scripts/feedback.py",
                  Path.home() / ".claude/skills/feedback-loop/scripts/feedback.py"]
    for c in candidates:
        if c and Path(c).is_file():
            try:
                subprocess.Popen(["python3", str(c), "log", "hook:my-skill/post-edit", "--reporter", "hook",
                                  "--severity", severity, "--summary", summary, "--quiet"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                pass  # best-effort by design: feedback must never break the hook
            return
```

## Plugins and CLIs

A plugin follows the skill pattern for its skills and agents and the hook pattern for its
hooks. A CLI that wants to capture its own failures without an agent present (as AEC does)
writes the same entry format directly; the entry fields are documented in the main SKILL.md
and covered by `scripts/test_feedback_loop.py`.
