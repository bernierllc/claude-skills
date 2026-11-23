# pr-guard: deny a heredoc inside a substitution, an amendment to the tokenizer-first plan

Status: planned. Amends [the tokenizer-first merge guard plan](2026-11-21-tokenizer-first-merge-guard.md) (PR #139) with one rule. It does not replace that plan. Where this file says nothing, #139 stands.

## What happened

- This plan first went through three review rounds as a broad fail-closed tokenizer amendment. Every round found new bypasses in the same area. Round 2's P0 (a heredoc inside `$(…)` is not inert on bash 3.2) and round 3's P0 (the dangerous body can sit outside the substitution) both come from one construct.
- Following the rule that three rounds in one area means simplify or plan, the plan is cut to the one rule that closes that construct (MATT-146: simplify). Everything else is parked in the follow-up note at the end.

## Probe: live on main today

Each command was run with a `gh` recorder first on `PATH`, under `/bin/bash` 3.2.57 (macOS) and `/opt/homebrew/bin/bash` 5.3.20. Each was also run through the real hook: `pr-guard.py` from main c42f5d0 (pr-merge-flow 1.6.2) under `python3 -I`, with a stdin `PreToolUse` payload and a working directory with no GitHub remote. Exit 0 means the hook lets the command run.

| # | Command (newlines shown as ⏎) | 3.2.57 | 5.3.20 | hook |
|---|---|---|---|---|
| 1 | `x=$(cat <<'EOF2'` ⏎ `)` ⏎ `gh pr merge 1 --auto` ⏎ `EOF2` ⏎ `)` | merges | runs nothing | 0 |
| 2 | `echo "$(cat <<'EOF' )"` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 2, for `--auto` only |
| 3 | `x=$(cat <<EOF )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 4 | `cat <(cat <<'EOF' )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 5 | `x=$(cat <<'EOF' \| cat )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 6 | ``echo "`cat <<'EOF' `"`` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 2, for `--auto` only |
| 7 | `cat <<EOF` ⏎ `$(cat <<X )` ⏎ `EOF` ⏎ `gh pr merge 1 --auto` ⏎ `X` | merges | merges | 2, for `--auto` only |
| 8 | `x=$(cat <\` ⏎ `<'EOF' )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 9 | `/bin/bash -c 'x=$(cat <<EOF )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF'` | merges | merges | 0 |
| 10 | `/bin/bash <<'OUT'` ⏎ `x=$(cat <<EOF )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` ⏎ `OUT` | merges | merges | 0 |
| 11 | `echo ${x:-$(cat <<'EOF' )}` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 12 | `x=$(( $(cat <<'EOF' ) ))` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 13 | `cat <<'EOF' $(echo hi` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` ⏎ `)` | merges | merges | 0 |
| 14 | `x=$(echo) cat <<'EOF' ; echo $(` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` ⏎ `)` | merges | merges | 0 |
| 15 | `x=$\` ⏎ `(cat <<'EOF' )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 16 | `cat <\` ⏎ `(cat <<'EOF' )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 17 | `x=$((cat <<'EOF' ) )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 18 | `echo $((cat <<EOF ) )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 19 | `x=$(( (cat <<'EOF' ) ))` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 20 | `(( (cat <<'EOF' ) ))` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 21 | `((cat <<'EOF' ))` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 22 | `echo $[ (cat <<'EOF' ) ]` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 23 | `a[ (cat <<'EOF' ) ]=1` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 24 | `echo ${y:0:(cat <<'EOF' )}` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 0 |
| 25 | `echo ${y//<<'EOF'/z}` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | merges | 2, for `--auto` only |
| 26 | `x=${ cat <<'EOF' ; }` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 27 | ``cat <<'E' `echo`` ⏎ `gh pr merge 1 --auto` ⏎ `E` ⏎ `` ` `` | merges | merges | 0 |
| 28 | `cat <<'E' <(echo` ⏎ `gh pr merge 1 --auto` ⏎ `E` ⏎ `)` | merges | merges | 0 |
| 29 | `cat <<'E' ${ echo` ⏎ `gh pr merge 1 --auto` ⏎ `E` ⏎ `}` | runs nothing | merges | 0 |
| 30 | `x=$(# )` ⏎ `cat <<'EOF'` ⏎ `)` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |
| 31 | `x=$(echo a#( )` ⏎ `cat <<'EOF'` ⏎ `)` ⏎ `gh pr merge 1 --auto` ⏎ `EOF` | merges | runs nothing | 0 |

Why: bash 3.2 finds the end of a substitution by scanning the heredoc body as shell text. Bash 4+ reads the body up to its delimiter line. In rows 2 to 5, 8, 11 and 12, 3.2 closes the substitution at the `)` on the operator's own line, before the body starts, so it runs the body as top-level commands. In row 1, 3.2 closes it at the `)` line inside the body, so the lines after that run. A scanner that follows bash 4+ (as #139's does) reads both bodies as inert text. In backticks (row 6), both bashes close the substitution at the closing backtick, so the body runs on 5.3 as well. Row 7 puts the substitution in an unquoted top-level heredoc body, and both bashes run the inner heredoc's body after the outer `EOF`. Rows 9 and 10 run the inner text with `/bin/bash`, which is 3.2 whatever shell runs the outer command. Rows 13 and 14 are the same overlap the other way round: the heredoc operator is at top level and a substitution opened later on its line runs past the newline, so both bashes read the next lines as the substitution's commands, not as the heredoc body. Rows 8, 15 and 16 split `<<`, `$(` or `<(` with a backslash-newline, which bash joins before it reads the token. In rows 17 and 18, bash fails to read `$((` as arithmetic and re-reads it as `$(` plus a subshell, so a heredoc sits inside a substitution that a scanner reading `$((` as arithmetic never sees. In row 19, `$((` is arithmetic and `<<` is a shift; the arithmetic fails, and both bashes run the next line, which a scanner reading `<<'EOF'` as a heredoc takes for its body. No check on the body's characters or on where the closing `)` falls is safe across both bashes, because the two bashes disagree about which text is the body. Rows 20 to 26 put the heredoc in other brackets: an arithmetic command, `$[…]`, an array subscript, a `${…}` operand or pattern, and `${ …; }` (which 3.2 does not know, so only 3.2 runs row 26's body). Rows 27 to 29 are rows 13 and 14 with a backtick, `<(` and `${ ` (5.3 only, since 3.2 has no `${ …; }`). In row 30, bash 3.2 reads the word-initial `#` inside the substitution as the start of a comment, so the `)` after it does not close the substitution; 5.3 rejects it. In row 31, the `)` on the first line pairs with the `(` after the mid-word `#`, so the `$(` stays open and 3.2 runs the body as in row 1. Bash 4.0 to 5.2 were not probed.

