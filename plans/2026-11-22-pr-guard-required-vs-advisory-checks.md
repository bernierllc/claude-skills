# pr-merge-flow guard: required checks must pass, only pinned advisory checks may be red

Status: planned, no code. Plan id: CS-PRGUARD-REQUIRED-VS-ADVISORY (revision 2). **Supersedes the fix design in `2026-11-21-pr-guard-required-vs-advisory.md`** (revision 1, merged in #143). Revision 1 stays in the repo for history, and its research (endpoints, union key, fail-closed cases, open-PR ordering) is reused below. Proposed priority: P1. The PM scheduled task sets the final tier. Owner: the claude-skills cop (`pr-merge-flow`). Tracker: https://app.notion.com/p/CS-PRGUARD-REQUIRED-VS-ADVISORY-pr-merge-flow-guard-blocks-only-on-the-ruleset-s-required-checks-a-41f4efecc95a81d0b22cd96bbf51034d (revision 1's row, updated to point here; Owner Needs-PM).

## Why a revision and not a new plan

Revision 1 already plans this fix, so this file replaces its design and keeps one plan id and one Tracker row. The Program Cop set binding constraints on 2026-11-22. Revision 1 breaks two of them:

| Program Cop constraint | Revision 1 | Revision 2 |
|---|---|---|
| 1. The required set is the ruleset requirements UNION the repo's own policy | Ruleset UNION classic protection only. A test that the repo requires but GitHub does not is invisible. | Adds a repo policy file, read from the base branch (below). |
| 3. A failed lookup never means "none required" | Blocks on every failure | Falls back to today's all-green rule (see "Lookup fails"). Either answer is allowed, and this plan says why it picks the fallback. |
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

1. **Required** = ruleset-required UNION classic-required UNION repo-policy-required (keyed `(context, app or pin)`, as in revision 1). Each one must be present on the current head, satisfy its pin, and be green.
2. **Advisory** = an entry that matches the **pinned advisory list** shipped in `pr-guard.py`, is not in the required set, and passes provenance. It may be red or pending. The guard prints it, and it never blocks.
3. **Everything else** = must be green, exactly as today. This is the default, and it is what keeps a red `Test & Build`, CodeQL or Security Scan blocking even where no rule requires it (constraint 4).

So the guard loosens in exactly one place, a red advisory-list entry. It tightens in one place, a required check that is missing or fails its pin.

### Where repo policy lives: `.github/required-checks.json`

- **Location:** a committed JSON file at `.github/required-checks.json`, read **from the base branch**: `gh api repos/{o}/{r}/contents/.github/required-checks.json?ref=<baseRefName>`, using the PR's own host and repo, as `_api_lines` already does. The guard never reads the PR head's copy, so a PR cannot loosen its own gate. A change to the file reaches the base only through a reviewed PR that passed Review Gate, which is the same trust a workflow file has. The name states its domain (deliberate-naming rule). JSON, because the guard is stdlib-only.
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

  Each entry has a `name` (the check's context, which for an Actions job is the job name). It also has exactly one pin: `workflow` + `event`, for an Actions job matched through the existing `run_workflows`/`run_jobs` provenance, or `app_id`, for a third-party check run or status context. An entry without a pin is malformed. An unknown key, an unknown `schema`, or a duplicate name with conflicting pins is malformed.
- **The file can only add requirements.** It has no `advisory` key and no way to exempt anything. A repo cannot make `Test & Build` advisory by editing it (constraint 4). Making something advisory is a claude-skills change (next section).
- **Owner:** each repo's owner. The repo's traffic cop authors the PR, and Review Gate on the base branch approves it. Adding CODEOWNERS on the file is a P2 option for each repo owner and is not required here.
- **Absent file:** the repo has not opted in. The guard keeps today's behavior: every reported check must be green, and there is no advisory exemption. This is constraint 3 ("missing policy file never means none required"), and it is also the rollout switch (see "Rollout"). A repo with no extra requirements opts in with `{"schema": 1, "required": []}`.
- **Open decision for Matt (recommendation given, does not block the plan):** whether an org-level default should exist later (for example a `bernierllc/.github` repo file that every repo inherits). Recommendation: **no**, not now. A per-repo file on the base branch is reviewable by the people who merge there, and org inheritance adds a second trust root and a second lookup that can fail. Revisit after the fleet has opted in.

### The pinned advisory list (owner: the claude-skills cop)

- A constant in `pr-guard.py`, `ADVISORY_CHECKS`. Each entry is a full pin `(job name, workflow path, event)`. It starts with exactly one entry:

  `("doctor", ".github/workflows/review-gate-doctor.yml", "pull_request")`

  The values are taken from `review-gate/templates/review-gate-doctor.yml` (job `doctor`, `on: pull_request`). The installer writes that file to exactly that path.
- **What makes `doctor` advisory:** (a) it is on this list; (b) no ruleset, classic rule or repo policy requires it. If any source requires it, required wins and a red `doctor` blocks, because that repo chose to make it a gate. (c) It is a read-only consistency report with no token and no secrets (template header, line 13). Its red means "this repo's vendored copy has drifted", which is a maintenance signal for the repo's cop, not a defect in the PR.
- **How `doctor` is pinned:** in the guard, by the triple above plus provenance. Only an entry whose run id resolves through `run_workflows` to that path and event for THIS PR, and whose job id `run_jobs` confirms with the same name and conclusion, counts as advisory. In the repo, the doctor's code is the repo's own vendored `.claude/skills/review-gate` copy, at the version committed on the PR's merge ref (3.2.19+ no-clone job). CS-DOCTOR-LATEST-RELEASE adds the declared floor file. The old clone-main job (nevar-aec-catalog today) is **not** pinned in that sense: it runs claude-skills `main`. The guard's pin still applies to it because path, event and job name are unchanged, so the guard stops it from blocking merges. The migration in CS-DOCTOR-LATEST-RELEASE is what removes the drift itself.
- **Adding an entry** is a claude-skills PR labelled `review:high` that names the detector and why it is advisory by design. Every entry must be a drift or consistency report, never a test, build, lint, security or review check. A test in `pr-merge-flow/tests/` fails if `ADVISORY_CHECKS` contains a name on a deny-list (`Review Gate`, `Security Scan`, names containing `test`, `build`, `codeql`, `security`). The deny-list makes an accidental addition fail loudly (rung 3).

### Evaluation, step by step (current head only)

1. `gh pr view` as today, adding `baseRefName` to the `--json` fields. The rollup is the PR's **current** head. Collapsing superseded runs (lines 766-784) is unchanged. Provenance (`run_workflows`, `run_jobs`) is unchanged and not weakened.
2. Read the requirement set: rules endpoint (all pages), classic protection endpoint, and the policy file at `baseRefName`.
3. **If any of the three lookups fails, or the policy file is absent, stop here and apply today's rule:** every entry in `latest` must be green. The block message adds one line: `required-check lookup unavailable: <source> <status or error>; using the all-green rule`.
4. Otherwise, for each required key: look for an entry in `latest` that has the name, satisfies the pin (app id, or workflow path + event through provenance), and is green. If none exists, block with `required check <name> is <MISSING|PENDING|FAILURE|…> on <head sha>`. A required entry whose provenance cannot be resolved (no run id, a jobs API failure, an exhausted budget) does not satisfy its pin, which fails closed.
5. For each entry in `latest` that is not green: if it matches `ADVISORY_CHECKS` (name + path + event through provenance) and is not required, record it as advisory. Otherwise, block, exactly as today.
6. Allowed with advisory entries: the guard prints `advisory check doctor is FAILURE (pinned advisory: .github/workflows/review-gate-doctor.yml); not blocking`. The cop must see it, so the output channel is an open item (test 12). When a merge is blocked, the block message lists the advisory entries as well, each labelled advisory, so whoever reads it sees all of them.

### Lookup fails: why the fallback is today's rule and not a block

Revision 1 blocked every merge when a lookup failed. Both answers satisfy constraint 3. This plan falls back because:

- The fallback is **never looser than today**. It adds no exemption, so a failed lookup cannot hide a red check.
- Revision 1's own open question was that a token without Administration: read on the classic endpoint would block **every merge in every repo**. The fallback turns that into "the advisory exemption is off", which is visible in the block message.
- What it gives up: on a failed lookup, a required check that is missing from the rollup is not detected. That is today's behavior, and today's ruleset still enforces it at merge time on GitHub's side.

Revision 1's failure cases 4a-4i (exit codes, 403, a 404 that is not "Branch not protected", truncated pagination, malformed JSON, a rule with an empty context list, a rollup that cannot be confirmed complete) all map to step 3. The documented "Branch not protected" 404 on the classic endpoint is a successful empty answer, as revision 1 says. Confirm it against a recorded real response.

### Review Gate

- `Review Gate` is never advisory: it is on the deny-list above, so it can never be added to `ADVISORY_CHECKS`. In the nevar fleet it is ruleset-required, so step 4 requires it.
- Its provenance belongs to review-gate. The gate runs on `pull_request_target`, and review-gate's own PreToolUse `merge-guard.py` runs `check-forged-review-gate.py` on the same `gh pr merge` call. pr-guard does not re-implement that check (each component does its own job). pr-guard's only obligations: Review Gate must be present and green on the current head, and never exempted. A repo may pin it in `required-checks.json` with `workflow: .github/workflows/review-gate.yml, event: pull_request_target`. Whether `run_workflows` resolves `pull_request_target` runs to this PR (`pull_requests == [number]`, head branch match) has **not** been verified. Until a recorded run proves it, the plan recommends pinning Review Gate by `app_id` (GitHub Actions, 15368) in the file, or not listing it there and relying on the ruleset entry.

### Forged names and same-name checks

- **A same-named advisory check cannot hide a failure.** An exemption needs all three of name, workflow path and event, resolved through the run id and confirmed by the jobs API. A PR that adds `evil.yml` with a red job named `doctor` gets no exemption: it is "everything else", so it blocks, and the only person it hurts is that PR's author.
- **A PR can edit `review-gate-doctor.yml` itself**, because `pull_request` runs the head's copy. The worst case is that the PR makes `doctor` red and that red is advisory. It cannot make any **other** check pass or disappear: other checks are judged on their own entries, and an exemption covers only the job named `doctor` in that one file. A job renamed to `doctor` in the doctor file is advisory only for itself, and the real `Test & Build` from `ci.yml` is still judged on its own.
- **A PR that deletes a test workflow** removes its entry from the rollup. Today nothing catches that unless a ruleset requires the check. With the policy file, a required entry that is missing blocks (step 4). This is the main reason constraint 1 needs a policy source: the policy file catches it.
- **A green check forged under a required name** (SEC-MVS-01's threat): a policy entry pinned by `workflow` + `event` is satisfied only by that workflow's run of this PR, so a PR-added job with the same name does not satisfy it. A Checks-API-published run with no job URL has no run id, so it satisfies no workflow pin. That is the same known limit `check-forged-gate-names.py` documents for `app_id` pins (anything running as the Actions app can publish under 15368). This plan does not widen that limit. The permanent fix is SEC-MVS-01's option A or B.

## Rollout (recommendation: ship enforcing, behind a per-repo opt-in)

1. **Release 1.6.0** after #131 and #132. With no policy file, every repo behaves exactly as it does on 1.5.x. Revision 1's parity test (`tests/test_pr_guard_parity.py`, from #131) stays green for every repo without the file. The new behavior only exists behind the file, and new tests pin it.
2. **Canary:** nevar-aec-catalog (the incident repo) adds `.github/required-checks.json` listing what its owner considers required. Its traffic cop re-vendors the guard to 1.6.0. Watch one red-`doctor` merge and one required-red refusal.
3. **Shadow mode is not recommended.** The only loosening is one pinned, provenance-checked entry, and only in repos that opted in. A shadow phase would leave the incident unfixed while measuring a change that is already off by default. If the Program Cop wants shadow anyway, the cheap form: for one release, step 5's exemption logs `would allow` through the existing `fb_log` (line 909) and still blocks.
4. **Fleet:** each repo's cop adds the file in its next re-vendor PR, which is the same PR CS-DOCTOR-LATEST-RELEASE and `review-gate-stale-vendor-fleet.md` already plan per repo. There is no extra PR per repo.

## Blast radius

- **Repos with pr-merge-flow installed** (the guard is vendored or installed through `aec`): nothing changes until a repo re-vendors 1.6.0 **and** commits the policy file. Re-vendoring without the file changes nothing in behavior.
- **A repo that opts in:** a red pinned `doctor` stops blocking. A required check that is missing or fails its pin starts blocking. That can surface a policy entry with a wrong pin as a false block, which is why the canary goes first. The block message names the entry and its pin, so the fix is a one-line policy PR.
- **Repos whose token cannot read the rules or protection endpoints:** fallback, the same as today, with a visible line. This is not verified for the fleet (revision 1's open question, still open). Check with the real agent token on three repos before the canary.
- **Per-merge cost:** up to three extra `gh api` calls, inside the existing `GH_BUDGET_S` deadline, where an exhausted budget is a failed lookup and so the fallback. #128 and #136 already track merge-guard call budgets. The guard's work is a separate hook, but the cop should check the combined time on the canary.

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

The suite follows the repo's rule: no mocks of what we own. `check()`, `not_green()`, the policy parser and the collapse logic run for real. Only `gh` (third-party) is replaced by a fixture-replaying stub. Every fixture is a recorded real response, trimmed but not hand-invented: rollup, `actions/runs`, `actions/runs/<id>/jobs`, `rules/branches`, `branches/<b>/protection/required_status_checks`, and `contents/.github/required-checks.json`. One validation test diffs the stub's field set against a fresh recording, so the stub cannot drift from GitHub's shape.

1. **The incident (nevar-aec-catalog #14 shape):** the ruleset requires `Review Gate`, which is green; the policy file is `{"schema":1,"required":[]}`; the pinned `doctor` is FAILURE. Allowed, and the output names `doctor` as advisory.
2. **No policy file:** same rollup, file 404. Blocked, as on 1.5.4, with the "lookup unavailable … all-green rule" line.
3. **Arbitrary non-required red still blocks:** `Test & Build` FAILURE, not required anywhere, policy file present. Blocked. The same for `Security Scan` and CodeQL.
4. **Forged advisory:** a red job named `doctor` from `.github/workflows/evil.yml`. Blocked. The same from the right path with event `push`: blocked.
5. **Advisory but required:** `doctor` listed in a ruleset (or in the policy file) and red. Blocked.
6. **Required missing:** the policy file requires `Test & Build` (pinned to `ci.yml` / `pull_request`), and the rollup has no such entry. Blocked: `required check Test & Build is MISSING on <sha>`.
7. **Required pin not satisfied:** a green `Test & Build` from a PR-added `other.yml`. Blocked. A green status context from the wrong `app_id`: blocked.
8. **Required pending, cancelled or skipped:** blocked each time, and the message names it.
9. **Superseded run:** an older failed run of a required job and a newer green run of the same workflow. Allowed. An older failed `doctor` run and a newer one also failed: advisory, allowed.
10. **Lookup failures fall back, one test per case 4a-4i of revision 1:** each one blocks on a red pinned `doctor`, with the lookup line, and allows when everything is green.
11. **Malformed policy:** unknown schema, an entry without a pin, an unknown key, conflicting duplicates. Each is a failed lookup, so the fallback applies and the message names the file and the problem.
12. **Output channel:** the advisory line reaches the model on an **allowed** merge. Before promising this, establish against the harness whether exit-0 stdout or stderr is shown, or whether it must go out as `hookSpecificOutput.additionalContext` JSON (revision 1's test 10, still open: verify, do not assume).
13. **No bypass:** `# advisory-ok:`, `# codex-review-ok:`, `# sync-base:` and any environment variable leave tests 3-8 blocked.
14. **Deny-list:** `ADVISORY_CHECKS` contains no `Review Gate`, `Security Scan`, or name matching `test|build|codeql|security`.
15. **Unchanged rules:** `--admin`, `--auto`, the missing `--match-head-commit` SHA, the Codex mention and the polling rules block exactly as on 1.5.4. The #131 parity test passes for every fixture without a policy file.

## Acceptance criteria

- 1.6.0 is released with tests 1-15 green in CI, and `SKILL.md` + `hooks.json` agree on the version. The release note says: no behavior change without `.github/required-checks.json`; with it, only the pinned `doctor` may be red, and listed checks must be present.
- nevar-aec-catalog has the policy file and the 1.6.0 guard. A PR there with a red `doctor` and green `Review Gate` merges through the cop with the advisory line visible, and a PR with a red required check is refused.
- `SKILL.md` has one section, "What blocks a merge", that covers the three kinds of check, the policy file and its schema, the advisory list and who can change it, and the fallback.
- Revision 1's file carries the "superseded by" line, and the Tracker row points at this plan.

## P2 / P3

- P2: Each repo owner decides whether `.github/required-checks.json` gets a CODEOWNERS entry.
- P2: `aec doctor` (or `review-gate doctor`) WARNs when a repo has the guard at 1.6.0+ but no policy file, so opting in is not left to memory (rung 3). That is a new check in another skill, so it gets a plan of its own when it is picked up.
- P2: Verify that `run_workflows` resolves `pull_request_target` runs to the PR, or document `app_id` as the only supported pin for Review Gate.
- P3: Compare `headRefOid` with the `--match-head-commit` SHA in the guard and give a clear message, instead of relying on `gh` to refuse a moved head.
- P3: Use GraphQL `isRequired` as a cross-check against the computed required set, and log disagreement through `fb_log`.
- P3: Read `mergeStateStatus` (fetched and unused today) as a corroborating signal in the block message.
- P3: Decide on an org-level default policy (Matt's open decision above).

## Not in scope

Changing any ruleset. Making `doctor` required anywhere. The doctor job's own drift and its migration (CS-DOCTOR-LATEST-RELEASE). Review Gate's forged-check logic (SEC-MVS-01, #128, #136). The tokenizer (#124, #139). Editing #131 or #132.
