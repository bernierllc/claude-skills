# Tokenizer-first merge guard: one shell tokenizer, decisions on tokens only

Status: planned. Priority: P1. Tracker: https://app.notion.com/p/TOKENIZER-FIRST-MERGE-GUARD-one-shell-tokenizer-decisions-on-tokens-only-claude-skills-plan-owed-41f4efecc95a8185beeffea8ba1d6bf5 (tier and schedule come from the PM task). Owed by PR https://github.com/bernierllc/claude-skills/pull/137 (review-gate 3.2.18), whose "Simplify or plan" section records the raw-text second pass as a stopgap and says "a plan for it is owed". Amends plan `pr-guard-shell-parsing-design.md` (issue #124): its Rule A, Rule B and parity harness become the shared module's, for both guards. Why P1: both guards are the last client-side stop before an unreviewed merge, and each bypass found so far was a real `gh pr merge` that ran while the hook said allow.

## What happened

Two PreToolUse hooks decide, from the Bash command string, whether a command will merge a PR or post a forbidden comment:

- `review-gate/scripts/merge-guard.py` (4,236 lines)
- `pr-merge-flow/scripts/pr-guard.py` (933 lines)

Neither decides on the words the shell will run. merge-guard has dozens of detectors. Some read `shlex` tokens. Some run regexes over raw text (`MERGE_RE`, `_PR_MERGE_LOOSE_RE`, `QUOTE_SMASHED_GH_RE`, `_ARRAY_ASSIGN_RE`, the printf and positional-parameter scanners). Some re-implement one more piece of Bash first (`_dequote_shell_text`, `_collapse_empty_quotes`, `_decode_ansi_c`, the heredoc and comment scanners). pr-guard has its own shlex-based `segments()` with private-use stand-ins for quoted operators.

Each review round found the next spelling that one detector saw differently from Bash:

| PR | Guard | Bypass spellings found in review (each one ran a merge, or would have, while the guard allowed it) |
|---|---|---|
| #129 (pr-merge-flow 1.5.4) | pr-guard | `env -S 'env X=\\c gh pr merge 1 --admin'`: `.split("\\c")` treated an escaped backslash as the start of `\c`. Also `env -S 'gh\c' pr merge 1`, `env '-Sgh\c' pr merge 1`, `env --split-string='gh\_pr\c' merge 1`, `env -S "env X='\c' gh pr merge 1"` |
| #130 (review-gate 3.2.15) | merge-guard | `git commit -m "\"'$(gh pr merge 5 --admin)"\'`: the inert-mention check misread an escaped quote and treated an executed `$(…)` as literal text. `git commit --amend -m "gh pr merge 5 --admin"` with a `post-commit` hook or `GIT_EDITOR` that merges: a blanket `git commit` exemption. #130 fixed both by dropping the inert-mention allowlist: a quoted `gh pr merge` now denies with the `git commit -F <file>` hint (`QuotedMentions`) |
| #132 (pr-merge-flow 1.5.5, open) | pr-guard | `/usr/bin/env -S'gh pr merge 17 --admin'`, `env -vS'gh pr merge 17 --admin'`, `env -S 'env -S "gh pr merge 17 --admin"'`, ``env -S "`printf gh` pr merge 17 --auto"``, `builtin exec env -S 'gh pr merge 17 --admin'`, ``echo `env -S 'gh pr merge 17 --admin'` ``, `bash -c "env -S 'gh pr merge 17 --admin'"` (also `sh -c`, `/bin/bash -c`, `/bin/sh -c`) |
| #137 (review-gate 3.2.18), 3 P1 rounds | merge-guard | `": '" + "z"*16001 + "'; g''h pr mer''ge 7 --squash"` and `g\h pr mer\ge 7` (a size shortcut decided on raw text); `$'\x67\x68' pr $'mer\x67e' 7` and `g\<newline>h pr mer\<newline>ge 7` (Bash finishes the words before running them, the guard did not); `gh pr ` × 2,000 (`MERGE_RE` backtracked past the 25 s hook timeout, and a hook killed at its timeout loses its denial); an 80 KB command took 6-50 s |

#137 ended with this shape:

- `normalize_command` joins continuations and decodes `$'…'` before any check.
- Because that pass does not track quoting, the raw text is checked a second time, and the guard denies if either pass does.
- A 22 s `setitimer` deadline denies before the hook timeout.

The second pass can add a denial but never drops one, so it is safe. But it is a stopgap: every future check now runs twice, on two texts, and still on text instead of words.

## Root cause

