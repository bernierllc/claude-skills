---
name: review-gate
description: Enforce adversarial review before merge and save CI minutes when review comments land. Use when installing review gates on nevar* repos, when CI should cancel on new review comments, when merge must wait for unresolved threads or unanswered P2s, or when doctoring whether a repo's ruleset and review-gate.yml are configured. Companion to adversarial-review and pr-merge-flow.
version: 1.0.0
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
# or: python3 "$(dirname)/scripts/install-workflow.py"
```

Then flip GitHub rulesets (no Actions minutes):

```bash
# For each ruleset that has a pull_request rule (usually staging + main):
gh api -X PUT "repos/<owner>/<repo>/rulesets/<id>" --input - <<'EOF'
{ ...keep existing fields..., "rules": [ { "type": "pull_request", "parameters": { "required_review_thread_resolution": true, ... } } ] }
EOF
```

Email_demo and Prevost already have `required_review_thread_resolution: true` (2026-10-17/18). Add the workflow as a **required check** on those rulesets beside CI.

Doctor:

```bash
aec run-script skill:review-gate doctor-review-gate.py
# or: python3 review-gate/scripts/doctor-review-gate.py
```

## What the workflow does

### Job `cancel-ci-on-review-comment`

On `pull_request_review_comment` created: cancel in-progress workflow runs for that PR's head SHA (skips the `Review Gate` workflow itself). Saves runner minutes when a review arrives mid-CI.

### Job `gate`

On PR open/sync/edit/label and on review / review_comment events: fail the required check unless all hold:

1. A completed Codex review exists on the **current head**, or the PR body's `## Review` section names a fallback (`agy` / `superpowers` / `claude`).
2. PR body contains a `## Review` section.
3. Every review thread whose **root** comment matches `\bp2\b` has a reply with a closing token: Notion link, `fixed in <sha>`, or `not-a-finding: …`.
4. When `base` is `main`: label `review:high` or `review:ultra` is present.

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
