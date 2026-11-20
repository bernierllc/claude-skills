# Review Gate: stop stale vendored copies of review-gate.yml from blocking merges

Status: planned. Owner: the cop of each repo named below (re-vendor); the claude-skills cop (doctor check). Tracker: https://app.notion.com/p/REVIEW-GATE-STALE-VENDOR-FLEET-41e4efecc95a816488e4ff9fc8dabf7e. Source: Program Cop request, 2026-11-20 23:08Z (better practice: a superseded Review Gate run blocks merges).

## What happened

`pr-guard` blocked merges on a superseded failed or cancelled `Review Gate` run in nevar-secrets PRs 23, 24, 25 and 26. The newest run was cancelled, a cancelled newest run is what the required check reads, and the PR stayed blocked until someone re-ran it by hand.

## Root cause

The guard is not the defect. nevar-secrets installed review-gate on 2026-11-15 from the pre-3.2.8 template. That template has `concurrency: cancel-in-progress: true` and POSTs check runs, so every new push or body edit cancels the previous run, and a cancelled run is a failed required check.

The incumbent already fixes this. Since review-gate 3.2.8 the template has no `concurrency:` group on purpose (its comment cites nevar-fund #27), and the job named `Review Gate` is itself the check; nothing is POSTed. The defect is stale vendoring: `install-workflow.py` copies the workflow into each repo once, and nothing tells a repo when its copy has fallen behind the skill.

## Measured 2026-11-20

Default-branch `review-gate.yml` in these 17 org repos still carries `cancel-in-progress: true`:

nevar-secrets, nevar-design, nevar-mail, mbernier.com, nevar-social, nevar-contacts, a10d.info, agents-environment-config, prevost, tools, nevar-notify, agency-agents, nevar-logs, nevar-research, nevar-aec-catalog, nevar-admin, nevar-ai.

Re-measure before each re-vendor PR; the list is a snapshot, not a contract.

## Fix

1. Re-vendor review-gate 3.2.14 in each listed repo with `install-workflow.py --force`, one PR per repo, handled by that repo's traffic cop. nevar-secrets goes first because it is the repo that hit the false blocks. `agents-environment-config` and `agency-agents` are handled by the aec cop.
2. A guard so stale vendoring cannot go unseen again. Use the incumbent `install-workflow.py --doctor-job`, which writes the optional `review-gate-doctor.yml`. It runs `doctor-review-gate.py --strict` on each PR and fails when the repo's `review-gate.yml` or a vendored `scripts/` file is missing or differs from the skill on claude-skills main. It is not a required check (making it one is each repo owner's branch-protection decision) and costs one job of about 10 s per push, billed on private repos. Each re-vendor PR turns it on. A repo that does not want the job can instead be covered by a fleet check that lists repos whose workflow differs from the template.
3. No new script: the re-vendor and the doctor job are both `install-workflow.py` features. Anything added beyond them must say why the incumbent was not enough.

## Done when

- None of the repos above has `cancel-in-progress: true` in its default-branch `review-gate.yml` (check with `gh api repos/bernierllc/<repo>/contents/.github/workflows/review-gate.yml`).
- Each repo runs the doctor job, or is listed in the fleet check's output as matching the template.
- A cancelled or superseded `Review Gate` run no longer blocks a PR in any of them.

## Owners and routing

| Work | Owner |
|---|---|
| Re-vendor in each repo | That repo's traffic cop; the aec cop for `agents-environment-config` and `agency-agents` |
| Doctor job wiring and `install-workflow.py` changes | claude-skills cop |
| Fleet status to Matt | Program Cop |

## Not in scope

Changing `pr-guard` behavior (see `pr-guard-rollup-and-auto-message.md`) and the guard's shell parsing (see `pr-guard-shell-parsing-design.md`).
