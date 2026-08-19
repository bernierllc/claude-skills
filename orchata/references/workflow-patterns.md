# Workflow Patterns

Canonical script shapes for the Orchestrate phase. These target the Workflow tool
(`agent()` / `pipeline()` / `parallel()` / `phase()`). No Workflow tool in the host →
approximate with parallel Agent-tool dispatches and note the degradation in the retro.

## Plan → execute → verify (the default)

```js
export const meta = {
  name: 'orchata-run',
  description: '<one line: what this run builds>',
  phases: [{ title: 'Implement' }, { title: 'Verify' }],
}
const results = await pipeline(
  STAGES,                                   // from the Phase-2 plan, tagged with tier/effort
  s => agent(s.prompt, { label: `impl:${s.key}`, phase: 'Implement',
                         model: s.model, effort: s.effort, schema: RESULT_SCHEMA }),
  (r, s) => agent(`Verify with evidence: ${JSON.stringify(r)}`,
                  { label: `verify:${s.key}`, phase: 'Verify',
                    effort: 'high', schema: VERDICT_SCHEMA })
)
return results.filter(Boolean)
```

Notes:
- Stage prompts must be self-contained: the worker sees none of your session context. Include
  file paths, conventions, and the skill to invoke (e.g. "Invoke the
  superpowers:test-driven-development skill before writing code").
- Escalation-flagged stages are **excluded from the script** and go straight to the punch
  list. Never put a stop-and-confirm action inside a worker prompt.
- Stream per-agent verdicts to `<state-dir>/fleet-results.json` from inside the script
  (append on each `agent()` return, not just the final `return`) — a dead workflow's
  progress is then readable without journal spelunking.

## Waiting on CI/deploy

Use a backgrounded until-loop, never a foreground `sleep` (the harness refuses it), and
never coreutils `timeout` — macOS doesn't have it. Cap the loop with an iteration counter.

## Migration-runner authoring

Two known fail-opens: BEGIN/COMMIT guard clauses over SQL text need a semicolon anchor
(`DO $$ ... END $$` bodies otherwise trip them), and numeric-prefix comparisons need an
explicit NaN branch — `NaN <= N` is false, so an unnumbered filename executes instead of
being baselined.

## Adversarial verify (risky stages: money/auth/data/contract changes)

```js
const votes = await parallel([1, 2, 3].map(i => () =>
  agent(`Lens ${['correctness', 'security', 'reproduces'][i - 1]}: try to REFUTE this change:
         ${claim}. Default to refuted=true if uncertain.`,
        { effort: 'high', schema: VERDICT })))
const survives = votes.filter(Boolean).filter(v => !v.refuted).length >= 2
```

Diverse lenses beat identical refuters — different failure modes need different eyes.

## Parallel file mutation

Workers that edit the repo concurrently get `isolation: 'worktree'` and **file ownership**:
map every file each worker touches before dispatch; a file in two scopes means one owner or
sequential execution. After integration, run the test suite before committing the merge.

## Resume, don't restart

Interrupted or partially wrong run → fix the script file and relaunch with `resumeFromRunId`;
completed unchanged stages replay from cache. Read the run's `journal.jsonl` before diagnosing
unexpected results.
