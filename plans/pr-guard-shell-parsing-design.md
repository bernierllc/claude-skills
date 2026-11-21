# pr-guard: stop shell-string parsing from regressing, and fix the 1.5.1 false blocks

Status: planned. Issue: https://github.com/bernierllc/claude-skills/issues/124. Context: PR https://github.com/bernierllc/claude-skills/pull/123 (pr-merge-flow 1.5.1, merged as dd01440). Owner: the author thread of #123, as routed by the claude-skills traffic cop on 2026-11-20.

Amended 2026-11-21 by plan `2026-11-21-tokenizer-first-merge-guard.md` (PR #139): Rule A, Rule B and the parity harness (`pr-merge-flow/tests/test_pr_guard_parity.py`, landed in #127 as aeae404) move into a shared `shell_tokens.py` that both pr-guard and review-gate's merge-guard use. Rule A's wrapper list grows to every wrapper merge-guard 3.2.18 denies. The rules below are otherwise unchanged.

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

## What already exists, and what this plan reuses

Nothing here replaces an incumbent. The guard already has the pieces; the gap is a regression check.

- `segments()` (shlex-based, operator-aware) is the single tokenizer every detector reads. It is kept; no second parser is added.
- Fail-closed wrappers already exist in `segments()`: `env` yields every later word as a candidate command (round 8), and `command` strips its options. Every detector (Codex mention, body file, `gh pr merge`, base sync, draft) reads `segments()`, so a wrapper rule there covers all of them at once.
- Effective-flag parsing already exists: `comment_posts()` with `GH_VALUE_FLAGS` reads pflag short clusters (`-iXPOST`, `-iF x`).
- The round-8 harness (`diff.py`, 46 lines) already loads two copies of `pr-guard.py` in-process, stubs `pr_state`, `not_green`, `unpinned_fork`, `draft_mode` and `fb_log`, and replays every call the test file makes. It is committed as is, not rewritten.
- `scripts/check-version-bumps.py` and `scripts/generate-manifest.py --check` already gate versions in CI.

## Correct fix

### 1. Commit the differential harness as a CI test

- File: `pr-merge-flow/tests/test_pr_guard_parity.py`, adapted from the round-8 `diff.py`.
- **Baseline:** the previous released guard, computed by the test from git, not held in a constant. The repo has no tags or releases, so "released" means on `origin/main`. The test walks `git log origin/main -- pr-merge-flow/` newest first and takes the first commit whose `pr-merge-flow/SKILL.md` version is lower than the head's version. It reads `git show <that sha>:pr-merge-flow/scripts/pr-guard.py`. By construction the baseline is an ancestor of `main` and carries the previous version: for the 1.5.2 PR it resolves to dd01440 (1.5.1). The test prints the SHA and version it chose, and fails if none is found or if `origin/main` is missing. Nothing has to be moved by hand on a release. `check-version-bumps.py` already makes every change to the skill dir bump the version, so the previous version is always the last release.
- **Inputs:** the union of (a) every command string the head `test_pr_guard.py` passes to a guard function, (b) the same from the baseline commit's `test_pr_guard.py` (so deleting a test case cannot drop its input from the check), and (c) `pr-merge-flow/tests/fixtures/pr_guard_inputs.txt`, one command per line with its cwd, holding the review-round attack inputs that never became test cases (the cop's 3,310-input set minus duplicates).
- **Stubs:** the four configs from round 8: base `staging` or `main`, times checks green or red.
- **Compare:** for every input and stub config, call `check(cmd, cwd)` on the baseline and on the head. The baseline blocks when it returns a message. The test fails when the baseline blocks and the head does not, unless the exact `(cmd, cwd)` pair is listed in `ALLOWED_FLIPS` in the test file. Each entry carries a one-line reason and the issue or PR that approved it. New blocks on the head are reported, not failures.
- **Crashes:** an exception from the head fails the test, naming the input. An exception from the baseline is not a block in production: `main()` lets it escape, Python exits 1, and only exit 2 blocks a tool call. The test still treats a baseline crash as "baseline blocks", so the head must block that input. This is a deliberately stricter test policy, so that a crash in the old guard cannot turn into a silent allow in the new one. The test lists such inputs separately.
- **CI:** one step in the `consistency` job, which already checks out with `fetch-depth: 0`, so the `git log` walk and `git show` work without a new fetch. The step: `python3 pr-merge-flow/tests/test_pr_guard_parity.py`.
- **Runtime:** pending until step 1 lands. The author measured the round-8 harness on a laptop at 6.3 s for 838 inputs x 4 configs, but `diff.py` and its corpus are not in the repo yet, so nobody else can reproduce that. Step 1's first commit adds `diff.py` (as `test_pr_guard_parity.py`) and the fixture corpus, then records the measured CI wall time in the PR. The budget is 30 s; the test prints its wall time, and the 5-minute job timeout stays as is.

