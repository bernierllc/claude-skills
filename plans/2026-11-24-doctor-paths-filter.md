# Review Gate doctor job: run only when a file the doctor reads changes

Status: planned. Plan id: CS-DOCTOR-PATHS-FILTER. Proposed priority: P3 (a cost and noise cut; nothing is broken); the PM scheduled task sets the final tier. Owner: the claude-skills cop (template, installer, test, SKILL.md); each repo's traffic cop only when that repo next re-vendors. Source: nevar-mail author FYI `work:1145-p2s` (ops#1 IC_kwDOV09ZVM8AAAABqafcgQ, 2026-11-24 18:54Z), better practice raised from nevar-mail PR #1149, which carries the filter locally.

## Incumbent

`review-gate/templates/review-gate-doctor.yml`, written by `install-workflow.py --doctor-job`, already exists and, since 3.2.19, runs the repo's own committed `.claude/skills/review-gate/scripts/doctor-review-gate.py --strict` with no clone. That removed the "an upstream release turns every repo red" half of the cost (`2026-11-21-doctor-latest-release-coupling.md`). It did **not** remove the per-push cost: the template is `on: pull_request` with no filter, and `review-gate/SKILL.md` (3.2.14 paragraph) says so: "It has no paths filter". So the ask is not moot; the 3.2.19 template made the job cheaper and deterministic, and left it running on every push of every PR, about 10 s each, 1 billed minute per run on a private repo.

Nothing else in the repo provides a path filter for it. This plan adds one to the same template; it adds no script and no new workflow.

## What a filter loses, and why that is acceptable

With 3.2.19 the doctor judges only files in the PR's merge ref: `review-gate.yml`, the security workflows, the vendored `scripts/` and `.claude/skills/review-gate/`. A PR that changes none of them leaves each of those files exactly as it is on the PR's base branch (the default branch, or `staging` or a feature branch for a PR that targets one), so the doctor's verdict on that PR equals its verdict on that base. The rollout proof below is about the default branch only; a base that differs from the default branch is verified by dispatching on that base (`--ref <base>`). A red doctor on such a PR therefore reports a property of the repo, not of the PR, and today it repeats on every unrelated PR (the "red on every PR" noise recorded in the 3.2.14 SKILL.md paragraph). The filter keeps the PR-level signal (a PR that touches the gate files and breaks them) and drops the repeats.

It does lose one thing: a repo whose default branch is already stale shows nothing on PRs that do not touch those files. Two things cover that, and both are in this plan:

1. `workflow_dispatch:` on the same workflow, so the owner can run the doctor on any ref on demand (`gh workflow run review-gate-doctor.yml --ref <default>`). Dispatch needs the ref to be a branch or tag in the repo that already carries a `workflow_dispatch` copy of the workflow: a PR branch or `staging` cut before the upgrade, and a fork's branch, cannot be dispatched. For those, the exact-checkout command is the repo's own vendored doctor run from a checkout of that revision (`git switch --detach <sha> && python3 .claude/skills/review-gate/scripts/doctor-review-gate.py --strict`, the line the job runs). On the default branch that is also a better verification than a PR, because it judges the branch itself and not a merge ref.
2. The re-vendor rollouts keep their done-when proof (below), which moves from "a PR that touches nothing" to the dispatch run.

A recurring fleet-wide drift check is still not proposed here; `review-gate-stale-vendor-fleet.md` already states that a repo that cannot take the job needs its own plan naming a command, a schedule and a maintainer.

## Limits we accept, and what we change because of them

