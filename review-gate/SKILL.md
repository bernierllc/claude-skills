---
name: review-gate
description: Enforce adversarial review before merge via a trusted pull_request_target gate and PreToolUse merge guard. Use when installing review gates on nevar* repos, when merge must wait for unresolved threads or unanswered P2s, or when doctoring whether a repo's ruleset and review-gate.yml are configured. Companion to adversarial-review and pr-merge-flow.
version: 3.2.8
author: Bernier LLC
---

# Review gate

Programmatic enforcement for the adversarial review loop. Ships:

1. **Workflow template** — `.github/workflows/review-gate.yml` (`pull_request_target`)
2. **Trusted checker** — `scripts/check-review-gate.py` (loaded only from the repo **default branch**)
   plus the **forged-check detector** `scripts/check-forged-gate-names.py` (vendored byte-identical from
   `bernierllc/agents-environment-config@dba592dbf5a95d89a19d7b4dfaf2ea11fdf44821`, never edited here; the
   installer never overwrites a repo's differing copy) and
   its wrapper `scripts/check-forged-review-gate.py`, also loaded from the default branch
3. **Doctor** — warns when the workflow, checker, ruleset conversation-resolution flag, or required `Review Gate` status check is missing
4. **PreToolUse merge guard** — blocks `gh pr merge` when the local gate check fails

## Install (per repo)

```bash
aec setup .                      # only if `aec install` says "Not in a tracked repo"
aec install skill review-gate
# copies workflow + trusted checker into the repo (run from the repo root; commit both to the default branch):
aec run-script skill:review-gate install-workflow.py
# or manually:
#   cp …/templates/review-gate.yml .github/workflows/review-gate.yml
#   cp …/scripts/check-review-gate.py …/scripts/check-forged-gate-names.py \
#      …/scripts/check-forged-review-gate.py scripts/
```

Upgrading to 3.2.2: re-run `install-workflow.py --force` to pick up the fail-closed detector (aec dba592db). A repo whose `scripts/check-forged-gate-names.py` differs from the skill's copy keeps its own and gets a `KEPT` message. The merge guard no longer reads `pr-merge-flow` as `pr … merge`. Also in 3.2.2: a known older vendored detector (3.2.0/3.2.1 or any pre-dba592db aec copy) is now replaced on `--force`; only a newer or custom copy is KEPT, and an identical file is left untouched; each `Review Gate` check run carries `external_id: review-gate-pr-<n>` and is reused only by that PR, so two PRs on one head sha cannot complete each other's runs (pre-3.2.2 unmarked runs are left alone; push a new commit if one stays red); the PR that replaces a legacy review-gate.yml passes the forged-check step when its own legacy `Review Gate` job ran that file from the default branch under pull_request_target (needs `PR_NUMBER`); a `##` line with `Review` on the next line no longer counts as the `## Review` section. 3.2.3: `## Review-notes`, `## Reviewers` and other headings that only start with `Review` no longer count as the `## Review` section. A heading, list item, fence or thematic break after a `>` quote now ends the quote, so a `## Review` section that follows a quote is seen. 3.2.4: the vendored `check-forged-gate-names.py` is re-vendored from aec b4a8c9c (comment-only: the plan path now names the aec repo); `install-workflow.py --force` replaces the 3.2.2/3.2.3 copy. 3.2.5: only what CommonMark lets interrupt a paragraph ends a `>` quote's lazy continuation: an ATX heading, a thematic break, a real fence, a non-empty bullet item, or a non-empty ordered item starting at 1. `2. note`, an empty `-` and a ``` line whose info string holds a backtick stay inside the quote, so a quoted example can no longer satisfy the gate. A fenced block now ends the paragraph before it, so an attestation after a closed fence that follows a quote is seen. Re-run `install-workflow.py --force` to pick up `scripts/check-review-gate.py`. 3.2.6: every gate evaluation publishes a NEW `Review Gate` check run and completes all of this PR's runs on the head with the same result, because the Checks API cannot choose a suite and a reused run left in an older suite read "expected" (BLOCKED, all green) on claude-skills #90, nevar-logs #12 and nevar-audit #17. The exact trigger is unresolved: nevar-content #12 had runner-only suites and was not blocked. The gate fails closed, naming the fix, when a non-cancelled review-gate suite on the head holds none of this PR's runs (a 3.2.6 POST that missed its own suite); a cancelled duplicate suite is exempt. This template change is UNPROVEN until a live run, because `pull_request_target` runs the default branch's copy. Until it is proven, keep the interim author rule: set the `review:high` label and the `## Review` section in the `gh pr create` call itself (its opened + labeled pair cancels one run, which merged CLEAN on nevar-audit #18), and change neither the body nor the labels after the first gate run (an edit-triggered suite blocked nevar-logs #12 at d1c6e07); if a PR still reads BLOCKED with every check green, rerun the gate in place, then push a new head. The bootstrap exception for a legacy `Review Gate` job now requires the run's own head fields (sha, branch, repo) to equal this PR's head (never the run's `pull_requests` association), no other PR on that head, and the workflow file at the PR's base to equal the default branch's copy. A `>` line with nothing after the marker now ends a quote's lazy continuation, so `fixed in <sha>` after it closes a P2 thread. `doctor-review-gate.py` warns when the installed workflow differs from the template. Re-run `install-workflow.py --force`. 3.2.7 (P1): do not vendor 3.2.6. Its `run-name` was an unquoted YAML scalar, so ` #` started a comment and every run was titled `Review Gate - PR` with no number; the suite check matched no runs and passed without checking anything (fail-open). The value is now quoted, and the gate fails closed unless its own run is among the runs it matched. UNPROVEN until a live run (nevar-auth #23 after its re-vendor). Evidence for the unresolved BLOCKED trigger (claude-skills #104, 3.2.6 gate): `gh pr create --label` fired opened + labeled, concurrency cancelled the older run, and every `Review Gate` POST, including those from the surviving run and its reruns, landed in the cancelled run's (older) suite. The required-status rule reads the workflow's latest suite, which held only review-gate-runner, so the merge API refused with "Review Gate is expected" while every check read green; rerunning in place did not help; recover with a new head (one synchronize event, one suite). Re-run `install-workflow.py --force`.

Upgrading to 3.2.8: the gate's own job is now named `Review Gate` and its exit code is the result; nothing is POSTed to the Checks API. 3.2.0-3.2.7 assumed a `pull_request_target` job attaches to the base SHA; it attaches to the PR head, in its own run's suite (email_demo #1068: job 133165097976 on PR commit 6402d452, suite 118647401541). A POSTed run lands in the head's OLDEST suite, any workflow's (email_demo #1068: a skipped Claude Code run's suite), and the required-status rule read "expected" (claude-skills #104), so the 3.2.6/3.2.7 suite check and the interim "set the label in `gh pr create`" rule are gone. Legacy POSTed runs of this PR are still completed with each evaluation's result. The forged-check wrapper now accepts a `Review Gate` job from (review-gate.yml, pull_request_target) only when its workflow run is this PR's: the run title must be `Review Gate - PR #<n>` (the run-name, fixed at run creation, confirmed live on nevar-auth #23), so another PR's gate job on a shared head, closed-unmerged included, fails the gate; the legacy-workflow bootstrap exception is gone: a pre-3.2.8 `Review Gate` job from that pair passes only if its run carries the exact numbered title, so a same-head job from an older template (no or unquoted run-name) fails the gate; push a fresh head after upgrading. `install-workflow.py` refuses (exit 1, before writing anything) when the repo's `scripts/check-forged-gate-names.py` cannot serve the bundled wrapper, judged by parsing it, never running it (missing names, an old `forged` signature, no non-empty `Review Gate` entry in a `PROTECTED` dict literal); `--force` backs it up to `.custom.bak` (then `.custom.1.bak`, …, never overwriting one) and replaces it. A newer or custom copy the wrapper runs against is still KEPT. A P2 closing reply whose `fixed in <sha>` sits on an indented continuation line of a list item (`- Addressed:` / `    fixed in …`) now counts: indented code cannot interrupt a paragraph. Closing tokens may follow a CommonMark ordered marker (`1. fixed in …`, `2) …`, 1-9 digits); a marker other than 1 counts only at a block start or as the next line of the same list (same indent and delimiter), since only a non-empty item numbered 1 interrupts a paragraph; anything else, such as an item after a lazy continuation line, fails closed (reply on its own line). A fence that is indented or follows a list marker (`- ```` `, `1. ~~~`, `  ```` ` under an item) makes the rest of the PR body or reply code, so an example attestation or closing reply inside a list-nested fence never counts; put the `## Review` attestation and closing replies before any such fence (a fence at column 0 closes normally). An attestation or closing reply now counts only on a line whose source can only be paragraph text: at column 0, after one list marker (`- `, `1. `) and then a letter, `[` or a URL, or as the indented continuation of such a line; a line in or after a quote, heading, link definition, HTML block or anything starting with code fails closed, and so does every line of a block (lines between blank lines) that has a `===`/`---` underline at any indent or holds a `<`, `[` or `]` outside a construct closed on its own line (a code span, a `[label](url)` link, a bare-attribute tag or autolink after other text, a bracket pair that is not a link or definition), since HTML, link titles and reference labels can span lines; write it as a plain line in its own block. Re-run `install-workflow.py --force`. Live proof (private sandbox repo, 3.2.8 on its default branch, `Review Gate` required): same head opened, then body edit, then `review:high` label, into main and into staging; see PR #105.

Actions event policy (Dec 2, 2026): GitHub's default block on `pull_request_target` applies to PUBLIC repos only, and this gate runs on `pull_request_target`. Before installing or upgrading, check visibility with `gh repo view <owner>/<repo> --json visibility`. In a public repo (the public gate repos today: aec and claude-skills), confirm a test PR gets a `Review Gate - PR #<n>` run before the ruleset requires `Review Gate`; a private repo is unaffected. Do not request a blanket policy for every gate repo.

Upgrading to 3.2.1: the workflow now reuses the head's one `Review Gate` check run instead of adding a new one per evaluation (GitHub blocks the PR while any same-named run in the suite is red, so 3.2.0 heads that failed once could never go green). Re-run `install-workflow.py --force` and commit; the next evaluation completes every earlier run on the head.

Upgrading to 3.2.0: re-run `install-workflow.py --force` and commit the workflow together with all three scripts. The new workflow fails closed until the scripts are on the default branch.

Upgrading an existing install: 3.1.0 accepts `codex` (a local Codex review, e.g. T3 Codex high) as an attestation reviewer; 2.0.0 tightened the fallback rule, and the repo's committed checker is a copy. Re-run `install-workflow.py --force` in each repo to pick it up; until then that repo still accepts the old looser fallback.

### Migrating to 3.2.8

`pull_request_target` runs the workflow from the default branch, so the PR that upgrades the gate is judged by the version it replaces, and the first PR judged by 3.2.8 is the one after it. Check visibility first (`gh repo view <owner>/<repo> --json visibility`): a public repo also needs the Dec 2 check above.

- **From 3.2.6 / 3.2.7.** The old gate POSTs `Review Gate` into the head's oldest suite and then fails its own suite check when a head has two gate runs (opened + labeled, or a push + body edit cancel one into a second suite). Make the upgrade PR's final head a single-event head: (1) `install-workflow.py --force`, commit, open the PR with `--label review:high` (base main) and a `## Review` section; (2) once a review of the reviewed head R is clean (or its findings are fixed and re-reviewed), make an empty commit E on R locally, check `git diff --exit-code R E --` (any tree change means E needs its own review), edit the PR body so the attestation names E and says its tree is identical to reviewed R, wait for that edit's run to start, then push once. The pushed head gets exactly one `synchronize` run and one suite, and merges CLEAN without a ruleset bypass (sandbox PR #21: 3.2.7 base, run 43931045425, check 133523273629). Do not edit the body or labels on that head after the push. If it still reads BLOCKED, repeat step 2 with a new empty commit.
- **From 3.2.0-3.2.5.** These reuse one POSTed run per head, which also lands in the oldest suite. The same single-event head sequence applies (sandbox PR #24: 3.2.5 base, run 43931901065, check 133526298501, suite 118931384467, app 15368, CLEAN).
- **Never vendored.** Nothing evaluates the install PR, so: (1) `install-workflow.py`, commit, merge the install PR into the default branch BEFORE any ruleset requires `Review Gate`; (2) open a throwaway PR and confirm it gets a run titled `Review Gate - PR #<n>` with a `Review Gate` check (in a public repo this is also the Dec 2 check); (3) only then add `Review Gate` (integration github-actions) and thread resolution to the staging and main rulesets (that change is the repo owner's).
- **After any upgrade.** The first PR opened after the merge is judged by 3.2.8: its job is named `Review Gate`, nothing is POSTed, and older checks in older suites no longer block. Into main, `review:high` may be added after opening: the `labeled` event re-runs the gate on the same head and the newest run's result is the check (sandbox PR #4: failure before the label, success after).
- **`main-via-staging.yml` is not part of this upgrade.** Each repo's `.github/workflows/main-via-staging.yml` is owned by the AEC canonical copy (agents-environment-config); a skill update and `install-workflow.py --force` never write or update it. Keep it in sync with AEC's canonical file through AEC, and leave a repo's differing copy to that repo's cop. Observed on nevar-social 7c051dd, a same head with two events: the guard's job runs landed in their own suites (133080263189 → 118577425577, 133081202771 → 118578175718), unlike the 3.2.7 POSTed `Review Gate` (133081228023 → older suite 118577296902), so the guard is not affected by the oldest-suite capture that 3.2.8 fixes. Whether a second event that turns a successful guard run into a failure is read correctly is unproven; 3.2.8 changes nothing there.

Then flip GitHub rulesets (no Actions minutes):

```bash
# For each ruleset that has a pull_request rule (usually staging + main):
gh api -X PUT "repos/<owner>/<repo>/rulesets/<id>" --input - <<'EOF'
{ ...keep existing fields..., "rules": [ { "type": "pull_request", "parameters": { "required_review_thread_resolution": true, ... } } ] }
EOF
```

Email_demo and Prevost already have `required_review_thread_resolution: true` (2026-10-17/18). Add **`Review Gate`** (the job display name / Checks API context — not the workflow file name alone) as a **required check** on those rulesets beside CI.

Doctor:

```bash
aec run-script skill:review-gate doctor-review-gate.py
# or: python3 review-gate/scripts/doctor-review-gate.py
```

## What the workflow does

Triggers **only** `pull_request_target` so the workflow YAML always comes from the PR **base** (trusted). Same-repo `pull_request_review` / `pull_request_review_comment` would execute PR-modified workflow code with write tokens — not used. After Codex completes, a new P2 thread, or a P2 closing reply with no push, **re-fire the gate** via a label toggle or PR body edit (agents: see `adversarial-review`); do not reintroduce review-event workflow triggers. A green Checks API run can otherwise go stale relative to later threads — the PreToolUse merge guard still re-evaluates live before `gh pr merge`.

### Job `gate` (display name `Review Gate`: the required check itself)

Loads `scripts/check-review-gate.py` from the repository **default branch** only (never the PR head or an untrusted PR base) and fails unless all hold:

1. A completed review from the exact Codex bot login `chatgpt-codex-connector` exists on the **current head** (not body text / substring logins), **or** the PR body's `## Review` section contains the explicit completed fallback-review attestation below on one line, bound to the current head.
2. PR body contains a `## Review` section.
3. Every review thread whose **root** comment matches `\bp2\b` has a reply whose rendered text has a line starting with a closing token (optionally after a list marker — bullet, or ordered `1.` / `1)` with 1-9 digits — or `Tracked:`): a Notion link, `fixed in <sha>`, or `not-a-finding: …`. Quotes (lazy continuations and quotes inside list items included), code blocks, inline code spans (a span that is only a commit SHA keeps its text), comments and mid-sentence mentions do not count; the same rule applies to the `Fallback review:` line (all thread/comment pages are fetched). A clean Codex run posts no review, only a `codex-review-state:v1` marker in its summary comment; that marker counts when it is `completed` with no unresolved findings on the current head.
4. When `base` is `main`: label `review:high` is present.
5. **No forged `Review Gate`** (SEC-MVS-01 S5, PRs into every branch): the head SHA's check runs
   (`check-runs?filter=all`, paginated, under `pipefail`) go through `check-forged-review-gate.py`.
   An Actions job named `Review Gate` from any workflow other than (review-gate.yml, `pull_request_target`)
   fails the gate, and so does that pair's job when its run is titled for another PR (not `Review Gate - PR #<n>`), or an
   unreadable listing or lookup (exit 2, fails closed). The legitimate `Review Gate` is this workflow's
   own job, which sits on the PR head in its run's own suite (3.2.8). The wrapper checks only
   `Review Gate`: the vendored map also names `PRs into main must come from staging`, which several
   repos still publish from a plain `pull_request` job; that name stays with each repo's main-via-staging guard.
   Residual: a PR job with `checks: write` POSTing `Review Gate` straight to the Checks API looks the same as
   a legacy (3.2.0-3.2.7) run and is not detected (plan options A/B in aec). A job publishing after the scan is
   caught by the cop's pre-merge run (pr-merge-flow rule 2).

Fallback attestations use exactly this format (plain text on its own line inside `## Review`):

```text
Fallback review: <reviewer> on <sha> — verdict: <verdict>
```

- `reviewer`: `codex` (a local Codex review, such as T3 Codex high, that the GitHub Codex bot did not post), `agy`, `antigravity`, `superpowers`, or `claude-sonnet`.
- `sha`: the current `headRefOid` in full or a prefix of at least 7 hex characters. The entire supplied prefix must match.
- `verdict`: `clean` or `findings fixed`; attest only after the review completed and any findings were fixed.

Copy-pasteable example (replace `89cda061` with the head actually reviewed):

```text
## Review

Fallback review: claude-sonnet on 89cda061 — verdict: clean
```

Reviewer, SHA and verdict must all be on that same line. Lines containing `pending`, `running` or `TODO` (case-insensitive) are rejected. URLs, generated Claude Code footers and keyword-only prose do not count. After every push, rerun the review before replacing the attested SHA; copying the new SHA alone does not attest a review. Earlier free-form fallback summaries no longer satisfy this gate.

The `pull_request_target` job's check run is on the PR **head**, in its run's own check suite, which is the suite the required-status rule reads (opened / synchronize / label / edit). That job is the `Review Gate` check.

Unresolved threads are **not** checked here — that is GitHub's `required_review_thread_resolution` on the ruleset (free, instant on resolve).

Judgment/Jev triage is **out of scope** for v1 (still piloted in NevarMail per the 2026-10-16 enforcement plan).

## Promotion guard order (main-via-staging)

A repo's `main-via-staging.yml` and its guard script (`scripts/check-forged-gate-names.py` and the
validator it checks out) must already be **on main** before the first `staging` → `main` promotion
PR opens. `pull_request_target` loads the workflow from the default branch and the job checks out
`pull_request.base.sha`, so a guard that exists only on staging or the PR head does not run, and the
required check stays `expected` (fails closed). Never point the checkout at staging or the PR head to
"bootstrap" it: that runs untrusted code with `checks: write`. Land the guard on main first.

## Merge guard

PreToolUse blocks `gh pr merge` (including `--auto`) when `check-review-gate.py` fails for that PR. **Required form for any compound shell command** (`&&`, `||`, `;`, newlines, subshells, `export`, …): `gh -R owner/repo pr merge <n>` (literal repo). The guard does **not** model cwd/`cd`/`export GH_REPO`/subshell interactions across segments — pass `-R` instead. A single-segment `gh pr merge <n>` in the tool cwd is still allowed. Override with `# review-gate-ok: <reason>` in the command only for Matt-approved escapes.

## Apply across nevar*

1. `aec install skill review-gate` + `install-workflow.py` in each repo (or a small apply PR series).
2. Doctor in CI or a weekly scheduled task; warn (do not hard-fail) until the first month of data.
3. Keep `adversarial-review` installed so agents post the inline comments the gate expects.

## Related

- Loop behavior: skill `adversarial-review` / `~/.claude/references/pr-review-loop.md`
- Base-sync discipline: skill `pr-merge-flow`
- Plan of record: `email_demo/plans/2026-10-16-dev-environment-enforcement-plan.md` §6

<!-- feedback-loop:begin -->
## Feedback

If the `feedback-loop` skill is installed, use it to improve this skill over time:

- When this skill's own instructions cause rework, a wrong default, a missed case or a needless
  pause, log it as it happens: subject `skill:review-gate`, with the phase or section at fault and the
  concrete fix to these instructions.
- When the project's own process causes friction during this skill's work (for example a flaky
  or slow CI job, a test that missed a regression, a plan that was wrong about the code), log it
  as subject `process:<project>` with `--area <ci|test|plan|review|deploy|dev>`.
- At the end of a run, check `skill:review-gate`; if a review is due, make the feedback-loop offer.

If `feedback-loop` is not installed, ignore this section.
<!-- feedback-loop:end -->
