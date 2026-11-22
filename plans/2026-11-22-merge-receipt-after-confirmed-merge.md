# pr-merge-flow: a merge receipt only after gh confirms MERGED

Status: planned, no code. Plan id: EEA-2. Owner: `pr-merge-flow` (the claude-skills cop). Proposed priority: P2; the PM scheduled task sets the final tier. Tracker: https://app.notion.com/p/EEA-2-plan-merge-receipt-after-gh-confirms-MERGED-idempotent-key-durable-outbox-configurable-sin-4204efecc95a81a4b84be8f6e613f49f

## Incumbent check (read first)

What already covers "tell people a PR merged":

- **`pr-merge-flow` 1.6.0** (`scripts/pr-guard.py`, a PreToolUse hook). It decides whether a merge may *start*: `gh pr merge <n> --squash --match-head-commit <sha>`, no `--auto`, no `--admin`, required checks green. It runs before the command and never sees the result. It has no post-merge step and writes no record of a merge.
- **The cop's `MERGED PR #<n> as <sha>` ping.** Step 4 of the traffic-cop procedure (in the operator's own global config, not this repo) tells the author thread after a merge. It is a chat message the cop writes by hand. Nothing checks that it was sent, that the sha is the one GitHub merged, or that it reached anyone who was not in the thread. A cop that runs out of context or quota between the merge and the message leaves no trace.
- **The program attention view** (PAV, in the org's platform-ops tooling, `scripts/attention.mjs`). It reads an ACK log of one-line events and lists the waits nobody has closed. PAV-9 (planned) already reports a PR that left the open list as merged, closed or `outcome unknown` by asking GitHub. That is an inference after the fact, not a receipt: it does not say who merged it, at which head, or whether the author was told.

None of them produces a record, written only after GitHub says MERGED, that a reader other than the merging thread can rely on. That gap is what this plan fills. It adds a new script to the skill that owns merging and changes none of the three above.

## Dedupe (searched 2026-11-22)

- **claude-skills `main`:** no plan, script or issue covers a merge receipt, an outbox, or a post-merge report. `plans/` holds `2026-11-22-pr-guard-required-vs-advisory-checks.md` and `pr-guard-shell-parsing-design.md` (#139), both about what the guard lets *start*, not what happens after.
- **agents-environment-config `staging`:** no receipt or outbox plan.
- **Platform-ops issues and the PAV plan** (`plans/2026-11-20-program-attention-view.md`, PAV-8 to PAV-12): PAV-9 derives merged/closed/unknown for departed PRs; PAV-11 has NevarPlan publish a `merged[]` list `{pr_url, merge_commit, merged_at}` labelled OBSERVED, planned and not yet published; PAV-12 consumes PAV-11. None of them writes a receipt at merge time. This plan's receipts are a source PAV-11/12 can read, not a replacement for them.

## Related open work

- **#139 (tokenizer-first guard plan)** rewrites how `pr-guard.py` reads shell commands. This plan does not touch `pr-guard.py` and does not parse shell commands, so it neither waits on #139 nor conflicts with it.
- **#131 and #132** (guard changes, held under MATT-120) were cut at 1.5.5 while `main` is at 1.6.0, so they already need a rebase and a new version. This plan ships as **1.7.0** in new files only (`scripts/merge-receipt.py`, its tests, a `SKILL.md` section). Whichever lands second takes the next minor and rebases; the receipt adds no hunk to any file they edit except the version fields and `SKILL.md`.

## Design

### 1. A receipt only after GitHub reports MERGED

`scripts/merge-receipt.py report <owner/repo#n> --head <sha>` never runs `gh pr merge`. It asks GitHub:

```
gh pr view <n> -R <owner/repo> --json number,url,state,headRefOid,mergeCommit,mergedAt,mergedBy
```

and writes a receipt only when all of these hold:

- `state == "MERGED"`;
- `headRefOid == <sha>` passed in (the head the cop checked, the same value as `--match-head-commit`);
- `mergeCommit.oid` is a 40-hex sha.

The ref is always canonical `owner/repo#n`. A bare `#n` or a URL is resolved once to that form (URL parsed; bare number needs `-R`), and anything else is refused, so two spellings of one PR never make two receipts. `owner/repo` is compared case-insensitively and written lowercase.

Any other answer writes no receipt: `OPEN` or `CLOSED` exits 1 with `not merged`; a head mismatch exits 1 with both shas; a `gh` error or timeout exits 2 with `could not confirm` and queues a **confirm** job (below), never a receipt.

The cop runs it right after its merge command returns, instead of writing the `MERGED PR` line by hand; the script prints that line (format in point 4) for the cop to send. Wiring it into the cop procedure is a one-line edit in the operator's config, listed in rollout step 4.

### 2. Preflight returns an already-merged receipt

`merge-receipt.py preflight <owner/repo#n> --head <sha>` is for the moment a thread is about to open a HANDOFF or wait on a merge. It runs the same `gh pr view`:

- MERGED at that head: prints the receipt (from the outbox if one exists, else it writes one through point 1) and exits 0, so the caller sends the receipt instead of opening a new wait.
- MERGED at a *different* head: exits 1 and names both; the caller must not report its own head as merged.
- OPEN: exits 3, `not merged, open a wait`.
- CLOSED unmerged: exits 1.
- gh error: exits 2, `could not confirm`; the caller opens the wait as it would today (a failed lookup never means merged).

This kills the case where a thread hands off, or keeps waiting on, a PR the cop already merged.

### 3. Idempotent key, bounded retry, durable outbox

- **Key:** `merge-receipt:v1:<owner/repo>#<n>:<merge_commit>`. One merged PR has one merge commit, so the key is the same however many times the script runs, from any thread.
- **Outbox:** one JSON file per key under `${XDG_STATE_HOME:-~/.local/state}/pr-merge-flow/outbox/`, written atomically (temp file, `fsync`, `rename`) *before* any delivery is attempted. Fields: key, ref, url, head, merge_commit, merged_at, merged_by, from, to, created_at, attempts, last_error, delivered_at.
- **Delivery:** up to 3 attempts per run with short backoff (1 s, 4 s), each bounded by a timeout. Success sets `delivered_at`. Failure leaves the file with `attempts` and `last_error` and exits 2, `receipt queued, not delivered`.
- **`merge-receipt.py flush`** retries every undelivered file (and every queued confirm job, which re-runs point 1's check first). It is safe to run from cron, a SessionStart hook or by hand, and it is the only retry loop: the script never sleeps waiting on a sink.
- **Never rerun the merge.** The script has no code path that calls `gh pr merge`, and a test pins that (rollout step 1). A failed report is a delivery problem; the merge already happened and GitHub is the record.
- **Never a false Done.** A receipt exists only after point 1's three checks pass. Exit 0 means delivered; 2 means confirmed-but-queued or not-confirmed, and the caller must say which (the script prints it). Nothing else may report the PR closed.
- **Dedupe at the sink.** Before posting, a sink that can be read (GitHub comment, JSONL file) is searched for the key; a hit marks the file delivered without posting again. The key is on the receipt's second line so a reader can grep it. A write-only sink (a command) gets the key as `MERGE_RECEIPT_KEY` and must dedupe itself; the docs say so.

### 4. The line format: existing PAV tokens only

The attention view's parser (`scripts/attention.mjs`, read on its `main` and `staging` 2026-11-22) knows these kinds:

- `OPENS = ["ACK", "HANDOFF"]` open a wait.
- `CLOSES = ["DONE", "LANDED"]` close one.
- Any other kind parses but does nothing.
- **`MERGED` is not a token.** A line starting `MERGED PR #…` lands in `unparsed`, so today's cop ping closes nothing in the view.

A wait's key is the ref plus the unordered `{from, to}` pair, so a `LANDED` from the cop to the author closes the author's `HANDOFF` to the cop. Only a comment's first line is the event.

So the default receipt's first line is:

```
LANDED <owner/repo>#<n> | from=<from> | to=<to> | merged <head> as <merge_commit> | <HH:MM>Z
```

and its second line is `merge-receipt:v1:<owner/repo>#<n>:<merge_commit>` (the key, ignored by the parser). `from` and `to` are passed with `--from` and `--to` in whatever form the sink's readers use; left out, the line omits them and the receipt still works for a file or command sink.

Two facts the plan does not settle and asks the Program Cop's author to confirm:

1. That `LANDED` (not `DONE`) is the right close for "merged", and that no `MERGED` kind should be added instead. This plan adds no token.
2. Which `|` format is current. The platform-ops README, the single source for the ACK protocol, still documents the older `·` format (`<KIND> <ref> · from … · to … · <detail> · <HH:MMZ>`, kinds ACK, BLOCKED, DONE, ASK, GO, FYI, ref `PR #<n>`); the parser reads only the `|` format with `owner/repo#n` refs (PAV-6). Old-format lines land in `unparsed`. The receipt uses the format the parser reads.

The cop's chat ping keeps its words for the thread (`MERGED PR #<n> as <sha>`) and is printed by the script from the same receipt, so the two cannot disagree.

### 5. A generic skill: the sink is configurable

The skill is public, so nothing in it names an org, a person, an issue number or a chat tool. The sink is an aec setting, read the way `pr-guard.py` already reads `settings.pr_open_mode` (`draft_mode()`, `~/.agents-environment-config/preferences.json`):

```json
{"settings": {"merge_receipt_sink": {"kind": "github-issue", "target": "my-org/my-ops-repo#1"}}}
```

| kind | delivers to | dedupe |
|---|---|---|
| `none` (default) | outbox only; the line is printed | n/a |
| `jsonl` | appends one JSON object to `target` (a path) | scans the file for the key |
| `github-issue` | `gh issue comment` on `target` (`owner/repo#n`) | searches the issue's comments for the key line |
| `command` | runs `target` with the receipt on stdin, key in `MERGE_RECEIPT_KEY` | the command's job |

`--sink` on the command line overrides the setting for one run. An unreadable or unknown setting is an error that names the setting, not a silent `none`: a user who configured a sink must not believe receipts are delivered when they are not. Unset means `none`. The org that runs the attention view sets `github-issue` with its own ACK-log issue in its own preferences; that value never appears in the skill.

### 6. Audit, and how success is measured

`merge-receipt.py audit --since <date> -R <owner/repo> [...]` lists the PRs GitHub says merged since that date (`gh pr list --state merged --search "merged:>=<date>"`) and, for each, whether a delivered receipt with the matching key exists (outbox, plus the sink if it is readable). It prints counts and the missing refs.

**Success measure:** missing receipts at most 5% of PRs merged through the cop in the 3 days after the release reaches the cops, measured by the Engineering Effectiveness Auditor 3 days after ship with `audit`, over the repos whose cops have adopted it. A missing receipt is a merged PR with no delivered receipt for its key. Queued-but-undelivered counts as missing.

## Rollout

1. **Script and tests (pr-merge-flow 1.7.0).** `scripts/merge-receipt.py` (standard library plus `gh`) with `report`, `preflight`, `flush`, `audit`. Tests run the real script against a fake `gh` on `PATH` (a small script returning recorded `gh pr view` JSON, since GitHub is third-party) and a temp `XDG_STATE_HOME`:
   - MERGED at the right head writes one receipt; running it twice writes one, delivers once.
   - OPEN, CLOSED, head mismatch and a `gh` failure each write no receipt and exit as listed.
   - A sink that fails twice then succeeds delivers on the third attempt; one that always fails leaves a queued file and exit 2; `flush` then delivers it.
   - A crash between outbox write and delivery (killed process) leaves a file that `flush` delivers once.
   - The first line parses as `LANDED` with the parser's own `REF` pattern, copied into the test with its source and date.
   - No code path invokes `gh pr merge` (the fake `gh` fails the test if it ever sees `merge`).
   - A validation test records one real `gh pr view --json …` of a merged claude-skills PR, so the fake's shape is checked against GitHub.
2. **Docs.** A `SKILL.md` section: when the cop runs `report`, when an author runs `preflight`, how to set the sink, what exit 2 means. Versions bumped in `SKILL.md`, `hooks.json` and `skills-manifest.json`.
3. **Confirm tokens** (point 4) with the Program Cop's author before step 4.
4. **Adoption (outside this repo).** One-line edit to the cop procedure's post-merge step: run `report` and send the line it prints. The org sets its sink in its own preferences. Authors run `preflight` before a HANDOFF.
5. **Measure.** EEA runs `audit` 3 days after step 4 and records the rate on the Tracker row.

## Out of scope

- Changing `pr-guard.py`, or blocking a merge on a receipt. The receipt reports; it never gates.
- Adding a `MERGED` kind to the parser, or editing the platform-ops README (that owner's call, asked in point 4).
- Posting to any chat system. The `command` sink lets a user wire one.
- Backfilling receipts for PRs merged before adoption; `audit` will list them and that is fine.