- **Diff window.** GitHub evaluates `paths:` against a diff capped at 3,000 files; a PR that large can change a watched file outside the window and get no doctor run. Accepted: such a PR is not a normal change, and the owner verifies its exact revision with the exact-checkout command above (or a dispatch when the branch carries the new workflow). The SKILL.md paragraph says so.
- **Symlinks.** The doctor follows symlinks (`is_file()` / `read_bytes()`), so a target outside the path list could change the verdict without matching the filter. The filter is only sound over ordinary files, so this plan adds a no-symlink input contract: the doctor fails (`--strict` and default) when any file it reads, or an ancestor directory below the repo root, is a symlink, matching what `install-workflow.py` already refuses to write through. Step 2 tests it.
- **Existing required doctors.** A filtered workflow that is a required check leaves an unrelated PR pending forever, and `pr-guard` blocks a missing required `doctor` (an advisory pin cannot override a requirement). The current template does not forbid a repo requiring it, so a repo that does must not take the filtered template: before a repo re-vendors with `--doctor-job --force`, its rulesets, classic branch protection and `.github/required-checks.json` are checked for `doctor`. If it is required, the repo keeps its current job file until the owner removes the requirement (the job file is opt-in via `--doctor-job`, so skipping it is always possible). `install-workflow.py --doctor-job` also refuses to overwrite when the local `.github/required-checks.json` lists `doctor`; rulesets and classic protection are the fleet checklist's job (step 4).

## Fix

1. **Template.** `review-gate/templates/review-gate-doctor.yml` changes `on: pull_request` to a `pull_request` trigger with a `paths:` list, plus `workflow_dispatch:`. The list is exactly what the doctor reads:
   - `.github/workflows/review-gate.yml` (the gate; the `.yaml` spelling is only probed through the Contents API on the default branch, and that probe is skipped in the job, so it is not a merge-ref read and stays out of the list);
   - `.github/workflows/review-gate-security-scan.yml` (the marker that turns the security lane on);
   - `.github/workflows/review-gate-security-refresh.yml`;
   - `.github/workflows/review-gate-doctor.yml` (the job itself, so a PR that edits or removes it is checked by the new copy);
   - `scripts/` plus each name in `installer.VENDORED_SCRIPTS` (today `check-review-gate.py`, `check-forged-gate-names.py`, `check-forged-review-gate.py`, `check-security-scan.py`, `lint-review-body.py`);
   - `.claude/skills/review-gate/**`.
   The header comment says the job is a PR-time check of those files, that a path-filtered workflow reports no check on a PR that touches none of them, and therefore that it must never be made a required check (a required check whose workflow is skipped stays pending and blocks the merge). The cost line becomes "one ~10 s job on a PR that touches those files".
2. **A test, not a prose rule.** The path list is a conservative superset of what the doctor reads, plus named trigger-only entries. In `review-gate/tests/`:
   - The doctor runs against temporary repos for each branch that changes what it reads (security marker `review-gate-security-scan.yml` present and absent, refresh workflow present and absent, every script in `installer.VENDORED_SCRIPTS` present, hooks.json and SKILL.md version parity) with `Path.read_bytes`, `Path.is_file`, `Path.read_text` and `open` spied on. Every repo-relative path the doctor opens must match a template `paths:` glob; a read with no glob fails the test, so a new read added to the doctor without a path fails here and not in a fleet.
   - Trigger-only entries are an explicit allowlist in the test: the doctor's own workflow (a PR that edits or removes the job is checked by the new copy) and the unread files under `.claude/skills/review-gate/**` (docs, tests; a superset on purpose, because the skill directory is installed and upgraded as a unit). Any other glob the template lists that no run opened fails the test.
   - `installer.VENDORED_SCRIPTS` is imported, so the list and the template cannot drift.
   - The no-symlink contract: a fixture with a symlinked script, and one with a symlinked `scripts/` ancestor, makes the doctor exit non-zero.
