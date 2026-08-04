# Model Tiers & Effort Rules

Rule of thumb: **omit the override unless a tier clearly fits; never pay top-tier prices for
mechanical work; never trust a single pass on risky work.**

## Tier table

| Tier | Effort | Use for |
|------|--------|---------|
| `haiku` | `low` | renames, grep sweeps, formatting, data extraction, doc regeneration, manifest updates |
| `sonnet` | default (omit) | standard implementation, test writing, straightforward bug fixes |
| `opus` or inherit | `high` | hard design, gnarly debugging, adversarial verification, judging |
| session model (orchestrator) | — | planning, judging panels, synthesis, integration — never fan-out work |

Effort overrides (`low`–`max`) are per-call options on the Workflow tool's `agent()`. The
Agent-tool fallback supports `model` only — when falling back, drop the effort column and
compensate by making verify prompts more explicit.

## Assignment heuristics

- If a worker's prompt could be executed by a careful intern with a checklist → haiku/low.
- If the stage's failure would be caught cheaply downstream (tests, verify stage) → don't
  over-tier it; let verification catch it.
- If the stage's failure would ship silently (auth logic, migrations, money paths) → opus/high
  on the *verify* side at minimum, and use 2–3 diverse-lens verifiers, not one.
- When genuinely unsure → omit the override (inherit the session model).

## Workflow shape rules

- `pipeline()` by default — no barrier between stages unless stage N needs *all* of stage
  N−1's results (dedup, early-exit on zero findings, cross-comparison prompts).
- Worktree isolation (`isolation: 'worktree'`) only when workers mutate files in parallel;
  it costs setup time and disk per agent.
- Cap fan-out to what the task warrants; log any deliberate coverage cap (top-N, sampling)
  so truncation is never silent.
- Structured output (`schema`) on every stage whose result feeds another stage.
