# Run state — `.otto/run-state.json`

Per-run checkpoint file. Lives in the project repo (never in `~/.claude/orchata/`), is
**committed to the working branch** after every step, and is what makes any orchata run
resumable after a usage-limit cut, crash, or interrupt.

## Schema

```json
{
  "run_id": "orchata-2026-08-09-orchata-v1.1",
  "objective": "One sentence: what done looks like for this run",
  "branch": "feat/orchata-v1.1-checkpointed-runs",
  "plan_file": "plans/2026-08-09-context-orchestration-optimization.md",
  "tracker_row": "https://www.notion.so/<page-id>",
  "steps": [
    {
      "id": "2.1",
      "description": "Add granularity table to Phase 2",
      "status": "done",
      "evidence": "commit abc1234; diff adds ### Task granularity",
      "timestamp": "2026-08-09T14:05:00-06:00"
    },
    {
      "id": "2.2",
      "description": "Write references/run-state.md",
      "status": "in_progress",
      "evidence": null,
      "timestamp": "2026-08-09T14:10:00-06:00"
    }
  ],
  "blockers": [
    {
      "what": "Stripe apiVersion pin blocks commits",
      "tracker_row": "https://www.notion.so/<page-id>",
      "routed_around": true
    }
  ],
  "next_action": "Copy skill dir to ~/.claude/skills/orchata/ and commit"
}
```

`status` ∈ `pending | in_progress | done | blocked | skipped`. `evidence` is required to
mark `done` — a commit hash, test output line, or URL; never a bare claim. `next_action`
is always populated: it is the single line a fresh session executes first on resume.

## Triple-redundancy order (after every completed step)

1. **Write `run-state.json`** — local, always succeeds.
2. **`git add .otto/ && git commit -m "chore(otto): checkpoint <step-id>"`** on the
   working branch — survives the machine, visible in the PR.
3. **Update the Tracker row** (`Notes` = current step + next_action) — visible to the
   human outside the CLI.

Each layer backs up the one below it. Layer 3 failure (Notion down/blocked) never blocks
the run — record `"tracker_synced": false` on the step and continue. Do the checkpoint
**immediately after each step**, not batched at the end: the end is the part that gets cut.

## Resume protocol (Phase 1 intake)

1. `.otto/run-state.json` exists with any step not `done`/`skipped` → this is a resume.
2. Reconcile against reality before trusting it: does the branch exist, do the `done`
   steps' commits exist (`git log`), is the PR/CI/deploy state what the file claims, does
   the Tracker row agree? One line per drift found.
3. Execute `next_action`, then continue from the first non-done step.
4. Run fully done → set every step `done`, final commit, Tracker row `Status: Done`, and
   note the run in the Activity Log per global rules.

Fallback archaeology when run-state is missing or stale: the Tracker row's Notes, then
`.otto/activity.jsonl`, then `git log` on the branch — in that order.

## Companion files in `.otto/`

- `activity.jsonl` — one JSON line per shipped unit (the global Notion-fallback log).
- `fleet-results.json` — streamed worker verdicts during fan-out runs (see SKILL.md
  Supervisor resilience).
- `.otto/.gitignore` keeps `*.local.*` and `cache/` out; everything above is committed.
