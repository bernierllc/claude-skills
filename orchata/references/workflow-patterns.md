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
- Stream per-agent verdicts to `<state-dir>/fleet-results.json` as they land. Workflow
  scripts have no filesystem access, so the script itself cannot write the file — instead,
  each worker's prompt ends with "append your verdict as one JSON line to
  `<state-dir>/fleet-results.json`" (workers have Bash). In Agent-tool fallback mode the
  orchestrator appends between dispatches. Either way, a dead run's progress is readable
  from the file; the Workflow tool's own `journal.jsonl` is the backstop.
- Guards over generated or matched text fail **open**, not closed: a regex that misses
  (a transaction guard, a filename-prefix comparison, a `NaN <= N` branch) silently lets
  the unguarded case through. When a worker authors such a guard, its verify stage must
  include an input designed to slip past it.

## Waiting on CI/deploy

Use a backgrounded until-loop capped by an iteration counter. Prefer it over a foreground
`sleep` (some harnesses refuse foreground sleeps) and over coreutils `timeout` (absent on
macOS).

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
