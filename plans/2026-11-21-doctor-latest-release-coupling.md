# Review Gate doctor: an upstream release must not turn every vendoring repo red

Status: planned. Plan id: CS-DOCTOR-LATEST-RELEASE. Proposed priority: P1 for the migration (step 1, it clears the red today), P2 for the floor design (step 2); the PM scheduled task sets the final tier. Owner: the claude-skills cop (script, template, installer); each repo's traffic cop (re-vendor PR). Tracker: https://app.notion.com/p/CS-DOCTOR-LATEST-RELEASE-review-gate-doctor-job-must-not-turn-red-on-an-upstream-release-migrate-t-41f4efecc95a81d7bd93ff2bb0cc62cd (Owner Needs-PM). Related: CS-GUARD-DETECTOR-COUPLING (https://app.notion.com/p/CS-GUARD-DETECTOR-COUPLING-installer-and-doctor-refuse-a-job-guard-whose-pinned-detector-is-not-yet-41f4efecc95a8153bb78eb7b475994d3, the other half of the same "one repo's state depends on another's release" family; this plan does not replace it), `review-gate-stale-vendor-fleet.md` (the re-vendor rollout this plan amends), `2026-11-21-pr-guard-required-vs-advisory.md` (why a red doctor blocked merges at all).

## What happened

