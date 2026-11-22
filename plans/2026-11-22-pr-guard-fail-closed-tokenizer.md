# pr-guard: fail-closed tokenizer, an amendment to the tokenizer-first plan

Status: planned. Amends [the tokenizer-first merge guard plan](2026-11-21-tokenizer-first-merge-guard.md) (PR #139). It does not replace it. Each section below names the #139 section it changes. Where this file says nothing, #139 stands.

## What happened

- PR #132 (pr-merge-flow, the `env -S` fix that grew into nested-code parsing) went through three review rounds.
  - Round 1 was clean on the `env -S` block.
  - Rounds 2 and 3 added a nesting core to `segments()`: substitution bodies, `bash -c`, `eval`, `builtin`, `$'…'`, `${…}` skipping, a private-use character ban, an input cap and a crash exit.
  - Round 3 (review 6013559168) was NOT CLEAN, with five P1 bypasses in the same class.
- The traffic cop stopped patching: no fourth round. The Program Cop routed the work two ways:
  - land the round-1 `env -S` block alone, as its own PR (pr-merge-flow 1.6.1);
  - close #132 as superseded;
  - write the fail-closed design as #139's tokenizer step, which is this file.
- Root cause, the same as #139's: `segments()` reads the command string with patches layered on shlex. Each round closed the spellings it was shown, and the next review found a sibling. The fix is a tokenizer that marks what it cannot resolve and denies it, not a longer list of spellings.

## Probe: these bypasses are live on main today

Run on origin/main d270515 (pr-merge-flow 1.6.0, the parity baseline 75137f8), through the real hook (`pr-guard.py` with a stdin JSON `PreToolUse` payload, `tool_name: Bash`). Exit 0 means the command runs.

| # | Command | main 1.6.0 | Fixed by |
|---|---|---|---|
| 1 | `>/dev/null gh pr merge 1 --auto` | 0 (runs) | this plan, A2 |
| 2 | `2>&1 gh pr merge 1 --auto` | 0 (runs) | this plan, A2 |
| 3 | `function f { gh pr merge 1 --auto; }; f` | 0 (runs) | this plan, A2 |
| 4 | `FOO+=x gh pr merge 1 --auto` | 0 (runs) | this plan, A2 |
| 5 | `echo "$(! case x in x) gh pr merge 1 --auto;; esac)"` | 0 (runs) | this plan, A3 |
| 6 | `echo "$(echo ${x:-$(echo })}; gh pr merge 1 --auto)"` | 0 (runs) | this plan, A3 |
| 7 | `echo \ # ; gh pr merge 1 --auto` | 0 (runs) | this plan, A2 |
| 8 | `/usr/bin/env -vS'gh pr merge 1 --admin'` | 0 (runs) | the `env -S` PR (1.6.1) |
| 9 | `env -S 'gh pr merge 1 --auto'` | 2 (denied) | already denied |
| 10 | `$(true` + 58K newlines + `)` then a merge | 2 (denied, 0.5 s) | already denied |

Rows 1 to 7 predate #132: #132's round 3 found them, but they are live on main. That is why this step is urgent and why #132 is not the place to fix them. Row 8 is closed by the `env -S` PR, which lands first.

## Amendments

### A1. Migration step 1 (#139 "Migration order", step 1)

Replace "Wait for #131 and #132" with:

1. **Wait for #131 and the `env -S` PR.**
   - The `env -S` PR (pr-merge-flow 1.6.1) ports #132's round-1 commits onto 1.6.0, and nothing else:
     - `env -S` / `--split-string` is denied on sight: any path, clusters such as `-vS`, `--sp` prefixes, behind `sudo`/`nice`;
     - command words match by basename;
     - the parity harness writes the baseline's `tests/fixtures/` into its temp dir, which every PR after 1.6.0 needs.
   - #132 closes as superseded, with a pointer to the `env -S` PR. Its branch `fix/pr-guard-env-s-closed` stays.
   - **#132's round 2 and 3 test inputs become corpus rows** (section "Tests" below), not code to port. That is the same treatment #139 already gives #131's and #132's cases.

### A2. The tokenizer reads characters, not regexes (#139 section 1)

Add to "How it finds the ends of constructs":

- **One linear character loop, no `re` in the tokenizer path.** `shell_tokens.tokenize` and everything it calls index the string one character at a time with an explicit context stack. They do not import `re`. This is what makes section 4's deadline enforceable (A4).
- **Size caps record a failure, which denies (R7).**
  - Input over 128 KiB (131,072 bytes after UTF-8 encoding) is a failure before scanning starts.
  - The scanner counts every character it reads, including re-reads when a body is fed back through `tokenize`. Past 2× the input length it records a failure. This bounds the nested re-scan cost at linear.
- **`#` starts a comment only at the start of a word.** The test is "the character before it ends a word": unquoted whitespace, a control operator, or the start of input. So `echo \ #` keeps `#` inside the word (the escaped space is part of the word), and `; gh pr merge …` after it is a new segment (probe row 7). `a#b` and `"#"` are not comments.
- **A leading redirect is not the command word.** A segment may start with any number of redirects: `>f`, `2>&1`, `<f`, `&>f`, `>|f`, `n>&m`, and a heredoc operator. They go into the segment's `redirects`, and the next word is the command position (probe rows 1 and 2). Redirects between words are handled the same way.
- **Every assignment form is a prefix, not a command.** `NAME=v`, `NAME+=v` and `NAME[i]=v` before the command word are bindings, and the next word is the command position (probe row 4).
- **`function name { …; }`, `function name() …` and `name() …` bodies are segments.** The body's first word is a command position (probe row 3). #139 already lists `function` and `name()` as segment starts. This makes the `function` keyword form with a `{` body explicit, with a test row.

### A3. Fail closed inside substitution bodies (#139 sections 1 and 2)

#139 parses `$(…)` and backtick bodies into `nested`. That is correct when the scanner can find where each body ends, and Bash agrees. Probe rows 5 and 6 are two spellings where it cannot:

- `case` patterns use an unbalanced `)` inside `$(`. bash 3.2 (macOS `/bin/bash`) and bash 4+ end the body at different characters.
- `${x:-$(echo })}` nests a `}` that the scanner and Bash may close at different places.

Rather than reproduce each Bash version's grammar, the tokenizer records a failure for these constructs **inside a substitution body**, when the body could run a guarded command:

- **Hard constructs** (a failure when inside `$(…)`, backticks, `<(…)` or `>(…)`):
  - the reserved word `case`;
  - `${`;
  - `$'` and `$"`;
  - a heredoc operator (`<<`, `<<-`; `<<<` is a here-string and is not on this list);
  - an unmatched `$(` or backtick.
- **Trigger: the failure fires only when the body's own words, after quote removal, contain one of:**
  - a word whose `command_name` (basename) is in `NESTED_TRIGGER_COMMANDS` or ends in `sh`;
  - an expansion in the first position of a segment that is not an assignment;
  - `$'`, `$"` or a backslash inside a word.
- `NESTED_TRIGGER_COMMANDS` is one constant in `shell_tokens.py`, listed in pr-merge-flow's `SKILL.md`:
  `gh`, `git`, `eval`, `command`, `exec`, `builtin`, `xargs`, `source`, `.`, `env`, `nohup`, `time`, `sudo`, `nice`, `timeout`, `busybox`, `ssh`, `su`, `watch`, `find`.
- Outside the trigger, the hard constructs stay allowed, so everyday commands keep working. For example, `--body "$(cat <<'EOF' … EOF)"` has a heredoc inside `$(`, but `cat` is not a trigger and the body has no first-position expansion, so it stays allowed. R10 still scans the heredoc text.
- **Why a trigger at all.** The cop's review point (2): the trigger is a fail-open filter, and a missing word means a bypass. So the list is explicit, documented and pinned by a mutation test (Tests, below). Leaving the trigger out would deny every `$(cat <<'EOF' …)` commit and PR body. That is the most common heredoc in agent use, and denying it would push agents to `--no-verify`-style workarounds.
- **R6 restated for pr-guard.** Any word after `merge` that is not a `Literal` denies. `--match-head-commit` must be a `Literal` of exactly 40 hex characters. #139 R6 already says this; this plan adds the test rows.

### A4. The deadline cannot interrupt a regex, so no regex may be slow (#139 section 4)

The cop's review point (1): `signal.setitimer` and a watchdog thread do not fire while CPython runs one C-level `re` match. The signal handler runs only between bytecodes, and `re`'s matcher does not release the GIL or check for signals. #139 section 4 calls the alarm "the last resort that turns a check stuck outside a cooperative deadline check (a regex, …) into a denial". For a regex, that is wrong. A backtracking pattern on 128 KiB runs past the hook's 20 s timeout. The hook is then killed, and a killed hook does not deny, so the command runs.

Replace that sentence, and add:

- **The tokenizer path uses no `re`** (A2). An AST test parses `shell_tokens.py` and fails on `import re`, `from re import …` or `__import__("re")`.
- **Every regex left in either guard has no nested quantifier.** The AST test walks both guards' and `hook_runtime.py`'s module-level and function-level string constants passed to `re.compile`, `re.search`, `re.match`, `re.fullmatch`, `re.sub`, `re.findall` and `re.finditer`. It fails when a pattern has a quantified group containing another quantifier (`(a+)+`, `(\s*x)*`, `(?:a|ab)*` with overlapping alternatives). A pattern built at run time fails the test unless it is listed, with its reason, in one allowlist in the test file.
- **A regex-hostile perf test.** The test runs `check()` and the real `main()` on each shape below at 128 KiB, and each must finish in under 2 s on the CI runner. A failure names the shape.
  - `gh pr ` repeated;
  - `$(` × N, then `)` × N;
  - `"` × N;
  - `\` + space, repeated;
  - 58K newlines inside `$(true …)`;
  - `a=` repeated;
  - `# ` repeated;
  - a heredoc whose body is near-miss terminators;
  - `--body "` + 128 KiB of `x` + `"`.
- **Fallback if a shape cannot meet 2 s without a regex rewrite:** `run_hook` runs the check in a child process (`multiprocessing` or `subprocess` with the same interpreter) with a hard timeout of `alarm_s`. On timeout it kills the child and exits 2. This costs about 30 to 60 ms per hook run in process start-up, so it is the fallback, not the default. The step-3 PR records which path it took.

## Tests (added to #139 "Tests: every bypass spelling, pinned")

- **The bypass corpus**, one fixture file, `pr-merge-flow/tests/fixtures/pr_guard_bypass_corpus.txt`, in the same JSON-lines `[cwd, cmd]` form as `pr_guard_inputs.txt`. It holds:
  - every input from #132 rounds 1 to 3 (its `NESTED` and `ROUND3` tables);
  - probe rows 1 to 8 above;
  - the `case`-in-`$(` and `${x:-$(echo })}` spellings under each bash version present.
- **Each corpus row is tested two ways:**
  1. **The real hook denies it.** The row goes through `main()` with a stdin payload and must exit 2.
  2. **Bash really runs a merge.** The row runs under `/bin/bash`, and under a bash ≥ 4.2 when one is installed, with a harmless `gh` recorder first on `PATH`. The recorder must see `pr merge`. A row whose recorder sees no merge is not a bypass: the test fails and asks for the row to move to the negatives.
  - This is #132's recorder pattern, kept: real behavior, no mocks of our own code.
- **Negatives that must stay allowed**, also run under the recorder (no merge seen) and through `main()` (exit 0):
  - `--body "$(cat <<'EOF' … EOF)"` with apostrophes;
  - `git commit -m "$(cat <<'EOF' … EOF)"`;
  - `bash -c 'echo gh pr merge'` with single quotes;
  - `$'…'` and `${…}` used as plain text;
  - a `deploy.sh` argument;
  - `echo a#b`.
- **The mutation test for `NESTED_TRIGGER_COMMANDS`.** For each listed word, the test builds a hard-construct body around a merge, wrapped in that word. It does this in four spellings: plain, `w''w`-split (`g''h`), backslash-split (`g\h`) and quote-joined (`"g"h`). Each of the four must deny. The test also removes each word from a copy of the constant and asserts that at least one corpus row then passes. If no row passes, the word has no test case and the test says so.
- **The AST and perf tests** from A4.
- **Parity.** `test_pr_guard_parity.py` runs against the previous pr-merge-flow release: lost = 0, crashed = 0. New denials are allowed and are listed in the PR.

## Affected surfaces

- `pr-merge-flow/scripts/pr-guard.py`. `token_checks` is added beside `legacy_checks`, per #139 step 3. Nothing in `legacy_checks` changes.
- `pr-merge-flow/scripts/shell_tokens.py` and `review-gate/scripts/shell_tokens.py`, the byte-identical mirror from #139.
- `pr-merge-flow/scripts/hook_runtime.py` and its review-gate mirror. This adds the child-process fallback only if A4's perf test needs it.
- `pr-merge-flow/SKILL.md`, for the `NESTED_TRIGGER_COMMANDS` list and the fail-closed constructs.
- `pr-merge-flow/tests/test_pr_guard.py`, the new corpus fixture, and `test_pr_guard_parity.py`.
- review-gate's `merge-guard.py` takes the same tokenizer at #139 step 4. The A3 trigger applies there too, through the shared module.
- Consumers: the vendored copies re-vendor per #139 step 5. Nothing in this plan touches a vendored copy directly.

## Not in scope

- Anything #139 lists as not in scope: computed command names, stdin piped to a shell, sourced files, server-side enforcement.
- Reproducing bash 3.2 versus 4+ grammar differences. A3 fails closed on them instead.
- #131 and the fence-guard plan PR. They stay held until the `env -S` PR lands, per the Program Cop.

## Done when

1. The `env -S` PR (1.6.1) is merged, and #132 is closed as superseded with a pointer to it.
2. #139 step 2 has landed with A2 and A4 in `shell_tokens.py` and `hook_runtime.py`: the AST ban, the regex test and the perf test are green.
3. #139 step 3 has landed in pr-guard with A3. Every corpus row exits 2 through `main()`, and its recorder shows a merge. The negatives exit 0. The mutation test is green, and parity is lost = 0.
4. Probe rows 1 to 8 re-run on the released main exit 2, recorded in the release PR.
