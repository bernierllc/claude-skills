# nevar-security-review: roll the Security Scan lane out to the org

Status: planned. Plan id: NEVAR-SEC-SKILL-1 (PR D). Tracker: https://app.notion.com/p/NEVAR-SEC-SKILL-1-nevar-security-review-skill-review-loop-security-gate-OSS-scanner-CI-templates-4204efecc95a8149ab9ef28850ec899c. Owner of this plan: the claude-skills cop. Owner of each repo's rollout: that repo's `Traffic Cop · <repo>`. Related: SKILLS-SEC-CLAIM-2 (https://app.notion.com/p/SKILLS-SEC-CLAIM-2-check-security-scan-py-treats-negated-scanner-reports-as-pass-claims-and-does-no-4204efecc95a81cabcede155ccbc6a95), [`review-gate-stale-vendor-fleet.md`](review-gate-stale-vendor-fleet.md), [`2026-11-22-security-scan-osv-include-resolution.md`](2026-11-22-security-scan-osv-include-resolution.md).

## What exists today

- review-gate 3.3.2 (rule 6) has the opt-in security lane. The lane is on only when the default branch carries `.github/workflows/review-gate-security-scan.yml` and the vendored `scripts/check-security-scan.py`. The gate then needs the trusted `Security Scan` check to have passed on the PR head, under the default branch's current `.github/security-scan/` config tree.
- PR #147 shipped the scan workflow template, `scan.py`, the scanner configs and `exceptions.json` (`nevar-security-review/templates/`). Install steps 1 to 5 and the trust table are in `nevar-security-review/references/nevar.md`.
- The canary repo `bernierllc/nevar-security-scan-canary` ran the lane end to end (evidence below).
- No other org repo has the lane on. mbernier.com carries `check-security-scan.py` on review-gate 3.3.1, but it has no marker workflow.

This plan adds no new scanner, script or workflow. It orders the install the skill already documents. It also adds one design item that the canary showed is missing: the config-digest re-fire (finding 2).

## Canary evidence (bernierllc/nevar-security-scan-canary)