When review-gate 3.2.21 shipped, the `doctor` job went red on open PRs in every repo that vendors review-gate at once (nevar-plan #102 and #103, tools #285 and #286 were reported). The `pr-merge-flow` guard refuses a merge while any check is red, so every merge in those repos stopped, with nothing wrong in any of the PRs.

## Root cause

The premise to correct first: the doctor script and the template on `main` (3.2.21) no longer compare a repo with the latest release. The coupling is in the copies already installed in the fleet.

- **Shipped before 3.2.19 (template added in 3.2.14, f65afe7; replaced in 3.2.19, 0cf5b00):** the doctor job's only step was `git clone --depth 1 … claude-skills` followed by `python3 $RUNNER_TEMP/cs/review-gate/scripts/doctor-review-gate.py --strict`. It ran the doctor from claude-skills `main` against the repo, so `local_checks()` compared the repo's `review-gate.yml` and `scripts/*.py` with whatever `main` held that minute. The template's own header said so: "A claude-skills release that changes a vendored file therefore turns this job red on every PR until the repo re-runs install-workflow.py --force." No repo action causes the red, and no repo action before the release can prevent it. Releases 3.2.20 and 3.2.21 changed vendored files (`check-forged-gate-names.py`, `check-forged-review-gate.py`, `install-workflow.py`), which is what turned the job red.
- **Shipped from 3.2.19 (`review-gate/templates/review-gate-doctor.yml`, `doctor-review-gate.py`):** the job runs the repo's committed `.claude/skills/review-gate/scripts/doctor-review-gate.py --strict` and clones nothing. `vendored_skill_parity()` returns early when the doctor is the vendored copy (`dest.resolve() == skill_root`), so a release cannot change its result. Verified by reading both files at origin/main 891b7e9.
- **So the defect is two things:** (a) installed jobs lag the template: measured 2026-11-21 on each repo's default branch, 15 of 21 repos checked still carry the clone-main job (list below); only `tools` (3.2.21) and `a10d.info` (3.2.20) carry the vendored job, and `tools` #285 and #286 show `doctor` SUCCESS at 17:41Z today while `nevar-plan` #102 still shows FAILURE (14:14Z run). I did not establish when `tools` switched, so "red then green" for tools is from the report, not re-observed. (b) 3.2.19 removed the coupling by removing the staleness signal: the job can no longer say "this repo's copy is behind the latest release". The comment in the template says to run the newer release's doctor by hand for that. Nothing does, so the fleet plan's "stale copies go unseen" gap is reopened.

## Measured 2026-11-21 (default branches; a snapshot, not a contract: re-measure before each PR)

| Doctor job | Repos |
|---|---|
| clone-main (red whenever main moves): 15 | nevar-secrets (vendored skill 3.2.14), nevar-contacts (3.2.14), agency-agents (3.2.14), nevar-logs (3.2.14), nevar-aec-catalog (3.2.16), nevar-design (3.2.17), nevar-social (3.2.17), prevost (3.2.17), nevar-plan (3.2.17), mbernier.com (3.2.18), and with **no committed `.claude/skills/review-gate`**: nevar-mail, nevar-notify, nevar-research, nevar-ai, email_demo |
| vendored (3.2.19+ shape): 2 | tools (3.2.21), a10d.info (3.2.20) |
| no doctor job: 4 | agents-environment-config, nevar-admin, nevar-content (vendored 3.2.14), nevar-fund (vendored 3.2.11) |

The doctor template only exists from 3.2.14, so a repo on 3.2.11-3.2.13 has no job to turn red; the clone-main job exists on 3.2.14-3.2.18 copies.

## Options weighed

| Option | Effect | Verdict |
|---|---|---|
| **Pin**: job compares the repo with one exact release | Every new release is a red repo-by-repo until each pin moves; a pin is the old coupling with the date moved | Reject |
| **Latest-release coupling** (the clone-main job) | Red everywhere at every release | Reject; already removed from the template |
| **Consistency only** (3.2.19 as shipped) | Never red from upstream; also blind to "behind" | Keep as the base, add the floor |
| **Declared floor + advisory latest** | Red only when the vendored copy is below a floor the repo declares, or is internally inconsistent; a newer release is a printed WARN naming the version and the fix | **Recommended** |

### Recommendation: declared minimum-version floor

Incumbent named: `vendored_skill_parity()` already compares `have` (the repo's vendored version) with `want` (the running release's version) and prints the one fix line. Run from claude-skills it is, in effect, a floor equal to the latest release. The change is to let the repo choose the floor instead of the release choosing it.

1. **The floor lives in repo config the installer never overwrites.** A one-line file next to the workflow (proposed `.github/review-gate-min-version`, a dotted version). `install-workflow.py --doctor-job` writes it on first install, equal to the installed version, and never lowers it. Its name states its domain (deliberate-naming rule); the file name is the open choice for the claude-skills cop.
2. **Red only below the floor.** The doctor fails with exit 1 when the vendored skill's version is below the floor, when the floor file is present but unreadable or malformed (fail closed, FAIL line naming the file), or when the existing consistency checks fail (workflow or vendored scripts differ from the repo's own vendored skill, hooks.json and SKILL.md disagree).
3. **A newer release is a WARN.** An optional lookup of the newest claude-skills release prints `WARN vendored 3.2.20, 3.2.22 is out: <fix>`. It never changes the exit code. A failed lookup prints `WARN could not check for a newer release: <reason>` (no swallowed errors) and also never changes the exit code. The job stays read-only and gets no token. The lookup can be dropped from the job and kept for the local `aec doctor` run if CI egress is unwanted; that is the claude-skills cop's call.
4. **Raising the floor is a deliberate act with an owner**: the repo's cop, in a PR, when a release matters to that repo (a merge-guard or forged-check fix; see CS-GUARD-DETECTOR-COUPLING for how those releases are ordered). A release that must reach everyone raises the floor through the fan-out PRs, not through a red job.

### Fan-out consequence

- Today a release needs a same-day fan-out to keep merges unblocked, which is the window the ops log shows (nevar-mail waiting on the 3.2.19 fan-out). With the floor, a release creates no obligation until it is a floor bump, so fan-out is scheduled by severity: guard-correctness and security releases bump the floor in the fan-out PRs; the rest age as WARN lines.
- `review-gate-stale-vendor-fleet.md` gets one change when it is next edited: each re-vendor PR also writes the floor file. That file is not edited here.
- The signal that the fleet is behind moves from a red check to the program cop's fleet table (the job's WARN output is the data).

## Migration: the 15 clone-main repos (this is step 1 and does not wait for the floor)

