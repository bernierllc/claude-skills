# pr-merge-flow guard: required checks must pass, only pinned advisory checks may be red

Status: planned, no code. Plan id: CS-PRGUARD-REQUIRED-VS-ADVISORY (revision 2). **Supersedes the fix design in `2026-11-21-pr-guard-required-vs-advisory.md`** (revision 1, merged in #143). Revision 1 stays in the repo for history, and its research (endpoints, union key, fail-closed cases, open-PR ordering) is reused below. Proposed priority: P1. The PM scheduled task sets the final tier. Owner: the claude-skills cop (`pr-merge-flow`). Tracker: https://app.notion.com/p/CS-PRGUARD-REQUIRED-VS-ADVISORY-pr-merge-flow-guard-blocks-only-on-the-ruleset-s-required-checks-a-41f4efecc95a81d0b22cd96bbf51034d (revision 1's row, updated to point here; Owner Needs-PM).

## Why a revision and not a new plan

Revision 1 already plans this fix, so this file replaces its design and keeps one plan id and one Tracker row. The Program Cop set binding constraints on 2026-11-22. Revision 1 breaks two of them:

| Program Cop constraint | Revision 1 | Revision 2 |
|---|---|---|
| 1. The required set is the ruleset requirements UNION the repo's own policy | Ruleset UNION classic protection only. A test that the repo requires but GitHub does not is invisible. | Adds a repo policy file, read from the repo's default branch (below). |
| 3. A failed lookup never means "none required" | Blocks on every failure | Falls back to today's all-green rule, and still enforces every requirement the other sources resolved (see "Lookup fails"). Either answer is allowed, and this plan says why it picks the fallback. |
| 4. Only checks on an explicit advisory list may be red | **Every** check the rules do not require becomes a warning, so a red `Test & Build` or a red security scan that is not in the ruleset would merge | Only the entries on one pinned list, shipped in the guard, may be red. Every other red check still blocks. |
| 5. The drift detector (`doctor`) is advisory and pinned by design | Says nothing about pinning | Pinned by workflow path, event and job name, with provenance (below). |

Revision 1's file gets one line at the top pointing here, in this PR. Nothing else in it changes.

## Dedupe: what exists (searched 2026-11-22)

- **Plans in this repo:** `2026-11-21-pr-guard-required-vs-advisory.md` (revision 1, the incumbent, extended here). `2026-11-21-doctor-latest-release-coupling.md` (CS-DOCTOR-LATEST-RELEASE: why `doctor` goes red on an upstream release, and the migration to the pinned, no-clone doctor job). That plan **is** the Program Cop's "upstream-drift detector pinned/advisory" plan for the detector itself: its rollout step 5 points at this plan for the guard side. This plan does not repeat it. `pr-guard-rollup-and-auto-message.md` (the collapse of superseded runs that this plan builds on). `pr-guard-shell-parsing-design.md` / PR #139 / issue #124 (tokenizer, a different part of the same file). `review-gate-stale-vendor-fleet.md` (re-vendoring). No plan in `docs/superpowers/plans/` covers it.
- **Issues:** #124 (tokenizing), and #128 and #136 (how many calls the forged-gate check makes) are known and different. No open issue covers required versus advisory checks.
- **Open PRs touching `pr-guard.py`:** #131 and #132 (both 1.5.5) and #139 (plan only). The ordering is unchanged from revision 1: this lands after #131 and #132, as 1.6.0.
- **agents-environment-config `plans/`:** no drift-detector plan. `2026-11-16-unforgeable-required-checks.md` (SEC-MVS-01) is the forged-name plan that this design must not weaken (see "Forged names").
- **Notion Tracker:** searched by title (`advisory`, `PRGUARD`, `drift`, `required check`). It holds the revision 1 row (reused), CS-DOCTOR-LATEST-RELEASE, CS-GUARD-DETECTOR-COUPLING and SEC-MVS-01, and none of them duplicates this plan. The Roadmap database was not searched.
- **Is `review-gate doctor` already planned as advisory?** Yes, implicitly. CS-DOCTOR-LATEST-RELEASE keeps `doctor` out of every ruleset ("Making `doctor` a required check" is out of scope there, and it belongs to each repo owner). It also makes the doctor job unable to go red because of an upstream release once a repo migrates. No plan says what the **guard** does with a red `doctor`, and this plan covers that.

## What happened

- nevar-mail #1129 (2026-11-21, revision 1's incident): every required check was green and `doctor` was red, and the guard refused the merge.
- nevar-aec-catalog #14 (2026-11-22, this revision): Review Gate was green, and ruleset 27343449 requires only `Review Gate`. A `doctor` check that no rule requires went red after review-gate 3.3.2 shipped, because the repo vendors 3.2.16. Verified today: the repo's `review-gate-doctor.yml` on main still has the `git clone` (the old clone-main shape, row 5 of CS-DOCTOR-LATEST-RELEASE's table), and #14 is still open at head `2e343f1e2fa010eaa1df4e365e58b13d0808ed0d`. The only override in the guard was the Matt-only `# codex-review-ok` marker, which does not apply to this rule and must not be used.

**The fastest unblock for #14 is not this plan.** It is CS-DOCTOR-LATEST-RELEASE migration step 2 for nevar-aec-catalog (re-vendor to the no-clone doctor job). That turns `doctor` green with no change to the guard. This plan stops the next upstream release, or the next advisory detector, from stopping merges again.

## Root cause (verified at origin/main df98c76, pr-merge-flow 1.5.4)

- `not_green()` (`pr-merge-flow/scripts/pr-guard.py:728`) reads `statusCheckRollup` with `gh pr view` (line 740). It collapses superseded runs per (workflow file path + event, job name), and only for entries whose run id resolves to this PR's own Actions run (`run_workflows`, line 693) and whose job id the jobs API confirms with the same name and conclusion (`run_jobs`, line 716). It then reports **every** remaining entry that is not green (lines 785-787).
- `check()` (line 818) blocks `gh pr merge` when that string is non-empty (line 854-858). The guard has no list of required checks, no list of advisory checks, and no override for a red check. That last part is correct and stays.
- `mergeStateStatus` is requested on line 741 and never read. The guard also never compares `headRefOid` with the `--match-head-commit` SHA, so it relies on `gh` to refuse a moved head (see P3).

The defect: "every reported check must be green" mixes three different kinds of check. **Required** checks must be green. **Advisory drift detectors** are allowed to be red by design. Everything else (a test job outside the ruleset, a security scan) the repo has not declared advisory, so it must stay blocking.

## Incumbents: what already knows which checks are required

| Source | What it gives | Enough on its own? |
|---|---|---|
| GitHub rulesets, `GET repos/{o}/{r}/rules/branches/{base}` (paginated) | Every active rule on the base branch, including `required_status_checks` contexts with an optional `integration_id` | No. It only knows what the ruleset owner put there, and constraint 1 says repos require more. **Reused** as one input. |
| Classic protection, `GET repos/{o}/{r}/branches/{base}/protection/required_status_checks` | `checks[]` entries with `context` and `app_id` | Same as above. **Reused** as one input. Revision 1's union key `(context, integration_id)` is kept. |
| GraphQL `isRequired(pullRequestNumber:)` on `CheckRun` / `StatusContext` (documented in GitHub's GraphQL reference; not yet called from this repo, verify before use) | GitHub's own required flag per reported context | No. It cannot name a required context that is absent from the rollup. It is only a cross-check (P3). |
| `review-gate/scripts/doctor-review-gate.py` (`ruleset_requires_review_gate`, line 166, and the rulesets listing at line 327) | Reads `repos/{o}/{r}/rulesets/{id}` and looks only for `Review Gate`. Its output is WARN-only because CI tokens often cannot read rulesets. | No. It checks one context, and the doctor is the wrong owner for merge-time decisions. The guard reuses its **parsing shape** (rule type `required_status_checks`, `parameters.required_status_checks[].context`), not its code: the two skills ship separately, and a shared import would couple their versions. |
| `aec` org config (`aec/lib/org_config/`) | Org-level preferences and allow-lists. It holds nothing about required checks (searched: no `required`, `ruleset` or `required_status` in it). | No. Org scope cannot say "this repo needs its integration test", and `aec` is not in the merge path. |
| `review-gate/scripts/check-forged-gate-names.py` | Treats a protected name as legitimate only when it comes from one pinned workflow (path + event) | It is not a required-set source, but it is the **pinning pattern** this plan reuses for policy entries and the advisory list. |

Nothing records "required by repo policy beyond the ruleset" or "advisory by design", so those two need a new home (below).

## Design

### Three kinds of check

1. **Required** = ruleset-required UNION classic-required UNION repo-policy-required (keyed `(context, app or pin)`, as in revision 1). Each one must be present on the current head, satisfy its pin, and pass `required_ok`: conclusion (or status state) `SUCCESS` and nothing else. `green()` also accepts `NEUTRAL` and `SKIPPED`, which is right for "everything else" but wrong for a requirement: a required job skipped by an `if:` never ran. `required_ok` is a separate predicate, so `green()` and the existing collapse do not change.
2. **Advisory** = an entry that matches the **pinned advisory list** shipped in `pr-guard.py`, is not in the required set, and passes provenance. It may be red or pending. The guard prints it, and it never blocks.
3. **Everything else** = must be green, exactly as today. This is the default, and it is what keeps a red `Test & Build`, CodeQL or Security Scan blocking even where no rule requires it (constraint 4).

So the guard loosens in exactly one place, a red advisory-list entry. It tightens in one place, a required check that is missing or fails its pin.

### Where repo policy lives: `.github/required-checks.json`

- **Location:** a committed JSON file at `.github/required-checks.json`, read **from the repo's default branch**, whatever the PR's base is: `gh api repos/{o}/{r}/contents/.github/required-checks.json` with no `ref`, which the contents API resolves to the default branch, using the PR's own host and repo, as `_api_lines` already does. It costs no extra call to learn the default branch.
  - **Why not the base branch:** anyone who can push a branch can open a PR into a branch they created, with a policy file that requires nothing, so a base-branch read lets a contributor pick their own policy. The default branch is the one the repo's rulesets protect most, and the one every promotion ends on.
  - **Never the head:** the guard never reads the PR head's copy, so a PR cannot loosen its own gate.
  - **What this means for the policy:** a policy change takes effect for every PR, including PRs into `staging`, only once it reaches the default branch through a reviewed PR that passed Review Gate. That is the same trust a ruleset change has. A repo whose default branch accepts unreviewed pushes has no trustworthy policy source, and a person with that access can merge anything anyway, so the guard adds nothing there and claims nothing.
  - The name states its domain (deliberate-naming rule). JSON, because the guard is stdlib-only.
- **Format (schema 1):**

  ```json
  {
    "schema": 1,
    "required": [
      {"name": "Test & Build", "workflow": ".github/workflows/ci.yml", "event": "pull_request"},
      {"name": "deploy-preview", "app_id": 12345}
    ]
  }
  ```

  Each entry has a `name` (the check's context, which for an Actions job is the job name). It also has exactly one pin:
  - `workflow` + `event`, for an Actions job. It is matched through the existing `run_workflows`/`run_jobs` provenance **and** the check-run identity check below.
  - `app_id`, for a check run published by a GitHub App. `gh pr view`'s rollup does not carry app ids, so the data source is REST `GET repos/{o}/{r}/commits/{head}/check-runs` (paginated), whose entries carry `id`, `app.id`, `name`, `conclusion` and `details_url`. An entry satisfies an `app_id` pin only when the REST check run with that name has that `app.id`.
  - **Status contexts are not supported in schema 1.** The statuses API gives a `creator` user, not an app id, so an `app_id` pin can never be satisfied by a status context, and an entry aimed at one fails closed (`MISSING`). Pinning a status context by creator is P2.

  An entry without a pin is malformed. An unknown key, an unknown `schema`, or a duplicate name with conflicting pins is malformed.
- **The file can only add requirements.** It has no `advisory` key and no way to exempt anything. A repo cannot make `Test & Build` advisory by editing it (constraint 4). Making something advisory is a claude-skills change (next section).
- **Owner:** each repo's owner. The repo's traffic cop authors the PR, and Review Gate on the base branch approves it. Adding CODEOWNERS on the file is a P2 option for each repo owner and is not required here.
- **Absent file:** the repo has not opted in. The guard keeps today's behavior: every reported check must be green, and there is no advisory exemption. This is constraint 3 ("missing policy file never means none required"), and it is also the rollout switch (see "Rollout"). A repo with no extra requirements opts in with `{"schema": 1, "required": []}`.
- **Open decision for Matt (recommendation given, does not block the plan):** whether an org-level default should exist later (for example a `bernierllc/.github` repo file that every repo inherits). Recommendation: **no**, not now. A per-repo file on the base branch is reviewable by the people who merge there, and org inheritance adds a second trust root and a second lookup that can fail. Revisit after the fleet has opted in.

### The pinned advisory list (owner: the claude-skills cop)

- A constant in `pr-guard.py`, `ADVISORY_CHECKS`. Each entry is a full pin `(job name, workflow path, event)`. It starts with exactly one entry:

  `("doctor", ".github/workflows/review-gate-doctor.yml", "pull_request")`

  The values are taken from `review-gate/templates/review-gate-doctor.yml` (job `doctor`, `on: pull_request`). The installer writes that file to exactly that path.
- **What makes `doctor` advisory:** (a) it is on this list; (b) no ruleset, classic rule or repo policy requires it. If any source requires it, required wins and a red `doctor` blocks, because that repo chose to make it a gate. (c) It is a read-only consistency report with no token and no secrets (template header, line 13). Its red means "this repo's vendored copy has drifted", which is a maintenance signal for the repo's cop, not a defect in the PR.
- **How `doctor` is pinned:** in the guard, by the triple above plus provenance plus check-run identity. Only an entry whose run id resolves through `run_workflows` to that path and event for THIS PR, whose job id `run_jobs` confirms with the same name and conclusion, and that passes the identity check below, counts as advisory.
- **Check-run identity (why provenance alone is not enough):** `detailsUrl` is writable. `run_jobs` proves the URL names a real job, but a second check run can copy the real doctor's URL, name and conclusion and pass `run_jobs` too. An Actions job's check-run id equals its job id, and the REST `commits/{head}/check-runs` list carries each check run's immutable `id` and `app.id`. So an entry is that job only when, in that list, **exactly one** check run's `details_url` names job id J, its `id` equals J, and its `app.id` is 15368 (GitHub Actions). If two check runs claim job J, neither gets the exemption, and neither satisfies a workflow pin: both are "everything else", and a red one blocks. The same rule applies to required entries pinned by `workflow` + `event`. If the check-runs call fails or the budget is gone, nothing is authenticated, so no exemption and no pin is satisfied (fail closed). In the repo, the doctor's code is the repo's own vendored `.claude/skills/review-gate` copy, at the version committed on the PR's merge ref (3.2.19+ no-clone job). CS-DOCTOR-LATEST-RELEASE adds the declared floor file. The old clone-main job (nevar-aec-catalog today) is **not** pinned in that sense: it runs claude-skills `main`. The guard's pin still applies to it because path, event and job name are unchanged, so the guard stops it from blocking merges. The migration in CS-DOCTOR-LATEST-RELEASE is what removes the drift itself.
- **Adding an entry** is a claude-skills PR labelled `review:high` that names the detector and why it is advisory by design. Every entry must be a drift or consistency report, never a test, build, lint, security or review check. A test in `pr-merge-flow/tests/` fails if `ADVISORY_CHECKS` contains a name on a deny-list (`Review Gate`, `Security Scan`, names containing `test`, `build`, `codeql`, `security`). The deny-list makes an accidental addition fail loudly (rung 3).

### Evaluation, step by step (current head only)

1. `gh pr view` as today, adding `baseRefName` to the `--json` fields (for the rules and protection endpoints). The rollup is the PR's **current** head. Provenance (`run_workflows`, `run_jobs`) is unchanged and not weakened.
   - **Authenticate before collapsing (tightened in every mode, with or without the policy file).** Today an entry joins the superseded-run collapse (lines 766-784) once `run_jobs` confirms its URL, name and conclusion. A forged check run can copy an old green job's URL with a later `startedAt` (writable) and supersede a newer failed run of the same job. So an entry may join the collapse only after it also passes check-run identity (exactly one check run claims job J, its id is J, its app id is 15368), read from one `commits/{head}/check-runs` call. An entry that fails identity is never collapsed and must be `green()` on its own. If that call fails or the budget is gone, nothing collapses (fail closed), which can only add blocks. The parity test allows this: it fails on a lost block, not on a gained one.
2. Read the policy file from the default branch. **A 404 means the repo has not opted in:** stop here and apply today's rule (every entry in `latest` must be `green()`), with no further lookups and no extra lines. The only change from 1.5.x on this path is step 1's authenticated collapse, which can only add blocks. GitHub's own rules still enforce ruleset requirements at merge time.
3. Otherwise read the rest: rules endpoint for `baseRefName` (all pages), and the classic protection endpoint. The `commits/{head}/check-runs` list from step 1 also supplies app ids for `app_id` pins.
4. **Requirements from every source that resolved are enforced, always.** For each required key from a resolved source: take **every** entry in `latest` (after collapse) that has the name and satisfies the pin (identity-checked `app_id`, or workflow path + event through provenance and identity), At least one must exist, and **every** one must pass `required_ok`. Same-named jobs in the surviving run (a matrix, or jobs sharing a name across `needs:`) are each judged on their own, as the collapse already does for `green()`, so one `SUCCESS` never covers a `SKIPPED` or `NEUTRAL` sibling. If none exists, block with `required check <name> is MISSING on <head sha>`; if one fails `required_ok`, block with `required check <name> is <PENDING|FAILURE|SKIPPED|NEUTRAL|…> on <head sha>`. A required entry whose provenance or identity cannot be resolved does not satisfy its pin, which fails closed.
5. **If any lookup failed** (the policy file is unreadable or malformed, the rules or protection call fails, or the check-runs call fails): the advisory exemption is off, and every entry in `latest` must also be `green()`. The block message adds one line per failed source: `required-check lookup unavailable: <source> <status or error>; using the all-green rule`. A failed lookup therefore never drops a requirement that another source did resolve, and never means "none required".
6. **Only when every lookup resolved:** for each entry in `latest` that is not `green()`, if it matches `ADVISORY_CHECKS` (name + path + event through provenance and identity) and is not required, record it as advisory. Otherwise, block, exactly as today.
7. Allowed with advisory entries: the guard prints `advisory check doctor is FAILURE (pinned advisory: .github/workflows/review-gate-doctor.yml); not blocking`. The cop must see it, so the output channel is an open item (test 12). When a merge is blocked, the block message lists the advisory entries as well, each labelled advisory, so whoever reads it sees all of them.

### Lookup fails: why the fallback is today's rule and not a block

Revision 1 blocked every merge when a lookup failed. Both answers satisfy constraint 3. This plan falls back to all-green **plus** every requirement it did resolve, because:

- The fallback is **never looser than today**. It adds no exemption, so a failed lookup cannot hide a red check.
- It is **never looser than what was learned**. A policy file that resolved still has its requirements enforced when the rules call fails, so a missing policy-only check (a deleted test workflow) still blocks. The reverse holds too: resolved ruleset entries are still enforced when the file is unreadable.
- Revision 1's own open question was that a token without Administration: read on the classic endpoint would block **every merge in every repo**. The fallback turns that into "the advisory exemption is off", which is visible in the block message.
- What it gives up: a requirement held only by the source that failed, and missing from the rollup, is not detected. If that source is the ruleset or classic protection, GitHub still enforces it at merge time. If it is the policy file, the file is unreadable, so there is nothing to enforce, and the message names the file.

Revision 1's failure cases 4a-4i (exit codes, 403, a 404 that is not "Branch not protected", truncated pagination, malformed JSON, a rule with an empty context list, a rollup that cannot be confirmed complete) all map to step 5. A 404 on the policy file is not a failure: it is step 2's opt-out. The documented "Branch not protected" 404 on the classic endpoint is a successful empty answer, as revision 1 says. Confirm it against a recorded real response.

### Review Gate

- `Review Gate` is never advisory: it is on the deny-list above, so it can never be added to `ADVISORY_CHECKS`. In the nevar fleet it is ruleset-required, so step 4 requires it.
- Its provenance belongs to review-gate. The gate runs on `pull_request_target`, and review-gate's own PreToolUse `merge-guard.py` runs `check-forged-review-gate.py` on the same `gh pr merge` call. pr-guard does not re-implement that check (each component does its own job). pr-guard's only obligations: Review Gate must be present and green on the current head, and never exempted. A repo may pin it in `required-checks.json` with `workflow: .github/workflows/review-gate.yml, event: pull_request_target`. Whether `run_workflows` resolves `pull_request_target` runs to this PR (`pull_requests == [number]`, head branch match) has **not** been verified. Until a recorded run proves it, the plan recommends pinning Review Gate by `app_id` (GitHub Actions, 15368) in the file, checked against REST check-runs, or not listing it there and relying on the ruleset entry. An `app_id: 15368` pin is the weakest pin (any workflow runs as that app), so it adds presence, not provenance. review-gate's own forged-gate check supplies the provenance.

### Forged names and same-name checks

- **A same-named advisory check cannot hide a failure.** An exemption needs all three of name, workflow path and event, resolved through the run id and confirmed by the jobs API. A PR that adds `evil.yml` with a red job named `doctor` gets no exemption: it is "everything else", so it blocks, and the only person it hurts is that PR's author.
- **A check run that copies the real doctor's job URL** passes `run_jobs` (the URL names a real job with that name and conclusion) but fails check-run identity: its own `id` is not the job id, and the job id is now claimed by two check runs. Neither entry is exempt, so a red one blocks. Without this rule, any separate failing check named `doctor` could borrow the exemption.
- **A PR can edit `review-gate-doctor.yml` itself**, because `pull_request` runs the head's copy. The worst case is that the PR makes `doctor` red and that red is advisory. It cannot make any **other** check pass or disappear: other checks are judged on their own entries, and an exemption covers only the job named `doctor` in that one file. A job renamed to `doctor` in the doctor file is advisory only for itself, and the real `Test & Build` from `ci.yml` is still judged on its own.
- **A PR that deletes a test workflow** removes its entry from the rollup. Today nothing catches that unless a ruleset requires the check. With the policy file, a required entry that is missing blocks (step 4). This is the main reason constraint 1 needs a policy source: the policy file catches it.
- **A green check forged under a required name** (SEC-MVS-01's threat): a policy entry pinned by `workflow` + `event` is satisfied only by that workflow's run of this PR, so a PR-added job with the same name does not satisfy it. A Checks-API-published run with no job URL has no run id, so it satisfies no workflow pin, and one that copies a real job URL fails check-run identity. That is the same known limit `check-forged-gate-names.py` documents for `app_id` pins (anything running as the Actions app can publish under 15368). This plan does not widen that limit. The permanent fix is SEC-MVS-01's option A or B.

## Rollout (recommendation: ship enforcing, behind a per-repo opt-in)

1. **Release 1.6.0** after #131 and #132. With no policy file, every repo behaves as it does on 1.5.x, except that a forged entry can no longer supersede a real run (step 1), which only adds blocks. The parity test (`tests/test_pr_guard_parity.py`, #131) replays every test and fixture input against the previous release and fails on a lost block unless the input is listed in `ALLOWED_FLIPS` with a reason. Every input without a policy file keeps its old verdict or gains a block. The inputs that the previous release blocks and 1.6.0 allows (tests 1 and 9's advisory case) each get an `ALLOWED_FLIPS` entry naming this plan, added on purpose in the same PR, not by loosening the test.
2. **Canary:** nevar-aec-catalog (the incident repo) adds `.github/required-checks.json` listing what its owner considers required. Its traffic cop re-vendors the guard to 1.6.0. Watch one red-`doctor` merge and one required-red refusal.
3. **Shadow mode is not recommended.** The only loosening is one pinned, provenance-checked entry, and only in repos that opted in. A shadow phase would leave the incident unfixed while measuring a change that is already off by default. If the Program Cop wants shadow anyway, the cheap form: for one release, step 5's exemption logs `would allow` through the existing `fb_log` (line 909) and still blocks.
4. **Fleet:** each repo's cop adds the file in its next re-vendor PR, which is the same PR CS-DOCTOR-LATEST-RELEASE and `review-gate-stale-vendor-fleet.md` already plan per repo. There is no extra PR per repo.

## Blast radius

- **Repos with pr-merge-flow installed** (the guard is vendored or installed through `aec`): the loosening (advisory `doctor`) and the new requirements need a re-vendor to 1.6.0 **and** the policy file. Re-vendoring without the file only adds the authenticated collapse: an entry that fails check-run identity, or a failed check-runs call, stops superseding older runs. That can block a PR whose old run failed and whose new run passed, until the check-runs call succeeds on a retry. The block message says which.
- **A repo that opts in:** a red pinned `doctor` stops blocking. A required check that is missing or fails its pin starts blocking. That can surface a policy entry with a wrong pin as a false block, which is why the canary goes first. The block message names the entry and its pin, so the fix is a one-line policy PR.
- **Repos whose token cannot read the rules or protection endpoints:** fallback, the same as today, with a visible line. This is not verified for the fleet (revision 1's open question, still open). Check with the real agent token on three repos before the canary.
- **Per-merge cost:** every repo gains two calls, the paginated check-runs list (step 1) and the contents call. A repo with the policy file adds two more (rules, protection), all inside the existing `GH_BUDGET_S` deadline, where an exhausted budget is a failed lookup and so the fallback. #128 and #136 already track merge-guard call budgets. The guard's work is a separate hook, but the cop should check the combined time on the canary.

## Who owns what

| Piece | Owner |
|---|---|
| `pr-guard.py` changes, `ADVISORY_CHECKS`, deny-list test, release 1.6.0, `SKILL.md` text | claude-skills cop |
| `.github/required-checks.json` in each repo | that repo's owner, authored by its traffic cop through a reviewed PR |
| Rulesets and classic protection | the repo or org owner (Platform Ops for org rulesets) |
| `doctor` job shape, floor, migration | CS-DOCTOR-LATEST-RELEASE (claude-skills cop, then each repo's cop) |
| Review Gate provenance | review-gate (`merge-guard.py`, `check-forged-review-gate.py`) |
| Org-level default policy (if ever) | Matt (open decision above) |

## Tests (real `check()` and `not_green()` against `statusCheckRollup` fixtures)

The suite follows the repo's rule: no mocks of what we own. `check()`, `not_green()`, the policy parser and the collapse logic run for real. Only `gh` (third-party) is replaced by a fixture-replaying stub. Every fixture is a recorded real response, trimmed but not hand-invented: rollup, `actions/runs`, `actions/runs/<id>/jobs`, `rules/branches`, `branches/<b>/protection/required_status_checks`, `commits/<sha>/check-runs`, and `contents/.github/required-checks.json`. One validation test diffs the stub's field set against a fresh recording, so the stub cannot drift from GitHub's shape.

1. **The incident (nevar-aec-catalog #14 shape):** the ruleset requires `Review Gate`, which is green; the policy file is `{"schema":1,"required":[]}`; the pinned `doctor` is FAILURE. Allowed, and the output names `doctor` as advisory.
2. **No policy file:** same rollup, file 404. Blocked, as on 1.5.4, with the "lookup unavailable … all-green rule" line.
3. **Arbitrary non-required red still blocks:** `Test & Build` FAILURE, not required anywhere, policy file present. Blocked. The same for `Security Scan` and CodeQL.
4. **Forged advisory:** a red job named `doctor` from `.github/workflows/evil.yml`. Blocked. The same from the right path with event `push`: blocked. A separate red check run named `doctor` whose `details_url` copies the real doctor job's URL (so `run_jobs` confirms it), with its own check-run id: blocked, and the real doctor entry loses its exemption too.
4a. **Forged supersede (every mode, with and without the policy file):** an older run's green `Test & Build` URL copied onto a forged check run with a later `startedAt`, while the newer real run of that job failed. Blocked: the forged entry fails identity, so it supersedes nothing and the real failure stays. The same with the check-runs call failing: nothing collapses, and the older failed run blocks.
5. **Advisory but required:** `doctor` listed in a ruleset (or in the policy file) and red. Blocked.
6. **Required missing:** the policy file requires `Test & Build` (pinned to `ci.yml` / `pull_request`), and the rollup has no such entry. Blocked: `required check Test & Build is MISSING on <sha>`.
7. **Required pin not satisfied:** a green `Test & Build` from a PR-added `other.yml`. Blocked. A green check run whose REST `app.id` differs from the pinned `app_id`: blocked. A green status context with the required name and an `app_id` pin: blocked as `MISSING` (status contexts are unsupported in schema 1). A green check run with the right app id: allowed.
8. **Required pending, cancelled, skipped or neutral:** blocked each time, and the message names the state. A matrix where one `Test & Build` job is `SUCCESS` and a sibling with the same name in the same run is `SKIPPED`: blocked, naming the skipped one. `SKIPPED` and `NEUTRAL` are the cases where `green()` and `required_ok` differ, so each has its own test.
9. **Superseded run:** an older failed run of a required job and a newer green run of the same workflow. Allowed. An older failed `doctor` run and a newer one also failed: advisory, allowed.
10. **Lookup failures fall back, one test per case 4a-4i of revision 1, plus a failed check-runs call:** each one blocks on a red pinned `doctor`, with the lookup line, and allows when everything is green.
10a. **A partial failure keeps resolved requirements:** the rules call fails, the policy file resolves and requires `Test & Build`, every reported entry is green, and `Test & Build` is absent. Blocked, naming `Test & Build` as `MISSING`, plus the lookup line. The reverse (file unreadable, ruleset resolves and requires a missing `Review Gate`): blocked, naming `Review Gate`.
11. **Malformed policy:** unknown schema, an entry without a pin, an unknown key, conflicting duplicates. Each is a failed lookup, so the fallback applies and the message names the file and the problem.
12. **Output channel:** the advisory line reaches the model on an **allowed** merge. Before promising this, establish against the harness whether exit-0 stdout or stderr is shown, or whether it must go out as `hookSpecificOutput.additionalContext` JSON (revision 1's test 10, still open: verify, do not assume).
13. **No bypass:** `# advisory-ok:`, `# codex-review-ok:`, `# sync-base:` and any environment variable leave tests 3-8 blocked.
14. **Deny-list:** `ADVISORY_CHECKS` contains no `Review Gate`, `Security Scan`, or name matching `test|build|codeql|security`.
15. **Unchanged rules:** `--admin`, `--auto`, the missing `--match-head-commit` SHA, the Codex mention and the polling rules block exactly as on 1.5.4. The #131 parity test passes, with `ALLOWED_FLIPS` entries only for the allowed advisory cases (rollout step 1).
16. **Policy source is the default branch:** a PR into a contributor-created base branch whose copy of the file is `{"schema":1,"required":[]}`, while the default branch requires `Test & Build`, which is missing. Blocked. The stub asserts the contents call carries no `ref`, so neither the base nor the head copy is ever read.

## Acceptance criteria

- 1.6.0 is released with tests 1-16 green in CI, and `SKILL.md` + `hooks.json` agree on the version. The release note says: without `.github/required-checks.json`, the only change is the authenticated collapse, which can only block more; with it, only the pinned `doctor` may be red, and listed checks must be present.
- nevar-aec-catalog has the policy file and the 1.6.0 guard. A PR there with a red `doctor` and green `Review Gate` merges through the cop with the advisory line visible, and a PR with a red required check is refused.
- `SKILL.md` has one section, "What blocks a merge", that covers the three kinds of check, the policy file and its schema, the advisory list and who can change it, and the fallback.
- Revision 1's file carries the "superseded by" line, and the Tracker row points at this plan.

## P2 / P3

- P2: Each repo owner decides whether `.github/required-checks.json` gets a CODEOWNERS entry.
- P2: `aec doctor` (or `review-gate doctor`) WARNs when a repo has the guard at 1.6.0+ but no policy file, so opting in is not left to memory (rung 3). That is a new check in another skill, so it gets a plan of its own when it is picked up.
- P2: Support status contexts in the policy file, pinned by the statuses API `creator` login, if a repo needs one. Until then such an entry fails closed.
- P2: Verify that `run_workflows` resolves `pull_request_target` runs to the PR, or document `app_id` as the only supported pin for Review Gate.
- P3: Compare `headRefOid` with the `--match-head-commit` SHA in the guard and give a clear message, instead of relying on `gh` to refuse a moved head.
- P3: Use GraphQL `isRequired` as a cross-check against the computed required set, and log disagreement through `fb_log`.
- P3: Read `mergeStateStatus` (fetched and unused today) as a corroborating signal in the block message.
- P3: Decide on an org-level default policy (Matt's open decision above).

## Not in scope

Changing any ruleset. Making `doctor` required anywhere. The doctor job's own drift and its migration (CS-DOCTOR-LATEST-RELEASE). Review Gate's forged-check logic (SEC-MVS-01, #128, #136). The tokenizer (#124, #139). Editing #131 or #132.
