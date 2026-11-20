# pr-guard: stop shell-string parsing from regressing, and fix the 1.5.1 false blocks

Status: planned. Issue: https://github.com/bernierllc/claude-skills/issues/124. Context: PR https://github.com/bernierllc/claude-skills/pull/123 (pr-merge-flow 1.5.1, merged as dd01440). Owner: the author thread of #123, as routed by the claude-skills traffic cop on 2026-11-20.

## What happened

`pr-merge-flow/scripts/pr-guard.py` is a PreToolUse hook that tokenizes the Bash command string. It does this to block a Codex review mention, an unreadable comment body file, unsafe merges and base syncs. On #123 it took eight review rounds. Each round fixed one shell form and opened the next:

| Round | Change | New finding |
|---|---|---|
| 5 | join backslash-newline before every detector | H1: a mention split across a continuation passed |
| 6 | `env` short-option cluster rule | J1: `env -uC gh` hid `gh` |
| 7 | `env` option table | K1: `env -S gh` hid `gh` |
| 8 | delete the `env` option parser; try every word after `env` as the command | P1 false block `env echo gh pr merge 1` (accepted by Matt as documented) |

Round 8 lost no block against 1.5.0. That was checked by a differential run: 3,310 inputs x 4 stub configs, 13,240 comparisons. The harness was a throwaway script and is not in the repo.

## Root cause

The guard decides what a shell will execute by re-implementing shell parsing: quoting, continuations, `env` options, `cd` state and wrappers. Every partial re-implementation has edge cases. Review finds them one per round, and nothing in CI stops a fix from losing a block that an earlier release had.

## Correct fix

1. **Commit the differential harness as a test.** Move the round-8 harness (`diff.py`: every attack input from `test_pr_guard.py`, plus the review-round inputs, run against the previous release's `pr-guard.py` fetched from the last release tag) into `pr-merge-flow/tests/`. Assert that every input the previous release blocks (exit 2) still blocks. This turns a "lost block" regression into a CI failure instead of a review round.
2. **Narrow what the guard parses.** Stop interpreting wrappers. If a command contains `gh` as a word in a position the guard does not fully resolve (after `env`, `command`, `xargs`, `sudo`, `nice`, `timeout` or similar), the guard either treats the rest as the command (as `env` does now) or blocks once, with a fix message ("run gh directly"). It never guesses option arities. Pick per detector and record the choice in SKILL.md "Best-effort guard".
3. **Fix or WONTFIX each 1.5.1 false block** (all fail closed today):
   - `env echo gh pr merge 1`: a fix needs to know that `echo` is not a wrapper. Either keep a small allowlist of real wrappers whose next word is the command, or WONTFIX with the reason that the false block is rare and has a one-line workaround.
   - A Codex mention split by a backslash-newline inside single quotes: in single quotes the shell keeps the backslash-newline literally, so the posted text contains no mention. A fix is to join continuations only outside single quotes when scanning the joined text.
   - Read-only `gh api -X GET … -F x=@"$F"` with an unresolvable file: exempt `-X GET` (and `--method GET`) from the body-file check. Tracker: https://app.notion.com/p/PR-GUARD-GET-BODY-FILE-FALSE-BLOCK-41e4efecc95a81eabd64fc8a79af8296
4. Version bump (1.5.2), regenerate the manifest with `python3 scripts/generate-manifest.py`, and update SKILL.md limits.

## Affected surfaces

- `pr-merge-flow/scripts/pr-guard.py`, `pr-merge-flow/tests/test_pr_guard.py`, `pr-merge-flow/SKILL.md` (Best-effort guard and Known limits), `pr-merge-flow/hooks.json` version.
- Vendored copies in about 20 repos (`.claude/skills/pr-merge-flow/` in nevar-content, prevost, email_demo, agency-agents, nevar-*, tools and others). Each takes the new version through its own re-vendor PR to its cop, after 1.5.1's re-vendor (nevar-content first).

## Not in scope

The guard is a quota guard, not a security boundary. `bash -c`, `eval`, variables and command substitution stay out of scope, as SKILL.md says.

## Done when

- The differential test is in CI and passes against 1.5.1.
- Each of the three false blocks is fixed with a test, or has a written WONTFIX in SKILL.md with its reason.
- No input 1.5.1 blocks becomes allowed.
- The PR goes to main, gets the adversarial review and Review Gate, and is merged by the claude-skills traffic cop.