3. **SKILL.md and release.** This is a minor release, 3.9.0 (`CLAUDE.md` → Versioning: patch is "no behavior change"; a path filter and a `workflow_dispatch` trigger change when the job runs and add a capability). The 3.2.14 sentence "It has no paths filter" is superseded by an "Upgrading to 3.9.0" paragraph stating the filter, `workflow_dispatch`, the never-required warning, the existing-required-doctor rule, the 3,000-file limit, the no-symlink contract and the commands to re-run the doctor on a ref. SKILL.md and hooks.json versions agree, and `python3 scripts/generate-manifest.py` regenerates `skills-manifest.json` in the same commit (`scripts/check-version-bumps.py origin/main` and `generate-manifest.py --check` pass locally before push). A vendored copy older than the latest release still fails the release-parity check when the doctor is run externally; only the self-vendored job skips that comparison, and the paragraph says so. `install-workflow.py` needs no template logic change beyond the required-checks refusal above: `--doctor-job --force` rewrites the file from the template, so a forced reinstall now keeps the filter instead of dropping a local one (the nevar-mail complaint).
4. **Fan-out: none of its own.** No repo gets a standalone PR, and a repo whose `doctor` is required is skipped (see Limits). A repo takes the new template on its next re-vendor (`install-workflow.py --force --doctor-job`), including the re-vendor PRs of `review-gate-stale-vendor-fleet.md` and the clone-main migration PRs of `2026-11-21-doctor-latest-release-coupling.md`. nevar-mail's local filter should be byte-identical to the template after the next re-vendor; the nevar-mail cop reconciles it then.
5. **Amend both rollout plans' done-whens, in this PR.**
   - `review-gate-stale-vendor-fleet.md` currently proves a re-vendor with "a verification PR that must not touch `.github/workflows/` or the vendored `scripts/`", a PR that the filter would skip. The bullet gains one sentence (already written): once a repo has the filtered template, the proof is the newest `workflow_dispatch` run of `review-gate-doctor.yml` on the default branch, green; the verification-PR route applies only to a repo still on the unfiltered template.
   - `2026-11-21-doctor-latest-release-coupling.md` ("Done when", release bullet) requires a release to leave `doctor` green "on an open PR in a migrated repo", which an unrelated PR no longer has once filtered. The bullet changes to: dispatch the doctor before and after the release against one immutable ref (a tag, or a recorded commit SHA reachable from a branch that carries the dispatch-enabled workflow), confirm from the run records that both runs checked the same SHA, and both are green. A PR run is not used: it checks a synthetic merge commit, and a branch name can advance between runs.

## Done when

- The template has the `paths:` list and `workflow_dispatch:`, and the new tests (reads covered, trigger-only allowlist, no-symlink contract) pass in claude-skills CI.
- `python3 review-gate/scripts/install-workflow.py --doctor-job --force` in a scratch repo writes a doctor workflow whose triggers match the template (an installer test, extending `test_install_workflow.py`), and refuses when `.github/required-checks.json` lists `doctor`.
- SKILL.md and hooks.json say 3.9.0, `skills-manifest.json` is regenerated, and SKILL.md no longer says the job has no paths filter.
- The stale-vendor-fleet and doctor-latest-release-coupling done-whens name the dispatch proof.
- The next repo to re-vendor (nevar-mail is the first with a local filter) shows a doctor run on a PR that touches `.claude/skills/review-gate/`, and no run on one that does not.

## Not in this plan

- Making the doctor a required check: stays each repo owner's branch-protection decision, and a filtered job cannot be one.
- A schedule or push-to-default-branch trigger: costs a run per merge; propose it only with a named maintainer for the red result.
- The Program Cop's FYI `work:skill-vendor-drift` (vendored `pr-merge-flow` 1.5.4 in nevar-chat against 1.6.2 upstream, other repos unchecked): the doctor compares `review-gate` only. A version-drift check for other vendored skills is a separate design (one more file read set, its own paths filter, its own owner) and gets its own plan if the Program Cop asks for it; it is recorded here so it is not lost.

## Risks

- A path missed from the list silently hides a doctor run on a change that matters. The spied-read test in step 2 is the guard; without it the list would drift as soon as a script is added.
- A repo already red on its default branch stops seeing that red on unrelated PRs. That is the intent; the dispatch run is how an owner sees it.
