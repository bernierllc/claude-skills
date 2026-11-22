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
| Rollback: deleting the marker turns the lane off (canary PR 4 removes `review-gate-security-scan.yml`) | Pending. After PR 4 merges, a re-fire of fixture PR 2 must log `security lane not enabled`. The run URL gets recorded on the Tracker row. |

What the canary did not prove: a PR whose gate is already green is neither re-fired nor blocked when the default branch's config changes. Nothing ran on PR 4 until a person re-ran the scan and edited the body. That is finding 2, below. The canary also covers same-repo PRs only.

## Trust checks a to f

The gate trusts the `Security Scan` check only when all six hold. The state column says what is enforced today and what waits.

| Check | What the gate verifies | State |
|---|---|---|
| (a) Workflow path and ref | The check's job belongs to a run of `.github/workflows/review-gate-security-scan.yml` that this PR's `pull_request_target` event started. The workflow file is read from the default branch. | Enforced (review-gate 3.3.2, rule 6). Any other job's check named `Security Scan` is reported as forged and fails the gate. |
| (b) App identity | The check run's app is `github-actions`. | Enforced. Every workflow in the repo is also `github-actions`, so (b) alone cannot tell jobs apart. (a) and forged-name detection cover that. Prevention, rather than detection, needs a ruleset that pins the check's source (step 6). |
| (c) Head SHA | The check run's `head_sha` equals the PR head. | Enforced. Canary: check 137151881184 on `eb70c70e`. |
| (d) Freshness | The newest `Security Scan` job on the head decides, and it must be complete. | Enforced each time the gate runs. A scan that finishes after the gate leaves it incomplete until it is re-fired (a label toggle). Not enforced between gate runs (finding 2). |
| (e) Config digest | The notice `outcome=<o> config-tree=<sha>` matches the conclusion, and `<sha>` equals the default branch's current tree of `.github/security-scan/`. | Enforced each time the gate runs. Canary: run 45002600312 failed on the stale digest. Not enforced between gate runs (finding 2). |
| (f) A PR cannot change the validator, config or baseline | The gate scripts, `scan.py`, the scanner configs and `exceptions.json` load from the default branch. The PR head is checked out as data only. Adding or deleting the marker in a PR changes nothing. | Enforced. Whoever controls the default branch controls the scanner. A repo admin's edit is out of scope. |

Also:

- Publisher trust is ADVISORY / UNVERIFIED. A `Security review:` line in the PR body, and any model or human claim of review coverage, can be edited by the author. It is never a check. A scanner-pass claim in the body with no verified passing scan behind it fails the gate (3.3.2 reads a negated report as no claim, which fixed finding 1 of SKILLS-SEC-CLAIM-2).
- Fork-PR residual: fork PRs are unverified. The template checks out the head sha from the base repository, and GitHub serves fork heads there, so the scanned bytes are the fork's. The canary covers same-repo PRs only. Until a fork-PR canary exists, a repo that accepts fork PRs treats a green lane on a fork PR as advisory.
- Same-name residual: a job anywhere in the repo that has `checks: write` can create a check named `Security Scan`. The gate detects it as forged but cannot prevent it until step 6. So each repo runs the collision check before install (below).

## Finding 2: a config change after a green gate (SKILLS-SEC-CLAIM-2)

Finding 2, verbatim: "lane-on only: the default-branch .github/security-scan digest is checked once when the gate runs, so a later config change does not refire or block an already green PR, and the merge guard runs only the forged-check wrapper (line ~161)".

Measured on origin/main 25598d4: `review-gate/scripts/merge-guard.py` `forged_gate_check()` (around line 3758) runs only `check-forged-review-gate.py` before a merge. It does not run the lane. A PR whose gate passed before a config change therefore keeps a green required check, and nothing re-fires it.

Design, owned by review-gate. Both parts land, and are proven on the canary, before any repo turns the lane on as more than a pilot:

1. Primary: re-fire when the config changes. The template set gains a trusted workflow that runs on `push` to the default branch, filtered to `.github/security-scan/**` and `.github/workflows/review-gate-security-scan.yml`. For each open PR into the default branch, it re-runs the newest `Security Scan` run (`gh run rerun`, already proven to read the current config) and the newest `Review Gate` run. The gate goes red on the digest mismatch at once. That blocks the merge, and it turns green only once the re-run scan has passed under the new tree. The workflow needs `actions: write` and only re-runs existing runs, never PR code. Before step 3 ships, the pilot must show that a re-run `Review Gate` reads the current default-branch digest and not the one from the original event.
2. Defense in depth: the merge guard checks the lane live. `merge-guard.py` calls `check-security-scan.py` with the live default-branch digest whenever the lane is on, and fails closed exactly as `forged_gate_check()` does. This covers an agent merge in the gap before the re-fire lands. A human merge in the GitHub UI is covered only by part 1, which is why part 1 is primary.

