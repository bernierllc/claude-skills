# Tokenizer-first merge guard: one shell tokenizer, decisions on tokens only

Status: planned. Owed by PR https://github.com/bernierllc/claude-skills/pull/137 (review-gate 3.2.18), whose "Simplify or plan" section records the raw-text second pass as a stopgap and says "a plan for it is owed". Priority: P1. Both guards are the last client-side stop before an unreviewed merge, and each bypass found so far was a real `gh pr merge` that ran while the hook said allow. Tier and schedule: the PM task sets them from the Tracker row.

## What happened

Two PreToolUse hooks decide, from the Bash command string, whether a command will merge a PR or post a forbidden comment:

- `review-gate/scripts/merge-guard.py` (4,236 lines)
- `pr-merge-flow/scripts/pr-guard.py` (933 lines)

Neither decides on the words the shell will run. merge-guard has dozens of detectors. Some read `shlex` tokens. Some run regexes over raw text (`MERGE_RE`, `_PR_MERGE_LOOSE_RE`, `QUOTE_SMASHED_GH_RE`, `_ARRAY_ASSIGN_RE`, the printf and positional-parameter scanners). Some re-implement one more piece of Bash first (`_dequote_shell_text`, `_collapse_empty_quotes`, `_decode_ansi_c`, the heredoc and comment scanners). pr-guard has its own shlex-based `segments()` with private-use stand-ins for quoted operators.

Each review round found the next spelling that one detector saw differently from Bash:

| PR | Guard | Bypass spellings found in review (each one ran a merge, or would have, while the guard allowed it) |
|---|---|---|
| #129 (pr-merge-flow 1.5.4) | pr-guard | `env -S 'env X=\\c gh pr merge 1 --admin'`: `.split("\\c")` treated an escaped backslash as the start of `\c` |
| #130 (review-gate 3.2.15) | merge-guard | `git commit -m "\"'$(gh pr merge 5 --admin)"\'`: the inert-mention check misread an escaped quote and treated an executed `$(…)` as literal text. `git commit --amend -m "gh pr merge 5 --admin"` with a `post-commit` hook or `GIT_EDITOR` that merges: a blanket `git commit` exemption |
| #132 (pr-merge-flow 1.5.5, open) | pr-guard | `/usr/bin/env -S'gh pr merge 17 --admin'`, `env -vS'gh pr merge 17 --admin'`, `env -S 'env -S "gh pr merge 17 --admin"'`, ``env -S "`printf gh` pr merge 17 --auto"``, `builtin exec env -S 'gh pr merge 17 --admin'`, ``echo `env -S 'gh pr merge 17 --admin'` ``, `bash -c "env -S 'gh pr merge 17 --admin'"` (also `sh -c`, `/bin/bash -c`, `/bin/sh -c`) |
| #137 (review-gate 3.2.18), 3 P1 rounds | merge-guard | `": '" + "z"*16001 + "'; g''h pr mer''ge 7 --squash"` and `g\h pr mer\ge 7` (a size shortcut decided on raw text); `$'\x67\x68' pr $'mer\x67e' 7` and `g\<newline>h pr mer\<newline>ge 7` (Bash finishes the words before running them, the guard did not); `gh pr ` × 2,000 (`MERGE_RE` backtracked past the 25 s hook timeout, and a hook killed at its timeout loses its denial); an 80 KB command took 6-50 s |

#137 ended with this shape:

- `normalize_command` joins continuations and decodes `$'…'` before any check.
- Because that pass does not track quoting, the raw text is checked a second time, and the guard denies if either pass does.
- A 22 s `setitimer` deadline denies before the hook timeout.

The second pass can add a denial but never drops one, so it is safe. But it is a stopgap: every future check now runs twice, on two texts, and still on text instead of words.

## Root cause

Both guards decide on text that Bash has not finished turning into words. Each detector re-derives, its own way, what the shell will run: quoting, escapes, `$'…'`, continuations, wrappers, operators. Two derivations of the same command disagree at the edges, and an attacker (or an unlucky agent) needs only one detector to say "no merge here". The review loop finds one disagreement per round. Nothing makes a fix in one detector reach the others.

