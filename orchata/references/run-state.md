# Run state — `<state-dir>/run-state.json`

Per-run checkpoint file. Lives in the project repo (never in `~/.claude/orchata/`), is
**committed to the working branch** after every step, and is what makes any orchata run
resumable after a usage-limit cut, crash, or interrupt.

The state dir defaults to **`.orchata/`**; the user's global or project instructions may
name a different directory — honor theirs (see SKILL.md "State files").

## Schema

```json
{
  "run_id": "orchata-2026-08-09-widget-refactor",
  "objective": "One sentence: what done looks like for this run",
  "branch": "feat/widget-refactor",
  "plan_file": "plans/2026-08-09-widget-refactor.md",
  "tracker_row": "https://tracker.example.com/issue/123",
  "steps": [
    {
      "id": "2.1",
      "description": "Extract widget renderer into its own module",
      "status": "done",
      "evidence": "commit abc1234; tests 42/42 passing",
      "timestamp": "2026-08-09T14:05:00-06:00"
    },
    {
      "id": "2.2",
      "description": "Add renderer contract test",
      "status": "in_progress",
      "evidence": null,
      "timestamp": "2026-08-09T14:10:00-06:00"
    }
  ],
  "blockers": [
    {
      "what": "API key rotation needs the human",
      "tracker_row": "https://tracker.example.com/issue/124",
      "routed_around": true
    }
  ],
  "next_action": "Run the contract test and commit step 2.2"
}
```

`status` ∈ `pending | in_progress | done | blocked | skipped`. `evidence` is required to
mark `done` — a commit hash, test output line, or URL; never a bare claim. `tracker_row`
fields are optional — populate only when an external tracker is configured. `next_action`
is always populated: it is the single line a fresh session executes first on resume.

## Triple-redundancy order (after every completed step)

1. **Write `run-state.json`** — local, always succeeds.
2. **`git add <state-dir>/ && git commit -m "chore(run): checkpoint <step-id>"`** on the
   working branch — survives the machine, visible in the PR.
3. **Update the external tracker row** (current step + next_action), if the user has one
   configured — visible to the human outside the CLI.

Each layer backs up the one below it. Layer 3 is optional, and its failure (tracker down
or permission-blocked) never blocks the run — record `"tracker_synced": false` on the step
and continue. Do the checkpoint **immediately after each step**, not batched at the end:
the end is the part that gets cut.

## Resume protocol (Phase 1 intake)

1. `<state-dir>/run-state.json` exists with any step not `done`/`skipped` → this is a
   resume.
2. Reconcile against reality before trusting it: does the branch exist, do the `done`
   steps' commits exist (`git log`), is the PR/CI/deploy state what the file claims, does
   the tracker row (if any) agree? One line per drift found.
3. Execute `next_action`, then continue from the first non-done step.
4. Run fully done → set every step `done`, final commit, close out the tracker row if one
   exists, and report per the user's own logging conventions.

Fallback archaeology when run-state is missing or stale: the tracker row's notes (if
configured), then `git log` on the branch.

## Companion files in `<state-dir>/`

- `fleet-results.json` — streamed worker verdicts during fan-out runs (see SKILL.md
  "Supervisor resilience").
- A `.gitignore` **inside the state dir** keeps `*.local.*` and `cache/` out; everything
  above is committed. The state dir itself must never be repo-gitignored — committed
  checkpoints are the resilience.
