# pr-merge-flow: a merge receipt only after gh confirms MERGED

Status: planned, no code. Plan id: EEA-2. Owner: `pr-merge-flow` (the claude-skills cop); one small dependency on aec (settings registration, rollout step 1). Proposed priority: P2; the PM scheduled task sets the final tier. Tracker: https://app.notion.com/p/EEA-2-plan-merge-receipt-after-gh-confirms-MERGED-idempotent-key-durable-outbox-configurable-sin-4204efecc95a81a4b84be8f6e613f49f

## Incumbent check (read first)

What already covers "tell people a PR merged":

- **`pr-merge-flow` 1.6.0** (`scripts/pr-guard.py`, a PreToolUse hook). It decides whether a merge may *start*: `gh pr merge <n> --squash --match-head-commit <sha>`, no `--auto`, no `--admin`, required checks green. It runs before the command and never sees the result. It has no post-merge step and writes no record of a merge. aec's hook schema has no post-tool event (`GENERIC_EVENTS` in `aec/lib/hooks/schema.py`: `on_file_edit`, `on_file_read`, `pre_tool_use`, `session_start`, `pre_commit`, `pre_push`), so no hook can react to a merge finishing.
- **The cop's `MERGED PR #<n> as <sha>` ping.** Step 4 of the traffic-cop procedure (in the operator's own global config, not this repo) tells the author thread after a merge. It is a chat message the cop writes by hand. Nothing checks that it was sent or that the sha is the one GitHub merged, and nobody outside the thread can read it. A cop that runs out of context or quota between the merge and the message leaves no trace.
- **The program attention view** (PAV, in the org's platform-ops tooling, `scripts/attention.mjs`). It reads an ACK log of one-line events and lists the waits nobody closed. PAV-9 (planned) reports a PR that left the open list as merged, closed or `outcome unknown` by asking GitHub. That is an inference after the fact, not a receipt: it does not record the head, and it does not close the wait.

None of them produces a record, written only after GitHub says MERGED, that a reader other than the merging thread can rely on. This plan adds one as a new script in the skill that owns merging. It changes none of the three above, and it does not rely on the cop remembering to run it (point 5).

## Dedupe (searched 2026-11-22)

- **claude-skills `main`:** no plan, script or issue covers a merge receipt, an outbox, or a post-merge report. `2026-11-22-pr-guard-required-vs-advisory-checks.md` and `pr-guard-shell-parsing-design.md` (#139) cover what the guard lets *start*.
- **agents-environment-config `staging`:** no receipt or outbox plan.
- **Platform-ops issues and the PAV plan** (`plans/2026-11-20-program-attention-view.md`, PAV-8 to PAV-12):
  - PAV-9 derives merged/closed/unknown for departed PRs.
  - PAV-11 has NevarPlan publish a `merged[]` list `{pr_url, merge_commit, merged_at}` labelled OBSERVED, planned and unpublished.
  - PAV-12 consumes PAV-11.

  None writes a receipt. Receipts here are a source PAV-11/12 can read, not a replacement.

## Related open work

- **#139 (tokenizer-first guard plan)** rewrites how `pr-guard.py` reads shell commands. This plan does not touch `pr-guard.py` or parse shell commands, so it neither waits on #139 nor conflicts with it.
- **#131 and #132** (guard changes, held under MATT-120) were cut at 1.5.5 while `main` is at 1.6.0, so they need a rebase and a new version regardless. This plan ships as **1.7.0** in new files (`scripts/merge-receipt.py`, its tests, a `SKILL.md` section) plus the lockstep version fields. Whichever lands second takes the next minor; the only shared hunks are the version fields and `SKILL.md`.

## Design

### 1. One record per merged PR, written only after GitHub confirms

- **Record:** one JSON file per merged PR, `<state dir>/prs/<owner__repo lowercased>__<n>.json`, where the state dir is `${XDG_STATE_HOME:-~/.local/state}/pr-merge-flow/`.
  - It holds `ref` (GitHub's case), `url`, `head`, `merge_commit`, `merged_at`, `base`, `source` (`report`, `preflight` or `reconcile`, whichever first confirmed it), `first_seen`, and `deliveries`. Each delivery has a status (`queued` or `done`), `attempts` and `last_error`.
  - A record exists only for a PR GitHub reports as MERGED. There is no "pending" record: a run that cannot confirm a merge writes nothing and exits 11, and the next `reconcile` finds the merge in GitHub's listing whenever it happens (point 5). So nothing ever needs to be expired.
- **Receipt key:** `merge-receipt:v1:<owner/repo lowercased>#<n>:<merge_commit>`. One merged PR has one merge commit, so every run on every machine computes the same key.
- **Locking:** one exclusive `fcntl.flock` per PR, on `<record>.lock`, taken before reading or writing that PR's record, with a re-read after the lock. Two runs on one machine never race on a PR. Across machines, delivery is **at least once, deduplicated best-effort** at the sink (point 4), and the plan claims no more than that.
- **Writes:** temp file, `fsync`, `rename`, then `fsync` of the directory. A lock file is removed with its record.
- **Retention:** a record whose deliveries are all done is deleted 30 days after its last change. The sink is the durable record; the state dir is a queue.

### 2. Exit codes, one table for every subcommand

Codes stay clear of 1 (Python's uncaught-exception exit) and 2 (argparse's usage exit), so a crash or a typo never reads as an outcome. `main()` catches every exception and exits 19; `ArgumentParser.error` is overridden to exit 18.

| code | `report` | `preflight` | `reconcile` | `audit` | `status` |
|---|---|---|---|---|---|
| 0 | merged at the given head; recorded; every delivery done | merged at the given head; recorded; nothing delivered | every listed merge recorded and delivered | at or under the limit | healthy |
| 10 | merged at the given head; recorded; a delivery queued | n/a | a delivery queued | n/a | n/a |
| 11 | not confirmed: gh error, still OPEN after the re-reads, or no merge commit yet; nothing recorded | not confirmed; nothing recorded | a gh read failed; that repo's watermark not advanced | a gh or sink read failed | n/a |
| 12 | CLOSED unmerged | OPEN, or CLOSED unmerged | n/a | n/a | n/a |
| 13 | merged at a different head; both shas printed; nothing recorded | same | n/a | n/a | n/a |
| 14 | config error | config error | config error | config error | config error |
| 15 | n/a | n/a | n/a | over the limit, or not measurable | heartbeat stale, or a delivery queued for over a day |
| 18 | usage error | usage error | usage error | usage error | usage error |
| 19 | internal error, outcome unknown | same | same | same | same |

- **Config errors (14):** corrupt `preferences.json`, an unknown value, a missing target for `jsonl` or `github-issue`, or `ackline` with any sink other than `github-issue`.
- **`reconcile` precedence:** it handles many PRs and exits with the highest-precedence code it saw, in the order 19, 14, 11, 10, 0.
- **Sink `none`:** a delivery is done once the receipt is recorded, so `none` never leaves anything queued.
- **13 under `report`:** this means the cop's `--match-head-commit` sha is not what GitHub merged. `report` records nothing. `reconcile` later records the merge as `source: reconcile`, which attests only that GitHub says it merged, and `audit` counts it in the reconcile share.
- **No exit code means "merge again".** The script has no code path that calls `gh pr merge`. `SKILL.md` states, in a line of its own, that none of these codes is grounds to rerun a merge: GitHub is the record of the merge, and the receipt only reports it.

### 3. `report` and `preflight`: confirm, then record

`merge-receipt.py report <owner/repo#n> --head <sha>` asks GitHub:

```
gh pr view <n> -R <owner/repo> --json number,url,state,headRefOid,baseRefName,mergeCommit,mergedAt
```

It records the PR only when three things hold:
- `state == "MERGED"`;
- `headRefOid == <sha>`, the head the cop passed to `--match-head-commit`;
- `mergeCommit.oid` is a 40-hex sha.

It then delivers (point 4) and prints the `plain` receipt line, which the cop's own ping can quote.

The cop runs `report` right after its merge command returns, so GitHub may lag: the PR can still read OPEN (a merge queue, a slow read), or MERGED with no merge commit yet. `report` re-reads up to 3 times over about 10 s. If it still cannot confirm, it exits 11 and writes nothing. It exits 12 only when GitHub says CLOSED.

`merge-receipt.py preflight <owner/repo#n> --head <sha>` is for a thread about to open a HANDOFF or keep waiting. It reads the PR once and, on a confirmed merge, records it as `report` would, but delivers nothing.
- On 0, the caller sends the printed receipt instead of opening a wait.
- On 12 or 11, the caller opens the wait as today: a failed lookup never means merged.
- On 13, the caller must not report its own head as merged.

The head check belongs to the call: a stale `--head` only changes that call's exit code and never blocks a later receipt.

**Refs:** the ref is parsed from `owner/repo#n` or a PR URL; a bare `#n` needs `-R`; anything else exits 18. Keys lowercase `owner/repo`, so two spellings give one record. A `plain` line prints GitHub's case. An `ackline` post copies each wait's own ref string (point 4).

### 4. Line formats, sinks, dedupe

**`plain` (default):** `merged <ref> head <head> as <merge_commit> into <base> at <merged_at> via <source>`. A comment or file entry that carries it also carries the receipt key on a second line. The default carries no org's protocol.

**`ackline`** is a preset for a team that tracks waits as one-line events in a GitHub issue. `SKILL.md` documents the protocol it reads:
- A first line `<KIND> <owner/repo#n> | from=<a> | to=<b> | <detail> | <HH:MM>Z`.
- `ACK` and `HANDOFF` open a wait on (ref, {from, to}); `DONE` and `LANDED` close it; the latest event per wait wins.

It requires the `github-issue` sink (otherwise exit 14).

**`ackline` delivery:** for a merged PR, the run takes every wait on that ref (matched case-insensitively) and applies two tests:
- the wait was **open at merge time**: its latest event with `created_at <= mergedAt` is `ACK` or `HANDOFF`;
- the wait has **no event after the merge**.

For each wait that passes both, it posts one comment. The comment's first line is `LANDED <that wait's exact ref> | from=<a> | to=<b> | merged <head> as <merge_commit> via <source> | <HH:MM>Z`, with the time taken from `mergedAt` in UTC. Its second line is the receipt key.
- That rule is the dedupe. A `LANDED` already posted is an event after the merge, so the wait is not posted again. Two machines racing post at most a duplicate `LANDED` on a wait that is already closed, and that changes nothing.
- A wait **opened after the merge** (a HANDOFF to whoever checks the deploy, say) is about post-merge work. It is not the receipt's to close, so it is never closed.
- A merged PR with no wait open at merge time gets no post. Nothing is written to the issue that the parser cannot read.
- `shortcut:` this re-implements the protocol's line rules in Python. Rollout step 4 adds a test, in the parser owner's repo, that runs both parsers on the same fixtures.

| sink | delivers to | dedupe |
|---|---|---|
| `none` (default) | the state dir only | n/a |
| `jsonl` | appends one object: `key`, `ref`, `url`, `head`, `merge_commit`, `merged_at`, `base`, `source`, `delivered_at` | an existing object with the same `key` |
| `github-issue` | `gh issue comment` on the target `owner/repo#n` | `plain`: a comment whose second line equals the receipt key exactly, so a comment that only quotes a receipt does not count. `ackline`: the rule above |

**Reading the sink:** each run reads the whole sink once, a file read or `gh api --paginate` over the issue's comments, as the attention view itself does. It holds the result in memory and adds each new post to it. A `since=` filter would hide the HANDOFF that opened a wait, so none is used. `shortcut: O(comments) per run; past ~10k comments, page by created_at and cache the older pages.`

**Delivery:** up to 3 attempts per delivery per run (1 s and 4 s backoff), each with a timeout. A failure leaves the delivery `queued` with `attempts` and `last_error`.

**No `command` sink.** A command target that an org overlay could set would run on every developer's machine. A write-only sink also cannot be audited. A user who wants chat can read the `jsonl` file.

### 5. `reconcile`: receipts and closed waits without relying on the cop

The failure this plan exists for is a cop that stops between the merge and the message. That cop never runs `report` either. `merge-receipt.py reconcile -R <owner/repo>[=<adopted ISO timestamp>] [-R ...]` runs on a schedule, and `SKILL.md` gives a cron or launchd line, as `prune-merged-worktrees.sh` does. It is not a `session_start` hook, because a gh listing per repo at every session start is too slow.

1. **List merges into every base.** There is no `--base` filter: feature PRs into `staging` and promotions into `main` both count.

   ```
   gh pr list -R <repo> --state merged --search "merged:<A>..<B>" --limit 1000 --json number,url,headRefOid,baseRefName,mergeCommit,mergedAt
   ```

   If a window returns 1000 rows, it is split in half by time and both halves are listed. GitHub's search sorts by creation date, so only covering windows are sound.
2. **The window.** `A` is the earlier of the repo's watermark and now minus 24 h; `B` is now.
   - The 24 h lookback re-lists recent merges on every run, so a merge that search indexed late is still found, and dedupe makes re-listing harmless.
   - The watermark is stored per repo in `<state dir>/watermarks.json`. It is the earliest `mergedAt` among records with a queued delivery, or else `B` of the last run that listed the repo without error.
   - The first run for a repo needs `=<adopted ISO timestamp>` and starts there; later runs use the watermark. There is no backfill before adoption.
3. **Record and deliver.** A merged PR with no record is recorded with `source: reconcile`. Then every queued or due delivery is attempted. Under `ackline`, every listed PR is re-checked against the sink, so a wait the last run missed is closed now.
4. **Heartbeat.** A run that finishes writes `last_reconcile_at`.

`merge-receipt.py status` is local only. It prints:
- the queued deliveries, with their attempts and last error;
- the age of the newest record;
- `last_reconcile_at`.

It exits 15 when the heartbeat is older than twice `merge_receipt_interval_min`, or a delivery has been queued for over a day. A machine that runs `reconcile` can alarm on it.

### 6. Settings, kept out of the org overlay

The skill is public: nothing in it names an org, a person, an issue number or a chat tool. Settings follow `pr_open_mode`, as flat scalar keys in `~/.agents-environment-config/preferences.json` → `settings`:

| key | type | default |
|---|---|---|
| `merge_receipt_sink` | `enum[none,jsonl,github-issue]` | `none` |
| `merge_receipt_target` | string: a path or `owner/repo#n` | empty |
| `merge_receipt_format` | `enum[plain,ackline]` | `plain` |
| `merge_receipt_interval_min` | int | `15` |

- All four go in aec's `KNOWN_PREFERENCE_KEYS` (`aec/lib/preferences.py`).
- The org overlay's `PREFERENCES_ALLOW_LIST` (`aec/lib/org_config/allow_lists.py`) gets only `merge_receipt_sink` and `merge_receipt_format`. That list holds only `bool`, `enum[...]`, `int[...]` and path tags.
- `merge_receipt_target` is a free string, set by the user only, and goes in `PREFERENCES_EXCLUDED_KEYS`. An overlay cannot point every machine's receipts somewhere.
- The script parses `preferences.json` itself, not through aec's `load_preferences`, which falls back to defaults on bad JSON. A user who configured a sink must not believe receipts are delivered when they are not, so any config error exits 14 and names the key.
- `--sink`, `--target` and `--format` override the settings for one run.
- A team that uses an ACK-log issue sets `github-issue`, its own issue and `ackline` in its own preferences. None of those values appears in the skill.

### 7. Audit, and how success is measured

`merge-receipt.py audit -R <owner/repo>=<adopted ISO timestamp> [-R ...] [--until <ts>]` uses the same covering listing as `reconcile`, over every base. It reads only GitHub and the sink, never the local state dir, so an auditor on any machine gets the same answer.

- **The window:** for each repo, from its adoption timestamp to `--until`. The default is now minus twice `merge_receipt_interval_min`, so a merge in the last few minutes is not yet counted as missing.
- **The unit, `plain` or `jsonl`:** each merged PR. It is delivered when the sink holds its receipt key, and missing otherwise.
- **The unit, `ackline`:** each wait that was open at merge time on a merged PR (point 4). It is closed when it has an event after the merge, and missing otherwise. A PR with no such wait contributes nothing: there was nothing to close.
- **Reported:**
  - the counts;
  - the refs of every missing unit;
  - the p95 time from `mergedAt` to the sink's timestamp (the comment's `created_at` or the object's `delivered_at`);
  - the share of receipts whose `source` is `reconcile`, which measures merges that bypassed `report`.
- **Not measurable:** it exits 15 with `not measurable` for the `none` sink, or with fewer than 20 units across all `-R` pairs. 5% of a handful is zero.

**Success measure:** across all adopted repos, at most 5% of units in each repo's first 3 days after its adoption timestamp are missing. The Engineering Effectiveness Auditor runs it 3 days after the last repo's adoption timestamp. It records the result, the p95 latency and the reconcile share on the Tracker row. Below 20 units, the window extends a day at a time until there are 20.

## Rollout

1. **aec settings** (owner: aec, a separate PR in agents-environment-config). Register the four keys as in point 6:
   - all four in `KNOWN_PREFERENCE_KEYS`;
   - sink and format in `PREFERENCES_ALLOW_LIST`, with no `install.settings.*` prompt forms, because no prompt sets them;
   - target in `PREFERENCES_EXCLUDED_KEYS`.
2. **Script and tests** (pr-merge-flow 1.7.0). `scripts/merge-receipt.py` uses the standard library plus `gh`, with `report`, `preflight`, `reconcile`, `audit` and `status`. Tests run the real script against a fake `gh` on `PATH`, a small script returning recorded JSON, since GitHub is third-party, with a temp `XDG_STATE_HOME`. Cases:
   - **Recording and delivery:**
     - MERGED at the right head records once and delivers once; two runs, or two concurrent runs, deliver once.
     - OPEN, CLOSED, a different head, a gh failure, and MERGED with a null merge commit each give their table code and record nothing. OPEN-then-MERGED across the re-reads gives 0.
     - A stale `preflight --head` (13) does not stop a later `report` or `reconcile` receipt.
     - A sink that fails twice then succeeds delivers on the third attempt. One that always fails exits 10, `reconcile` later delivers it, and `status` exits 15 after a day.
     - A process killed between the record write and delivery leaves a queued delivery that `reconcile` delivers once.
   - **`ackline`:**
     - It posts one `LANDED` per wait open at merge time, copying that wait's exact ref and endpoints. A HANDOFF dated before the merge is found even when the record is newer.
     - It posts nothing for a PR with no such wait, and nothing for a wait opened after the merge.
     - It posts nothing again once a `LANDED` exists, and it never posts a `plain` line.
     - `ackline` with a `jsonl` sink exits 14.
   - **`reconcile`:**
     - It lists merges into `staging` and `main`, and splits a 1000-row window.
     - A merge that appears in the listing only on the next run, within the 24 h lookback, is still recorded.
     - A first run without `=<timestamp>` exits 14.
   - **Sink dedupe:** a comment that only quotes a receipt does not count as one.
   - **`audit`:**
     - Run on a second state dir, it gives the same counts as on the first.
     - It exits 15 below 20 units.
   - **Exit codes:**
     - Corrupt `preferences.json` exits 14.
     - A raised exception exits 19.
     - A usage error exits 18.
   - **No merges:** the fake `gh` fails the test if it is ever called with `merge`.
   - **Validation:** one real `gh pr view --json …` and one real `gh pr list --search merged:…` of claude-skills are recorded, so the fake's shape is checked against GitHub.

   Versions are bumped in `SKILL.md`, `hooks.json` and `skills-manifest.json`. `hooks.json` gets only the lockstep version bump, with no hook changes.
3. **Docs.** A `SKILL.md` section covers:
   - when the cop runs `report`, and when an author runs `preflight`;
   - the `reconcile` and `status` schedule lines;
   - the settings;
   - the `ackline` protocol;
   - what each exit code means;
   - the line saying that no exit code means merge again.
4. **Confirm with the attention view's parser owner before step 5.** This plan adds no token. Two questions:
   1. Is `LANDED`, not `DONE` and not a new `MERGED` kind, the right close for "merged"? `MERGED` is not a parser token today: `OPENS` is `ACK`/`HANDOFF` and `CLOSES` is `DONE`/`LANDED`. A `MERGED PR #…` line therefore lands in `unparsed`, and today's cop ping closes nothing in the view.
   2. Is the `|` format current? The parser reads only the `|` format with `owner/repo#n` refs (PAV-6). The platform-ops README, the single source for the ACK protocol, still documents the `·` format (`<KIND> <ref> · from … · to … · <detail> · <HH:MMZ>`, ref `PR #<n>`), and lines in that format land in `unparsed`.

   The view's repo adds one test that feeds shared fixtures through both its exported `parseLine`/`openWaits` and the `ackline` preset's parser. That test belongs to the parser's owner and is not copied into this public skill.
5. **Adoption (outside this repo).**
   - The cop procedure's post-merge step runs `report` and quotes the receipt.
   - Each adopted repo gets a `reconcile` schedule, started with `=<adopted timestamp>`, and the timestamp is recorded on the Tracker row.
   - Authors run `preflight` before a HANDOFF.
6. **Measure.** The Engineering Effectiveness Auditor runs `audit` as in point 7.

## Out of scope

- Changing `pr-guard.py`, or blocking a merge on a receipt. The receipt reports; it never gates.
- Adding a token to the parser or editing the platform-ops README. That is the parser owner's call (rollout step 4).
- Closing waits opened after a merge.
- Posting to any chat system, and a command sink (point 4).
- Receipts for PRs merged before a repo's adoption timestamp.