1. **Vendor the skill first where it is missing** (nevar-mail, nevar-notify, nevar-research, nevar-ai, email_demo): the 3.2.19+ job fails with `::error::… is not committed` when `.claude/skills/review-gate` is absent, so swapping the job on those five without vendoring turns them red. `aec install skill review-gate` then commit `.claude/skills/review-gate`.
2. **Re-run the installer from the current release**: `install-workflow.py --force --doctor-job`, which replaces the workflow, the vendored scripts and `review-gate-doctor.yml` in one PR per repo (the same PR as the stale-vendor fleet's re-vendor where that repo is on its list: nevar-secrets, nevar-design, nevar-mail, mbernier.com, nevar-social, nevar-contacts, prevost, nevar-notify, agency-agents, nevar-logs, nevar-research, nevar-aec-catalog, nevar-ai).
3. Repos on 3.2.14-3.2.18 need the whole-copy refresh 3.2.19 added; a repo whose `.claude/skills/review-gate` is older than the installer is refused by the installer's version check, so the vendored copy is replaced first.
4. Bootstrap: the doctor workflow triggers on `pull_request`, which runs the PR's own merge-ref copy, so the migration PR is judged by the new job; its own doctor run must be green before it merges. Repos with no job today (agents-environment-config, nevar-admin, nevar-content, nevar-fund) are outside this migration; the stale-vendor fleet plan decides whether they take the job.
5. Stopgap until a repo migrates: a red advisory `doctor` must not stop a merge. That is `2026-11-21-pr-guard-required-vs-advisory.md`; the two plans are independent and either can land first.

## Affected surfaces

- `review-gate/scripts/doctor-review-gate.py` (`vendored_skill_parity`, `main`), `review-gate/scripts/install-workflow.py` (`--doctor-job`, floor file), `review-gate/templates/review-gate-doctor.yml` (stays no-clone), `review-gate/SKILL.md` and `hooks.json` (version bump), `skills-manifest.json`, `review-gate/tests/`.
- The 15 repos above (workflow file, vendored scripts, vendored skill, the floor file). AEC catalog hashes if the skill is installed through `aec`.
- Documentation: the "Migrating to 3.2.8" section of `review-gate/SKILL.md` gets a "Migrating the doctor job" paragraph; the template header is already accurate.

## Tests that pin the behaviour

1. **Release does not turn a repo red:** a fixture repo vendored at version N, doctor run from the vendored copy while a fixture "latest" tree at N+1 with changed scripts exists: exit 0.
2. **No upstream fetch in the template:** a contract test asserts `review-gate-doctor.yml` has no `git clone`, no `claude-skills` URL and no `curl`/`wget`; this pins 3.2.19 so the old shape cannot return.
3. **Floor below:** vendored 3.2.17, floor 3.2.19: exit 1 with FAIL naming both versions and the fix. Floor equal or lower: exit 0.
4. **Floor malformed or unreadable:** exit 1, FAIL names the file (fail closed).
5. **Newer release is a warning:** latest lookup stubbed to 3.2.22: output has `WARN` and the version, exit 0. Lookup stubbed to fail: `WARN could not check…`, exit 0.
6. **Installer never lowers the floor** and writes it equal to the installed version on first install; `--force` on a higher floor leaves it.
7. **Migration:** a fixture repo with the clone-main template: `install-workflow.py --force --doctor-job` rewrites it to the vendored shape; a fixture repo with no `.claude/skills/review-gate` makes the installer print the vendoring instruction instead of writing a job that would fail.

## Done when

- None of the 15 repos has a `git clone` of claude-skills in `review-gate-doctor.yml`: `gh api repos/bernierllc/<repo>/contents/.github/workflows/review-gate-doctor.yml --jq .content | base64 -d | grep -c 'git clone'` prints 0 (a retrieval error counts as a failure).
- A release published after the migration leaves `doctor` green on an open PR in a migrated repo, checked once on the first release after the rollout.
- Floor behaviour is released and pinned by the tests above, and the re-vendor PRs write it.

## Not in scope

Making `doctor` a required check (each repo owner's branch-protection decision). Changing `pr-guard` (see `2026-11-21-pr-guard-required-vs-advisory.md`). Detector promotion order (CS-GUARD-DETECTOR-COUPLING).