`check-forged-gate-names.py` and `check-forged-review-gate.py` have the same root cause in a different input. They read GitHub API JSON, not shell. They also decide on ad hoc string handling instead of parsed values:

- `display_title` matched by a regex built from `RUN_TITLE`
- `path.split("@", 1)` for required-workflow paths
- the verdict's kind chosen by `re.search(r"is also (PR #|open)", why)` on its own message text

#133, #135 and #137 each found a P1 there (fork-head equality, a closed sibling omitted from `/commits/{sha}/pulls`, a PR-controlled title). Shell tokens do not apply to JSON. The same rule does: parse once into typed values, decide on those values, and fail closed when a value does not parse.

## What already exists, and what this plan reuses

Incumbent check: does this reimplement something the framework, a dependency, or this repo already provides?

- **`shlex` (stdlib)** is the base of both guards' tokenizing today (`merge-guard._shell_tokens_once`, `pr-guard.shell_tokens` with `punctuation_chars`). This plan keeps it as the word splitter. It does not add a parser dependency. bashlex is unmaintained and has no `$'…'` or `env -S`. tree-sitter-bash is a compiled wheel a hook cannot assume. Both would also re-implement Bash.
- **`pr-guard.segments()`** is the most complete existing tokenizer: operator-aware, with quoted-operator stand-ins, and a fail-closed path when shlex cannot parse. It is the starting point of the shared module, not a second design.
- **`merge-guard.normalize_command` and `_decode_ansi_c`** (3.2.18) already do the pre-word steps. They move into the shared module as its first stage, with quoting tracked, so the raw-text second pass can go.
- **Plan `plans/pr-guard-shell-parsing-design.md`** (issue #124) already fixes pr-guard's wrapper rules (Rule A and Rule B) and its regression harness. This plan does not redo that. It takes Rule A and Rule B as the wrapper policy of the shared module, so merge-guard gets them too.
- **`pr-merge-flow/tests/test_pr_guard_parity.py`** (landed in #129) is the differential harness: baseline guard from `origin/main` against head, and every block the baseline had must survive. The same harness is extended to merge-guard. It is not rewritten.
- **`check-review-gate.gh_deadline` / `run_by_deadline`** (a `ContextVar` deadline for every `gh` call) and pr-guard's `_left(deadline, cap)` are the two existing deadline mechanisms. `merge-guard` adds a third, `HOOK_BUDGET_S` plus `CHECK_DEADLINE_S` via `setitimer`. They become one.
- **The byte-identical mirror pattern** (`scripts/check-review-gate.py` ↔ `review-gate/scripts/check-review-gate.py`, pinned by a test) is how one file ships inside two skills that are vendored independently.
- **Plan `docs/superpowers/plans/2026-11-17-api-merge-guard.md`** moves enforcement server-side, so an API, GraphQL or `git push` merge cannot skip the gate. That is the real boundary. This plan makes the client-side hook honest and cheap; it does not replace that plan, and its priority does not depend on it.

## Correct fix

### 1. One shared tokenizer: `shell_tokens.py`

One file, shipped as byte-identical copies in `review-gate/scripts/shell_tokens.py` and `pr-merge-flow/scripts/shell_tokens.py`. A repo test fails when the two differ. The skills are vendored separately into other repos, so neither may import the other's directory.

It turns a command string into a list of **segments**. Each segment is a list of **words**, and each word is one of:

- `Literal(text)`: a word whose final text is fully known after Bash's quote removal, escapes, `$'…'` decoding and continuation joins. Decided per quoting context, in one left-to-right pass: a backslash-newline joins only outside single quotes, and `\c`, `\\` and escaped quotes are read in the context they appear.
- `Unresolved(reason, raw)`: a word whose text the tokenizer cannot know. Causes: parameter or arithmetic expansion, `$(…)` or backticks, globs in the command position, `~user`, and any parse error (an unbalanced quote, an unknown `$'…'` escape). The reason names the construct.
- `Nested(segments)`: the parsed body of a string the shell will run as a command: `$(…)` and backtick bodies, `bash|sh|zsh -c` payloads, `env -S`/`--split-string` strings (including attached `-S'…'`, short clusters such as `-vS'…'`, and `\c` truncation), `eval` arguments and heredocs fed to a shell. These are parsed recursively by the same function, with a depth cap; past the cap a body is `Unresolved`.

Segments split on control operators (`;`, `&&`, `||`, `|`, `|&`, `&`, newline) and keep the operator, so a detector can still ask "does this run after a `cd`".

Wrapper policy: the shared module applies the #124 plan's Rule A (after `env`, `sudo`, `nice`, `timeout`, `xargs`, `nohup`, `time`, `exec`, `builtin`, `command`, every later word is a candidate command) and Rule B (directory and root are known only after nothing, a plain `command`, or `env NAME=value…`). It also recognizes absolute wrapper paths (`/usr/bin/env`, `/bin/bash`). pr-guard's own copy of these rules is deleted in the migration.

Cost: one pass over the characters, plus the shlex call per segment, which is linear. Each distinct text is tokenized once (`lru_cache`, as 3.2.18 already does). No regex in the module may backtrack: every pattern is anchored or a fixed literal, and the module has a test that times `gh pr ` × 2,000, 80 KB of padding and 2,000 nested quotes against a 1 s budget.

### 2. Decisions on tokens only, fail closed on anything unresolved

Every detector in both guards takes segments, never a string. The rules:

- **A merge is a segment whose resolved command words are `gh … pr … merge`** after skipping `gh`'s global flags (`-R`, `--repo`, `--hostname`). Wrappers are expanded per Rule A, and `Nested` bodies are checked the same way, recursively.
- **Unresolved fails closed where it matters.** If any candidate command word, or any `gh` subcommand word, is `Unresolved`, and the segment (or the command around it) contains a merge word that could complete it, the guard denies. The denial names the construct: "the command name comes from `$X`; write it literally". A `gh pr merge` in an unparseable command is denied. An `Unresolved` word in an argument position (a commit message, a file name) does not deny on its own.
- **Inert text stays inert only when the tokenizer proves it is a `Literal` argument.** `git commit -m "gh pr merge 5"` and `echo 'gh pr merge'` are allowed because the mention is one `Literal` argument word. `git commit -m "$(gh pr merge 5)"` is a `Nested` body, so it is checked. A blanket per-command exemption is never used: the #130 `git commit` early return is the example.
- **Effects outside the text stay a separate rule, decided on tokens.** Git hooks, `GIT_EDITOR`, `BASH_ENV`, `PATH` overrides, function and alias redefinitions of `gh`, and `command_not_found_handle` are kept as today's detectors. They are rewritten to read words (`Literal("GIT_EDITOR=…")` assignments, a `Literal("alias")` command), not regexes over raw text.
- **The raw-text second pass is deleted.** It exists only because `normalize_command` lost quoting. Once the tokenizer is the only reader of the text, no decision reads raw text.
- **The `# review-gate-ok:` override and the `pr-guard` overrides** are read from the tokenizer's comment list (it already separates comments from words), not by regex over the whole string.

### 3. One deadline

One monotonic deadline per hook run, set in `main()` from the hook's budget, is passed to every check and every `gh` call:

- `check-review-gate.gh_deadline` is the one mechanism. `merge-guard`'s `HOOK_BUDGET_S` / `CHECK_DEADLINE_S` / `setitimer` pair and pr-guard's `_left` both become callers of it. The `setitimer` backstop stays as the single last resort that turns "still running" into a denial.
- When it expires, the hook denies, naming the step that was running. It never lets the hook be killed at its timeout, because a killed hook loses its denial.

### 4. Typed parsing in the forged-check scripts

Same principle for JSON input:

- One `parse_run(obj)` returns a typed record from one API response: `workflow_path`, `ref` (split once, from `path@ref`), `event`, `head_sha`, `head_ref`, `head_repo`, `title_pr` (an `int` or `None`, from `RUN_TITLE`), `run_id`.
- A field that is missing, null, the wrong type, or does not parse raises `Ambiguous` (exit 2). This is what `_text()` already does for strings, extended to the whole record.
- Verdicts are an enum (`Accept`, `Competitor(pr)`, `SharedSha(pr)`, `Untrusted`, `Ambiguous(reason)`), and the message is rendered from it. The `re.search(r"is also (PR #|open)", why)` that reads a verdict back out of its own message is deleted.
- `branch_verdict` (3.2.18) stays the single accept path.
- Both detectors (`check-forged-gate-names.py`, `check-forged-review-gate.py`) use it, through the existing mirror copies in `scripts/`.

## Tests: every bypass spelling from #129-#137, pinned

One table-driven test file per guard, plus a shared tokenizer test:

- `review-gate/tests/test_shell_tokens.py` and the byte-identical `pr-merge-flow/tests/test_shell_tokens.py`. A mirror test pins that they match.
- `review-gate/tests/test_merge_guard_bypasses.py`
- `pr-merge-flow/tests/test_pr_guard.py`: new cases appended
- `review-gate/tests/test_forged_gate.py`: new cases appended

| Source | Input | Expected |
|---|---|---|
| #129 | `env -S 'env X=\\c gh pr merge 1 --admin'` | deny (pr-guard) |
| #130 | `git commit -m "\"'$(gh pr merge 5 --admin)"\'` | deny: `Nested` merge |
| #130 | `git commit --amend -m "gh pr merge 5 --admin"` with an executable `post-commit` hook that merges | deny (hook detector) |
| #130 | `GIT_EDITOR=./merge.sh git commit` | deny |
| #130 | `git commit -m "gh pr merge 5"` with no hooks | allow: `Literal` argument |
| #132 | `/usr/bin/env -S'gh pr merge 17 --admin'` | deny |
| #132 | `env -vS'gh pr merge 17 --admin'` | deny |
| #132 | `env -S 'env -S "gh pr merge 17 --admin"'` | deny: nested split string |
| #132 | ``env -S "`printf gh` pr merge 17 --auto"`` | deny: `Unresolved` command word with merge words |
| #132 | `builtin exec env -S 'gh pr merge 17 --admin'` | deny |
| #132 | ``echo `env -S 'gh pr merge 17 --admin'` `` | deny |
| #132 | `bash -c "env -S 'gh pr merge 17 --admin'"`, plus `sh -c`, `/bin/bash -c`, `/bin/sh -c` | deny |
| #137 | `": '" + "z"*16001 + "'; g''h pr mer''ge 7 --squash"` | deny |
| #137 | `g\h pr mer\ge 7` | deny |
| #137 | `$'\x67\x68' pr $'mer\x67e' 7` | deny |
| #137 | `g\<newline>h pr mer\<newline>ge 7` | deny |
| #137 | `'gh\<newline>' pr merge 7` (single-quoted continuation, kept literally by Bash) | the word is `gh\<newline>`, not `gh`: no merge, allow. This is the case the raw-text pass exists for; the test pins that the token path gets it right and denies when the continuation is unquoted |
| #137 | `gh pr ` × 2,000; 80 KB padding before a merge | decided (deny for the second) in under 1 s, in-process |
| #133 | run titled `Review Gate - PR #7` from a PR sharing #7's head sha | exit 1 or 2, never accept |
| #133 | fork head where `got == want` both name the fork | not accepted by the stale-main fallback |
| #133/#137 | closed sibling PR absent from `/commits/{sha}/pulls`; empty branch listing | exit 2 |
| #135 | each run read once: one API call per run in the recorder | pass |
| new | a run whose `path`, `event` or `display_title` is null, a number, or `path@` with an empty ref | exit 2 |

The table is the minimum. The implementing PR also feeds every row into the parity harness as fixture input, so a later change cannot drop one silently.

## Migration order

Each step is its own PR to main, through the adversarial review and Review Gate, merged by the claude-skills traffic cop. No step starts until the one before it has merged.

1. **Wait for #131 and #132** (pr-merge-flow 1.5.5, both open, both editing `pr-guard.py`, `test_pr_guard.py` and the fixture corpus). This plan does not touch those files until both merge. Their new cases (absolute `env` paths, short clusters, nested split strings, backticks, `bash -c`) become rows in the table above, not code to port.
2. **Add `shell_tokens.py` and its test, unused** (review-gate 3.2.20, pr-merge-flow next patch, with the mirror test). This step has no behavior change, and the parity test proves it.
3. **pr-guard reads the shared module.** `segments()`, `wrapped_words()` and the private-use stand-ins are deleted, and the #124 Rule A and Rule B move into the module. Parity is against the previous pr-merge-flow release. New denials are allowed; lost ones fail CI.
4. **merge-guard reads the shared module, one detector family per commit, in one PR:**
   - the merge matcher (`MERGE_RE`, `_PR_MERGE_LOOSE_RE`, quote-smash, ANSI-C)
   - wrappers and nested bodies
   - assignments, arrays, positionals and printf
   - environment and definition detectors (`PATH`, `BASH_ENV`, functions, aliases, `GIT_*`, hooks)

   Then the raw-text second pass and `normalize_command` are deleted. A merge-guard parity test (step 1 of the #124 plan, pointed at `merge-guard.check_command`) runs from the first commit.
5. **One deadline.** `merge-guard` and `pr-guard` take `gh_deadline` from the shared helper; the second timer and `_left` are deleted.
6. **Forged checks: typed records and the verdict enum** (`check-forged-*.py` and their `scripts/` mirrors). This step is independent of 2-5 and may run in parallel with them, because it touches no file they touch.
7. **Re-vendor.** The consumers are aec's catalog hash and vendored copies, and the ~20 repos carrying `.claude/skills/review-gate` and `.claude/skills/pr-merge-flow`. They take each release through their own cop, using the whole-copy refresh from review-gate 3.2.19 (`install-workflow.py --force`).

## Affected surfaces

- **review-gate:**
  - `scripts/merge-guard.py`
  - new `scripts/shell_tokens.py`
  - `scripts/check-forged-gate-names.py`, `scripts/check-forged-review-gate.py`
  - `scripts/check-review-gate.py` (the deadline helper)
  - `tests/`, `SKILL.md`, `hooks.json`
- **pr-merge-flow:** `scripts/pr-guard.py`, new `scripts/shell_tokens.py`, `tests/`, `SKILL.md` ("Best-effort guard" and "Known limits"), `hooks.json`
- **This repo:** the `scripts/` mirrors of the forged checks, `skills-manifest.json`, `.github/workflows/ci.yml` (the merge-guard parity step)
- **aec:** `catalog-hashes.json` and its vendored copies, updated through one PR to its cop per release
- **Vendored repos:** re-vendor PRs, one per repo per release

## Not in scope

- The guard stays a best-effort client-side check, not a security boundary. The server-side boundary is plan `2026-11-17-api-merge-guard.md`.
- Variables, `eval` of computed text and command substitution in the command position are denied when they can complete a merge, not evaluated.
- No Bash re-implementation beyond word formation. The tokenizer does no expansion it cannot do from the text alone.

## Done when

- `shell_tokens.py` is the only code in either guard that reads the command string. A test enforces this: a grep for `shlex.`, `re.` on the command, `MERGE_RE` and `normalize_command` outside `shell_tokens.py` finds nothing in the guards.
- The raw-text second pass is gone, and every row of the table above passes.
- Both parity tests run in CI, against the previous release of each skill.
- One deadline object governs each hook run, and the timing rows pass in under 1 s.
- The forged checks decide on typed records. No verdict is read back from message text, and the null and malformed rows exit 2.
- Each step merged through review and Review Gate, by the traffic cop.
