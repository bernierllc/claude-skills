# Friction Register & Improvement Loop

Friction = this skill's own instructions caused rework, a wrong default, a missed case, or an
unnecessary pause. Log it when it happens; the register is how the skill earns PRs back to its
source.

## Register: `~/.claude/orchata/friction.json`

```json
{
  "opt_out": false,
  "last_review": null,
  "source_repo": null,
  "entries": [
    { "date": "2026-08-04", "level": "medium", "phase": "orchestrate",
      "project": "/abs/path/to/project",
      "what_happened": "tier table sent a migration stage to haiku; verify caught it, one retry wasted" }
  ]
}
```

- One register across all projects (user-global). `entries.length` is the authoritative count;
  never store a separate total.
- Levels: **high** (caused wrong output or a blocked run), **medium** (caused rework or a
  wasted stage), **low** (annoyance, suboptimal default).
- `opt_out: true` → no logging, no offers, ever. Skip this file entirely.

## Retro evaluation

Count only entries with `date` **after** `last_review` (all clauses). Offer the improvement
conversation when: **any high, or ≥3 medium, or ≥5 total.**

Offer verbatim shape:

> Friction in the orchata skill has been noted in previous runs. Would you like to review it
> together and suggest PR(s) back to the skill? (Y / N / Never)

- **Y** — walk the qualifying entries, draft concrete diffs to this skill's files, resolve the
  source repo (below), and offer a PR. Open the PR only on explicit confirmation — proposals,
  never auto-merge. Then set `last_review` to today.
- **N** — set `last_review` to today (so old entries don't re-trigger next run); keep logging;
  re-offer only when *new* entries re-hit a threshold.
- **Never** — confirm once ("Stop logging friction and never ask again?"); on confirmation set
  `opt_out: true`.

## Source-repo resolution (for the PR)

Resolve in order, then cache the answer in `source_repo`:

1. Current working directory *is* the skill's source repo (the skill dir is tracked in git
   here, not an installed copy) → use it directly.
2. `aec` is available → ask it where the skill came from (`aec info skill orchata`).
3. Ask the user once for the repo path/URL.

PR mechanics: branch from the source repo's default branch, apply the diffs to the skill's
files there, conventional commit (`feat(orchata): ...` / `fix(orchata): ...`), and open the PR
with `gh` — all gated on the user's explicit go-ahead per the escalation contract.
