# Report template: `plan-review-<date>.md`

Write it for the person who decides. They should be able to act from the first screen, and look things up
in the rest. Link plans as paths, and cite workstreams and gaps by id. Follow the project's writing style.
Keep it under about 350 lines; the data files hold the detail.

```markdown
---
title: "Plan review <date>: every feature against its plans and gaps"
created: <date>
---
# Plan review <date>: every feature against its plans and gaps

**What this is.** One paragraph: what was asked, how many reviewers read how many features against how
many plans and gaps, and where the data lives (the map, reviews.json, gaps.json). End with: nothing in the
plans has changed yet; this is the proposal to accept or edit.

## Summary
Five bullets, each with a number:
- open gaps and workstreams by phase, and the features at risk;
- the worst risk nobody owned;
- how many conflicts, and how many need a product call;
- how many new plans, and how many of them are in phase 1;
- how many plan changes, and the catch-all plans.

## Act now (outside the plans)
Numbered. Live risks a person should handle today: a key to revoke, a job to pause, a PR to promote, a
deadline. Each item names its workstream or gap.

## Phase 1 critical path
The workstreams that must land for the nearest milestone, in order, grouped by what they unblock (per
customer or launch). Note go-live work that has no workstream yet.

## Decisions for <user>
One subsection per conflict that needs a product call:
- the plans involved;
- the issue in two sentences;
- the options;
- **Recommended:** the answer, and why;
- what changes if accepted.

## New plans
One paragraph each: slug, title, phase, outcome, the workstreams it carries, and why it is cut this way.

## Plan changes, ranked
A numbered list: plan, change, target, the one-line reason, and the features and workstreams behind it.

## Catch-all plans
Plans carrying work for many unrelated features, and how to split them.

## Mechanical fixes
Conflicts that need no decision (stale cross-references, duplicate scope, wrong phase), with the fix.

## Features at risk
Each at-risk feature: why, and which workstreams fix it.

## What happens when <user> accepts
The apply steps:
1. plan edits;
2. new plans;
3. archives;
4. rows;
5. PRs.
```

---

# Report template: `work-review-<date>.md` (stage 8)

Write it after the Work view builds clean. It answers one question: given the graph and the delivery
history, what should happen next and in what order. The build copies it next to the map, and the Work tab
links to it. Every number comes from the build output or `git.json`, never from memory: recompute after
each data change and re-read the figures before you publish.

```markdown
# Work review <date>: what the work graph and delivery data say

<one paragraph: what was measured, from what, and the one-line answer>

## The short answer
- The constraint: <agents, a person, review, CI, order of work>, with the numbers that show it.
- What to do first, second, third.

## 1. What the Work view shows
### Critical path to each milestone
<days, the chain in order, how many steps wait on <owner>>
### Linchpins
<the workstreams that unlock the most, and why each matters>
### Ready now
<agent-ready workstreams by phase; how many lanes can run at once>
### Waiting on people
<every human, external and decision wait on a critical path, oldest first>
### Graph defects to fix before dispatch
<phase inversions, missing records, edges that look wrong>

## 2. What the delivery data shows
<rework by feature, follow-up fix rate, PR and CI churn, promotion lag; numbers first>

## 3. What the gaps say about process
<gaps by cause and by how found; what each cause says about the process>

## 4. Diagnosis
<why the holes appeared, in three to five points, each tied to evidence above>

## 5. Recommendation: the next iteration
<numbered, each with an owner, a size and how we will know it worked>

## Limits
<what the data cannot say>
```

