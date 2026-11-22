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

### 1. One record per PR, one delivery per wait

- **Merge record:** one JSON file per PR, `<state dir>/prs/<owner__repo lowercased>__<n>.json`, where the state dir is `${XDG_STATE_HOME:-~/.local/state}/pr-merge-flow/`.
  - It holds `ref` (GitHub's case), `url`, `expected_head` (from `report`/`preflight`, absent when only `reconcile` saw the PR), `head`, `merge_commit`, `merged_at`, `base`, `source` (`report` or `reconcile`, whichever first confirmed it), `state`, `first_seen`, `deliveries`.
  - `state` is one of `pending`, `merged`, `mismatch`, `closed` or `expired`. `pending` means not yet confirmed; it replaces a separate confirm job.
- **Receipt key** (the merge fact): `merge-receipt:v1:<owner/repo lowercased>#<n>:<merge_commit>`. One merged PR has one merge commit, so every run from every machine agrees on it.
- **Delivery key** (one wait): `<receipt key>|<from>|<to>`, with the endpoints sorted the way the attention view sorts them, or `<receipt key>|-` for a delivery with no endpoints. A PR with two waits (author→cop, cop→tester) gets two deliveries, and an early endpoint-less delivery never suppresses a later one that closes a wait.
- **Locking:** one exclusive `fcntl.flock` per PR, on `<record>.lock`, taken by every subcommand before it reads or writes that PR, with a re-read after the lock. Confirming and delivering for a PR can therefore never race on one machine. Across machines, delivery is **at least once, deduplicated best-effort** at the sink (point 4), and the plan claims no more than that.
- **Writes:** temp file, `fsync`, `rename`, then `fsync` of the directory. Lock files are removed with their record.
- **Retention:** a record whose state is terminal (`merged` with every delivery done, `mismatch`, `closed`, `expired`) is deleted 30 days after its last change. The sink is the durable record; the state dir is a queue.

### 2. Exit codes, one table for every subcommand

Codes stay clear of 1 (Python's uncaught-exception exit) and 2 (argparse's usage exit), so a crash or a typo never reads as an outcome. `main()` catches every exception and exits 19; `ArgumentParser.error` is overridden to exit 18.

| code | `report` | `preflight` | `reconcile` | `audit` |
|---|---|---|---|---|
| 0 | merged at the expected head, every requested delivery done | merged at the expected head; receipt recorded, nothing delivered | every non-terminal PR handled | at or under the limit |
| 10 | merged at the expected head, a delivery queued | n/a | a delivery queued | n/a |
| 11 | not confirmed (gh error, still OPEN after the re-reads, no merge commit yet); PR left `pending` | not confirmed; open the wait as today | a PR still `pending` | n/a |
| 12 | CLOSED unmerged | OPEN (open the wait) or CLOSED unmerged | n/a | n/a |
| 13 | merged at a different head; both shas printed, no receipt | same | n/a (reported by `audit`) | n/a |
| 14 | config error: unknown or unreadable setting, or `pav` without `--from`/`--to` | unknown or unreadable setting | unknown or unreadable setting | unknown or unreadable setting |
| 15 | n/a | n/a | n/a | over the limit, or not measurable |
| 18 | usage error | usage error | usage error | usage error |
| 19 | internal error, outcome unknown | same | same | same |

- `reconcile` handles many PRs. It exits with the highest-precedence code it saw, in the order 19, 14, 11, 10, 0. Terminal states (`mismatch`, `closed`, `expired`, and `no-wait` deliveries) never affect its exit code; `audit` reports them.
- With sink `none`, a delivery is done when the receipt is printed (`report`) or recorded (`reconcile`), so `none` never leaves anything queued.
- **No exit code means "merge again".** The script has no code path that calls `gh pr merge`. `SKILL.md` states, in a line of its own, that none of these codes is grounds to rerun a merge: GitHub is the record of the merge, and the receipt only reports it.

### 3. `report` and `preflight`: confirm, then record

`merge-receipt.py report <owner/repo#n> --head <sha> [--from X --to Y] [--ref-as S]` asks GitHub:

```
gh pr view <n> -R <owner/repo> --json number,url,state,headRefOid,baseRefName,mergeCommit,mergedAt
```

It records the PR as `merged` only when three things hold: `state == "MERGED"`, `headRefOid == <sha>` (the head the cop passed to `--match-head-commit`), and `mergeCommit.oid` is a 40-hex sha. It then delivers.

The cop runs `report` right after its merge command returns, so GitHub may lag: still OPEN (a merge queue, a slow read), or MERGED with no merge commit yet. `report` re-reads up to 3 times over about 10 s. If it still cannot confirm, it leaves the PR `pending` with the expected head and endpoints, and exits 11. It exits 12 only when GitHub says CLOSED.

`merge-receipt.py preflight <owner/repo#n> --head <sha>` is for a thread about to open a HANDOFF or keep waiting. It reads the PR once, records it as `report` would, and delivers nothing.
- On 0, the caller sends the printed receipt instead of opening a wait.
- On 12 or 11, the caller opens the wait as today: a failed lookup never means merged.
- On 13, the caller must not report its own head as merged.

**Refs and case.** The ref is parsed from `owner/repo#n` or a PR URL; a bare `#n` needs `-R`; anything else exits 18. Keys lowercase `owner/repo`, so two spellings give one record. The printed ref keeps GitHub's case. The attention view's wait key is case-sensitive (`${e.ref} ${[e.from, e.to].sort()}`, attention.mjs:69), so `--ref-as` prints the exact string the HANDOFF used.

### 4. Sinks, line formats, dedupe

The script prints the receipt as two lines: a first line in the chosen format, and then a key line, which is the delivery key. It does not print the cop's chat ping, which the operator's procedure can quote from the receipt.

- **`plain` format (default):** `merged <ref> head <head> as <merge_commit> into <base> at <merged_at>`. The default carries no org's protocol.
- **`pav` format (a preset for the program attention view):** `LANDED <ref> | from=<from> | to=<to> | merged <head> as <merge_commit> | <HH:MM>Z`. The time is GitHub's `mergedAt` in UTC. `report` refuses `pav` without both `--from` and `--to` (exit 14), because `parseLine` returns null for a line missing either field.

| sink | delivers to | dedupe |
|---|---|---|
| `none` (default) | the state dir only; the receipt is printed | n/a |
| `jsonl` | appends one JSON object to a path | delivery key field. `shortcut: O(n) scan per run, index by key once a file passes ~10k lines.` |
| `github-issue` | `gh issue comment` on `owner/repo#n` | the key line equals the delivery key exactly, so a comment that only quotes a receipt does not count |

**Reading the sink:** each run reads the sink once, with `gh api --paginate` and `since=` set to the oldest record it is handling. It keeps the delivery keys in memory and adds each new post to that set. So a run over N PRs costs one paged read, not N.

**Delivery:** up to 3 attempts per delivery per run (1 s and 4 s backoff), each with a timeout. A failure leaves the delivery queued with `attempts` and `last_error`.

There is no `command` sink. A command target that an org overlay could set would run on every developer's machine, and a write-only sink cannot be audited. A user who wants chat can read the `jsonl` file.

### 5. `reconcile`: receipts and closed waits without relying on the cop

The failure this plan exists for is a cop that stops between the merge and the message. That cop never runs `report` either. `merge-receipt.py reconcile -R <owner/repo> [-R ...]` runs on a schedule. `SKILL.md` gives a cron or launchd line, as `prune-merged-worktrees.sh` does. It is not a `session_start` hook, because a gh listing per repo at every session start is too slow.

1. **List merges into every base.** No `--base` filter: feature PRs into `staging` and promotions into `main` both count. The listing:

   ```
   gh pr list -R <repo> --state merged --search "merged:<A>..<B>" --limit 1000 --json number,url,headRefOid,baseRefName,mergeCommit,mergedAt
   ```

   If a window returns 1000 rows, it is split in half by `mergedAt` time and both halves are listed. GitHub's search order is by creation date, so only covering windows are sound.

2. **Record each merged PR.** A PR with no record becomes `merged` with `source: reconcile`. For these, the head check is vacuous (the head comes from GitHub itself), so the receipt attests only "GitHub says merged". `audit` reports the share of receipts that come from `reconcile`, which measures merges that bypassed `report`. A `pending` record from `report` is confirmed against its expected head, and becomes `merged` or `mismatch`. A `pending` record older than 7 days, by elapsed time and not attempt count, becomes `expired`.

3. **Close the waits.**
   - Under `pav` with a `github-issue` sink, `reconcile` already holds the issue's comments for dedupe. It parses their first lines with the same rules as the view (kinds, `|` fields, `REF`). For each merged PR, it finds every wait on that ref that the view would list as open: the latest event per ref plus `{from, to}` pair is an `ACK` or `HANDOFF`. It posts one `LANDED` per open wait, copying that wait's exact ref and endpoints.
   - A merged PR with no open wait gets no post: its delivery is `no-wait`, kept only in the state dir. A `plain` line is never posted to a `pav` sink, so nothing lands in the view's unparsed panel (`UNPARSED_SHOWN = 20`).
   - Under `plain`, `reconcile` delivers one endpoint-less receipt per merged PR.
   - `shortcut:` the `pav` preset re-implements the view's line rules in Python. Rollout step 4 adds a test in the view's repo that runs both on the same fixtures, so the two cannot drift silently.

4. **Watermark.** Per repo, in `<state dir>/watermarks.json`: the earliest `mergedAt` among this repo's non-terminal records, or the end of the last listed window when there are none. Terminal records never pin it. The first run for a repo needs `--adopted <ISO timestamp>` and starts there. That is the adoption timestamp in point 6; there is no backfill before it.

5. **Already delivered.** "Already delivered" is read from the sink when it is readable, so a second machine running `reconcile` does not post again. With `none`, it is read from the local state dir.

6. **Heartbeat.** Each run that finishes writes `last_reconcile_at` to the state dir. `audit` reports it, and fails (15) when it is older than twice the configured interval.

### 6. Settings, kept out of the org overlay

The skill is public: nothing in it names an org, a person, an issue number or a chat tool. Settings follow `pr_open_mode`, as flat scalar keys in `~/.agents-environment-config/preferences.json` → `settings`:

| key | type | default |
|---|---|---|
| `merge_receipt_sink` | `enum[none,jsonl,github-issue]` | `none` |
| `merge_receipt_target` | string: a path or `owner/repo#n` | empty |
| `merge_receipt_format` | `enum[plain,pav]` | `plain` |
| `merge_receipt_interval_min` | int | `15` |

- All four go in aec's `KNOWN_PREFERENCE_KEYS` (`aec/lib/preferences.py`).
- Only `merge_receipt_sink` and `merge_receipt_format` go in the org overlay's `PREFERENCES_ALLOW_LIST` (`aec/lib/org_config/allow_lists.py`). That list holds only `bool`, `enum[...]`, `int[...]` and path tags.
- `merge_receipt_target` is a free string. It is user-set only and goes in `PREFERENCES_EXCLUDED_KEYS`, so an overlay cannot point every machine's receipts somewhere.
- The script parses `preferences.json` itself rather than through aec's `load_preferences`, which falls back to defaults on bad JSON. Corrupt JSON, an unknown value, or a missing target for `jsonl`/`github-issue` exits 14 and names the key, because a user who configured a sink must not believe receipts are delivered when they are not.
- `--sink`, `--target` and `--format` override the settings for one run.
- The org that runs the attention view sets `github-issue`, its own ACK-log issue and `pav` in its own preferences. None of those values appears in the skill.

### 7. Audit, and how success is measured

`merge-receipt.py audit -R <owner/repo>=<adopted ISO timestamp> [-R ...] [--until <ts>]` uses the same covering listing as `reconcile`, over every base. It reads deliveries **from the sink**, not the local state dir, so an auditor on another machine sees what everyone sees.

- **The window:** `--until` defaults to now minus twice `merge_receipt_interval_min`, so a PR merged in the last few minutes is not counted as missing.
- **Classes:** each merged PR falls into one class: delivered, `no-wait`, queued, missing, mismatch, or expired. `audit` prints the counts and the refs of every non-delivered class.
- **Wait checks under `pav`:** `audit` also lists every wait on a merged ref that is still open past the window.
- **Latency:** `audit` reports the p95 of `mergedAt` to the sink comment's `created_at`.
- **Origin:** `audit` reports the share of receipts that came from `reconcile`.
- It exits 15 with `not measurable` for the `none` sink, or below 20 merged PRs across all `-R` pairs. 5% of a handful of PRs is zero.

**Success measure:** across all adopted repos, at most 5% of PRs merged in each repo's first 3 days after its adoption timestamp are missing. Missing means missing, queued or expired; `no-wait` counts as delivered, because there was nothing to close. Under `pav`, the target also requires at most 5% of waits on those PRs still open after the window. The Engineering Effectiveness Auditor runs it 3 days after the last repo's adoption timestamp, and records the result, the latency and the reconcile share on the Tracker row. Below 20 PRs, the window extends a day at a time until there are 20.

## Rollout

1. **aec settings** (owner: aec, a separate PR in agents-environment-config). Register the four keys as in point 6:
   - all four in `KNOWN_PREFERENCE_KEYS`;
   - sink and format, with their `install.settings.` forms, in `PREFERENCES_ALLOW_LIST`;
   - target in `PREFERENCES_EXCLUDED_KEYS`.
2. **Script and tests** (pr-merge-flow 1.7.0). `scripts/merge-receipt.py` uses the standard library plus `gh`, with `report`, `preflight`, `reconcile` and `audit`. Tests run the real script against a fake `gh` on `PATH`, a small script returning recorded JSON, since GitHub is third-party, with a temp `XDG_STATE_HOME`. Cases:
   - MERGED at the right head records once and delivers once; two runs, or two concurrent runs, deliver once.
   - OPEN, CLOSED, a head mismatch, a gh failure, and MERGED with a null merge commit each give their table code. OPEN-then-MERGED across the re-reads gives 0.
   - A sink that fails twice then succeeds delivers on the third attempt. One that always fails exits 10, and `reconcile` later delivers it.
   - A process killed between the record write and delivery leaves a record that `reconcile` delivers once.
   - `reconcile` before `report --from A --to B` still lets the cop's `LANDED` post: different delivery keys.
   - `reconcile` under `pav` posts one `LANDED` per open wait, copying its exact ref and endpoints, posts nothing for a PR with no open wait, and never posts a `plain` line.
   - `reconcile` lists merges into `staging` and `main`; splits a 1000-row window; expires a `pending` record at 7 days; keeps the watermark moving past terminal records.
   - Dedupe ignores a comment that only quotes a receipt.
   - Exit codes: `pav` without `--from`/`--to` exits 14, corrupt `preferences.json` exits 14, a raised exception exits 19, a usage error exits 18.
   - The fake `gh` fails the test if it is ever called with `merge`.
   - A validation test records one real `gh pr view --json …` and one real `gh pr list --search merged:…` of claude-skills, so the fake's shape is checked against GitHub.

   Versions are bumped in `SKILL.md`, `hooks.json` and `skills-manifest.json`. `hooks.json` gets only the lockstep version bump: no hook changes.
3. **Docs.** A `SKILL.md` section covers:
   - when the cop runs `report`, and when an author runs `preflight`;
   - the `reconcile` schedule line;
   - the settings, and what each exit code means;
   - the line saying no exit code means merge again.
4. **Confirm with the Program Cop's author before step 5** (the parser's owner). This plan adds no token. Two questions:
   1. Is `LANDED` (not `DONE`, and not a new `MERGED` kind) the right close for "merged"? `MERGED` is not a parser token today: `OPENS` is `ACK`/`HANDOFF` and `CLOSES` is `DONE`/`LANDED`. So a `MERGED PR #…` line lands in `unparsed`, and today's cop ping closes nothing in the view.
   2. Is the `|` format current? The parser reads only the `|` format with `owner/repo#n` refs (PAV-6). The platform-ops README, the single source for the ACK protocol, still documents the `·` format (`<KIND> <ref> · from … · to … · <detail> · <HH:MMZ>`, kinds ACK, BLOCKED, DONE, ASK, GO, FYI, ref `PR #<n>`), and lines in it land in `unparsed`.

   The view's repo adds one test that feeds shared fixtures through both its `parseLine`/`openWaits` (both exported) and the `pav` preset's parser. That test belongs to the parser's owner and is not copied into this public skill.
5. **Adoption (outside this repo).** The cop procedure's post-merge step runs `report --from … --to …` and quotes the receipt. Each adopted repo gets a `reconcile` schedule, started with `--adopted <timestamp>`; the timestamp is recorded on the Tracker row. Authors run `preflight` before a HANDOFF.
6. **Measure.** The Engineering Effectiveness Auditor runs `audit` as in point 7.

## Out of scope

- Changing `pr-guard.py`, or blocking a merge on a receipt. The receipt reports; it never gates.
- Adding a token to the parser or editing the platform-ops README. That is the parser owner's call (rollout step 4).
- Posting to any chat system, and a command sink (point 4).
- Receipts for PRs merged before a repo's adoption timestamp.
