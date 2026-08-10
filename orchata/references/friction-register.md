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
    { "date": "2026-08-04", "severity": "medium", "project": "email_demo",
      "summary": "tier table sent a migration stage to haiku; verify caught it, one retry wasted",
      "suggestion": "flag data-integrity stages as mid-tier minimum in the tier table" }
  ]
}
```

Entry fields: `date`, `severity`, `project` (repo name or path), `summary` (what happened),
`suggestion` (the concrete fix to the skill's text). Optional: `phase` (intake / plan /
orchestrate / escalate / retro) when it's clear which phase's instructions were at fault.

Entries written by pre-1.3 versions used `level` and `what_happened`: read those as
`severity` and `summary` (treat `suggestion` as absent), count them in thresholds
normally, and rewrite them to the current field names on the next write to the file.

- One register across all projects (user-global). `entries.length` is the authoritative count;
  never store a separate total.
- Severities: **high** (caused wrong output or a blocked run), **medium** (caused rework or a
  wasted stage), **low** (annoyance, suboptimal default).
- `opt_out: true` → no logging, no offers, ever. Skip this file entirely.

## Retro evaluation

Count only entries with `date` **after** `last_review` (all clauses). Offer the improvement
conversation when: **any high, or ≥3 medium, or ≥5 total.**

When a threshold trips, present the register in this compact shape — never dump the raw JSON
or narrate every entry:

```
Friction register: <N> entries since <last_review> — threshold hit (<which clause>).
Top entries:
- [high] <summary> → <proposed fix>
- [medium] <summary> → <proposed fix>
(<K> more low-severity entries, listed on request)
Proposed diffs: <file>: <one-line change description> (one line per file)
```

Then the offer, verbatim:

> Friction in the orchata skill has been noted in previous runs. Would you like to review it
> together and suggest PR(s) back to the skill? (Y / N / Never)

- **Y** — walk the qualifying entries, draft concrete diffs to this skill's files, resolve the
  source repo (below), and offer a PR. Open the PR only on explicit confirmation — proposals,
  never auto-merge. Then set `last_review` to today.
- **N** — set `last_review` to today (so old entries don't re-trigger next run); keep logging;
  re-offer only when *new* entries re-hit a threshold.
- **Never** — confirm once ("Stop logging friction and never ask again?"); on confirmation set
  `opt_out: true`.

## Prune on review

The register is a **queue, not an archive**. At each review (Y or N), remove entries that are
addressed — a fix shipped into the skill's text, or the entry judged not-a-skill-problem. The
shipped diff/PR is the durable record; keeping addressed entries inflates future threshold
counts with noise. Entries deferred without a fix stay in the register.

## Source-repo resolution (for the PR)

Resolve in order, then cache the answer in `source_repo`:

1. Current working directory *is* the skill's source repo (the skill dir is tracked in git
   here, not an installed copy) → use it directly.
2. `aec` is available → ask it where the skill came from (`aec info skill orchata`).
3. Ask the user once for the repo path/URL.

PR mechanics: branch from the source repo's default branch, apply the diffs to the skill's
files there, conventional commit (`feat(orchata): ...` / `fix(orchata): ...`), and open the PR
with `gh` — all gated on the user's explicit go-ahead per the escalation contract.