Both guards decide on text that Bash has not finished turning into words. Each detector re-derives, its own way, what the shell will run: quoting, escapes, `$'…'`, continuations, wrappers, operators. Two derivations of the same command disagree at the edges, and an attacker (or an unlucky agent) needs only one detector to say "no merge here". The review loop finds one disagreement per round. Nothing makes a fix in one detector reach the others.

## What already exists, and what this plan reuses

Incumbent check: does this reimplement something the framework, a dependency, or this repo already provides?

- **`shlex` (stdlib)** is the base of both guards' tokenizing today (`merge-guard._shell_tokens_once`, `pr-guard.shell_tokens` with `punctuation_chars`). This plan keeps it as the word splitter inside spans the scanner has proven plain (section 1). It does not add a parser dependency. bashlex is unmaintained and has no `$'…'` or `env -S`. tree-sitter-bash is a compiled wheel a hook cannot assume. Both would also re-implement Bash.
- **`pr-guard.segments()`** is the most complete existing tokenizer: operator-aware, with quoted-operator stand-ins, and a fail-closed path when shlex cannot parse. It is the starting point of the shared module, not a second design.
- **`merge-guard.normalize_command` and `_decode_ansi_c`** (3.2.18) already do the pre-word steps. They move into the shared module, with quoting tracked, so the raw-text second pass can go.
- **merge-guard's 3.2.18 denials are the floor.** It denies, among others: `watch`, `find -exec`, `stdbuf`, `ssh`, `docker exec` and `xargs` wrapping a merge; `su -c`, `bash -c`, `eval`; `<(…)`, `${x:-$(…)}`, `$(…)` and backticks anywhere; heredoc bodies; a quoted `gh pr merge` mention in any argument; a dynamic `gh` executable name (`$X pr merge 7`, `'gh\<newline>' pr merge 7`); a dynamic subcommand slot (`gh $X merge 7`, `gh pr $X 7`, `gh $X`); a merge spelled through expansions (`gh${IFS}pr${IFS}merge 7`) or mentioned in a word that also expands (`"gh pr merge $N"`); `gh pr merge` assembled from a function, an array, `set --` or a variable (`a=(gh pr merge 7); "${a[@]}"`, `set -- gh pr merge 7; "$@"`, `c=gh; $c pr merge 7`); `gh`, `pr`, `merge` passed as arguments (`echo gh pr merge 7`); dynamic argv after `gh pr merge` (`gh pr merge $N`); compound commands (`{ …; }`, `( … )`, `if … fi`) and alias invocations that run a merge. Verified against `origin/main` 933f29e with `merge-guard.check_command`. The migration keeps every one of these denials (the parity harness enforces it) and adds no allow. Every row in the test table below states its result today; the few the plan denies and 3.2.18 allows are marked **new deny**, and the one known limit both allow is marked as such.
- **Plan `plans/pr-guard-shell-parsing-design.md`** (issue #124) already fixes pr-guard's wrapper rules (Rule A and Rule B) and its regression harness. This plan does not redo that. It takes Rule A and Rule B as the wrapper policy of the shared module, so merge-guard gets them too.
- **`pr-merge-flow/tests/test_pr_guard_parity.py`** (landed in #127, aeae404) is the differential harness: baseline guard from `origin/main` against head, and every block the baseline had must survive. The same harness is extended to merge-guard. It is not rewritten.
- **Deadlines today.** merge-guard has `HOOK_BUDGET_S = 20.0` for `gh` calls plus a `CHECK_DEADLINE_S = 22.0` `setitimer` alarm around the whole check (25 s hook timeout in `review-gate/hooks.json`). pr-guard has `GH_BUDGET_S = 15` and `_left(deadline, cap)` (20 s hook timeout in `pr-merge-flow/hooks.json`) and no alarm. `check-review-gate.gh_deadline` is a third, but it belongs to the CI checker, which is installed standalone and is not a hook; it stays as it is.
- **The byte-identical mirror pattern** (`scripts/check-review-gate.py` ↔ `review-gate/scripts/check-review-gate.py`, pinned by a test) is how one file ships inside two skills that are vendored independently.
- **Plan `docs/superpowers/plans/2026-11-17-api-merge-guard.md`** moves enforcement server-side, so an API, GraphQL or `git push` merge cannot skip the gate. That is the real boundary. This plan makes the client-side hook honest and cheap; it does not replace that plan, and its priority does not depend on it.

## Correct fix

### 1. One shared tokenizer: `shell_tokens.py`

One file, shipped as byte-identical copies in `review-gate/scripts/shell_tokens.py` and `pr-merge-flow/scripts/shell_tokens.py`. A repo test fails when the two differ. The skills are vendored separately into other repos, so neither may import the other's directory.

Its one entry point, `shell_tokens.tokenize(cmd) -> Parsed`, is the only function in either guard that reads the command string. `Parsed` holds the **segments**, the **comments** (where the `# review-gate-ok:` and pr-guard overrides live) and a list of **parse failures**. Each segment is a list of **words**, and each word is one of:

- `Literal(text)`: a word whose final text is fully known after Bash's quote removal, escapes, `$'…'` decoding and continuation joins, decided per quoting context: a backslash-newline joins only outside single quotes, and `\c`, `\\` and escaped quotes are read in the context they appear.
- `Unresolved(reason, raw, nested, fragments)`: a word whose text the tokenizer cannot know. Causes: parameter or arithmetic expansion (including `${x:-…}` forms), `$(…)`, backticks, `<(…)` and `>(…)`, globs in the command position, `~user`. The reason names the construct. A substitution has two effects, and the word keeps both: Bash runs the body, and its output becomes part of the word. `nested` carries each body that Bash runs (`$(…)`, backticks, `<(…)`, `>(…)`, and a `$(…)` inside `${x:-…}`), parsed into segments by the same function. `fragments` is the word's known literal text in order, with one hole where each expansion stands, after the same quote removal and escapes as a `Literal` (`gh${IFS}pr${IFS}merge` → `gh`, hole, `pr`, hole, `merge`; `"gh pr merge $N"` → `gh pr merge `, hole). Decisions may read `fragments`, which come from tokens. `raw` is the source span, used only to write the denial message; no decision reads it.
- `Nested(segments)`: the parsed body of a string that a wrapper hands to a shell as a command, where the word itself is consumed rather than kept as text: `bash|sh|zsh|dash|ksh -c`, `su -c`, `ssh <host> <command…>`, `docker|podman|kubectl exec … sh -c`, `env -S`/`--split-string` (including attached `-S'…'`, short clusters such as `-vS'…'`, and `\c` truncation), `eval`, `watch <command…>`, `find -exec|-execdir|-ok|-okdir … ;`, `xargs`, and heredoc or here-string bodies (a heredoc body is parsed for substitutions unless its delimiter is quoted, and parsed as a whole script when it feeds a shell).

Segments split on control operators (`;`, `&&`, `||`, `|`, `|&`, `&`, newline) and keep the operator, so a detector can still ask "does this run after a `cd`". Grouping and reserved words (`{`, `}`, `(`, `)`, `if`, `then`, `elif`, `else`, `fi`, `while`, `until`, `do`, `done`, `case`, `esac`, `function`, `name()`) also start a new segment, so the body of a group, subshell, condition, loop or function definition is its own segment and its first word is a command position. An array assignment `a=(w1 w2 …)` yields its elements as words of the segment, in order.

**Failures are part of the result, never an exception.** An unbalanced quote, an unknown `$'…'` escape, an unterminated `$(`, `${` or heredoc, a nesting depth past the cap, or a time or size budget hit is recorded in `Parsed.failures` with the construct and its offset. Section 2 denies the whole command on any failure.

**How it finds the ends of constructs.** One left-to-right scanner with a stack of quoting contexts (plain, single, double, `$'…'`, `$(…)`, backticks, `${…}`, `<(…)`/`>(…)`, heredoc). It tracks nesting itself and finds where each construct ends, including `)` inside quotes inside `$(…)`, `}` inside `${x:-"}"}`, and heredoc delimiters (with `<<-` tab stripping and quoted delimiters). shlex is never given text with an open construct: it splits only the plain spans between constructs, which the scanner has already closed. Each body found is fed back through `tokenize`, with the depth cap.

**Wrapper policy.** The shared module applies the #124 plan's Rule A and Rule B. Rule A's list (every later word is a candidate command) is at least every wrapper 3.2.18 denies: `env`, `sudo`, `doas`, `su`, `nice`, `ionice`, `timeout`, `xargs`, `nohup`, `time`, `exec`, `builtin`, `command`, `stdbuf`, `setsid`, `chroot`, `watch`, `find -exec` and its siblings, `ssh`, `docker|podman|kubectl exec`. Absolute and relative paths to any of them (`/usr/bin/env`, `./bash`) count. Rule B (directory and root are known only after nothing, a plain `command`, or `env NAME=value…`) is unchanged. pr-guard's own copy of these rules is deleted in the migration.

The wrapper list is not what finds a merge. Section 2's R2 and R3 look at every word of every segment, so a wrapper missing from the list still denies (as `unknown-wrapper gh pr merge 7` does today); the list only decides which strings are parsed as `Nested` and where Rule B can know the directory.

**Cost.** The scanner is one pass with a stack, linear in the length of the command; shlex on each closed plain span is linear too. Each distinct text is tokenized once (`lru_cache`, as 3.2.18 already does). No regex in the module may backtrack: every pattern is anchored or a fixed literal. A size or depth cap records a failure, which denies. The module has a test that times `gh pr ` × 2,000, 80 KB of padding before a merge, 2,000 nested quotes and 500 nested `$(` against a 1 s budget.

### 2. Decisions on tokens only, fail closed on anything unresolved

Every detector in both guards takes `Parsed`, never a string. The rules below reproduce 3.2.18's denials on words. Each is named so the test table and the denial message can cite it. Every rule applies to every segment, to every `Nested` body and to the `nested` bodies of every `Unresolved` word, recursively. A segment's **merge words** are `gh`, then `pr`, then `merge`, in order, after skipping `gh`'s global flags (`-R`, `--repo`, `--hostname`).

- **R1 executed merge.** The segment's merge words start at a command position: the first word of the segment, or a later word that Rule A makes a candidate command. Only a merge in a top-level segment goes on to the gate checks (reviews, threads, labels), and only behind the wrapper prefixes 3.2.18 gate-checks today. The same merge words at a command position inside a `Nested` body (`bash -c`, `ssh`, `env -S`, …) or inside a group, subshell, condition, loop or function body deny outright as wrapped or compound, as 3.2.18 does; the parity harness pins which is which. A wrapper missing from Rule A's list still reaches R2.
- **R2 displaced merge words.** The segment has merge words as separate `Literal` words, but `gh` is not at a command position: `echo gh pr merge 7`, `printf '%s ' gh pr merge 7`, `set -- gh pr merge 7`, the elements of `a=(gh pr merge 7)`, arguments to a function or to an unlisted wrapper. Deny: "`gh pr merge` must be the directly executed command". This is what denies array, positional and function-argument assembly without evaluating it.
- **R3 mention.** A word's text contains a `gh … pr … merge` spelling (the three words in order, separated by whitespace). For a `Literal` the text is the word; for an `Unresolved` it is its `fragments` joined with each hole read as a word separator. Deny with the hint 3.2.15 added: "write the message to a file and use `git commit -F <file>`". This covers a commit message, a grep pattern, a file name, an assignment value (`x="gh pr merge"`), a mention that also expands (`git commit -m "run gh pr merge $N"`, `echo "gh pr merge $N" | bash`) and a merge spelled through expansions (`gh${IFS}pr${IFS}merge 7`). It keeps the no-inert-mention rule that `QuotedMentions` (`review-gate/tests/test_merge_guard_hyphen.py`) pins: rc 2 plus the `git commit -F` hint. There is no allowlist of "inert" commands or arguments.
- **R4 unresolved command name.** A word at a command position is `Unresolved` and a later word in the segment is `merge` (`$X pr merge 7`, `c=gh; $c pr merge 7`, `$(printf g)h pr merge 7`, `'gh\<newline>' pr merge 7`). `$X pr view 7` and `$EDITOR notes.txt` stay allowed, as in 3.2.18.
- **R5 unresolved subcommand.** The command is `gh` and either subcommand slot after the global flags is `Unresolved`, whatever follows (`gh $X merge 7`, `gh pr $X 7`, `gh $X`).
- **R6 dynamic merge argv.** An R1 merge has an `Unresolved` word anywhere after `merge` (`gh pr merge $N`, `f() { gh pr merge "$@"; }; f 5`). The guard cannot know the PR, repo or flags, so it denies instead of checking gates on a guess.
- **R7 parse failure.** Any entry in `Parsed.failures` denies the whole command, naming the construct and offset. **Cost:** this denies a few commands that today's guards allow and Bash runs, for example a heredoc with no closing delimiter (`cat <<EOF` newline `hi`: Bash warns and runs it). Both guards allow that today, so these are **new denials**; the fix for the user is to close the construct. An unterminated quote or `$(` (`echo 'unterminated`, `echo $(ls`) is also allowed by both guards today; Bash rejects those as syntax errors, so denying them costs nothing.
- **R8 effects outside the text keep today's detectors, rewritten to read words.** These exist in 3.2.18 and move as they are: `PATH` and other shell-state assignments (including `case … ) PATH=`, `((PATH=0))`, `let`, `unset PATH`), `hash -p`, alias and function definitions of `gh` or of a command that then runs a merge (an alias body is a shell string, parsed as `Nested`, so `alias m='gh pr merge'` then `m 7` denies), and `command_not_found_handle`. They read `Literal("PATH=…")` assignment words and `Literal("alias")` command words instead of regexes over raw text. No new detector is added here; effects the text cannot show are under Not in scope.

Each denial names the rule and, for R4 to R6, the construct from `Unresolved.reason`: "the command name comes from `$X`; write it literally".

**Known limit, unchanged from 3.2.18: a command name computed at run time.** `$(printf 'gh pr m%s' erge) 7` and `x=$(printf 'gh pr m%s' erge); $x 7` are allowed today, and the plan keeps allowing them. No word is `merge` and no fragment spells it, so R3 and R4 do not fire. A rule that denied them (any `Unresolved` command word followed by any argument) would also deny `$EDITOR notes.txt` and every `"$cmd" args` script line, and still miss `$(cat cmd.txt)`. The boundary for computed commands is the server-side plan; the test table pins these two as allowed so a later change has to say so if it moves them.
- **The raw-text second pass and `normalize_command` are deleted.** They exist only because the first pass lost quoting.
- **Overrides** (`# review-gate-ok:`, the pr-guard overrides) are read from `Parsed.comments`.

### 3. Fail closed on a crash or a missing module

A hook that exits with anything but 2 lets the command run. Today merge-guard's `__main__` catches `BaseException` and exits 2, but pr-guard's `__main__` logs and re-raises, so a crash exits 1 and the merge runs.

- A second mirrored file, `hook_runtime.py`, ships byte-identical in both skills' `scripts/` (same mirror test). It holds `run_hook(main, budget_s)`, which both guards' `__main__` call. It catches `BaseException`, prints a denial naming the exception, and exits 2. A `SystemExit` passes through only for codes 0 and 2.
- **Unreadable hook input denies.** pr-guard's `main` returns 0 today when stdin is not JSON (`except ValueError: return 0`); `run_hook` reads stdin itself and denies instead, for both guards. A `tool_name` other than `Bash` stays an allow: it is not a shell command, and the hook is registered for `pre_tool_use` on every tool.
- **What exit 2 does depends on the agent.** Exit 2 is the deny code for Claude Code `PreToolUse` and Gemini `BeforeTool`. aec translates `hooks.json` per agent: Cursor has no exit-code deny and Codex has no entry for this event, so on those agents neither guard denies, before or after this plan. That is aec's hook-translation surface, not this plan's. The skill `hooks.json` keeps `timeout_ms`; aec writes each agent's own field (Claude Code's `timeout`, in seconds).
- Each guard loads `hook_runtime` and `shell_tokens` from its own directory inside a `try` that is the first statement of `__main__`. An `ImportError` or any error while loading prints "review-gate: guard module missing or broken (`<name>`); reinstall the skill" and exits 2. A test deletes each module from a copy of the skill and asserts rc 2 for a plain `gh pr merge 7` and for `ls`.
- **Rollback.** Each step below is one PR. If a released step blocks real work, revert that PR and release the revert as the next patch. The release before step 2 does not import either module, so a revert back to it is self-contained. A vendored copy missing one of the new files fails closed by the rule above. For review-gate, the whole-copy refresh from 3.2.19 (`install-workflow.py --force`) replaces `.claude/skills/review-gate` as one unit, so a half-updated copy is not a normal state. It does not touch `pr-merge-flow`, which has no installer of its own: its vendored copy is refreshed by `aec install skill pr-merge-flow`, or by replacing the directory with the release's as a whole; a partial copy still fails closed.

### 4. One deadline per hook run

- `hook_runtime.Deadline` is one monotonic deadline set in `run_hook` from that guard's budget, passed to every check and every `gh` call. It replaces merge-guard's `HOOK_BUDGET_S` and `CHECK_DEADLINE_S` and pr-guard's `GH_BUDGET_S` and `_left`.
- Each guard's budget is its own `hooks.json` `timeout_ms` minus a 3 s margin: 22 s for merge-guard (25 s timeout), 17 s for pr-guard (20 s timeout). A test reads each skill's `hooks.json` and fails when `budget_s + 3 > timeout_ms / 1000`, so a timeout change cannot leave the budget past it.
- **The margin is measured, not assumed.** The margin has to cover what runs outside the deadline: interpreter start, imports, reading stdin, and printing the denial after expiry. 3 s is the starting value. The step-2 PR measures that overhead on the CI runner (a guard run on `ls`, start to exit, 20 runs) and records the worst run in the test; the test fails when the margin is under 3× that number.
- When the deadline expires, the guard denies, naming the step that was running. A hook killed at its timeout loses its denial, so the guard must stop itself first.
- **One backstop alarm stays.** `run_hook` arms a single `signal.setitimer(ITIMER_REAL)` at the budget, the last resort that turns a check stuck outside a cooperative deadline check (a regex, a blocking read) into a denial. Its handler raises `hook_runtime.DeadlineExceeded`, a `BaseException` subclass, not an `Exception`, so a detector's `except Exception` (merge-guard has such blocks today) cannot swallow it; `run_hook`'s `BaseException` catch turns it into the deny, naming the step that was running. The cooperative `Deadline.check()` raises the same class. `setitimer` exists only on POSIX and works only on the main thread. A hook runs as its own process on the main thread, so the only place it is missing is Windows, where the cooperative deadline is the only stop. `run_hook` checks `hasattr(signal, "setitimer")` and `threading.current_thread() is threading.main_thread()` and says so in its docstring; the alarm test is skipped on Windows.
- `check-review-gate.gh_deadline` is not touched. It runs in CI, not as a hook, and is installed standalone.

## Tests: every bypass spelling, pinned

One table-driven test file per guard, plus shared module tests:

- `review-gate/tests/test_shell_tokens.py` and the byte-identical `pr-merge-flow/tests/test_shell_tokens.py`, plus the same pair for `hook_runtime`. A mirror test pins that each pair matches.
- `review-gate/tests/test_merge_guard_bypasses.py`
- `pr-merge-flow/tests/test_pr_guard.py`: new cases appended

Each row's result today was checked on `origin/main` (merge-guard with `check_command`, pr-guard by running the hook). A deny row is denied today unless it is marked **new deny**; the migration adds no allow. Rows marked **known limit** are allowed today and stay allowed.

| Source | Input | Expected |
|---|---|---|
| #129 | `env -S 'env X=\\c gh pr merge 1 --admin'`, `env -S 'gh\c' pr merge 1 --admin`, `env -S "env X='\c' gh pr merge 1 --admin"` | deny (both guards) |
| #129 | `env '-Sgh\c' pr merge 1` (attached `-S` with `\c`), `env --split-string='gh\_pr\c' merge 1 --admin` | deny (both guards). pr-guard denies both today; merge-guard allows both today, so they are **new denies** in merge-guard |
| #130 | `git commit -m "\"'$(gh pr merge 5 --admin)"\'`, the backtick form, and the same inside `grep -e` | deny: merge in the argument's `Unresolved.nested` body |
| #130 | `git commit --amend -m "gh pr merge 5 --admin"`, `cd /tmp && git commit --amend -m "gh pr merge 5 --admin"`, `git commit -m "docs: explain gh pr merge --squash"`, `git commit -m '$(gh pr merge 5)'`, `grep -rn "gh pr merge" SKILL.md`, `git add "notes on gh pr merge.md"` | deny with the `git commit -F <file>` hint (`QuotedMentions`) |
| #130 | `GIT_EDITOR=x git commit -m "gh pr merge 5"`, `git -c core.editor=x commit -m "gh pr merge 5"` | deny: the mention denies |
| #130 | `grep "gh pr merge 5" notes \| sh`, `grep -h "gh pr merge 5" notes > run.sh`, `rg --pre sh 'gh pr merge 5' notes` | deny |
| #130 | `grep x <(gh pr merge 5)`, `grep x; gh pr merge 5`, `grep x & gh pr merge 5`, `f() { gh pr merge "$@"; }; f 5` | deny |
| #130 | `alias grep='bash -c'` newline `grep 'gh pr merge 5'`, `hash -p /bin/bash grep; grep -c 'gh pr merge 5'`, `grep () { bash -c 'gh pr merge 5'; }; grep x` | deny |
| #132 | `/usr/bin/env -S'gh pr merge 17 --admin'`, `env -vS'gh pr merge 17 --admin'` | deny |
| #132 | `env -S 'env -S "gh pr merge 17 --admin"'` | deny: nested split string |
| #132 | ``env -S "`printf gh` pr merge 17 --auto"`` | deny: `Unresolved` command word with merge words |
| #132 | `builtin exec env -S 'gh pr merge 17 --admin'` | deny |
| #132 | ``echo `env -S 'gh pr merge 17 --admin'` `` | deny: merge in the argument's `Unresolved.nested` body |
| #132 | `bash -c "env -S 'gh pr merge 17 --admin'"`, plus `sh -c`, `/bin/bash -c`, `/bin/sh -c` | deny |
| #137 | `": '" + "z"*16001 + "'; g''h pr mer''ge 7 --squash"` | deny |
| #137 | `g\h pr mer\ge 7`, `$'\x67\x68' pr $'mer\x67e' 7`, `g\<newline>h pr mer\<newline>ge 7` | deny |
| #137 | `'gh\<newline>' pr merge 7` (single-quoted continuation: Bash keeps the word `gh\<newline>`) | deny: `Unresolved` command word with merge words, as 3.2.18 does |
| #137 timing | `gh pr ` × 2,000 | decided in under 1 s, in-process |
| #137 timing | 80 KB of padding, then `; gh pr merge 7` | deny, in under 1 s |
| #137 timing | 2,000 nested quotes; 500 nested `$(` | deny (depth cap failure), in under 1 s |
| #139 review | `$(printf g)h pr merge 7`, `$X pr merge 7`, `gh $X merge 7`, `gh pr $X 7`, `gh $X` | deny: unresolved executable or subcommand slot |
| #139 review | `echo "$(gh pr merge 7)"`, `echo ${x:-$(gh pr merge 7)}` | deny: merge in the argument's `Unresolved.nested` body |
| #139 review | `watch gh pr merge 7`, `find . -exec gh pr merge 7 \;`, `stdbuf -oL gh pr merge 7`, `su -c 'gh pr merge 7' me`, `ssh host gh pr merge 7`, `docker exec c gh pr merge 7`, `unknown-wrapper gh pr merge 7` | deny |
| #139 review | a heredoc whose unquoted body has `$(gh pr merge 7)`; `bash <<EOF` with a `gh pr merge 7` body | deny |
| #139 review | `echo "unbalanced`; an unterminated `$(` (`echo $(ls`) | **new deny** (R7). Both guards allow them today; Bash rejects both as syntax errors |
| #139 review | `shell_tokens` or `hook_runtime` missing from the skill copy; `check_command` raising; stdin that is not JSON | rc 2 for `gh pr merge 7` and for `ls` |
| #139 round 2 | `gh${IFS}pr${IFS}merge 7` | deny (R3 on `fragments`) |
| #139 round 2 | `echo "gh pr merge $N" \| bash`, `git commit -m "run gh pr merge $N"`, `grep "gh pr merge $N" notes \| sh`, `x="gh pr merge"` | deny (R3), with the `git commit -F <file>` hint |
| #139 round 2 | `echo gh pr merge 7`, `printf '%s ' gh pr merge 7`, `a=(gh pr merge 7); "${a[@]}"`, `set -- gh pr merge 7; "$@"` | deny (R2) |
| #139 round 2 | `c=gh; $c pr merge 7` | deny (R4) |
| #139 round 2 | `gh pr merge $N`, `f() { gh pr merge "$@"; }; f 5` | deny (R6) |
| #139 round 2 | `{ gh pr merge 7; }`, `(gh pr merge 7)`, `if true; then gh pr merge 7; fi` | deny outright as compound or wrapped (R1), without gate checks, as 3.2.18 does |
| #139 round 2 | `alias m='gh pr merge'` newline `m 7` | deny (R8) |
| #139 round 2 | `cat <<EOF` newline `hi` (no closing delimiter) | **new deny** (R7). Both guards allow it today, and Bash runs it with a warning |
| #139 round 2 | `echo 'unterminated` | **new deny** (R7). Both guards allow it today; Bash rejects it as a syntax error |
| #139 round 2 | `$(printf 'gh pr m%s' erge) 7`, `x=$(printf 'gh pr m%s' erge); $x 7` | allow: **known limit**, allowed today too (section 2) |

Allow rows guard against over-blocking and stay allowed (each allowed today): `$EDITOR notes.txt`, `gh pr view $N`, `$X pr view 7`, `ls $DIR`, `git commit -F msg.txt`, `git commit -m "fix $N"`, `gh${IFS}pr${IFS}view 7`, `echo "gh pr view $N" | bash`, `a=(gh pr view 7); "${a[@]}"`.

The table is the minimum. The implementing PR also feeds every row into the parity harness as fixture input, so a later change cannot drop one silently.

## Migration order

Each step is its own PR to main, through the adversarial review and Review Gate, merged by the claude-skills traffic cop. No step starts until the one before it has merged. Versions are each skill's next patch at the time the step's PR opens.

1. **Wait for #131 and #132.** #131 and #132 (pr-merge-flow 1.5.5, both open) edit `pr-guard.py`, `test_pr_guard.py` and the fixture corpus; their new cases (absolute `env` paths, short clusters, nested split strings, backticks, `bash -c`) become rows in the table above, not code to port. This plan touches none of those files until both merge. #138 (review-gate 3.2.19, the whole-copy refresh that step 6 relies on) merged as 0cf5b00.
2. **Add `shell_tokens.py`, `hook_runtime.py` and their tests, unused,** with the mirror tests. No behavior change, and the parity test proves it.
3. **pr-guard reads the shared modules.** `segments()`, `wrapped_words()`, the private-use stand-ins, `GH_BUDGET_S` and `_left` are deleted, the #124 Rule A and Rule B move into `shell_tokens`, and `__main__` calls `run_hook` (fail closed, one deadline). Parity is against the previous pr-merge-flow release. New denials are allowed; lost ones fail CI.
4. **merge-guard reads the shared modules, one detector family per commit, in one PR:**
   - the merge matcher (`MERGE_RE`, `_PR_MERGE_LOOSE_RE`, quote-smash, ANSI-C)
   - wrappers and nested bodies
   - assignments, arrays, positionals and printf
   - environment and definition detectors (`PATH`, `hash -p`, functions, aliases, `command_not_found_handle`)
   - repo and selector resolution (`extract_repo_resolution`, `-R`/`--repo`, `GH_REPO` and `GH_HOST` via `_apply_gh_host`, pull-URL selectors, `extract_merge_selector`, `extract_pr_and_repo`)
   - gh config overlays (`gh_config_overlay_unresolved`, `_apply_overlay_env_var`, `_env_overlay_unresolvable`)
   - directory changes (`_env_has_chdir`, `_part_may_chdir`, `scoped_dir_requires_repo`, the subshell `cd` check) and `names_git_commit`
   - `__main__` calls `run_hook`; `HOOK_BUDGET_S`, `CHECK_DEADLINE_S` and the local `setitimer` are deleted (the one alarm now lives in `run_hook`)

   Then the raw-text second pass and `normalize_command` are deleted. A merge-guard parity test (step 1 of the #124 plan, pointed at `merge-guard.check_command`) runs from the first commit.
5. **Enforce the single reader** (Done when, first item), as its own small PR once both guards are migrated.
6. **Re-vendor.** The consumers are aec's catalog hash and vendored copies, and the ~20 repos carrying `.claude/skills/review-gate` and `.claude/skills/pr-merge-flow`. They take each release through their own cop: review-gate with the whole-copy refresh from #138 (`install-workflow.py --force`, which replaces only `.claude/skills/review-gate`), pr-merge-flow with `aec install skill pr-merge-flow` or a whole-directory replace.

## Affected surfaces

- **review-gate:** `scripts/merge-guard.py`, new `scripts/shell_tokens.py` and `scripts/hook_runtime.py`, `tests/`, `SKILL.md`, `hooks.json`
- **pr-merge-flow:** `scripts/pr-guard.py`, new `scripts/shell_tokens.py` and `scripts/hook_runtime.py`, `tests/`, `SKILL.md` ("Best-effort guard" and "Known limits"), `hooks.json`
- **This repo:** `skills-manifest.json`, `.github/workflows/ci.yml` (the merge-guard parity step), `plans/pr-guard-shell-parsing-design.md` (amendment note)
- **aec:** `catalog-hashes.json` and its vendored copies, updated through one PR to its cop per release
- **Vendored repos:** re-vendor PRs, one per repo per release

## Not in scope

- The guard stays a best-effort client-side check, not a security boundary. The server-side boundary is plan `2026-11-17-api-merge-guard.md`.
- Effects the command text does not show: a git hook, an editor or a script file that runs a merge (`GIT_EDITOR=./merge.sh git commit` with no merge text). The guard cannot read those files' behavior; the server-side plan covers them.
- Variables, `eval` of computed text and command substitution in the command position are not evaluated. They deny when the words or fragments show a merge (R2 to R6). A command name computed at run time with no `merge` word or fragment (`$(printf 'gh pr m%s' erge) 7`) is allowed, today and after this plan: the known limit in section 2.
- No Bash re-implementation beyond word formation. The tokenizer does no expansion it cannot do from the text alone.
- **The forged-check scripts.** `check-forged-gate-names.py` is vendored byte-identical from aec, and `check-forged-review-gate.py` is a thin wrapper around it, so typed JSON parsing for them (parse each API record once into typed fields, a verdict enum instead of `re.search(r"is also (PR #|open)", why)` over its own message, fail closed on a missing or malformed field) belongs in an aec-owned plan. It was routed to aec's owner through the aec traffic cop on 2026-11-21. claude-skills re-vendors the result.

## Done when

- `shell_tokens.tokenize` is the only function in either guard that reads the command string. A test enforces this on the AST: in `merge-guard.py` and `pr-guard.py`, the hook input's `command` value flows only into `shell_tokens.tokenize` (the test finds the one `tool_input["command"]` read in each guard and asserts its only use is that call), and neither guard module imports `shlex` or `re`-matches a name bound to that value. The guards keep no copy of `MERGE_RE` or `normalize_command`.
- The raw-text second pass is gone, and every row of the table above passes in both guards where it applies.
- Both parity tests run in CI, against the previous release of each skill.
- Both guards run through `hook_runtime.run_hook`: one deadline per hook run, budgets pinned against `hooks.json`, rc 2 on any crash or missing module, and the timing rows pass in under 1 s.
- Each step merged through review and Review Gate, by the traffic cop.
