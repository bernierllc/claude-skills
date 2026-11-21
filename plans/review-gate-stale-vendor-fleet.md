# Review Gate: stop stale vendored copies of review-gate.yml from blocking merges

Status: planned. Owner: the cop of each repo named below (re-vendor); the claude-skills cop (doctor check). Tracker: https://app.notion.com/p/REVIEW-GATE-STALE-VENDOR-FLEET-41e4efecc95a816488e4ff9fc8dabf7e. Source: Program Cop request, 2026-11-20 23:08Z (better practice: a superseded Review Gate run blocks merges).

## What happened

`pr-guard` blocked merges on a superseded failed or cancelled `Review Gate` run in nevar-secrets PRs 23, 24, 25 and 26. The newest run was cancelled, a cancelled newest run is what the required check reads, and the PR stayed blocked until someone re-ran it by hand.

## Root cause

The guard is not the defect. nevar-secrets installed review-gate on 2026-11-15 from the pre-3.2.8 template. That template has `concurrency: cancel-in-progress: true` and POSTs check runs, so every new push or body edit cancels the previous run, and a cancelled run is a failed required check.

The incumbent already fixes this, in two steps. review-gate 3.2.8 made the job named `Review Gate` the check (nothing is POSTed) but kept the `concurrency:` group. review-gate 3.2.10 (bce2e9c) removed the group on purpose; the template comment cites nevar-fund #27. A repo on a 3.2.8 or 3.2.9 copy therefore has the job-shaped check and can still cancel runs (nevar-logs is one), so "already on 3.2.8" does not mean fixed. The defect is stale vendoring: `install-workflow.py` copies the workflow into each repo once, and nothing tells a repo when its copy has fallen behind the skill.

## Measured 2026-11-20

Default-branch `review-gate.yml` in these 17 org repos still carries `cancel-in-progress: true`:

nevar-secrets, nevar-design, nevar-mail, mbernier.com, nevar-social, nevar-contacts, a10d.info, agents-environment-config, prevost, tools, nevar-notify, agency-agents, nevar-logs, nevar-research, nevar-aec-catalog, nevar-admin, nevar-ai.

Re-measure before each re-vendor PR; the list is a snapshot, not a contract.

## Fix

1. Re-vendor review-gate 3.2.14 in each listed repo with `install-workflow.py --force`, one PR per repo, handled by that repo's traffic cop. nevar-secrets goes first because it is the repo that hit the false blocks. `agents-environment-config` and `agency-agents` are handled by the aec cop.
2. A guard so stale vendoring cannot go unseen again. Use the incumbent `install-workflow.py --doctor-job`, which writes the optional `review-gate-doctor.yml`. It runs `doctor-review-gate.py --strict` on each PR and fails when the repo's `review-gate.yml` or a vendored `scripts/` file is missing or differs from the skill on claude-skills main. It is not a required check (making it one is each repo owner's branch-protection decision) and costs one job of about 10 s per push, billed on private repos. Each re-vendor PR in this rollout turns it on; no repo opts out, because the repo has no fleet check and none is proposed here. A repo that cannot take the job needs a separate plan that names a command, a schedule and a maintainer for recurring drift coverage.

Bootstrap order: `pull_request_target` runs the workflow from the default branch, so the re-vendor PR itself is judged by the old copy, and body edits or label events on it can leave a cancelled newest run. Follow "Migrating to 3.2.8" in `review-gate/SKILL.md` for that PR (re-run the newest run by hand if it is cancelled). The first PR opened after the merge exercises the new copy; that PR must show a successful newest `Review Gate` run after a body edit and a label event, and that is recorded on the repo's Tracker row.
3. No new script: the re-vendor and the doctor job are both `install-workflow.py` features. Anything added beyond them must say why the incumbent was not enough.

## Done when

- None of the repos above has a top-level `concurrency:` group in its default-branch `review-gate.yml`. The Contents API returns the file base64-encoded, so decode it: `gh api repos/bernierllc/<repo>/contents/.github/workflows/review-gate.yml --jq .content | base64 -d | grep -c '^concurrency:'` must print 0, and a retrieval or decode error counts as a failure, not a pass. Do not grep for `cancel-in-progress`: the current template mentions it in a comment (line 54), so a correct copy would fail. This only proves the concurrency group is gone; freshness is proved by the doctor job below.
- Each repo runs the doctor job, and its newest run on the first PR opened against the default branch after the re-vendor merge is green. The doctor template triggers only on `pull_request`, so no default-branch run exists; the owner also confirms the installed default-branch `review-gate.yml` matches the skill. Green means the workflow and the vendored scripts match the skill, except one supported case: the doctor accepts a differing, compatible detector script that `installer.keeps_detector()` preserves, so a repo with a custom detector can pass while differing from the skill. The repo's Tracker row records whether it has one.
- A cancelled or superseded `Review Gate` run no longer blocks a PR in any of them.

## Owners and routing

| Work | Owner |
|---|---|
| Re-vendor in each repo | That repo's traffic cop; the aec cop for `agents-environment-config` and `agency-agents` |
| Doctor job wiring and `install-workflow.py` changes | claude-skills cop |
| Fleet status to Matt | Program Cop |

## Not in scope

Changing `pr-guard` behavior (see `pr-guard-rollup-and-auto-message.md`) and the guard's shell parsing (see `pr-guard-shell-parsing-design.md`).
