# Review Gate doctor job: run only when a file the doctor reads changes

Status: planned. Plan id: CS-DOCTOR-PATHS-FILTER. Proposed priority: P3 (a cost and noise cut; nothing is broken); the PM scheduled task sets the final tier. Owner: the claude-skills cop (template, installer, test, SKILL.md); each repo's traffic cop only when that repo next re-vendors. Source: nevar-mail author FYI `work:1145-p2s` (ops#1 IC_kwDOV09ZVM8AAAABqafcgQ, 2026-11-24 18:54Z), better practice raised from nevar-mail PR #1149, which carries the filter locally.

## Incumbent

`review-gate/templates/review-gate-doctor.yml`, written by `install-workflow.py --doctor-job`, already exists and, since 3.2.19, runs the repo's own committed `.claude/skills/review-gate/scripts/doctor-review-gate.py --strict` with no clone. That removed the "an upstream release turns every repo red" half of the cost (`2026-11-21-doctor-latest-release-coupling.md`). It did **not** remove the per-push cost: the template is `on: pull_request` with no filter, and `review-gate/SKILL.md` (3.2.14 paragraph) says so: "It has no paths filter". So the ask is not moot; the 3.2.19 template made the job cheaper and deterministic, and left it running on every push of every PR, about 10 s each, 1 billed minute per run on a private repo.

Nothing else in the repo provides a path filter for it. This plan adds one to the same template; it adds no script and no new workflow.

## What a filter loses, and why that is acceptable

With 3.2.19 the doctor judges only files in the PR's merge ref: `review-gate.yml`, the security workflows, the vendored `scripts/` and `.claude/skills/review-gate/`. A PR that changes none of them leaves each of those files exactly as it is on the default branch, so the doctor's verdict on that PR equals its verdict on the default branch. A red doctor on such a PR therefore reports a property of the repo, not of the PR, and today it repeats on every unrelated PR (the "red on every PR" noise recorded in the 3.2.14 SKILL.md paragraph). The filter keeps the PR-level signal (a PR that touches the gate files and breaks them) and drops the repeats.

It does lose one thing: a repo whose default branch is already stale shows nothing on PRs that do not touch those files. Two things cover that, and both are in this plan:

1. `workflow_dispatch:` on the same workflow, so the owner can run the doctor on the default branch on demand (`gh workflow run review-gate-doctor.yml --ref <default>`). That is also a better verification than a PR, because it judges the default branch itself and not a merge ref.
2. The re-vendor rollouts keep their done-when proof (below), which moves from "a PR that touches nothing" to the dispatch run.

A recurring fleet-wide drift check is still not proposed here; `review-gate-stale-vendor-fleet.md` already states that a repo that cannot take the job needs its own plan naming a command, a schedule and a maintainer.

## Fix

1. **Template.** `review-gate/templates/review-gate-doctor.yml` changes `on: pull_request` to a `pull_request` trigger with a `paths:` list, plus `workflow_dispatch:`. The list is exactly what the doctor reads:
   - `.github/workflows/review-gate.yml` (the gate; the `.yaml` spelling is only probed through the Contents API on the default branch, and that probe is skipped in the job, so it is not a merge-ref read and stays out of the list);
   - `.github/workflows/review-gate-security-scan.yml` (the marker that turns the security lane on);
   - `.github/workflows/review-gate-security-refresh.yml`;
   - `.github/workflows/review-gate-doctor.yml` (the job itself, so a PR that edits or removes it is checked by the new copy);
   - `scripts/` plus each name in `installer.VENDORED_SCRIPTS` (today `check-review-gate.py`, `check-forged-gate-names.py`, `check-forged-review-gate.py`, `check-security-scan.py`, `lint-review-body.py`);
   - `.claude/skills/review-gate/**`.
   The header comment says the job is a PR-time check of those files, that a path-filtered workflow reports no check on a PR that touches none of them, and therefore that it must never be made a required check (a required check whose workflow is skipped stays pending and blocks the merge). The cost line becomes "one ~10 s job on a PR that touches those files".
2. **A test, not a prose rule.** In `review-gate/tests/`, a test parses the template's `paths:` and asserts that every file the doctor reads is matched: the workflow names the doctor inspects, `installer.VENDORED_SCRIPTS` (imported, so the two cannot drift), and `VENDORED_SKILL`. It fails when a script is added to `VENDORED_SCRIPTS` or a workflow is added to the doctor's reads without a path, and fails when the template lists a path the doctor does not read. The test runs the doctor against a temporary repo for one script and one workflow it names, so the list is checked against behavior, not only against a copy of itself.
3. **SKILL.md.** The 3.2.14 sentence "It has no paths filter" is superseded: add an "Upgrading to 3.8.1" paragraph (new patch, template only) stating the filter, `workflow_dispatch`, the never-required warning and the one command to re-run it on the default branch. Version bump per the skill's release checklist (SKILL.md and hooks.json agree). `install-workflow.py` itself needs no change: `--doctor-job --force` already rewrites the file from the template, so a forced reinstall now keeps the filter instead of dropping a local one (the nevar-mail complaint).
4. **Fan-out: none of its own.** No repo gets a standalone PR. A repo takes the new template on its next re-vendor (`install-workflow.py --force --doctor-job`), including the re-vendor PRs of `review-gate-stale-vendor-fleet.md` and the clone-main migration PRs of `2026-11-21-doctor-latest-release-coupling.md`. nevar-mail's local filter should be byte-identical to the template after the next re-vendor; the nevar-mail cop reconciles it then.
5. **Amend the rollout plan's done-when, in this PR.** `review-gate-stale-vendor-fleet.md` currently proves a re-vendor with "a verification PR that must not touch `.github/workflows/` or the vendored `scripts/`", a PR that the filter would skip. The bullet gains one sentence: once a repo has the filtered template, the proof is the newest `workflow_dispatch` run of `review-gate-doctor.yml` on the default branch, green; the verification-PR route applies only to a repo still on the unfiltered template.

## Done when

- The template has the `paths:` list and `workflow_dispatch:`, and the new test passes in claude-skills CI.
- `python3 review-gate/scripts/install-workflow.py --doctor-job --force` in a scratch repo writes a doctor workflow whose triggers match the template (an installer test, extending `test_install_workflow.py`).
- SKILL.md says 3.8.1 and no longer says the job has no paths filter.
- The stale-vendor-fleet done-when names the dispatch proof.
- The next repo to re-vendor (nevar-mail is the first with a local filter) shows a doctor run on a PR that touches `.claude/skills/review-gate/`, and no run on one that does not.

## Not in this plan

- Making the doctor a required check: stays each repo owner's branch-protection decision, and a filtered job cannot be one.
- A schedule or push-to-default-branch trigger: costs a run per merge; propose it only with a named maintainer for the red result.
- The Program Cop's FYI `work:skill-vendor-drift` (vendored `pr-merge-flow` 1.5.4 in nevar-chat against 1.6.2 upstream, other repos unchecked): the doctor compares `review-gate` only. A version-drift check for other vendored skills is a separate design (one more file read set, its own paths filter, its own owner) and gets its own plan if the Program Cop asks for it; it is recorded here so it is not lost.

## Risks

- A path missed from the list silently hides a doctor run on a change that matters. The test in step 2 is the guard; without it the list would drift as soon as a script is added.
- A repo already red on its default branch stops seeing that red on unrelated PRs. That is the intent; the dispatch run is how an owner sees it.
