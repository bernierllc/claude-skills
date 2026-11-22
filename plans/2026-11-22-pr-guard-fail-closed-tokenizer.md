# pr-guard: fail-closed tokenizer, an amendment to the tokenizer-first plan

Status: planned. Amends [the tokenizer-first merge guard plan](2026-11-21-tokenizer-first-merge-guard.md) (PR #139). It does not replace it. Each section below names the #139 section it changes. Where this file says nothing, #139 stands.

## What happened

- PR #132 (pr-merge-flow, the `env -S` fix that grew into nested-code parsing) went through three review rounds.
  - Round 1 was clean on the `env -S` block.
  - Rounds 2 and 3 added a nesting core to `segments()`: substitution bodies, `bash -c`, `eval`, `builtin`, `$'…'`, `${…}` skipping, a private-use character ban, an input cap and a crash exit.
  - Round 3 (review 6013559168) was NOT CLEAN, with five P1 bypasses in the same class.
- The traffic cop stopped patching: no fourth round. The Program Cop routed the work two ways:
  - land the round-1 `env -S` block alone, as its own PR. That is #157, merged as 4974d55 (pr-merge-flow 1.6.1);
  - close #132 as superseded (closed; its branch `fix/pr-guard-env-s-closed` stays);
  - write the fail-closed design as #139's tokenizer step, which is this file.
- Root cause, the same as #139's: `segments()` reads the command string with patches layered on shlex. Each round closed the spellings it was shown, and the next review found a sibling. The fix is a tokenizer that marks what it cannot resolve and denies it, not a longer list of spellings.

## Probe: these bypasses are live on main today

Each row was run through the real hook: `pr-guard.py` under `python3 -I`, with a stdin JSON `PreToolUse` payload (`tool_name: Bash`) and a working directory with no GitHub remote. Exit 0 means the command runs. The 1.6.0 column is the parity baseline 75137f8. The 1.6.1 column is main 4974d55.

The "Bash runs a merge" column comes from running each row with a `gh` recorder first on `PATH`, once under `/bin/bash` 3.2.57 and once under `/opt/homebrew/bin/bash` 5.3.20. `min_bash` is 3.2 when `/bin/bash` 3.2 runs the merge. Otherwise it is 4.2, #132's figure for the bash that parses these forms the new way.

| # | Command | 1.6.0 | 1.6.1 | Bash runs a merge | Fixed by |
|---|---|---|---|---|---|
| 1 | `>/dev/null gh pr merge 1 --auto` | 0 | 0 | 3.2 and 5.3 | A2 (leading redirect) |
| 2 | `2>&1 gh pr merge 1 --auto` | 0 | 0 | 3.2 and 5.3 | A2 (leading redirect) |
| 3 | `function f { gh pr merge 1 --auto; }; f` | 0 | 0 | 3.2 and 5.3 | A2 (function body) |
| 4 | `FOO+=x gh pr merge 1 --auto` | 0 | 0 | 3.2 and 5.3 | A2 (assignment prefix) |
| 5 | `echo "$(! case x in x) gh pr merge 1 --auto;; esac)"` | 0 | 0 | 5.3 only (min_bash 4.2) | A3 (`case` is hard) |
| 6 | `echo "$(echo ${x:-$(echo })}; gh pr merge 1 --auto)"` | 0 | 0 | 5.3 only (min_bash 4.2) | A3 (non-trivial `${` is hard) |
| 7 | `echo \ # ; gh pr merge 1 --auto` | 0 | 0 | 3.2 and 5.3 | A2 (`#` only at word start) |
| 8 | `/usr/bin/env -vS'gh pr merge 1 --admin'` | 0 | 2 | 3.2 and 5.3 | 1.6.1 |
| 9 | `env -S 'gh pr merge 1 --auto'` | 2 | 2 | 3.2 and 5.3 | already denied |
| 10 | `$(true` + 58K newlines + `)` then a merge | 2 (0.5 s) | 2 | 3.2 and 5.3 | already denied |
| 11 | `echo $((gh pr merge 1 --auto); echo hi)` | 2 | 2 | 3.2 and 5.3 | denied by legacy; A3 pins it (`$((` is hard) |
| 12 | `echo "$(echo a # )` newline `gh pr merge 1 --auto` newline `)"` | 0 | 0 | 3.2 and 5.3 | A3 (comment in a substitution is hard) |
| 13 | `x="$(cat <<EOF` newline `msg $(gh pr merge 1 --auto)` newline `EOF` newline `)"` | 0 | 0 | 3.2 and 5.3 | A3 (an unquoted heredoc is an expansion context) |
| 14 | `a[$(gh pr merge 1 --auto)]=x` | 2 | 2 | 3.2 and 5.3 | denied by legacy; A2 pins it (subscripts are scanned) |
| 15 | `bash -c "env -S 'gh pr merge 1 --auto'"` | 0 | 0 | 3.2 and 5.3 | #139 `Nested` + 1.6.1's env rule in `token_checks` |
| 16 | `` echo `env -S 'gh pr merge 1 --auto'` `` | 0 | 0 | 3.2 and 5.3 | #139 `Nested` + 1.6.1's env rule in `token_checks` |
| 17 | `builtin exec env -S 'gh pr merge 1 --auto'` | 0 | 0 | 3.2 and 5.3 | #139 Rule A (`builtin`) + 1.6.1's env rule |

Rows 1 to 7, 12, 13 and 15 to 17 run a merge on main today while the hook allows it. #132's round 3 found rows 1 to 7, but they predate #132. #132's round 2 fixed rows 15 to 17, and #132 did not land. 1.6.1 denies `env -S` only in a top-level segment, so these three stay live. The exposure lasts until #139 step 3 ships, and it is tracked under "Interim exposure" below.

## Interim exposure

Until #139 step 3 ships, the forms above stay live. There is no interim mitigation in 1.6.1, and this plan does not add one silently. The decision is on Tracker row [PRGUARD-INTERIM-BACKSTOP](https://app.notion.com/p/PRGUARD-INTERIM-BACKSTOP-interim-block-for-nested-substitution-merges-156-probe-rows-1-7-env-S-4204efecc95a814d85aec336aa6e273b) (Owner Needs-PM). It offers two options:

- (a) a coarse backstop in `legacy_checks`, which would deny `gh` + `merge` anywhere inside a substitution or a shell string;
- (b) accept the exposure for the interval and list the live forms in pr-merge-flow's `SKILL.md`.

Both options are reversible, and neither changes this plan's design.

## Amendments

### A1. Migration step 1 (#139 "Migration order", step 1)

Replace "Wait for #131 and #132" with:

1. **Wait for the `env -S` PR (#157, merged as 4974d55, pr-merge-flow 1.6.1).**
   - 1.6.1 contains #132's round-1 commits on top of 1.6.0, plus these #157 review fixes:
     - `env -S` / `--split-string` is denied on sight. This covers any path, clusters such as `-vS`, `--sp` prefixes, and use behind `sudo`/`nice`. It also covers an option word that is not a plain word, such as `env {-S,x}`, `env $'\x2dS'`, ``env --chdir `pwd` -S`` and `env -u $X`. A `NAME=value` word ends env's options, so `env GH_TOKEN=$T gh pr view 1` stays allowed.
     - The env check runs before the `# sync-base:` early return. That comment waives only the base-sync check.
     - Command words match by basename.
     - A guard crash exits 2.
     - The parity harness writes the baseline's `tests/fixtures/` into its temp dir, which every PR after 1.6.0 needs.
   - #132 is closed as superseded. Its branch `fix/pr-guard-env-s-closed` stays.
   - **#132's round 2 and 3 test inputs become corpus rows** (section "Tests" below), not code to port. That is the same treatment #139 already gives #131's and #132's cases. This covers probe rows 15 to 17 and #132's `NESTED` and `ROUND3` tables. The crash-to-exit-2 fix is already in 1.6.1. The corpus keeps its row, a check that raises, so step 3 cannot lose it.
   - #131 is not a prerequisite of this plan. Its owner is being settled separately (the Program Cop decides whether to close or re-own it). Whatever lands keeps parity lost = 0.

### A2. The tokenizer reads characters, not regexes (#139 section 1)

Add to "How it finds the ends of constructs":

- **One linear character loop.** `shell_tokens.tokenize` and everything it calls index the string one character at a time with an explicit context stack.
- **No regex machinery in the shared module.** `shell_tokens.py` and `hook_runtime.py` import none of `re`, `shlex`, `fnmatch` or `glob`. `shlex` imports `re`, and `fnmatch` and `glob` compile regexes.
  - This amends #139 section 1, which kept `shlex` as the word splitter for the plain spans. The character loop splits words itself, and `shlex` stays only in `legacy_checks`.
  - The AST test is in A4.
- **Size caps record a failure, which denies (R7).**
  - **Input cap.** Input over 128 KiB (131,072 bytes after UTF-8 encoding) is a failure before scanning starts.
    - Cost: a large `cat > f <<'EOF'` that writes more than 128 KiB is denied. It has no waiver: a waiver marker would sit in text the scanner refuses to read.
    - The fix for the user is to write large files with the Write tool, not a heredoc. The denial message says so.
  - **Read budget.** The scanner counts every character it reads, including re-reads when a body is fed back through `tokenize`. Past 4× the input length it records a failure.
    - `--body "$(cat <<'EOF' … EOF)"` costs about 3n: the outer scan, the `$(` body fed back, and the heredoc body scanned for its delimiter. 2× would deny it, and 4× leaves headroom.
    - The step-2 PR measures the highest ratio over the corpus and the negatives and records it. A negative that exceeds the budget fails the test.
- **`#` starts a comment only at the start of a word.** The test is "the character before it ends a word": unquoted whitespace, a control operator, or the start of input.
  - So `echo \ #` keeps `#` inside the word (the escaped space is part of the word), and `; gh pr merge …` after it is a new segment (probe row 7).
  - `a#b` and `"#"` are not comments.
  - A comment inside a substitution body is a hard construct (A3).
- **Redirects are read by shape, not from a closed list.** A redirect is:
  1. an optional fd number or `{name}`;
  2. then one of `<`, `>`, `>>`, `>|`, `<>`, `<&`, `>&`, `&>`, `&>>`, `<<`, `<<-`, `<<<`;
  3. then its target word, or `-` with `<&`/`>&` (`>&-` closes the descriptor).

  So `{fd}>f`, `<>f`, `>&-` and `&>>f` are all redirects. A segment may start with any number of them. They go into the segment's `redirects`, and the next word is the command position (probe rows 1 and 2). Redirects between words are handled the same way. A redirect target is a word like any other: its `$(…)` is parsed.
- **Control operators, all of them:** `;`, `&`, `&&`, `||`, `|`, `|&`, `;;`, `;&`, `;;&`, newline, `(` and `)`. `|&` is a pipe: its right side is a new segment. `;&` and `;;&` end a `case` arm, the same as `;;`.
- **Reserved words that keep the command position open:** `!`, `time` (with `-p`), `coproc`, `[[`, `((`, `{`, `(`, `if`/`then`/`elif`/`else`, `while`/`until`/`do`, `function`.
  - After `!`, `time` or `coproc`, the next word is a command position.
  - `coproc NAME` followed by a compound command takes NAME as the coprocess name, and the compound's first word is the command position.
  - `[[ … ]]` words are not commands, but their `$(…)` bodies are parsed.
  - `((` follows A3's arithmetic rule.
- **Every assignment form is a prefix, not a command.** `NAME=v`, `NAME+=v` and `NAME[i]=v` before the command word are bindings, and the next word is the command position (probe row 4). The subscript `i` and the value `v` are scanned like any word: `a[$(gh pr merge 1 --auto)]=x` reaches R1 through the substitution (probe row 14).
- **`function name { …; }`, `function name() …` and `name() …` bodies are segments.** The body's first word is a command position (probe row 3). #139 already lists `function` and `name()` as segment starts. This makes the `function` keyword form with a `{` body explicit, with a test row.

### A3. Hard constructs fail at their own offset (#139 sections 1 and 2)

#139 parses `$(…)` and backtick bodies into `nested`. That is correct when the scanner can find where each body ends and Bash agrees. Probe rows 5, 6, 11 and 12 are spellings where the scanner and Bash can disagree about where a body ends. In some of them, bash 3.2 and bash 4+ also disagree with each other (rows 5 and 6). After that disagreement, the scanner is out of sync with Bash, and every word it reads later is suspect.

**Rule: a hard construct is a parse failure at the construct's own offset. The failure depends on nothing read after that offset.** The tokenizer does not look at the body's later words, command names, or any trigger list. The circular part of the earlier draft is gone: it read words past the point where the scanner may have lost sync, then decided from them. So `NESTED_TRIGGER_COMMANDS` is removed, and with it the mutation test and the "trigger matches any word" concern. Rows 5 and 6 fail at `case` and at `${` respectively, whatever follows.

**Where the rule applies.** It applies in every context that runs code inside a word:

- `$(…)`, backticks, `<(…)` and `>(…)` bodies, at any depth;
- the body of an unquoted heredoc. An unquoted delimiter makes the body an expansion context, read like a double-quoted string: its `$(…)`, backticks, `${…}` and `$((…))` are constructs under these rules, and its other text is data.

At top level (outside every substitution), #139 section 1 stands, with these exceptions, which apply everywhere: the `$((`/`((` rule below, and `${` whose operand holds `$(`, a backtick or another `${`.

**Hard constructs.** Each of these is a failure, unless it matches the allowlist below:

- the reserved word `case`;
- `${`;
- `$'` and `$"`;
- a heredoc operator (`<<`, `<<-`). `<<<` is a here-string, a plain word, and is not on this list;
- `$((` and `((`, anywhere, including top level. Bash reads `$((x); y)` as a command substitution when the arithmetic parse fails (probe row 11). The scanner does not try both readings; it allows only the shape below;
- a comment (`#` at the start of a word) inside a substitution body. The comment may hold a `)` that Bash ignores and the scanner might not (probe row 12);
- an unmatched `$(`, backtick, `${` or `((`.

**The allowlist.** These forms are allowed. Nothing else is.

1. **A heredoc whose segment command is `cat` or `printf`.** The command word must be a `Literal` whose basename is `cat` or `printf`, and it must come before the heredoc operator. `<<'EOF' cat` is a failure, because the command word must not come after the construct.
   - **Quoted delimiter** (`<<'EOF'`, `<<"EOF"`, `<<\EOF`, and the `<<-` forms of each): the body is inert text. It ends at the first line equal to the delimiter (tabs stripped for `<<-`), and R10 still scans it.
   - **Unquoted delimiter** (`<<EOF`): the body is an expansion context (above). Each construct in it is parsed under these rules, so row 13's `$(gh pr merge 1 --auto)` reaches R1 and is denied as a merge. `$VAR`, `\$`, `` \` `` and a harmless substitution such as `` `date` `` stay allowed.
2. **Trivial parameter expansion:** `${name}`, `${#name}`, and `${N}` or `${@}`/`${*}`/`${#}`/`${?}`, with nothing else between the braces. `name` is `[A-Za-z_][A-Za-z0-9_]*`, checked character by character. Each one becomes an `Unresolved` fragment, as `$name` does. `$(git log -1 --format=${FMT})` stays allowed.
3. **Arithmetic of plain shape**, for `$((…))` and `((…))`:
   - the body consists only of operands and operators;
   - an operand is a number, a `name`, `$name` or a trivial `${name}`;
   - an operator is one of `+ - * / % < > = ! & | ^ ~ ? : ,`, or a parenthesis;
   - every two operands have an operator between them;
   - the body contains no `;`, no newline, no quote, no backtick and no `$(`.

   `$((i+1))` and `((n > 2))` are allowed. `$((gh pr merge 1 --auto); echo hi)` fails, because `gh pr` is two operands with no operator.

**Cost (R7, new denials).** These forms are denied, and Bash would run some of them harmlessly. The fix for the user, in each denial message, is to move the logic out of the substitution or to use a plain variable.

- `$(case $x in a) echo a;; esac)`;
- `echo "$(echo ${x:-default})"`;
- `x=$(grep foo f # note)` spread over lines;
- `$(git commit -F - <<'EOF' … EOF)`, whose heredoc command is not `cat` or `printf`.

`--body "$(cat <<'EOF' … EOF)"` and `git commit -m "$(cat <<'EOF' … EOF)"`, the common agent heredocs, are allowed by item 1.

**R6 restated for pr-guard.** Any word after `merge` that is not a `Literal` denies. `--match-head-commit` must be a `Literal` of exactly 40 hex characters. #139 R6 already says this; this plan adds the test rows.

### A4. The hook decides in a child process with a hard timeout (#139 section 4)

The cop's review point (1): `signal.setitimer` and a watchdog thread do not fire while CPython runs one C-level `re` match. The signal handler runs only between bytecodes, and `re`'s matcher does not release the GIL or check for signals.

#139 section 4 calls the alarm "the last resort that turns a check stuck outside a cooperative deadline check (a regex, …) into a denial". For a regex, that is wrong. A backtracking pattern on 128 KiB can run past the hook's 20 s timeout. The hook is then killed, and a killed hook does not deny, so the command runs. `legacy_checks` keeps its regexes by design (#139 section 0), and a static lint for nested quantifiers misses polynomial patterns (`\s*x\s*y`-style overlaps). So the guarantee has to come from a process boundary, not from a lint.

Replace that sentence, and add:

- **`run_hook` runs `token_checks` first, in process, and returns on a deny.**
  - `token_checks` uses no regex (A2). It is bounded by the caps and by the cooperative `Deadline`, so the in-process alarm still works for it.
  - A deny there exits 2 with no child process started.
- **If `token_checks` allows, `legacy_checks` runs in a child process. This is the default, not a fallback.**
  - `run_hook` runs `subprocess.Popen([sys.executable, "-I", <the guard script>, "--legacy-only"], stdin=PIPE, stdout=PIPE, stderr=PIPE, start_new_session=True)`.
  - It writes the payload, then calls `communicate(timeout=…)`. The timeout is the time left until `alarm_s`.
  - The child gets the remaining cooperative budget in seconds as an argument and builds its own `Deadline` from it.
  - On `TimeoutExpired`, the parent calls `os.killpg` on the child's process group and exits 2 with "check timed out".
- **The parent maps the child's exit status:**
  - `0` → allow;
  - `2` → deny, with the child's stderr passed through;
  - anything else → deny (exit 2), naming the status. That covers a crash, a signal, a missing module and an unexpected code.
- **Why `subprocess` and not `multiprocessing`.** `multiprocessing`'s spawn start method (the default on macOS) re-imports the main module by name. The hyphenated `pr-guard.py` cannot be imported by name. Newer Pythons default to forkserver on Linux, which has the same problem. `subprocess` runs the script as a script.
- **Cost.** One interpreter start per hook run that `token_checks` allows, measured as about 30 to 60 ms for `python3 -I`. The step-3 PR records the measured median and p95 on the CI runner.
- **The no-regex ban is an AST test.**
  - It parses `shell_tokens.py` and `hook_runtime.py`.
  - It fails on any import of `re`, `shlex`, `fnmatch` or `glob`: `import x`, `from x import …`, `__import__("x")` and `importlib.import_module("x")`.
- **The nested-quantifier lint stays, as hygiene, not as the guarantee.**
  - It walks the string constants passed to `re.compile`, `re.search`, `re.match`, `re.fullmatch`, `re.sub`, `re.findall` and `re.finditer` in both guards.
  - It fails on a quantified group that contains another quantifier.
  - A pattern built at run time must be listed, with its reason, in one allowlist in the test file.
- **A hostile-input perf test with a measured ratio, as #139 section 4 does with its fixed shapes.**
  - **Shapes**, each at 128 KiB:
    - `gh pr ` repeated;
    - `$(` × N, then `)` × N;
    - `"` × N;
    - `\` + space, repeated;
    - 58K newlines inside `$(true …)`;
    - `a=` repeated;
    - `# ` repeated;
    - a heredoc whose body is near-miss terminators;
    - `--body "` + 128 KiB of `x` + `"`.
  - **Measurement.** The test times `check()` on each shape. It also times a reference command, `gh pr view 1` padded with plain words to the same size, on the same runner, in the same run.
  - **Pass condition.** Each shape must finish within 20× the reference and under `alarm_s` in absolute time.
  - **Reconciling #139's 1 s figure.** The ratio replaces a fixed seconds figure, so a slow CI runner cannot flip the test and a fast laptop cannot hide a quadratic shape. #139's own timing rows (1 s at 80 KB, in process) stay as they are for its shapes. This test adds the 128 KiB shapes on top.
  - A failure names the shape and its ratio.
  - The whole-hook path through `main()` (with the child process) is timed once per shape against `alarm_s` only.

## Tests (added to #139 "Tests: every bypass spelling, pinned")

- **The bypass corpus** is one fixture file, `pr-merge-flow/tests/fixtures/pr_guard_bypass_corpus.jsonl`. It holds one JSON object per line:

  ```json
  {"cwd": "…", "cmd": "…", "kind": "runs" | "policy", "min_bash": "3.2" | "4.2"}
  ```

  - **`kind: "runs"`** rows really run a merge. Each is tested two ways:
    1. **Bash really runs a merge.** Run the row with a harmless `gh` recorder first on `PATH`, under every installed bash at or above the row's `min_bash`. Check `/bin/bash` and every `bash` on `PATH`, and record each version. The recorder must see `pr merge`. A row whose recorder sees no merge fails the test and asks for the row to be reclassified. A row whose `min_bash` no installed bash meets is skipped, and the skip names the version needed.
    2. **The real hook denies it.** The row goes through `main()` with a stdin payload and must exit 2.
  - **`kind: "policy"`** rows run no merge themselves, or need something the test cannot provide. pr-guard denies them by policy (#139 R2, or a wrapper it does not trust). They are tested through `main()` only, and they must exit 2. Examples:
    - `echo gh pr merge 1 --auto`;
    - `ssh host gh pr merge 1 --auto`;
    - `/opt/homebrew/bin/gh pr merge 1 --auto`;
    - `docker exec c gh pr merge 1 --auto`.
  - **The `runs` rows include:**
    - every input from #132 rounds 1 to 3 that bash really runs (its `NESTED` and `ROUND3` tables);
    - probe rows 1 to 8 and 11 to 17;
    - rows 5 and 6 with `min_bash: "4.2"`;
    - one wrapper row per Rule A wrapper #139 lists: `doas`, `ionice`, `stdbuf`, `setsid`, `chroot`, `nice`, `timeout`, `nohup`, `time`, `exec`, `builtin`, `command`, `xargs`, `env`;
    - the macOS wrappers `arch` and `caffeinate`;
    - the brace form `g{h,} pr merge 1 --auto`.

    If a row's wrapper is not installed on the runner, its bash leg is skipped and the skip names the wrapper. Its `main()` leg always runs.
  - **Rows for A2 and A3:**
    - a comment holding `)` inside `$(`;
    - `{fd}>f`, `<>f`, `>&-`, `&>>f` and `|&` before a merge;
    - `;&` and `;;&` arms;
    - `!`, `time`, `coproc` and `[[ $(…) ]]` around a merge;
    - `a[$(…)]=x`;
    - `$((…); …)`;
    - quoted and unquoted heredocs that hold a merge in a substitution.
- **Negatives that must stay allowed.** Each runs under the recorder (no merge seen) and through `main()` (exit 0):
  - `gh pr merge 1 --squash --match-head-commit <40 hex>` with green checks stubbed at the `gh` recorder. This is the one allowed merge, and it pins that A2 and A3 deny nothing on the happy path;
  - `--body "$(cat <<'EOF' … EOF)"` with apostrophes;
  - `gh pr create --body "$(cat <<EOF … EOF)"` (unquoted) whose body holds `$VAR`, `\$`, an escaped `` \` `` and a harmless `` `date` ``;
  - a quoted heredoc body that contains `gh`, `git push` and a line holding only `.`;
  - `$(git log -1 --format=${FMT})`;
  - a 60 KB quoted heredoc body (inside the 128 KiB cap, under the 4× read budget);
  - `git commit -m "$(cat <<'EOF' … EOF)"`;
  - `bash -c 'echo done'`;
  - `$'…'` and `${…}` used as plain text at top level;
  - a `deploy.sh` argument;
  - `echo a#b`;
  - `$((i+1))` and `((n > 2))`.

  This replaces the earlier `bash -c 'echo gh pr merge'` negative, which #139 R2 denies (three separate `Literal` words in a `Nested` body).
- **Commit rows run against a real temporary git repo**, created by the test with `git init` and one commit, so `git commit` really runs under the recorder. No `git` stub.
- **The AST, lint and perf tests** come from A4.
- **The child-process tests:**
  - a check that raises in the child, a child killed by a signal, and a child that sleeps past the timeout each exit 2 through `main()`;
  - the parent's `killpg` leaves no process behind;
  - each of those runs only after `token_checks` allowed, and a `token_checks` deny starts no child. The test checks this through real behavior: it sets an environment variable that makes `--legacy-only` touch a marker file, then asserts that no marker file exists.
- **Parity.** `test_pr_guard_parity.py` runs against the previous pr-merge-flow release (1.6.1 at step 3): lost = 0, crashed = 0. New denials are allowed and are listed in the PR.

## Affected surfaces

- `pr-merge-flow/scripts/pr-guard.py`:
  - `token_checks` is added beside `legacy_checks`, per #139 step 3;
  - `--legacy-only` is the child-process entry;
  - nothing in `legacy_checks` changes.
- `pr-merge-flow/scripts/shell_tokens.py` and `review-gate/scripts/shell_tokens.py`, the byte-identical mirror from #139.
- `pr-merge-flow/scripts/hook_runtime.py` and its review-gate mirror: `run_hook` gains the token-first order, the child process, the exit mapping and `killpg`.
- `pr-merge-flow/SKILL.md`: the hard constructs, the allowlist, the 128 KiB cap with the Write-tool advice, and the new denials listed under A3's "Cost".
- `pr-merge-flow/tests/test_pr_guard.py`, the new corpus fixture, and `test_pr_guard_parity.py`.
- review-gate's `merge-guard.py` takes the same tokenizer and the same `run_hook` at #139 step 4. Its `legacy_checks` also moves into the child process. That is a step-4 change, reviewed there.
- Consumers: the vendored copies re-vendor per #139 step 5. Nothing in this plan touches a vendored copy directly.

## Not in scope

- Anything #139 lists as not in scope: computed command names, stdin piped to a shell, sourced files, server-side enforcement.
- Reproducing bash 3.2 versus 4+ grammar differences. A3 fails closed on them instead.
- #131 and the fence-guard plan PR. Their owners are being settled separately.
- The interim backstop, which is decided on its own Tracker row (see "Interim exposure").

## Done when

1. #157 (1.6.1) is merged, and #132 is closed as superseded. Both are done.
2. #139 step 2 has landed with A2 and A4 in `shell_tokens.py` and `hook_runtime.py`, and these tests are green:
   - the AST ban;
   - the nested-quantifier lint;
   - the perf ratio test;
   - the child-process tests.
3. #139 step 3 has landed in pr-guard with A3, and:
   - every `runs` corpus row's recorder shows a merge under each installed bash at or above its `min_bash`, and the row exits 2 through `main()`;
   - every `policy` row exits 2 through `main()`;
   - the negatives exit 0;
   - parity is lost = 0.
4. After the step-3 release is on main, the probe is re-run against that release with the probe script from this plan: every live row (1 to 7, 12, 13, 15 to 17) exits 2. The result is recorded on this plan's Tracker row, with the release commit SHA. It is not recorded in the release PR itself, which cannot cite its own merge.
