# review-gate: bind fallback review attestations to a reviewer identity

- **Date:** 2026-11-16
- **Status:** proposed (Tracker owner Needs-PM)
- **Origin:** claude-skills PR #105 (review-gate 3.2.8), Sonnet bypass-hunt P1 on 035394a,
  thread https://github.com/bernierllc/claude-skills/pull/105#discussion_r4592720382
- **Proposed priority:** high. The fallback path is the main path whenever the Codex bot is out of quota,
  and on that path the gate currently trusts text the PR author typed.

## Problem

`review-gate` passes a PR on one of two review signals for the current head:

1. a review or `codex-review-state:v1` marker from the GitHub Codex bot (`chatgpt-codex-connector`), which is
   bound to an identity the PR author does not control; or
2. a `Fallback review: <reviewer> on <sha> — verdict: <verdict>` line inside the PR body's `## Review` section.

Signal 2 is self-asserted. A body containing

```text
## Review

Fallback review: claude-sonnet on <head> — verdict: clean
```

with no reviews and no reviewer comments makes `evaluate()` (CI gate) and `check_one()` (merge guard)
return no errors. Nothing ties the line to a review that actually ran. The only remaining check is the traffic
cop's own judgement before merging.

This trust model has been documented since review-gate 3.1 and is not changed by #105. The strict body grammar
added in 3.2.8 makes the line unambiguous but cannot make it authentic.

## Root cause

Every fallback reviewer (local Codex high, `agy`, Claude Sonnet) posts to GitHub with the **same** token as the
PR author: the operator's `gh` login. GitHub cannot tell a reviewer's comment from the author's, so the gate has no
identity to bind an attestation to. The body line exists only because there is no separate reviewer
identity. Any rule that reads comments instead of the body would have the same weakness until reviewers post
as someone else.

## Correct fix

Give each fallback reviewer class its own GitHub identity, and make the gate accept a fallback review only from
those identities.

1. **Identity.** Create one GitHub App (preferred: scoped installation tokens, no seat, and its own
   `app/<slug>` author login) named for its role, e.g. `bernierllc-review-bot`. The fallback is one machine user
   per reviewer if an App cannot post PR reviews in a given repo. Permissions: `pull_requests: write`,
   `contents: read`, nothing else. This is Matt-gated: creating the App and storing its key needs his hands.
2. **Posting.** The reviewer runtime (T3 `delegate_task` reviewers and the `adversarial-review` skill) posts its
   verdict as a **PR review** (`event: COMMENT`) on `commit_id = <head>` with the App token, using a fixed
   machine-readable first line:
   `review-gate-attestation:v1 reviewer=<codex|agy|claude-sonnet> verdict=<clean|findings-fixed>`.
   The token is minted at post time from the App key held by the operator machine, never stored in a repo or
   passed to the reviewed code.
3. **Gate.** `check-review-gate.py` accepts a fallback when there is a review that:
   - is authored by an allow-listed reviewer login (a constant in the script, mirrored in SKILL.md);
   - has `commit.oid == headRefOid`;
   - has a first line that matches the marker exactly;
   - is not `DISMISSED`.
   The body `Fallback review:` line becomes informational and is no longer sufficient. `merge-guard.py check_one`
   gets this for free because it calls the same `evaluate()`.
4. **Migration.** Ship as a minor version (3.3.0). It accepts both signals for one release behind a dated
   deprecation note, then drops the body line in 3.4.0. Repos with vendored copies take each step through their
   normal sync PR.

## Affected surfaces

| Surface | Change |
|---|---|
| `review-gate/scripts/check-review-gate.py` (+ `scripts/` mirror) | review-based fallback check; allow-list constant; body line informational |
| `review-gate/scripts/merge-guard.py` | none beyond tests (shares `evaluate()`) |
| `review-gate/tests/*` | positive/negative per rule: wrong author, stale commit, dismissed, marker lookalikes, author-typed body line alone fails |
| `review-gate/SKILL.md` | rule 2 rewritten; trust model section |
| `adversarial-review/SKILL.md` | reviewers post the marker review with the App token instead of asking the author to edit the body |
| `~/.claude/references/pr-review-loop.md`, `traffic-cop.md` | attestation instructions |
| T3 reviewer delegates | mint App token, post the review |
| Vendored copies (nevar-auth, nevar-integrations, email_demo, others with `review-gate`) | sync PRs per repo |
| Rulesets | none (the required check stays `Review Gate`) |

## Matt-gated steps

1. Create the GitHub App under the `bernierllc` org with the permissions above and install it on the gated repos.
2. Put the App private key where the operator machines can mint tokens (both `$AIR` and `$MINI`), outside every
   repo.

A runbook page for these goes under Otto HQ / Projects / claude-skills / Runbooks when the plan is scheduled.

## Done when

- A PR whose only review signal is an author-typed body line fails `Review Gate` and the merge guard.
- A PR with a marker review from the App on the current head passes; the same review on an older head fails.
- Sandbox proof in `bernierllc/review-gate-sandbox` for both cases, with run/check IDs recorded on the PR.