Canary proof needed: open a same-repo PR and let its gate go green. Then merge a config-only change to the canary's default branch. With no PR event, the PR's `Review Gate` must turn red. After the re-run scan passes, it must turn green again. The merge guard must refuse `gh pr merge` while it is red. Record the run URLs on the SKILLS-SEC-CLAIM-2 row. The canary repo is therefore kept until this proof is done. Its deletion approval (Ops #61) covers the first phase only.

## Order

No required-check enforcement on the fleet comes before the canary proof and the trust proof (finding 2 parts 1 and 2 shown on the canary).

1. Canary: done, except the rollback row above.
2. Finding 2: implement parts 1 and 2 in review-gate (claude-skills cop, one PR, which carries its own tests), then prove them on the canary.
3. Tag a claude-skills release that has review-gate with finding 2 fixed and the #147 template (claude-skills cop). The AEC cop then cuts an AEC release whose vendored `.claude/skills` points at that tag.
4. Pin through the catalog. `nevar-aec-catalog` (its cop) takes skills from `aec.default.skills` and has no per-skill pin, so the pin is the AEC release from step 3, plus the claude-skills tag each repo's vendored copy is installed from. If `review-gate` and `nevar-security-review` are missing from `org/nevar.yaml` `items.skills`, add them with stance `recommended`, not `required`, until step 6.
5. Per-repo rollout, one PR per repo, by that repo's cop, in the table's order: mbernier.com first, then the others. Each PR follows the preflight below.
6. Ops: one deduped ask on bernierllc/nevar-platform-ops issue 1, and no new Ops issue. It is made only after step 3's tagged release exists and at least one repo past mbernier.com shows a passing lane on a new PR. It asks for a ruleset per repo that makes `Security Scan` a required check, with its source pinned to the scan workflow, so that the same-name residual is prevented and not only detected. Ops applies rulesets. No author or cop edits another repo's rulesets or settings.

## Per-repo preflight (every repo, every PR)

Owner: `Traffic Cop · <repo>`. Measure again before each PR; the table below is a snapshot.

1. Pin: install review-gate (at least 3.3.2, with finding 2 fixed) and the template from the step 3 claude-skills tag, never from `main`. Use `install-workflow.py --force` and add `--doctor-job`, as the stale-vendor plan requires. Where that plan's re-vendor is still open for the repo, this one PR does both, so the repo never gets two re-vendor PRs.
2. Collision check: no other job may be named `Security Scan`. On the default branch:

   ```sh
   repo=bernierllc/my-repo; ref=staging
   for f in $(gh api "repos/$repo/contents/.github/workflows?ref=$ref" --jq '.[].name'); do
     gh api "repos/$repo/contents/.github/workflows/$f?ref=$ref" --jq .content | base64 -d \
       | grep -nE '^[[:space:]]*name:[[:space:]]*["'"'"']?Security Scan["'"'"']?[[:space:]]*$' | sed "s|^|$f:|"
   done
   gh api "repos/$repo/commits/$ref/check-runs?check_name=Security%20Scan" --jq .total_count
   ```

   Expect no workflow hits and a count of 0. Run the check-runs query on the heads of the five newest open PRs as well. Any hit gets renamed in a PR that merges first (install step 2 in `references/nevar.md`). A workflow named `Security Scanning`, or jobs with other names, is not a collision.
3. Default branch: the marker, configs and exceptions go on the repo's default branch. For staging-default repos that is `staging`. A `staging` to `main` promotion PR is scanned with staging's config, because `pull_request_target` loads from the default branch.
4. Bootstrap: the install PR fails its own scan with zizmor `dangerous-triggers` on the new workflow. A dated, owned exception for that file merges first, exactly as `references/nevar.md` shows.
5. Dependency files: until the OSV coverage plan lands, any change, deletion or rename of a lockfile or requirements file is a `not-covered` finding on that file. It needs a per-file exception (`scanner: osv-scanner`, `rule: not-covered`, exact path, owner, expiry, reason) merged to the default branch first. Expect this on dependency-bump PRs, and do not batch the exceptions.
6. Proof: the first PR after the install merges must show a passing `Security Scan` with `config-tree=` equal to the default branch's tree, and a gate log saying `security lane ok`. Record both run URLs on the repo's Tracker row.
7. Rollback: delete `.github/workflows/review-gate-security-scan.yml` from the default branch. The gate then reports `security lane not enabled` (the canary rollback row proves this). The configs can stay. Roll the vendored review-gate back to its previous tag only if review-gate itself regresses.
8. Cost: Security Scan is one job per PR event. On private repos it bills Actions minutes (`ci-cost.md`), and nothing else turns on with it.

## Per-repo table (measured 2026-11-22)

Every row's owner is `Traffic Cop · <repo>`. "Collision" is the number of workflow jobs named `Security Scan` on the default branch, plus check runs of that name there. All rows except the canary are 0 today.

| Repo | Default | review-gate now | Lane script | First step |
|---|---|---|---|---|
| mbernier.com | staging | 3.3.1 | yes | Re-vendor review-gate 3.3.2 at the pin. 3.3.1 still has the negated-report false positive that SKILLS-SEC-CLAIM-2 finding 1 fixed. Its `security-scan.yml` ("Security Scanning": Dependency Vulnerability Scan, Secrets Detection, Scheduled audit issue) does not collide. |
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

- The canary rollback row and the finding 2 proof are recorded, with run URLs, on the Tracker and SKILLS-SEC-CLAIM-2 rows.
- A claude-skills tag and the matching AEC release exist, and the catalog pins to them.
- Every repo in the table has either the lane on, with its proof row recorded, or a written reason on its Tracker row why it waits.
- The single platform-ops issue 1 ask is answered, and rulesets pin `Security Scan` to its workflow in the repos that took the lane.
