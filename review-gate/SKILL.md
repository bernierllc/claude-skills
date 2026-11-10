---
name: review-gate
description: Enforce adversarial review before merge and save CI minutes when review comments land. Use when installing review gates on nevar* repos, when CI should cancel on new review comments, when merge must wait for unresolved threads or unanswered P2s, or when doctoring whether a repo's ruleset and review-gate.yml are configured. Companion to adversarial-review and pr-merge-flow.
version: 1.0.1
author: Bernier LLC
---

# Review gate

Programmatic enforcement for the adversarial review loop. Ships:

1. **Workflow template** — `.github/workflows/review-gate.yml`
2. **Doctor** — warns when the workflow or ruleset conversation-resolution flag is missing
3. **PreToolUse merge guard** — blocks `gh pr merge` when the local gate check fails

## Install (per repo)

```bash
aec install skill review-gate
# copy once into the tracked workflow (AEC install alone does not commit it):
mkdir -p .github/workflows
cp "$(aec path skill review-gate)/templates/review-gate.yml" .github/workflows/review-gate.yml
# or: python3 "$(aec path skill review-gate)/scripts/install-workflow.py"
```

Then flip GitHub rulesets (no Actions minutes):

```bash
# For each ruleset that has a pull_request rule (usually staging + main):
gh api -X PUT "repos/<owner>/<repo>/rulesets/<id>" --input - <<'EOF'
{ ...keep existing fields..., "rules": [ { "type": "pull_request", "parameters": { "required_review_thread_resolution": true, ... } } ] }
EOF
```

Email_demo and Prevost already have `required_review_thread_resolution: true` (2026-10-17/18). Add **`Review Gate`** (the job display name / Checks API context — not the workflow file name alone) as a **required check** on those rulesets beside CI.

Doctor:

```bash
aec run-script skill:review-gate doctor-review-gate.py
# or: python3 review-gate/scripts/doctor-review-gate.py
```

## What the workflow does

### Job `cancel-ci-on-finding`

On `pull_request_review_comment` created: cancel in-progress non-gate CI **only** for new top-level P0/P1 findings. Replies, closing tokens (Notion / `fixed in` / `not-a-finding:`), and P2-only comments do **not** cancel CI — those paths often need no new head, and a cancelled required check would otherwise stick.

### Job `gate` (display name `Review Gate`)

On eligible events (`pull_request`, `pull_request_review`): fail unless all hold:

1. A completed Codex review exists on the **current head**, or the PR body's `## Review` section names a fallback (`agy` / `superpowers` / `claude` / `antigravity`).
2. PR body contains a `## Review` section.
3. Every review thread whose **root** comment matches `\bp2\b` has a reply with a closing token: Notion link, `fixed in <sha>`, or `not-a-finding: …`.
4. When `base` is `main`: label `review:high` or `review:ultra` is present.

### Job `gate-refresh-on-comment`

`pull_request_review_comment` is **not** an eligible Actions event for required checks. That job re-evaluates the gate and publishes a Checks API run named `Review Gate` on the head SHA so a closing reply can clear a prior failure without a dummy push.

Unresolved threads are **not** checked here — that is GitHub's `required_review_thread_resolution` on the ruleset (free, instant on resolve).

Judgment/Jev triage is **out of scope** for v1 (still piloted in NevarMail per the 2026-10-16 enforcement plan).

## Merge guard

PreToolUse blocks `gh pr merge` (including `--auto`) when `check-review-gate.py` fails for that PR. Override with `# review-gate-ok: <reason>` in the command only for Matt-approved escapes.

## Apply across nevar*

1. `aec install skill review-gate` + copy workflow in each repo (or a small apply PR series).
2. Doctor in CI or a weekly scheduled task; warn (do not hard-fail) until the first month of data.
3. Keep `adversarial-review` installed so agents post the inline comments the gate expects.

## Related

- Loop behavior: skill `adversarial-review` / `~/.claude/references/pr-review-loop.md`
- Base-sync discipline: skill `pr-merge-flow`
- Plan of record: `email_demo/plans/2026-10-16-dev-environment-enforcement-plan.md` §6