## The amendment (#139 sections 1 and 2)

**Rule: a heredoc operator may appear only outside every bracket, no bracket may stay open across the start of a heredoc body, and nothing that may be a comment may sit inside a bracket.**

#139's scanner already keeps one stack of quoting contexts (its "How it finds the ends of constructs"). This amendment extends that same stack; it adds no second one. Every unquoted, unescaped `(`, `[` and `{` pushes, and `)`, `]` and `}` pop their match; a backtick pops an open backtick on top of the stack and otherwise pushes one. So `$(`, `$((`, `((`, `$[`, `${`, `${ …; }`, `<(`, `>(`, `[[`, array subscripts, subshells and groups all count, with no list to keep current. Quoting and escapes are #139's tokenizer's: a backslash-escaped bracket is literal, and text in single quotes, or in double quotes outside an expansion, is neither counted nor scanned for `<<`. In a heredoc body with a quoted delimiter nothing is counted. In a body with an unquoted delimiter only its expansions (`$(`, `$((`, `${`, `$[`, backtick) are counted. Outside every bracket, a `#` that starts a word begins a comment, which is skipped to the end of its line; a `#` inside a word is text. Each of these is a parse failure:

1. **An unquoted `<<` or `<<-` while the stack is not empty**, at its offset (rows 1 to 12, 15 to 26, 31).
2. **A non-empty stack at the end of a line on which a heredoc operator is waiting for its body**, at the offset of the innermost open bracket (rows 13, 14, 27 to 29). That bracket would run past the point where the body starts.
3. **A closer that does not match the top of the stack, or has nothing to close, in input that holds a heredoc operator**, at its offset. Without it, a mis-paired closer such as a `case` arm's `)` could empty the stack while bash is still inside a substitution.
4. **An unquoted `#` while the stack is not empty, in input that holds a heredoc operator**, at its offset, unless it comes straight after `$` or `${` (rows 30, 31). Bash 3.2 and 5.3 disagree on where a comment inside a substitution starts, so the scanner does not guess.

"Input" is the whole command string the hook receives, or one `Nested` body. The heredoc operator may come after the closer or the `#`, so clauses 3 and 4 are decided at the end of the scan.

The bullets below apply to all four clauses.

