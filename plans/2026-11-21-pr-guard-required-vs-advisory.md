# pr-merge-flow guard: block a merge only on required checks, warn on advisory ones

Status: planned. Plan id: CS-PRGUARD-REQUIRED-VS-ADVISORY. Proposed priority: P1 (it refuses merges that GitHub itself would allow, in every repo with an advisory check). The PM scheduled task sets the final tier. Owner: the claude-skills cop (`pr-merge-flow`). Tracker: https://app.notion.com/p/CS-PRGUARD-REQUIRED-VS-ADVISORY-pr-merge-flow-guard-blocks-only-on-the-ruleset-s-required-checks-a-41f4efecc95a81d0b22cd96bbf51034d (Owner Needs-PM). Related: `2026-11-21-doctor-latest-release-coupling.md` (why `doctor` went red), `pr-guard-rollup-and-auto-message.md` (the rollup reading this plan extends), `pr-guard-shell-parsing-design.md` and open PR #139 (tokenizer-first guard; a different part of the same file).

## What happened

nevar-mail #1129 was green on every required check and the guard refused its merge at 10:59Z on 2026-11-21 (ops log: bernierllc/nevar-platform-ops issue 1, comment 7061595772). The only red check was the advisory `doctor` job (`review-gate-doctor.yml`), which the repo does not require. GitHub would have merged the PR; the guard would not, and offers no override for it.

## Root cause

Verified in `pr-merge-flow/scripts/pr-guard.py` at origin/main (1.5.4):

- `not_green()` (line 728) reads `gh pr view --json statusCheckRollup,…` (line 741) and builds the list of checks that are not green. It collapses superseded runs by workflow path and job name so a newer run replaces an older one, and then treats every remaining entry the same way. There is no notion of which checks the branch requires.
- `check()` (line 818) blocks `gh pr merge` when that list is non-empty. The only overrides in the file are `# codex-review-ok: <reason>` (line 833, for the Codex mention rule) and `# sync-base: <reason>` (line 874, for the base-merge rule). Neither applies to a red check, so a red advisory check has no way through.
- The guard is a PreToolUse hook, and a hook blocks only on exit 2, so a wrong block is final for the agent that hit it.

The guard is doing what it was written to do ("all checks green before merge"). The defect is that "all checks" is the wrong set: the repo's rules say which checks gate a merge, and the guard does not read them. Any advisory check that can go red (`doctor`, a lint-only job, a coverage reporter) can therefore stop merges the repo has chosen to allow. This is not a defect of the doctor job: an advisory check that fails is allowed to fail.

## Fix

