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

1. **Resolve the required set from the branch's rules, not from the rollup.** Use the incumbent GitHub API, not a hand-kept list in the skill: `gh api repos/{owner}/{repo}/rules/branches/{base}` returns the rules that apply to the base branch from rulesets, including each `required_status_checks` rule's contexts. Where the repo uses classic branch protection instead, read `repos/{owner}/{repo}/branches/{base}/protection/required_status_checks`. The `review-gate` doctor already reads rulesets, so the lookup shape and its token-permission failure mode exist in this repo; reuse them rather than writing a second reader (the claude-skills cop confirms which helper, and says so if none can be shared).
2. **Block only on a required context that is not green.** A required context with no entry in the rollup is not green (a required check that never ran blocks, as it does on GitHub). Matching is by the check's context name, which for a job is its job name; where a ruleset pins `integration_id`, match on it too, so a forged check of the same name from another app does not satisfy the requirement (see CS-GUARD-DETECTOR-COUPLING and the forged-check guard in the main promotion workflow for the same concern).
3. **Advisory red is a warning, not a block.** Every non-required entry that is not green is printed as `warning: advisory check <name> is <state>; not blocking (not a required check)`. Naming the check is the point: the red stays visible to the agent and the human, and nobody has to guess why the merge was allowed.
4. **Fail closed when the required set cannot be resolved.** A rules lookup that errors (no permission, network, malformed JSON), or that returns an empty required set for a branch the repo protects, falls back to the old rule (every check must be green) and the block message says the required set could not be read and why. An empty set is not treated as "nothing is required": a protected branch with no readable required contexts is the case where silently allowing is the worst outcome. A branch with no rules at all (the API succeeds, the list has no `required_status_checks` rule) keeps the old rule as well; the repo has chosen no gate, so the guard stays as strict as today.
5. **No bypass flag.** No `# advisory-ok:` marker and no environment variable. The only way to make a red check non-blocking is to not require it in the repo's rules, which is the repo owner's decision and is reviewable. This is the "Remembering is a failure mode" rung 1 answer: the rule is derived from state the tooling already reads, so nobody has to remember an override.
6. **The other guard rules do not change**: `--admin`, `--auto`, the missing `--match-head-commit` SHA, the Codex mention rule and the base-sync rule keep their current behavior.

### Interaction with open PRs

- **#131 (`skip parity outside claude-skills, honor tool_input.dir_path`) and #132 (`env -S strings with $ or escapes fail closed`)** both edit `pr-guard.py`, `hooks.json`, `SKILL.md`, the tests and `skills-manifest.json`, and both bump the skill to 1.5.5, so those two already conflict with each other on version and manifest lines. They are not edited by this plan. This change should land after both, as 1.5.6 or later, rebased on their result, so it does not add a third 1.5.5 claim. It touches `not_green()` and the merge branch of `check()`, which neither PR rewrites; the expected conflicts are the version and manifest lines only.
- **#131's parity check** compares the installed guard with the skill's copy, so a repo that vendors `pr-guard.py` will see parity drift until it re-vendors the new version. That is the normal vendoring flow and needs no special handling, but the rollout note in the release must say the new version changes what the guard blocks.
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
2. **Required red blocks:** a required context red (and the same with PENDING, CANCELLED, SKIPPED, and a required context absent from the rollup): blocked, message names the check.
3. **Superseded run:** an older failed run of a required job followed by a newer green run: allowed (the existing collapse still applies to the required set).
4. **Unreadable rules fail closed:** the rules call exits non-zero, returns invalid JSON, or returns 403: the old all-green rule applies and the message says the required set could not be read, with the reason. A red advisory check then blocks, as it does today.
5. **Empty required set on a protected branch** and **no `required_status_checks` rule at all:** the old all-green rule applies.
6. **Same-name forged check:** a required context satisfied only by a check from a different `integration_id` than the ruleset pins: blocked.
7. **Classic protection path:** required contexts come from the branch-protection endpoint when no ruleset rule exists; same assertions as 1 and 2.
8. **No bypass:** a command carrying `# advisory-ok: x`, `# codex-review-ok: x` or `# sync-base: x` does not make a red required check pass, and no environment variable changes the result.
9. **Unchanged rules:** `--admin`, `--auto`, the missing `--match-head-commit` SHA and the Codex mention rule block exactly as before (the existing parity and fixture tests keep passing).
10. **Warning channel:** a test asserts the warning text reaches the model on an allowed merge, not only on a block. The PreToolUse hook contract only carries stderr to the agent on exit 2 and may not surface exit-0 output; this must be established against the harness before the behavior in item 3 of the fix is promised. If exit-0 output is dropped, the allowed-merge warning moves to `permissionDecisionReason` or `additionalContext` JSON on stdout, whichever the harness documents (verify, do not assume).

## Open questions for the claude-skills cop (do not block the plan)

- Token permission: the rules endpoint for branches is readable with the repo read permission the `gh` login already has on public and org repos in this fleet, but I did not verify it with the exact token an agent session uses; item 4 above makes the failure safe either way.
- The warning channel (test 10).
- Whether `doctor` should be required anywhere: the repo owner's call, out of scope here.

## Done when

- Replaying nevar-mail #1129's rollup shape through the released guard allows the merge with the `doctor` warning; a required red still blocks.
- The behaviors above are pinned by tests 1 to 10 and pass in CI.
- `pr-merge-flow/SKILL.md` and `hooks.json` agree on the new version, and the release note says the guard now follows the repo's required checks.
- The ops-log incident (nevar-platform-ops issue 1, comment 7061595772) is answered with the release version.

## Not in scope

Making any check required or advisory in a repo (branch-rule owners). The `doctor` job's red-on-release defect (`2026-11-21-doctor-latest-release-coupling.md`). The guard's shell parsing (`pr-guard-shell-parsing-design.md`, #139). Editing #131 or #132.