### 2. Keep wrappers fail closed: an allowlist of known prefixes, everything else unknown

Two rules, both in `segments()`, so every detector (Codex mention, body file, `gh pr merge`, base sync, draft) gets them at once. No wrapper's option arity is parsed, and there is no per-wrapper list of dangerous options.

**Rule A: which words may be the command.** This is unchanged in spirit from round 8. After `env`, every later word is a candidate command, and `command` keeps its current stripping. `sudo`, `nice`, `timeout`, `xargs`, `nohup`, `time` and `exec` get the `env` rule: every later word is a candidate. Today they hide the command. A false block from trying an argument as a command is the accepted cost.

**Rule B: when the directory and root are known (an allowlist).** For a candidate command, the directory and root are known only when the words before it are one of these:

- nothing (the candidate is the first word, after keywords and `NAME=value` prefixes);
- a plain `command` with no options;
- `env` followed only by `NAME=value` assignments.

`env -C dir`/`--chdir[=]dir` keeps today's `$ENV_CHDIR` behavior: the directory is unknown and the root is known, so only an absolute plain path is read. Any other word before the candidate puts the candidate in the unknown state. That covers any wrapper name (`sudo`, `timeout`, …), any option word (including `env -S`/`--split-string`, `env -i`, `env -u`), and any word holding whitespace (a split string such as `'sudo -R /x'`). In the unknown state every body-file input blocks, relative or absolute.

Pinned as blocked:

- body file through a root- or directory-changing word: `env -S 'sudo -R /x' gh pr comment 1 -F /body.md`, `env sudo -R /x gh pr comment 1 -F /body.md`, `sudo env -C d gh pr comment 1 -F /abs/body.md`, `sudo -R /x gh pr comment 1 -F /body.md`, `sudo -D other gh pr comment 1 -F body.md`, `timeout -k 5 60 gh pr comment 1 -F /abs/body.md`;
- body file through any wrapper, even with no options: `sudo gh pr comment 1 -F body.md`, `nice gh pr comment 1 -F "$B"`;
- Git and merge detectors through wrappers: `env git merge origin/main`, `command git merge origin/main`, `sudo git pull origin main`, `timeout 60 git rebase origin/staging`, `xargs gh pr merge`.

Pinned as read, as today:

- `gh pr comment 1 -F body.md`
- `command gh pr comment 1 -F body.md`
- `env X=1 gh pr comment 1 -F body.md`
- `env -C d gh pr comment 1 -F /abs/body.md` (the absolute path is read)

New blocks are not losses, so the parity test allows them. Today `sudo …` and `timeout …` hide `gh` entirely, so those were silent allows. `env -i`/`env -u` before a body file become new false blocks. That is the accepted cost, and SKILL.md "Known limits" records it.

### 3. The three 1.5.1 false blocks

Each one either flips with its exact command listed in `ALLOWED_FLIPS`, or is a written WONTFIX in SKILL.md "Known limits". There is no third option, so the invariant "exit 2 stays exit 2" has only those named exceptions.