1. **Resolve the required set as the UNION of every source that applies to the base branch, not from the rollup.** Use the incumbent GitHub API, not a hand-kept list in the skill. Both sources can apply at once and GitHub layers them ([about rule layering](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets#about-rule-layering)), so the guard reads both and unions them; classic protection is never read "only when no ruleset exists":
   - **Branch rulesets:** `gh api --paginate repos/{owner}/{repo}/rules/branches/{base}` returns the rules that apply to the base branch, including each `required_status_checks` rule's contexts (each with an optional `integration_id`). The endpoint is paginated; all pages are read.
   - **Classic branch protection:** `gh api repos/{owner}/{repo}/branches/{base}/protection/required_status_checks` (its `checks` entries carry `context` and `app_id`; the older `contexts` list has no app).
   - **Union key:** `(context, integration_id)`, with `integration_id` absent meaning "any app". A context required by either source is required. The same context with different app pins in two sources is two requirements, and both must be satisfied.
   The `review-gate` doctor already reads rulesets, so the lookup shape and its token-permission failure mode exist in this repo; reuse them rather than writing a second reader (the claude-skills cop confirms which helper, and says so if none can be shared).
2. **Block on any required context that is not green, including one that is absent.** A required context with no entry in the rollup is not green: a required check that never ran, or whose run is not in the rollup, blocks, as it does on GitHub. Reproduced by the reviewer on 1.5.4: the real `not_green()` given only `lint: SUCCESS` and `mergeStateStatus` BLOCKED returns `''` (allow), although a required context could be missing from the rollup. The guard must not infer "all required checks passed" from "every reported check is green". Matching is by the check's context name, which for a job is its job name; where a source pins `integration_id` (ruleset) or `app_id` (classic), match on it too, so a forged check of the same name from another app does not satisfy the requirement (see CS-GUARD-DETECTOR-COUPLING and the forged-check guard in the main promotion workflow for the same concern).
3. **Advisory red is a warning, not a block.** Every entry that is not in the union and is not green is printed as `warning: advisory check <name> is <state>; not blocking (not a required check)`. Naming the check is the point: the red stays visible to the agent and the human, and nobody has to guess why the merge was allowed.
4. **Fail CLOSED when the required set cannot be fully determined. There is no fallback to "every reported check is green".** If any of the following happens, the merge is blocked unconditionally, even when every reported check is green, and the block message names what could not be read and why (`could not read required checks: <endpoint> <status or error>`):
   - an API error or non-zero `gh` exit (network, timeout, rate limit);
   - 403, or a 404 that is not the documented "Branch not protected" response, on either the rules endpoint or the protection endpoint (a 404 whose body says the branch is not protected is a successful "no classic protection" answer; confirm that body against a recorded real response before relying on it);
   - a truncated or paginated result that was not read to the end (an unreadable next page, a page limit hit);
   - malformed or unparseable JSON, or a response missing the fields the reader needs;
   - an empty required set where a non-empty one is expected (the rules endpoint reports a `required_status_checks` rule but with no contexts; the protection endpoint answers but the set is empty while a ruleset rule exists);
   - a status-check rollup that cannot be confirmed complete (more entries than the single read returned).
   The only case that keeps the old behaviour is a fully successful read of both sources that finds no `required_status_checks` rule at all: the repo has chosen no gate, so the guard stays as strict as today (every reported check must be green). That is a determined answer, not a failed lookup.
5. **No bypass flag.** No `# advisory-ok:` marker and no environment variable. The only way to make a red check non-blocking is to not require it in the repo's rules, which is the repo owner's decision and is reviewable. This is the "Remembering is a failure mode" rung 1 answer: the rule is derived from state the tooling already reads, so nobody has to remember an override.
6. **The other guard rules do not change**: `--admin`, `--auto`, the missing `--match-head-commit` SHA, the Codex mention rule and the base-sync rule keep their current behavior.

### Interaction with open PRs

- **#131 (`skip parity outside claude-skills, honor tool_input.dir_path`) and #132 (`env -S strings with $ or escapes fail closed`)** both edit `pr-guard.py`, `hooks.json`, `SKILL.md`, the tests and `skills-manifest.json`, and both bump the skill to 1.5.5, so those two already conflict with each other on version and manifest lines. They are not edited by this plan. This change should land after both, as 1.5.6 or later, rebased on their result, so it does not add a third 1.5.5 claim. It touches `not_green()` and the merge branch of `check()`, which neither PR rewrites; the expected conflicts are the version and manifest lines only.
- **#131's parity test** (`tests/test_pr_guard_parity.py`) replays every test and fixture input against the previous release read from this repo's `origin/main` history and compares source baseline with head; it does not compare an installed guard with the skill's copy, and #131 makes it skip outside claude-skills. This plan's change is a deliberate behavior change (advisory red now allows a merge), so it must update or extend that baseline comparison on purpose rather than rely on it staying green; the test's "lost block" check will flag the advisory-red case and needs an explicit, reviewed exception for it. A repo that vendors `pr-guard.py` picks up the change only when it re-vendors, which is the normal vendoring flow; the release note must say the new version changes what the guard blocks.
- **#139 (tokenizer-first plan)** moves command parsing in the same file. The two changes are independent in behavior; whoever lands second rebases.

## Affected surfaces

- `pr-merge-flow/scripts/pr-guard.py` (`not_green`, the merge branch of `check`, new rules-reader), `pr-merge-flow/hooks.json` and `SKILL.md` (version, behavior description, the "never `--auto`" text is unchanged), `skills-manifest.json`, `pr-merge-flow/tests/`.
- `review-gate` doctor: only if the rules reader is shared (a refactor owned by the claude-skills cop, not required by this plan).
- Every repo that vendors the guard: no config change; behavior changes when the repo re-vendors. A repo with an advisory-only red check starts merging; a repo with a required red check still cannot.
- Documentation: `pr-merge-flow/SKILL.md` gets one paragraph, "What blocks a merge: required contexts, warnings for the rest, fail closed when unreadable".
- Policy follow-up (not this plan): each repo records which checks are required in its branch rules; `doctor` stays advisory unless its owner makes it required.

## Tests that pin the behaviour

Tests run the real `check()` against a stubbed `gh` (third-party), with the stub validated against recorded real API responses so the mock matches reality.

1. **The incident:** rollup has all required contexts green and `doctor` FAILURE, `doctor` not in the required set: merge allowed, output contains `warning: advisory check doctor is FAILURE`.
2. **Required red blocks:** a required context red (and the same with PENDING, CANCELLED, SKIPPED): blocked, message names the check.
2a. **Required context absent from the rollup blocks:** the rollup has only `lint: SUCCESS` and `mergeStateStatus` BLOCKED, and `build` is required: blocked, message names `build` as required and missing. This is the reviewer's reproduction of `not_green()` returning `''`; it must now block.
3. **Superseded run:** an older failed run of a required job followed by a newer green run: allowed (the existing collapse still applies to the required set).
4. **Unreadable discovery fails closed, one line per case.** Each case below blocks even when every reported check is green, and the message names the endpoint and the reason; none falls back to the all-green rule:
   - 4a. the rules call exits non-zero (network or `gh` error);
   - 4b. the rules call returns 403;
   - 4c. the rules call returns a 404 that is not "Branch not protected";
   - 4d. the protection call returns 403;
   - 4e. the protection call returns a 404 that is not "Branch not protected";
   - 4f. either call returns invalid JSON or a body missing the expected fields;
   - 4g. the rules result is paginated and a later page fails or is not read (truncated);
   - 4h. a `required_status_checks` rule is present but lists no contexts (empty where non-empty is expected);
   - 4i. the status-check rollup cannot be confirmed complete.
5. **Determined "no gate":** both sources read successfully and neither has a `required_status_checks` rule (the protection call returns the documented "Branch not protected" 404): the old all-green rule applies, so a red advisory check still blocks. This is the one case that keeps the old behavior, and it is a successful read, not a failure.
6. **Same-name forged check:** a required context satisfied only by a check from a different `integration_id` (ruleset) or `app_id` (classic) than the source pins: blocked.
7. **Mixed protection (union):** a ruleset requires `A`, classic protection requires `B`, and `C` is required by neither.
   - 7a. `B` (classic only) failing: blocked, message names `B`.
   - 7b. `A` (ruleset only) failing: blocked, message names `A`.
   - 7c. `C` (advisory only) failing with `A` and `B` green: allowed with the warning for `C`.
   - 7d. A ruleset-only repo and a classic-only repo each pass the assertions of 1 and 2.
   - 7e. The same context pinned to different apps in the two sources: both pins must be satisfied; a check satisfying only one blocks.
8. **No bypass:** a command carrying `# advisory-ok: x`, `# codex-review-ok: x` or `# sync-base: x` does not make a red required check pass, and no environment variable changes the result.
9. **Unchanged rules:** `--admin`, `--auto`, the missing `--match-head-commit` SHA and the Codex mention rule block exactly as before (the existing parity and fixture tests keep passing).
10. **Warning channel:** a test asserts the warning text reaches the model on an allowed merge, not only on a block. The PreToolUse hook contract only carries stderr to the agent on exit 2 and may not surface exit-0 output; this must be established against the harness before the behavior in item 3 of the fix is promised. If exit-0 output is dropped, the allowed-merge warning moves to `permissionDecisionReason` or `additionalContext` JSON on stdout, whichever the harness documents (verify, do not assume).

## Open questions for the claude-skills cop (do not block the plan)

- Token permission, **unverified**: I did not verify what the agent session's token can read. The branch rules endpoint (`rules/branches`) is documented as needing Metadata: read, and classic protection's `required_status_checks` endpoint as needing Administration: read; whether the agent token holds either on every repo in the fleet is not established. A 403 therefore hits the fail-closed rule (fix item 4, tests 4b and 4d), which blocks every merge in a repo whose token cannot read the rules. Check both endpoints with the real agent token on a sample of repos before this ships, because a token that cannot read them turns this change from "fewer false blocks" into "every merge blocked".
- The warning channel (test 10).
- Whether `doctor` should be required anywhere: the repo owner's call, out of scope here.

## Done when

- Replaying nevar-mail #1129's rollup shape through the released guard allows the merge with the `doctor` warning; a required red still blocks.
- The behaviors above are pinned by tests 1 to 10 and pass in CI.
- `pr-merge-flow/SKILL.md` and `hooks.json` agree on the new version, and the release note says the guard now follows the repo's required checks.
- The ops-log incident (nevar-platform-ops issue 1, comment 7061595772) is answered with the release version.

## Not in scope

Making any check required or advisory in a repo (branch-rule owners). The `doctor` job's red-on-release defect (`2026-11-21-doctor-latest-release-coupling.md`). The guard's shell parsing (`pr-guard-shell-parsing-design.md`, #139). Editing #131 or #132.
