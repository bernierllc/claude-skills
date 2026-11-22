# pr-merge-flow: a merge receipt only after gh confirms MERGED

Status: planned, no code. Plan id: EEA-2. Owner: `pr-merge-flow` (the claude-skills cop); one small dependency on aec (settings registration, rollout step 1). Proposed priority: P2; the PM scheduled task sets the final tier. Tracker: https://app.notion.com/p/EEA-2-plan-merge-receipt-after-gh-confirms-MERGED-idempotent-key-durable-outbox-configurable-sin-4204efecc95a81a4b84be8f6e613f49f

## Incumbent check (read first)

What already covers "tell people a PR merged":

- **`pr-merge-flow` 1.6.0** (`scripts/pr-guard.py`, a PreToolUse hook). It decides whether a merge may *start*: `gh pr merge <n> --squash --match-head-commit <sha>`, no `--auto`, no `--admin`, required checks green. It runs before the command and never sees the result. It has no post-merge step and writes no record of a merge. aec's hook schema has no post-tool event (`GENERIC_EVENTS` in `aec/lib/hooks/schema.py`: `on_file_edit`, `on_file_read`, `pre_tool_use`, `session_start`, `pre_commit`, `pre_push`), so a hook cannot react to a merge finishing.
- **The cop's `MERGED PR #<n> as <sha>` ping.** Step 4 of the traffic-cop procedure (in the operator's own global config, not this repo) tells the author thread after a merge. It is a chat message the cop writes by hand. Nothing checks that it was sent or that the sha is the one GitHub merged, and nobody outside the thread can read it. A cop that runs out of context or quota between the merge and the message leaves no trace.
- **The program attention view** (PAV, in the org's platform-ops tooling, `scripts/attention.mjs`). It reads an ACK log of one-line events and lists the waits nobody closed. PAV-9 (planned) reports a PR that left the open list as merged, closed or `outcome unknown` by asking GitHub. That is an inference after the fact, not a receipt: it does not record the head, and it does not close the wait.

None of them produces a record, written only after GitHub says MERGED, that a reader other than the merging thread can rely on. This plan adds that as a new script in the skill that owns merging. It changes none of the three above, and it does not rely on the cop remembering to run it (point 5).

## Dedupe (searched 2026-11-22)

- **claude-skills `main`:** no plan, script or issue covers a merge receipt, an outbox, or a post-merge report. `2026-11-22-pr-guard-required-vs-advisory-checks.md` and `pr-guard-shell-parsing-design.md` (#139) are about what the guard lets *start*.
- **agents-environment-config `staging`:** no receipt or outbox plan.
- **Platform-ops issues and the PAV plan** (`plans/2026-11-20-program-attention-view.md`, PAV-8 to PAV-12): PAV-9 derives merged/closed/unknown for departed PRs; PAV-11 has NevarPlan publish a `merged[]` list `{pr_url, merge_commit, merged_at}` labelled OBSERVED, planned and unpublished; PAV-12 consumes PAV-11. None writes a receipt. Receipts here are a source PAV-11/12 can read, not a replacement.

## Related open work

- **#139 (tokenizer-first guard plan)** rewrites how `pr-guard.py` reads shell commands. This plan does not touch `pr-guard.py` or parse shell commands, so it neither waits on #139 nor conflicts with it.
- **#131 and #132** (guard changes, held under MATT-120) were cut at 1.5.5 while `main` is at 1.6.0, so they need a rebase and a new version regardless. This plan ships as **1.7.0** in new files (`scripts/merge-receipt.py`, its tests, a `SKILL.md` section) plus the lockstep version fields. Whichever lands second takes the next minor; the only shared hunks are the version fields and `SKILL.md`.

## Design

### 1. Exit codes, one table for every subcommand

Codes stay clear of 1 (Python's uncaught-exception exit) and 2 (argparse's usage exit), so a crash or a typo can never read as an outcome. `main()` catches every exception and exits 19; `ArgumentParser.error` is overridden to exit 18.

| code | meaning | `report` | `preflight` | `reconcile` | `audit` |
|---|---|---|---|---|---|
| 0 | merged at the expected head, receipt delivered (preflight: receipt in the outbox) | yes | yes | all delivered | at or under the limit |
| 10 | merged at the expected head, receipt written, delivery queued | yes | n/a (preflight never delivers) | some queued | n/a |
| 11 | could not confirm (gh error, still OPEN after a merge, merge commit not yet set); a confirm job is queued, no receipt | yes | yes | some unconfirmed | n/a |
| 12 | not merged (OPEN, or CLOSED unmerged) | yes | yes | n/a | n/a |
| 13 | merged at a **different** head; no receipt, both shas printed | yes | yes | some mismatched | n/a |
| 14 | config error (unknown sink, format needs `--from`/`--to`, unreadable settings) | yes | yes | yes | yes |
| 15 | over the missing-receipt limit, or not measurable | n/a | n/a | n/a | yes |
| 18 | usage error | yes | yes | yes | yes |
| 19 | internal error, outcome unknown | yes | yes | yes | yes |

**No code means "merge again".** The script has no code path that calls `gh pr merge`, and `SKILL.md` says in its own line that none of these codes is grounds to rerun a merge: GitHub is the record of the merge, the receipt only reports it.

### 2. `report`: a receipt only after GitHub reports MERGED

`merge-receipt.py report <owner/repo#n> --head <sha> [--from X --to Y] [--ref-as S]` asks GitHub:

```
gh pr view <n> -R <owner/repo> --json number,url,state,headRefOid,mergeCommit,mergedAt
```

and writes a receipt only when `state == "MERGED"`, `headRefOid == <sha>` (the head the cop passed to `--match-head-commit`) and `mergeCommit.oid` is a 40-hex sha.

The cop runs it right after its merge command returns, so GitHub may lag: still OPEN (a merge queue, a slow read) or MERGED with no merge commit yet. `report` re-reads up to 3 times over about 10 s. If it still cannot confirm, it exits 11 and queues a confirm job (point 4); it never exits 12 for a PR it was told was just merged unless GitHub says CLOSED.

**Refs and case.** The ref is parsed from `owner/repo#n` or a PR URL; a bare `#n` needs `-R`; anything else exits 18. The idempotency key (point 4) lowercases `owner/repo`, so two spellings make one receipt. The printed ref keeps GitHub's own case (`nameWithOwner` from the PR URL), because readers may match it exactly. The attention view's wait key is case-sensitive (`${e.ref} ${[from, to].sort()}`, attention.mjs:69), so `--ref-as` lets the caller print the exact string the HANDOFF used.

### 3. `preflight`: return an existing receipt instead of opening a wait

`merge-receipt.py preflight <owner/repo#n> --head <sha>` is for a thread about to open a HANDOFF or keep waiting on a merge. It reads the PR once and never delivers:

- 0: merged at that head. The receipt is written to the outbox if missing, and printed. The caller sends the receipt instead of opening a wait; `reconcile` (point 5) delivers it.
- 12: OPEN, open the wait; or CLOSED unmerged.
- 13: merged at a different head; the caller must not report its own head as merged.
- 11: could not confirm; the caller opens the wait as it would today (a failed lookup never means merged).

### 4. Idempotent key, outbox, locking, bounded retry

- **Receipt key:** `merge-receipt:v1:<owner/repo lowercased>#<n>:<merge_commit>`. One merged PR has one merge commit, so every run from every thread produces the same key.
- **Confirm-job key:** `merge-confirm:v1:<owner/repo lowercased>#<n>:<head>`. A job exists only before the merge commit is known. It stops at 20 attempts or 7 days. After that it is `expired`, reported by `audit` and never retried again. A job that confirms becomes a receipt and is removed. One that finds CLOSED or a different head is closed as `not-merged` or `mismatch`.
- **Outbox:** one JSON file per key under `${XDG_STATE_HOME:-~/.local/state}/pr-merge-flow/outbox/` (receipts) and `.../confirm/` (jobs), written atomically (temp file, `fsync`, `rename`) *before* any delivery. Fields: key, ref, printed ref, url, head, merge_commit, merged_at, from, to, created_at, attempts, last_error, delivered_at, state.
- **Locking:** every subcommand takes an exclusive `fcntl.flock` on the key's lock file before it reads, delivers or updates that key, and re-reads the file after the lock. Two runs on one machine therefore deliver once. Runs on two machines can both post; delivery is **at least once, deduplicated best-effort** at the sink (next bullet), and the plan says no more than that.
- **Sink dedupe:** a readable sink is searched before posting. For `github-issue`, every comment is read with `gh api --paginate`, and only a comment whose second line equals the key exactly counts as a hit, so a comment that quotes a receipt does not. For `jsonl`, the key field is matched. A hit marks the receipt delivered without posting. A `command` sink gets the key in `MERGE_RECEIPT_KEY` and dedupes itself.
- **Retry:** up to 3 delivery attempts per run (1 s, 4 s backoff), each with a timeout. A failure leaves the receipt queued with `attempts` and `last_error` and exits 10. The script never sleeps waiting on a sink beyond that.
- **Never a false Done:** a receipt exists only after point 2's three checks pass. Only exit 0 means delivered.

### 5. `reconcile`: receipts do not depend on the cop remembering

The failure this plan exists for is a cop that stops between the merge and the message. That cop never runs `report` either, so delivering only what `report` queued would not help. `merge-receipt.py reconcile -R <owner/repo> [-R ...] [--since <date>]`:

1. Lists PRs merged into each repo's default branch since a per-repo watermark (first run: `--since`). It pages with `gh pr list --state merged --base <default> --search "merged:>=<date>" --limit 1000 --json number,url,headRefOid,mergeCommit,mergedAt`. If the result hits the limit, it narrows the window and repeats, so the list is never cut silently.
2. Writes a receipt for every merged PR that has none, at its actual head. A cop's `report` call is then an early copy, not the only one.
3. Runs every open confirm job and delivers every queued receipt.
4. Advances the watermark only past PRs it fully handled.

It runs on a schedule: `SKILL.md` gives a cron or launchd line, as `prune-merged-worktrees.sh` does. A `session_start` hook is not used, because a gh listing per repo at every session start is too slow.

**What a reconciled receipt can close.** It has no `--from`/`--to`, because nothing outside the cop knows which threads were waiting. A sink whose format needs them (the `pav` format, point 6) records it as `delivered-plain`: the receipt exists and `audit` counts it, but it does not close a wait. Closing those waits needs one of two things, asked in point 6: a parser rule, or the HANDOFF's endpoints recorded at hand-off time.

### 6. Line format: neutral by default, the attention-view format as a preset

The script prints one thing: the receipt, which is two lines, a first line in the chosen format and then the key line. It does not print the cop's chat ping. The operator's procedure can quote the receipt.

- **`plain` (default):** `merged <ref> head <head> as <merge_commit> at <merged_at>`. No org's protocol is in the default.
- **`pav` (preset for the program attention view):** `LANDED <ref> | from=<from> | to=<to> | merged <head> as <merge_commit> | <HH:MM>Z`. The time is GitHub's `mergedAt` in UTC, not the post time. `report` and `preflight` refuse this format without both `--from` and `--to` and exit 14, because `parseLine` returns null for a line missing either field.

What the parser accepts, read on its `main` and `staging` 2026-11-22:

- `OPENS = ["ACK", "HANDOFF"]` open a wait.
- `CLOSES = ["DONE", "LANDED"]` close one.
- Any other kind parses but does nothing.
- **`MERGED` is not a token.** A line starting `MERGED PR #…` lands in `unparsed`, so today's cop ping closes nothing in the view.

A wait's key is the exact ref plus the sorted `{from, to}` pair. So a `pav` receipt closes the author's `HANDOFF` to the cop only if the ref and both endpoints match that HANDOFF character for character, which is why `--ref-as` exists.

Three questions for the Program Cop's author. This plan settles none of them and adds no token:

1. Is `LANDED` (not `DONE`, and not a new `MERGED` kind) the right close for "merged"?
2. Which line format is current? The parser reads only the `|` format with `owner/repo#n` refs (PAV-6). The platform-ops README, the single source for the ACK protocol, still documents the `·` format (`<KIND> <ref> · from … · to … · <detail> · <HH:MMZ>`, kinds ACK, BLOCKED, DONE, ASK, GO, FYI, ref `PR #<n>`), and lines in it land in `unparsed`.
3. Should a `LANDED` for a ref close every open wait on that ref whatever its endpoints, so reconciled receipts (point 5) close waits too? Or should the HANDOFF record its endpoints somewhere the receipt can read?

### 7. A generic skill: settings, not hard-coded targets

The skill is public: nothing in it names an org, a person, an issue number or a chat tool. Settings follow `pr_open_mode`: flat scalar keys in `~/.agents-environment-config/preferences.json` → `settings`, which is the shape aec's preference lists accept (`KNOWN_PREFERENCE_KEYS` in `aec/lib/preferences.py`, `PREFERENCES_ALLOW_LIST` in `aec/lib/org_config/allow_lists.py`):

| key | type | default |
|---|---|---|
| `merge_receipt_sink` | `enum[none,jsonl,github-issue,command]` | `none` |
| `merge_receipt_target` | string: a path, `owner/repo#n`, or a command | empty |
| `merge_receipt_format` | `enum[plain,pav]` | `plain` |

How each sink delivers and dedupes:

| sink | delivers to | dedupe |
|---|---|---|
| `none` | outbox only; the receipt is printed | n/a |
| `jsonl` | appends one JSON object to the target path | key field |
| `github-issue` | `gh issue comment` on the target | second line equals the key |
| `command` | runs the target with the receipt on stdin | the command's job |

- The `jsonl` dedupe is a full scan. `shortcut: O(n) scan per receipt, index by key once a file passes ~10k lines.`
- `--sink`, `--target` and `--format` override the settings for one run.
- A set but unknown or unreadable value exits 14 and names the key. It never falls back to `none` silently, because a user who configured a sink must not believe receipts are delivered when they are not.
- The org that runs the attention view sets `github-issue`, its own ACK-log issue and `pav` in its own preferences. None of those values appears in the skill.

### 8. Audit, and how success is measured

`merge-receipt.py audit -R <owner/repo> --since <date> [--until <date>]` uses the same paged listing as `reconcile`. It reads receipts **from the sink**, not the local outbox, so an auditor on another machine sees what everyone sees. For each merged PR it reports one class: delivered, delivered-plain, queued, missing, mismatch (merged at a head no receipt was written for), or expired confirm. It prints counts and the refs in every class except delivered.

- With sink `none` or `command`, it exits 15 `not measurable: needs a readable sink`.
- Below 20 merged PRs in the window, it prints counts and no rate, and exits 15. 5% of a handful of PRs is zero.

**Success measure.** The window starts on each repo's **adoption date**: the day its cop's procedure first runs `report` and `reconcile` is scheduled for that repo, recorded on the Tracker row. Three days later the Engineering Effectiveness Auditor runs `audit` over every adopted repo for those 3 days, with a readable sink. The target is at most 5% missing, where missing = missing + queued + expired, over all PRs merged into those repos' default branches (in these repos only the cop merges, and `reconcile` covers any that bypass it). Below 20 PRs, the window extends day by day until it has 20.

## Rollout

1. **aec settings (owner: aec, a separate PR in agents-environment-config).** Register `merge_receipt_sink`, `merge_receipt_target` and `merge_receipt_format` in `KNOWN_PREFERENCE_KEYS` and `PREFERENCES_ALLOW_LIST` (and the `install.settings.` form), with the types above. Without this, the script still reads the keys, but aec does not know them.
2. **Script and tests (pr-merge-flow 1.7.0).** `scripts/merge-receipt.py` (standard library plus `gh`) with `report`, `preflight`, `reconcile` and `audit`. Tests run the real script against a fake `gh` on `PATH`, a small script that returns recorded JSON, since GitHub is third-party. They use a temp `XDG_STATE_HOME`. Cases:
   - MERGED at the right head writes one receipt; two runs write one and deliver once; two concurrent runs deliver once (the lock).
   - OPEN, CLOSED, a head mismatch, a gh failure and MERGED with a null merge commit each give the exit code in the table and no receipt. OPEN-then-MERGED across the re-reads gives 0.
   - A sink that fails twice then succeeds delivers on the third attempt; one that always fails exits 10; `reconcile` then delivers it.
   - A process killed between the outbox write and delivery leaves a file that `reconcile` delivers once.
   - `reconcile` writes receipts for merged PRs that `report` never saw, pages past the limit, and expires a confirm job after its cap.
   - Dedupe ignores a comment that only quotes a receipt.
   - `pav` without `--from`/`--to` exits 14. A raised exception exits 19, a usage error 18.
   - The fake `gh` fails the test if it is ever called with `merge`.
   - A validation test records one real `gh pr view --json …` of a merged claude-skills PR, so the fake's shape is checked against GitHub.

   Versions are bumped in `SKILL.md`, `hooks.json` and `skills-manifest.json`. `hooks.json` gets only the lockstep version bump: no hook changes.
3. **Docs.** A `SKILL.md` section covering:
   - when the cop runs `report`, and when an author runs `preflight`;
   - the `reconcile` schedule line;
   - the settings, and what each exit code means;
   - the rule that no exit code means merge again.
4. **Confirm the three questions** (point 6) with the Program Cop's author before step 5. The org adds a fixture test in the attention view's own repo that feeds a HANDOFF then a `pav` receipt through the real `parseLine` and open-wait logic. That test belongs to the parser's owner, so it is not copied into this public skill.
5. **Adoption (outside this repo).** The cop procedure's post-merge step runs `report --from … --to …` and quotes the receipt. Each adopted repo gets a `reconcile` schedule and records its adoption date on the Tracker row. Authors run `preflight` before a HANDOFF.
6. **Measure.** EEA runs `audit` 3 days after each repo's adoption date (point 8) and records the rate on the Tracker row.

## Out of scope

- Changing `pr-guard.py`, or blocking a merge on a receipt. The receipt reports; it never gates.
- Adding a token to the parser or editing the platform-ops README. That is the parser owner's call (point 6).
- Posting to any chat system. The `command` sink lets a user wire one.
- Backfilling receipts for PRs merged before a repo's adoption date.