| What | Result |
|---|---|
| Stale config digest blocks (fixture PR 2, head `1830247f3baf5f715df55095fdf80be5e1246966`, never merged) | Canary PR 3 merged as `ebc5a3e1` and changed `.github/security-scan/semgrep.yml`. After that, a body edit re-fired Review Gate run [45002600312](https://github.com/bernierllc/nevar-security-scan-canary/actions/runs/45002600312). It failed at 08:23:57Z. Check run 137147186347 has a head_sha that matches the PR head. The log says: `security lane: 'Security Scan' check 137143904677 scanned config tree dc6536940ae3, not main's current a44b610cf7b9; re-run Security Scan`. The stale scan check 137143904677 (run 45001524714) was itself a success. The gate check on the same head before PR 3 merged (137145599073) was also a success, so the config change alone flipped it. |
| Green path (canary PR 3, merged) | Review Gate run 45002079908 and Security Scan run 45001530399 both passed |
| Scan re-run picks up the new config (canary PR 4, head `eb70c70e2300a608d7869f2e3e3e926d4c3593d6`) | Run 45001534776, attempt 2 ([job 137149176630](https://github.com/bernierllc/nevar-security-scan-canary/actions/runs/45001534776/job/137149176630)) passed. Its head_sha matches, and its notice reads `outcome=not-applicable config-tree=a44b610cf7b9880bb0c6d77002293fde4a67c162` (main's current tree). The template checks out the default branch by name, so a `gh run rerun` reads the current config. |
| Gate passes after the re-run (canary PR 4) | Review Gate run [45004145291](https://github.com/bernierllc/nevar-security-scan-canary/actions/runs/45004145291) passed. Check run 137151881184 is on the PR head. The log says: `security lane ok: the trusted Security Scan passed on the PR head with the default branch's config` |
| Rollback: deleting the marker turns the lane off (canary PR 4 removes `review-gate-security-scan.yml`) | PR 4 merged as `564fe07c`. A body edit re-fired fixture PR 2, and Review Gate run [45004666710](https://github.com/bernierllc/nevar-security-scan-canary/actions/runs/45004666710) (check run 137153467177 on head `1830247f`) logged `security lane not enabled (no .github/workflows/review-gate-security-scan.yml on the default branch)`. |

What the canary did not prove: a PR whose gate is already green is neither re-fired nor blocked when the default branch's config changes. Nothing ran on PR 4 until a person re-ran the scan and edited the body. That is finding 2, below. The canary also covers same-repo PRs only.

## Trust checks a to f

The gate trusts the `Security Scan` check only when all six hold. The state column says what is enforced today and what waits.

| Check | What the gate verifies | State |
|---|---|---|
| (a) Workflow path and ref | The check's job belongs to a run of `.github/workflows/review-gate-security-scan.yml` that this PR's `pull_request_target` event started. The workflow file is read from the default branch. | Enforced (review-gate 3.3.2, rule 6). Any other job's check named `Security Scan` is reported as forged and fails the gate. |
| (b) App identity | The check run's app is `github-actions`. | Enforced. Every workflow in the repo is also `github-actions`, so (b) alone cannot tell jobs apart. (a) and forged-name detection cover that. A required status check pinned to an app cannot prevent a same-name check either, for the same reason. Prevention needs a required-workflow rule, or it stays detection only (step 6). |
| (c) Head SHA | The check run's `head_sha` equals the PR head. | Enforced. Canary: check 137151881184 on `eb70c70e`. |
| (d) Freshness | The newest `Security Scan` job on the head decides, and it must be complete. | Enforced each time the gate runs. A scan that finishes after the gate leaves it incomplete until it is re-fired (a label toggle). Not enforced between gate runs (finding 2). |
| (e) Config digest | The notice `outcome=<o> config-tree=<sha>` matches the conclusion, and `<sha>` equals the default branch's current tree of `.github/security-scan/`. | Enforced each time the gate runs. Canary: run 45002600312 failed on the stale digest. Not enforced between gate runs (finding 2). |
| (f) A PR cannot change the validator, config or baseline | The gate scripts, `scan.py`, the scanner configs and `exceptions.json` load from the default branch. The PR head is checked out as data only. Adding or deleting the marker in a PR changes nothing. | Enforced. Whoever controls the default branch controls the scanner. A repo admin's edit is out of scope. |

Also:

- Publisher trust is ADVISORY / UNVERIFIED. A `Security review:` line in the PR body, and any model or human claim of review coverage, can be edited by the author. It is never a check. A scanner-pass claim in the body with no verified passing scan behind it fails the gate. In 3.3.2 every pass word counts, negated or not, so a failure report such as `semgrep did not pass` still counts as a claim and fails the gate. The author rewords it without a pass word, for example `semgrep reported 2 findings`, and the failure message says how. That closed finding 1 of SKILLS-SEC-CLAIM-2. 3.3.1 parsed negation, and review evaded that three ways. A repo that upgrades must reword such lines, not expect them to pass.
- Fork-PR residual: fork PRs are unverified. The template checks out the head sha from the base repository, and GitHub serves fork heads there, so the scanned bytes are the fork's. The canary covers same-repo PRs only. Until a fork-PR canary exists, a repo that accepts fork PRs treats a green lane on a fork PR as advisory.
- Same-name residual: a job anywhere in the repo that has `checks: write` can create a check named `Security Scan`. The gate detects it as forged but cannot prevent it until step 6. So each repo runs the collision check before install (below).

## Finding 2: a config change after a green gate (SKILLS-SEC-CLAIM-2)

Finding 2, verbatim: "lane-on only: the default-branch .github/security-scan digest is checked once when the gate runs, so a later config change does not refire or block an already green PR, and the merge guard runs only the forged-check wrapper (line ~161)".

Measured on origin/main 25598d4: `review-gate/scripts/merge-guard.py` `forged_gate_check()` (around line 3758) runs only `check-forged-review-gate.py` before a merge. It does not run the lane. A PR whose gate passed before a config change therefore keeps a green required check, and nothing re-fires it.

Design, owned by review-gate. Both parts land, and are proven on the canary, before any repo turns the lane on as more than a pilot:

1. Primary: re-fire when the config changes. This plan sets the requirements. The step 2 review-gate PR owns the mechanics, which workflows and which triggers, and proves them with its own tests and on the canary. Review rounds on this plan found three P1s in those mechanics, so they are designed where they can be tested, not here. Requirements:
   1. A change on the default branch to `.github/security-scan/**`, the scan workflow, or the lane's policy code (`scripts/check-security-scan.py` and `review-gate.yml`) re-evaluates `Security Scan` and `Review Gate` for every open PR, whatever its base, with no PR event. Rule 6 applies to every base, and a `staging` to `main` promotion is scanned with staging's config.
   2. The gate goes red on the stale digest, then turns green again once a scan under the new tree passes, with no manual step.
   3. The mechanism is trusted code from the default branch and never checks out or runs PR code. Its token has the least permissions that work and is proven on the private canary: at least `actions: write`, plus `pull-requests: read` to list PRs in a private repo.
   4. It only touches runs of the lane's own workflows, for that PR, on its current head. Overlapping config pushes each finish, and the newest tree wins.
   5. A run that cannot be re-run fails closed: missing, past GitHub's 30-day re-run window, past the attempt limit, or with its workflow disabled. The mechanism fails visibly and names the PR. Recovery is an event that starts both workflows: re-enable a disabled workflow, then close and reopen the PR. A label toggle starts only `Review Gate`, because the scan template triggers on `opened`, `synchronize`, `reopened` and `ready_for_review`.
   6. The installer and doctor install and verify every workflow the lane needs (preflight 1).
   7. Freshness is one invariant: a scan result is accepted only while every input that decided it is unchanged and still valid. Review rounds found these inputs one at a time, so the step 2 PR names them in the scan notice and checks them all in `check-security-scan.py`, which the gate and the live merge guard both call. The inputs, at least:
      1. the PR head SHA;
      2. the base it was compared against: a retarget changes the diff without changing the head, and the scan template does not trigger on `edited`;
      3. the config tree of `.github/security-scan/` on the default branch;
      4. the scan workflow's revision on the default branch: a re-run keeps its original workflow version, so the re-fire must run the current trusted definition;
      5. the validity of every exception the scan applied: an exception that expires while the PR is open invalidates the result;
      6. the scan's age: OSV reads a live advisory database, so a dependency can become vulnerable with every other input unchanged. Advisory data cannot be pinned, so the result expires after a maximum age that the step 2 PR sets and documents (for example 24 hours), and the mechanism re-scans open PRs before that. Between scans, an advisory published after the last scan is a stated residual on each repo's Tracker row;
      7. the lane's policy code on the default branch, `scripts/check-security-scan.py` and `review-gate.yml`: a gate that passed under an older validator is stale once a stricter one lands.
      A change to any input makes the result stale. The gate and the merge guard refuse it until a fresh scan passes, and the mechanism starts that scan. A new input found later is added to this list, not designed in a new section.
2. Defense in depth: the merge guard checks the lane live. `merge-guard.py` calls `check-security-scan.py` with the live default-branch digest whenever the lane is on, and fails closed exactly as `forged_gate_check()` does. This blocks an agent merge at once, whatever state the re-fire is in.
3. Kept residual: the UI-merge window. Invalidation is asynchronous, whichever requirement 7 input changes: a config, workflow or validator push, a retarget, an exception expiring, or a result passing its maximum age. From that change until the re-run `Review Gate` finishes, the old green check stands, and a merge in the GitHub UI succeeds. When the re-fire workflow is queued or failing, the window lasts until it runs. The lane therefore claims only this much: an agent merge is blocked at once (part 2), and a UI merge is blocked once the re-fire lands (part 1). Only an evaluation at merge time can close the window, such as a merge queue that re-runs required checks on `merge_group`. review-gate's workflows do not handle `merge_group` today, so that is a separate review-gate decision, outside this rollout. Each repo's Tracker row states the window, and config changes merge when no PR is about to merge.

Canary proof needed:

- Open a same-repo PR into the default branch and a PR into a second, non-default branch, and let both gates go green.
- Merge a config-only change to the default branch. With no PR event, both PRs' `Review Gate` must turn red, then turn green again once the re-run scan passes, with no manual event.
- The merge guard must refuse `gh pr merge` while a gate is red.
- Delayed invalidation: disable the re-fire workflow, merge another config change, and record that `gh pr view --json mergeStateStatus` still reads mergeable while the merge guard refuses. That proves the residual is exactly as stated above.
- The fail-closed path for runs that cannot be re-run is unit-tested in the step 2 PR, because a 30-day expiry cannot be staged on the canary. The canary does show recovery after a missing run: delete the PR's newest scan run, then close and reopen the PR.
- The canary is private, so these runs also prove the token's permissions. Record the re-fire workflow's permissions block, and show that it never checks out PR code (requirement 3).
- Workflow-only change: merge a change to the scan workflow alone. The old definition's result must not pass the gate, and a scan under the new definition must (requirement 7, input 4).
- Same-head retarget: change a green PR's base to a branch that adds a changed file. The old result must stop passing, and a fresh scan of the new comparison must decide (requirement 7, input 2).
- Exception expiry: a PR passes under a dated exception. Once that exception expires, the gate and the merge guard must refuse the old result. The step 2 PR unit-tests the boundary with an injected clock, and the canary shows it with an exception dated to expire during the proof (requirement 7, input 5).
- Maximum age: the step 2 PR unit-tests the boundary with an injected clock, and the canary shows a result past its age refused until a re-scan passes (requirement 7, input 6).
- Validator change: merge a stricter `check-security-scan.py` to the default branch alone. A gate that passed under the old validator must be re-evaluated, with no PR event (requirement 7, input 7).
- Overlapping pushes and a moving head: merge two config changes back to back and show that the newest tree decides. Push to a PR while its re-fire runs and show that only the new head's runs count. Run a same-name job from another workflow and show it is neither re-run nor counted (requirement 4).
- Install the lane on the canary with the extended installer, and show that the doctor passes only once every lane workflow is on the default branch (requirement 6).

Record the run URLs on the SKILLS-SEC-CLAIM-2 row. The canary repo is therefore kept until this proof is done. Its deletion approval (Ops #61) covers only the first phase.

## Order

No required-check enforcement on the fleet comes before the canary proof and the trust proof (finding 2 parts 1 and 2 shown on the canary).

1. Canary: done. Phase 1 DONE-PROOF is on bernierllc/nevar-platform-ops issue 61. The repo stays up for the finding 2 proof.
2. Finding 2: implement parts 1 and 2 in review-gate, then prove them on the canary. The claude-skills cop owns this as one PR, with its own tests. The same PR also does two things:
   - It extends the installer (`install-workflow.py`) and the scanner install steps in `references/nevar.md` to install the finding 2 workflows. It also extends the doctor to verify, on the default branch, that every lane workflow is present.
   - It adds the fail-closed collision check to review-gate's doctor (preflight 2).
   - It corrects `nevar-security-review/references/nevar.md` install step 5. That step says the install PR fails its own scan, but the canary install PR 1 had no Security Scan run (preflight 4).
3. Tag a claude-skills release that has review-gate with finding 2 fixed and the #147 template (claude-skills cop). The AEC cop then cuts an AEC release whose vendored `.claude/skills` points at that tag.
4. Pin through the catalog. `nevar-aec-catalog` (its cop) takes skills from `aec.default.skills` and has no per-skill pin, so the pin is the AEC release from step 3, plus the claude-skills tag each repo's vendored copy is installed from. If `review-gate` and `nevar-security-review` are missing from `org/nevar.yaml` `items.skills`, add them with stance `recommended`, not `required`, until step 6.
5. Per-repo rollout, one PR per repo, by that repo's cop, in the table's order: mbernier.com first, then the others. Each PR follows the preflight below.
6. Ops: one deduped ask on bernierllc/nevar-platform-ops issue 1, and no new Ops issue. It is made only after step 3's tagged release exists and at least one repo past mbernier.com shows a passing lane on a new PR. A required status check pinned to an app cannot single out the scan workflow, because every Actions workflow publishes as `github-actions`. So the ask is for one of two outcomes. The first is a ruleset "require workflows to pass" rule that names the scan workflow at a pinned ref, if the org's plan offers it and it is proven compatible with check (a) on the canary first. That rule starts its own run, so check (a)'s event and path rules must accept that run. The second is no prevention: the same-name residual stays detection only, and the trust table records that. Ops applies rulesets. No author or cop edits another repo's rulesets or settings.

## Per-repo preflight (every repo, every PR)

Owner: `Traffic Cop · <repo>`. Measure again before each PR; the table below is a snapshot.

1. Pin: install review-gate (at least 3.3.2, with finding 2 fixed) and the template from the step 3 claude-skills tag, never from `main`. Use `install-workflow.py --force` and add `--doctor-job`, as the stale-vendor plan requires. That installer, as step 2 extends it, also installs the finding 2 workflows. The doctor must show every lane workflow on the default branch before the repo counts as installed. Where that plan's re-vendor is still open for the repo, this one PR does both, so the repo never gets two re-vendor PRs. The repo's row closes only when both plans' acceptance criteria are recorded: this plan's proof (preflight 6), and the stale-vendor plan's green doctor job, default-branch file check, and a passing gate after a body edit and a label event.
2. Collision check: no other job may publish a check named `Security Scan`. Run review-gate's doctor, which step 2 extends to do this check fail-closed. It parses every workflow file on the default branch with a YAML parser and takes each job's effective check name: its `name:`, or its job id when there is none. An exact `Security Scan` is a collision unless it is the trusted scanner's own job in `.github/workflows/review-gate-security-scan.yml`, which the check excludes by workflow path. A job name that holds an expression (`${{`), including a matrix-derived name, is flagged for a person to inspect. Any API, decode or parse error exits non-zero and never reads as clean. As a cross-check only, the doctor also counts `Security Scan` check runs on the default-branch head and on the heads of the five newest open PRs. It leaves out runs whose job belongs to a run of the trusted scanner workflow, using the same provenance test as check (a). Expect 0 foreign runs. The step 2 PR tests the doctor both before and after the install. Any hit gets renamed in a PR that merges first (install step 2 in `references/nevar.md`). A workflow titled `Security Scanning`, or titled `Security Scan` with jobs that have other names, is not a collision: the job name is the check name.
3. Default branch: the marker, configs and exceptions go on the repo's default branch. For staging-default repos that is `staging`. A `staging` to `main` promotion PR is scanned with staging's config, because `pull_request_target` loads from the default branch.
4. Bootstrap: the install PR is not scanned. `pull_request_target` runs the default branch's copy of the workflow, and the marker is not there yet. On the canary, the first Security Scan run (08:10:05Z) came after install PR 1 merged (08:08:56Z). Any later PR that edits the scanner workflow gets zizmor `dangerous-triggers` on that file. For those PRs, a dated, owned exception for that file merges first, as `references/nevar.md` shows. The install PR should carry it: that counts as merging first, so no separate exception PR is needed. The first PR after the install proves that the scan runs (preflight 6). The first PR that edits the workflow proves that the exception applies, and its run URL goes on the Tracker row.
5. Dependency files: until the OSV coverage plan lands, any change, deletion or rename of a lockfile or requirements file is a `not-covered` finding on that file. It needs a per-file exception (`scanner: osv-scanner`, `rule: not-covered`, exact path, owner, expiry, reason) merged to the default branch first. Expect this on dependency-bump PRs, and do not batch the exceptions.
6. Proof: the first PR after the install merges must show a passing `Security Scan` with `config-tree=` equal to the default branch's tree, and a gate log saying `security lane ok`. Record both run URLs on the repo's Tracker row.
7. Rollback, in order:
   1. If step 6 made `Security Scan` required in the repo, Ops removes that rule first, on the same platform-ops issue 1 thread.
   2. Delete `.github/workflows/review-gate-security-scan.yml` from the default branch. The gate then reports `security lane not enabled`; the canary rollback row proves this.
   3. Re-fire the gates of open PRs with a label toggle. Only `Review Gate` needs to run here, because the lane is off once the marker is gone.
   4. Show that a fresh PR merges, and record that on the Tracker row.

   The configs can stay. Roll the vendored review-gate back to its previous tag only if review-gate itself regresses.
8. Cost: Security Scan is one job per PR event, plus the finding 2 refreshes: a re-scan and gate run for every open PR on each input change, and periodic re-scans that keep each open PR inside the maximum age. The step 2 PR documents that cadence next to the maximum age. On private repos all of it bills Actions minutes (`ci-cost.md`).

## Per-repo table (measured 2026-11-22)

Every row's owner is `Traffic Cop · <repo>`. "Collision" is the number of workflow jobs named `Security Scan` on the default branch, plus check runs of that name there. All rows except the canary are 0 today.

| Repo | Default | review-gate now | Lane script | First step |
|---|---|---|---|---|
| mbernier.com | staging | 3.3.1 | yes | Re-vendor review-gate at the step 3 tag, the release that carries finding 2. 3.3.2 is the first release with the claims fix, but it lacks finding 2. 3.3.1 still parses negation in claims, which SKILLS-SEC-CLAIM-2 finding 1 showed could be evaded. After the upgrade, a failure report that uses a pass word must be reworded. Its `security-scan.yml` ("Security Scanning": Dependency Vulnerability Scan, Secrets Detection, Scheduled audit issue) does not collide. |
| nevar-mail | staging | 3.2.22 | no | Re-vendor at the pin |
| nevar.io | staging | 3.2.22 | no | Re-vendor at the pin |
| nevar-api | staging | 3.2.20 | no | Re-vendor at the pin |
| nevar-auth | staging | 3.2.21 | no | Re-vendor at the pin |
| nevar-audit | staging | 3.2.20 | no | Re-vendor at the pin |
| a10d.info | staging | 3.2.20 | no | Re-vendor at the pin |
| nevar-plan | staging | 3.2.17 | no | Re-vendor at the pin |
| nevar-social | staging | 3.2.17 | no | Re-vendor at the pin |
| nevar-design | staging | 3.2.17 | no | Re-vendor at the pin |
| nevar-content | staging | 3.2.14 | no | Re-vendor at the pin |
| nevar-logs | staging | 3.2.14 | no | Re-vendor at the pin |
| nevar-chat | staging | 3.2.11 | no | Re-vendor at the pin |
| nevar-buzz | staging | 3.2.11 | no | Re-vendor at the pin |
| nevar-fund | staging | 3.2.11 | no | Re-vendor at the pin |
| nevar-integrations | staging | 3.2.8 | no | Re-vendor at the pin. Its 3.2.8 copy still cancels runs, so follow "Migrating to 3.2.8" in `review-gate/SKILL.md`. |
| prevost | main | 3.2.17 | no | Re-vendor at the pin |
| nevar-aec-catalog | main | 3.2.16 | no | Re-vendor at the pin, after step 4's catalog change |
| nevar-contacts | main | 3.2.14 | no | Re-vendor at the pin |
| agency-agents | main | 3.2.14 | no | Re-vendor at the pin (aec cop) |
| nevar-secrets | main | 3.2.14 | no | Re-vendor at the pin |
| tools | main | 3.2.21 | no | Re-vendor at the pin |
| nevar-app, nevar-research | staging | no vendored version found | no | Install review-gate at the pin first, then the lane |
| agents-environment-config, nevar-admin, nevar-notify, nevar-ai | main | no vendored version found | no | Install or re-vendor review-gate at the pin first (the stale-vendor plan lists their `review-gate.yml`), then the lane |
| claude-skills | main | source repo | yes | Runs review-gate from its own tree. Decide in step 5 whether it takes the lane. |

Excluded: review-gate-sandbox, review-gate-repro14, and the canary (test repos).

## Done when

- The finding 2 proof is recorded, with run URLs, on the Tracker and SKILLS-SEC-CLAIM-2 rows. It covers every bullet under "Canary proof needed": both bases, delayed invalidation, missing-run recovery, permissions, the workflow-only change, the same-head retarget, exception expiry, maximum age, a validator change, overlapping pushes and a moving head, foreign-run isolation, and the installer and doctor round trip.
- A claude-skills tag and the matching AEC release exist, and the catalog pins to them.
- Every repo in the table has either the lane on, with its proof row recorded, or a written reason on its Tracker row why it waits.
- The single platform-ops issue 1 ask is answered and recorded. Either a required-workflow rule is proven on the canary and applied in the repos that took the lane, or the trust table keeps the same-name residual as detection only.