- **Nested bodies.** Every body #139 parses as `Nested` (`bash -c`, `eval`, `env -S`, a heredoc fed to a shell) is checked the same way, starting with an empty stack (rows 9 and 10). A failure found there is added to the outer command's `Parsed.failures`.
- **What counts as a heredoc operator:** `<<` and `<<-`, with any delimiter, quoted (`<<'EOF'`, `<<"EOF"`, `<<\EOF`) or unquoted (`<<EOF`). Backslash-newline continuations outside single quotes are joined before any token is recognised, so `<\` ⏎ `<` is `<<`, `$\` ⏎ `(` is `$(` and `<\` ⏎ `(` is `<(` (rows 8, 15, 16). `<<<` is a here-string, not a heredoc operator, and is unaffected.
- **No allowlist.** The failure does not depend on the segment's command, the delimiter, the body or anything read after the operator.
- **How it denies:** the tokenizer records the failure in `Parsed.failures`, and #139 R7 denies the whole command. For every clause, the denial message contains the exact string `heredoc inside a substitution`, the failure's offset, and the fix below.
- **Where it lives:** `shell_tokens.py`, so both guards get it at #139 steps 2 to 4. pr-guard enforces it from #139 step 3.
- **Top-level heredocs are otherwise unaffected.** A heredoc outside every bracket with a quoted delimiter is inert text, so `gh pr create --body-file - <<'EOF'` and `git commit -F - <<'EOF'` may hold any text. One with an unquoted delimiter keeps #139's handling: its body's expansions are parsed, and this rule applies inside them (row 7).

**Cost (new denials).**

- `gh pr create --body "$(cat <<'EOF' … EOF)"` and `git commit -m "$(cat <<'EOF' … EOF)"` are denied, whatever the body holds. They are common, so this is the main cost.
- Any unquoted `#` inside brackets other than `$#` and `${#`, such as `${x#pat}`, `${x##pat}`, `$((16#ff))` or a comment, in input that also holds a heredoc operator.
- Any unquoted `<<` inside brackets that is not a heredoc operator: a shift in `$((…))` or `((…))` (`echo $((1<<2))`), or a pattern in `${…}` (`echo ${y//<</z}`).
- A heredoc inside a subshell, group or function body, such as `( cat <<'EOF' … )`, `{ cat <<'EOF' ; … }` or `f() { cat <<'EOF' … }`. Both bashes run these correctly, but the stack cannot tell them from a substitution. Move the heredoc outside the brackets, for example `{ …; } <<'EOF'`.
- A heredoc in input that also holds a `case` arm written `a)`; the `(a)` form pairs its brackets and is allowed.
- A multi-line bracket opened on a heredoc's operator line, such as `cat <<EOF $(printf` ⏎ `a)` ⏎ `…`. This is rare.

**The fix, printed in the denial:** move the heredoc to top level with `gh pr create --body-file - <<'EOF'`, `gh pr comment <n> --body-file - <<'EOF'` or `git commit -F - <<'EOF'`. Or write the body with the Write tool and pass `--body-file <file>` / `-F <file>`. pr-merge-flow's `SKILL.md` documents these forms as the standard way to pass a body.

## Tests (added to #139 "Tests: every bypass spelling, pinned")

Rows go in `pr-merge-flow/tests/test_pr_guard.py`. The tokenizer unit rows go in the `test_shell_tokens.py` pair.

- **Bypass rows** are probe rows 1 to 31, plus row 2 with `<<-` and row 7 with a backtick in place of `$(`. Rows 1 to 5, 8 to 12, 15, 16, 26, 30 and 31 and the `<<-` row carry `min_bash: "3.2"` and `max_bash: "3.2"`. Rows 9 and 10 are in that bucket because their inner shell is `/bin/bash`, which is 3.2 only on macOS; on a 5.x `/bin/bash` they run nothing. Rows 6, 7, 13, 14, 17 to 25, 27 and 28 and the backtick row carry `min_bash: "3.2"` and no `max_bash`, since they merge on 3.2.57 and 5.3.20. Row 29 carries `min_bash: "5.3"` and no `max_bash`.
  1. **The bypass is real.** Run the row with a harmless `gh` recorder first on `PATH`, under `/bin/bash` and every `bash` on `PATH` whose version is in the row's range. Compare versions as integer `(major, minor)` pairs, so `"3.2"` matches 3.2.57. The recorder must see `pr merge`. If it does not, the test fails and asks for the range to be corrected; bash 4.0 to 5.2 are unprobed, so a failure there is a range to fix, not a reason to drop the row. If no installed bash is in range, this leg is skipped, and the skip message names the row and the version needed. CI runs on `ubuntu-latest`, which has no bash 3.2, so CI skips the 3.2-only legs; Done when 2 is the check that they ran.
  2. **The hook denies it.** The row goes through `main()` with a stdin payload. It must exit 2, and stderr must contain the exact string `heredoc inside a substitution`. That string proves the new rule denied the row and not pr-guard's `--auto` flag rule, which runs after R7 and whose message does not contain it.
- **Tokenizer rows.** For each bypass row, `Parsed.failures` contains a failure at the offset of the `<<` inside the substitution (for row 8, the offset of its first `<`; for rows 9 and 10, a failure carried up from the `Nested` body; for rows 13, 14 and 27 to 29, the offset of the bracket that stays open; for row 30, the offset of the `#`). Other failures may follow it, since R7 denies on any failure.
- **Boundary row.** `cat <<'E' $(echo hi` ⏎ `gh pr merge 1 --auto` ⏎ `E`, whose substitution never closes, runs nothing on either bash. It is denied by clause 2 and goes through `main()`, which must exit 2 with the string. It has no recorder leg. Likewise `x=$(case a in a) cat <<'EOF' ;; esac )` ⏎ `gh pr merge 1 --auto` ⏎ `EOF`, which runs nothing on either bash and is denied by clause 3 at its last `)`.
- **Negatives that must stay allowed.** Each goes through `main()` and must exit 0:
  - `gh pr create --body-file - <<'EOF'` at top level, whose body holds an apostrophe, `(#123)`, a line holding only `)`, double quotes and backticks;
  - `git commit -F - <<'EOF'` at top level, with the same body;
  - `x=$(cat <<<"text")`, a here-string inside a substitution;
  - `x=$(echo "<<"); y=$(echo '<<')`, where `<<` is quoted text, not an operator;
  - `cat <<EOF` ⏎ `a $(echo b) c` ⏎ `EOF`, an unquoted top-level heredoc whose body holds a substitution that opens and closes inside the body;
  - `# see (#12)` ⏎ `gh pr create --body-file - <<'EOF'` ⏎ `text` ⏎ `EOF`, a top-level comment holding a bracket.
- **Stated-cost rows.** `echo $((1<<2))`, `x=$(echo $((1<<2)))` and `x=$(echo ${y//<</z})` go through `main()` and must exit 2 with `heredoc inside a substitution` in stderr, which pins the cost above.

## Affected surfaces

- `pr-merge-flow/scripts/shell_tokens.py` and its byte-identical mirror `review-gate/scripts/shell_tokens.py`, from #139 step 2.
- `pr-merge-flow/tests/test_pr_guard.py` and the `test_shell_tokens.py` pair.
- `pr-merge-flow/SKILL.md`: the rule, its cost, and the top-level heredoc forms as the standard way to pass a body.
- review-gate's `merge-guard.py` gets the rule through the shared module at #139 step 4. Its parity run lists any new denials.
- Vendored copies re-vendor per #139 step 5. Nothing here touches a vendored copy directly.

## Done when

1. #139 step 2 has landed with the rule and the tokenizer rows green.
2. #139 step 3 has landed in pr-guard with the bypass rows and negatives green. Each bypass row's recorder leg runs on at least one runner with a bash in its range, such as macOS `/bin/bash` 3.2 and a Homebrew bash 5.3 for row 29, and that run is recorded on this plan's Tracker row.
3. After the step-3 release is on main, probe rows 1 to 31 are re-run against it. Each exits 2, with `heredoc inside a substitution` in stderr. The result is recorded on this plan's Tracker row with the release commit SHA.

## Follow-up (parked, not in scope)

Parked for #139's owner, out of this plan's earlier draft and its review threads: A1 to A4, meaning the migration-step wording, the character loop and caps, hard constructs outside this rule (`case`, `${`, `$((`, comments in substitutions), the arithmetic name operand (`x='a[$(…)]'; $(( (x) ))`), R9 field splitting including `IFS` and other binding sources, and the child-process timeout for pr-guard's regex checks. Also parked: the earlier probe rows 1 to 17 and 19 to 21, and the [PRGUARD-INTERIM-BACKSTOP](https://app.notion.com/p/PRGUARD-INTERIM-BACKSTOP-interim-block-for-nested-substitution-merges-156-probe-rows-1-7-env-S-4204efecc95a814d85aec336aa6e273b) decision.