- **`env echo gh pr merge 1`: WONTFIX.** Fixing it means knowing that `echo` is not a wrapper, which is the wrapper knowledge step 2 rules out. Reason in SKILL.md: rare, fails closed, workaround is to drop the `env`.
- **A Codex mention whose own characters are split by a backslash-newline inside single quotes: fix.** The form is the one SKILL.md "Known limits" already names: `'@co\<newline>dex'`. In single quotes the shell keeps the backslash-newline, so the posted text holds no mention. The continuation join skips single-quoted spans when building the joined text. The unjoined scan still runs, so an intact mention still blocks. Every existing true positive stays blocked, including the round-5 (H1) cases at test_pr_guard.py:603-605. In those, the backslash-newline only comes before an intact mention (`'thanks\<newline>` + mention + ` review'`), so the mention is still in the posted text. The fix PR adds exactly the split-handle inputs (single-quoted, the handle split at each character position) and lists each one in `ALLOWED_FLIPS`. Double-quoted and unquoted splits, where the shell does join the line, stay blocked, and test cases pin that.
- **Read-only `gh api -X GET … -F x=@"$F"` with an unresolvable file: fix, with effective-method resolution first.** The effective method is the last `-X`/`--method` value in the call, read the way `comment_posts()` already reads flags: separate (`-X GET`), attached (`-XGET`, `--method=GET`) and inside a short cluster (`-iXPOST`). The exemption applies only when that effective method is the literal word `GET`. A variable, a quoted or unknown value, or no `-X` at all (gh then defaults to POST when fields are given) is not GET and stays checked. `gh api repos/o/r/issues/123/comments -X GET -iXPOST -F body=@sub/bad.md` and every other case pinned at test_pr_guard.py:634-640 stay blocked. `ALLOWED_FLIPS` gets exactly `gh api -X GET repos/o/r/issues -F labels=@"$LABEL_FILE"` and `gh api -X GET repos/o/r/issues --input "$B"`. Tracker: https://app.notion.com/p/PR-GUARD-GET-BODY-FILE-FALSE-BLOCK-41e4efecc95a81eabd64fc8a79af8296

### 4. Version

The version bump rides each commit that changes `pr-merge-flow/`, in that same commit. The fix PR lands as one squash commit, so it ships as 1.5.2: SKILL.md and hooks.json bumped, the manifest regenerated with `python3 scripts/generate-manifest.py`, and SKILL.md "Best-effort guard" and "Known limits" updated. The parity test resolves its baseline to dd01440 (1.5.1) on its own.

## Affected surfaces

- In this repo: `pr-merge-flow/scripts/pr-guard.py`, `pr-merge-flow/tests/test_pr_guard.py`, the new `pr-merge-flow/tests/test_pr_guard_parity.py` and `pr-merge-flow/tests/fixtures/pr_guard_inputs.txt`, `pr-merge-flow/SKILL.md`, `pr-merge-flow/hooks.json`, `skills-manifest.json` and `.github/workflows/ci.yml` (one step).
- AEC distribution: agents-environment-config installs the skill from this repo's catalog (`aec install skill pr-merge-flow`, pinned in its `catalog-hashes.json`, hook registered via `.aec/installed-hooks/skill.pr-merge-flow.json`), and carries its own vendored copies under `.claude/agents/.claude/skills/pr-merge-flow/` and `.cursor/commands/`. The catalog hash and those copies update through one PR to the agents-environment-config cop.
- Vendored copies in about 20 repos (`.claude/skills/pr-merge-flow/` in nevar-content, prevost, email_demo, agency-agents, nevar-*, tools and others). Each takes the new version through its own re-vendor PR to its cop, after 1.5.1's re-vendor (nevar-content first).

## Not in scope

The guard is a quota guard, not a security boundary. `bash -c`, `eval`, variables and command substitution stay out of scope, as SKILL.md says.

## Done when

- `test_pr_guard_parity.py` and its fixture corpus are committed and run in CI. The test resolves its baseline to dd01440 (1.5.1), passes, fails on a deliberately lost block (shown once in the fix PR), and its CI wall time is recorded in the PR.
- `ALLOWED_FLIPS` holds only the exact inputs named in step 3, each with its reason.
- `env echo gh pr merge 1` is a written WONTFIX in SKILL.md; the other two false blocks are fixed with tests.
- The step 2 cases are pinned: the blocked list blocks and the read list reads.
- The PR goes to main, gets the adversarial review and Review Gate, and is merged by the claude-skills traffic cop.
