# Agent brief templates

Fill the `{PLACEHOLDERS}` for the project and save each brief as a file in the scratchpad. Then each
agent's prompt can be three lines: read the brief, the input path, the output path. Every brief keeps the
same shape (Why, Inputs, Decide, Output, Final message), because agents do best when they know the goal
and where they fit, and get exact paths, a schema and a size limit for every field.

Common placeholders:
- `{PROJECT}` and `{REPO}`: the project name and the repo checkout path, read-only for agents unless stated.
- `{N}`: how many agents run in parallel.
- `{PHASES}`: the project's phases in one line, for example "1 = launch, 2 = scale, 3 = later".
- `{PRINCIPLES}`: the file holding the product principles and plan rules.
- `{FM}`: the feature-map directory.
- `{STYLE}`: the project's writing rules, for example "plain words, no em-dashes".
- `{OWNER}`: the person whose steps gate work (`owner_label` in config.json).
- `{INTEGRATION}` and `{RELEASE}`: the branches work lands on and is promoted to (`branches` in config.json).

Contents:
1. Plan tagging
2. Tracker-row tagging
3. External plan reading
4. Debt harvest
5. Surface-parity audit
6. Missing-capability hunt
7. Gap enrichment
8. Feature review
9. Plan synthesis
10. Apply edits to plans
11. Write new plans
12. Tracker rows from workstreams
13. Workstream dependencies (stage 8)
14. Delivery data (stage 8)
15. Context boundaries (stage 9)

---

## 1. Plan tagging

**Why.** We are building a feature map of {PROJECT}. Every plan is linked to the features it adds,
changes, fixes or removes, and to the holes (gaps) it reveals in them. You are one of {N} agents and own
only the plans in your bucket. Read each plan once, carefully, and decide.

**Inputs (read-only).** `{REPO}`. The registry `{FM}/features.json` lists the ids to use; read it fully
first. Your plans are listed in the bucket file. Read `{PRINCIPLES}` and the roadmap for context.

**Decide, per plan.**
- `summary`: one plain sentence on what the plan changes, and for whom.
- `built`: `none`, `partial`, `most`, `all` or `unknown`, with `built_evidence` (status and PRs, or the
  code path you checked).
- `features`: `{id, kind: adds|changes|fixes|removes, note}`, usually 1 to 6. List what the plan
  materially changes, not everything it mentions.
- `new_features`: only for a capability a customer, operator or integrator would recognise as its own,
  and no registry id covers. Include `{id, name, area, description, built, evidence, related: [{id, kind,
  note}]}`. A plan's capability that has already shipped but is missing from the registry also counts
  (`built: yes`, with the code path). That is how the registry finds its blind spots.
- `gaps`: holes in features today, `{feature, summary, severity, covered_by, still_open, evidence}`.
  Include what the plan defers, puts out of scope, leaves as a follow-up, an open question or a known
  limitation. Those are the most valuable gaps, because nobody may own them. `covered_by: null` when
  nothing covers the gap.

**Output.** One JSON array, one record per plan: `{plan, title, summary, built, built_evidence, features,
new_features, gaps}`. Validate that it parses. Use {STYLE}, with notes of at most about 140 characters.

**Final message.** At most 6 lines: plans tagged, new feature ids, gaps found (how many with no cover),
and anything odd.

## 2. Tracker-row tagging

Same as 1, over open tracker rows that have no plan. Per row:
- `features`: `<verb>:<id>` entries, 1 to 4.
- `note`: one line.
- `gap`: optional, only when the row describes something broken or missing today.
- `new_feature`: optional.

Put a row in `skipped` (with the reason) only when it touches no product feature at all, such as a
personal follow-up or scheduling. When in doubt, tag it. An agent may fetch a row's page only when the
title and notes are too thin to decide. Read-only.

## 3. External plan reading (for example a Notion tree)

**Why.** Some planning lives outside the repo. Describe each plan page the same way repo plans are
described, so they can join the map. Read-only. Skip trashed and "delete me" pages.

**Decide, per page.**
- Is it a plan (program, sub-plan, design, runbook, draft) or not (notes, status tables, link lists)?
- If it only **mirrors** a repo plan, record `mirror_of: "plans/<file>.md"`, plus a `drift` line if it
  is out of date with the repo plan.
- Otherwise record:
  - `{id, url, title, path, kind, phase, status, summary, features, notes}`;
  - `repo_plans`, with the relation: extends, implements, supersedes or related;
  - `tracker_rows`;
  - `depends_on`;
  - `gaps`, in the same shape as 1.

**Output.** One JSON array, one record per page.

## 4. Debt harvest

**Why.** Repos keep their own lists of known debt. Each entry is a gap someone already found:
- baselines and exclusion lists;
- allow-lists of ungated routes;
- TODO and FIXME markers;
- feature flags left off;
- skipped tests.

**Decide.** Find every such list (grep the config, the test fixtures and the scripts). For each entry,
record a gap with `cause: debt`, the list it came from as `source`, its path and line as evidence, and
the home feature. Group a long list into gaps by feature, not one gap per line, when the entries share
a fix.

## 5. Surface-parity audit

**Why.** A feature usually has several surfaces:
- UI;
- public API;
- CLI or MCP tools;
- SDK;
- customer docs;
- verification or test docs.

A capability that exists on one surface and is missing on another is a gap nobody files.

**Decide, per feature.** List the surfaces it has, and record each missing one as a gap with `cause:
parity`. Note any project rule that makes a surface mandatory (for example "every API endpoint has an SDK
method").

## 6. Missing-capability hunt

**Why.** The registry was seeded from a code read and the plans. Find built capabilities that are in
neither: routes, jobs, admin tools, integrations, webhooks.

**Decide.** Propose each as a new feature, with its code path and the links to existing features.

## 7. Gap enrichment

**Why.** Every open gap will be tracked, owned by a plan, and acted on by someone who did not find it. Make
each one self-explanatory and correct. Gaps that span features must name all of them. You are one of
{N}; you own only your gaps.

**Inputs.**
- Your gaps.
- `{FM}/features.json`, which you read fully first.
- The plans and `{FM}/external-plans.json`.
- A read-only tracker snapshot at `{SNAPSHOT}`.
- The code.

Do not run the app, and do not edit anything.

**Decide, per gap.**
1. `duplicate_of`: another gap in your input that is the same hole. Keep the clearest, most severe one.
2. `related`: every other feature whose code or behaviour must change to close the gap (usually 0 to 3).
3. `detail`: 1 to 3 sentences (at most 400 characters) on who hits it, what goes wrong and what fixing it
   looks like. It goes on a tracker row, so write it for a stranger.
4. `evidence`: up to 4 pointers you actually opened, as `path:line`, `plan#heading` or a URL.
5. `status`: `open`, `fixed` (put the code that closes it first in evidence) or `unverified`. Spend at
   most a couple of searches per gap.
6. `cause`: from the taxonomy in `data-model.md`.
7. `existing_row`: an open tracker row that is clearly this same work, if one exists.
8. `owner_plan`: only when no plan owns the gap. Name a live plan whose stated scope clearly includes it.
   Do not stretch; null is fine.

**Output.** One JSON array, one object per gap, every input id present.

## 8. Feature review

**Why.** The user does not want a row per gap. They want the work re-cut **by feature**: for each feature,
everything planned for it and everything missing from it, and the best way to organise the fix. That cut
can show plans that overlap, conflict, are stale or slice the work badly. You are one of {N}; you own only
your features. Phases are {PHASES}. Product principles are in `{PRINCIPLES}`: a plan that breaks one is
wrong.

**Inputs.** Per feature:
- `feature`;
- `open_gaps_home`: full records, with `covered_by`;
- `open_gaps_related`: gaps homed elsewhere that also touch this feature;
- `plans`: every plan naming the feature, with verb, note, status, phase, summary and built;
- `tracker_rows_without_plan`;
- `links`.

Also the plans, the registry, the gap table and the code, when you need to judge size or check a claim.

**Decide, per feature.**
1. `summary`: 1 to 2 sentences on what it does today and its main weakness.
2. `health`: `solid`, `gaps` or `at-risk`.
3. `plans`: each plan's role (`owns`, `touches`, `stale`, `conflicts`), with a note.
4. `workstreams`: group `open_gaps_home` into the fewest coherent units one person could ship. Every home
   gap goes in exactly one. Do not place related gaps; their home reviewer does. Per workstream:
   - `title`: imperative, at most 80 characters;
   - `why`: what goes wrong and what done looks like, at most 300 characters;
   - `gaps`;
   - `features`: home first;
   - `owner`: a live plan whose scope fits, or `"new"`;
   - `phase`;
   - `size`: S, M or L;
   - `depends_on`.
5. `conflicts`: plans that disagree about this feature, with a proposed resolution.
6. `plan_changes`: `{plan, change: merge-into|split|re-scope|close|move-phase|add-gaps, target, detail}`.
   Only real improvements, with the reason.
7. `new_plans`: for the `"new"` workstreams, `{title, scope, features, workstreams, phase}`. At most one
   per feature. Say whether it should merge with an existing plan instead.

**Output.** One JSON array, one object per input feature. Before finishing, check that every home gap is
in exactly one workstream and every plan key exists.

## 9. Plan synthesis

**Why.** {N} reviewers each saw a slice. Take the cross-feature cut: decide the plan set the workstreams
should live in, then write the report.

**Inputs.**
- `{FM}/reviews.json`;
- `{FM}/gaps.json`;
- `{FM}/features.json`;
- the plans and the roadmap;
- `{FM}/external-plans.json`;
- `{PRINCIPLES}`.

**Decide.**
1. **New plans:** merge every `owner: null` workstream and every reviewer proposal into the smallest
   sensible set. One plan is one coherent outcome a person could own end to end. Never "misc fixes for
   area X", unless that truly is the outcome. Prefer folding a workstream into a live plan whose scope
   fits. Per plan: `slug`, `title`, `phase`, `outcome` (2 sentences), `features`, `workstreams`,
   `depends_on` and `notes`.
2. **Owners:** the final owner of every workstream, an existing plan key or `new:<slug>`. List only the
   ones that change.
3. **Plan changes:** deduplicate and rank them, each with a one-line reason and the features and
   workstreams behind it. Flag catch-all plans and propose splits.
4. **Conflicts:** deduplicate them. For each give the plans, the issue, a resolution, and `needs_user`
   (a product call) or mechanical.
5. **Phase 1:** the workstreams that must land for the nearest milestone, in order.
6. **Consolidate:** where workstreams share an owner and phase and would ship together, keep one id,
   absorb the others, and retitle it. Never merge across phases or unrelated outcomes. Aim for about a
   third of the original count.

**Output.** A synthesis JSON (`new_plans`, `owners`, `plan_changes`, `conflicts`, `phase1`,
`merge_workstreams`) and the report, written from `report-template.md`. Before finishing, check that every
workstream has an owner and every plan key exists.

Split it across 2 or 3 agents (structure, changes, phase 1) when the inputs are large.

## 10. Apply edits to plans

**Why.** The user accepted the review. Make the plans say what was decided. Agents work in parallel, each
owning a disjoint set of plan files; others write the new plans and edit external pages.

**Input.** `your_plans`, the only files you may edit, and `items`, each `{kind, obj, plans}`:
- `decision`: settled by accepting the recommended resolution;
- `fix`: a mechanical fix;
- `change`: re-scope, split, merge-into, close or move-phase.

Items often name several plans; apply only your part.

**How.**
- **Decision or fix:** rewrite the conflicting sentences so the plan states the decision; never leave
  both versions. Add `Decided <date> (<user>, plan review): <one sentence>.` where it matters.
- **Re-scope:** edit the scope, steps and acceptance; drop what moved out, with a pointer to where it went.
- **Split:** remove the section and leave a one-line pointer to the new plan, which another agent writes.
- **Merge-into, both plans yours:** fold the unique, still-valid content into the target, then close the
  source as below.
- **Close:** use only the project's valid statuses. `done` needs PRs. Otherwise archive per the project's
  convention, with a first line saying why and where the open work went.
- **Move-phase:** set `phase`, and add a line saying why.

In every file: bump `updated`, keep the frontmatter valid, and update `features:` if the scope changed.
Do **not** edit `gaps:`, the roadmap file, manifests or `{FM}/`; the lead syncs those. Keep the plan's
voice. Run the plan checker at the end.

**Output.** `{plans: {path: {status, phase, archive, superseded_by, note}}, new_files, workstream_moves:
[{ws, to}], skipped: [{index, why}]}`. `workstream_moves` matters most: the lead re-owns workstreams from it.

## 11. Write new plans

**Why.** The review found work no plan owned. Each new plan must say where it came from.

**Input.** Per plan:
- `plan`: slug, title, phase, outcome, features, workstreams, depends_on, notes;
- `workstreams`: full records, with gap details;
- `split_from`: sections to lift out of existing plans.

**Write** `{plans_dir}/<date>-<slug>.md`:
- the project's frontmatter, with `gaps:` listing every gap of its workstreams;
- the title, then the **provenance line**: "Created <date> by the feature-map plan review (<link to
  report>). It carries workstreams WS-…, which close gaps GAP-…. Before this review no plan owned this
  work." Adjust the last sentence for content split from another plan;
- `## Why`: what goes wrong today, for whom;
- `## Outcome`: checkable statements;
- `## Workstreams`: one `### WS-NNN <title>` per workstream, with the why, size, phase, the gap list
  (`- GAP-0123 (high): summary`) and concrete steps naming real files and functions (read the code the
  evidence points at);
- `## Verification`;
- `## Docs`;
- `## Out of scope`;
- `## Open questions`: real ones only.

60 to 150 lines. Use `changes:` on the nearest feature for a capability with no id, and report the
missing id for the lead to add.

**Output.** `[{path, title, phase, features, gaps, missing_features: [{id, name, area, description}]}]`.

## 12. Tracker rows from workstreams

**Why.** One tracker row per workstream, under its plan's row, so the backlog matches the plans and every
row traces back to its gaps. The lead has written the rows; your job is to create them exactly and link
them.

**Input.** A list of `{ws, owner, parent, parent_kind, properties, content}`. Use `properties` and
`content` verbatim.

**Steps.**
1. **Resume safely.** Load your output file if it exists, and skip the ws ids already in it. Query the
   tracker for rows carrying your remaining ws ids, and record any you find instead of creating
   duplicates.
2. **Create** in batches of 10 to 15, mapping the returned URLs to ws ids by title. Rewrite the output
   file after every batch.
3. **Link to parents.** Fetch each parent, read its current children, and set children to the existing
   ones plus yours. Never drop any. One update per parent. If the parent is not a row in the same
   database, do not edit it; list the ws ids as `unlinked`, with the reason.
4. Touch nothing else.

**Output.** `{rows: {ws: url}, parents_linked: {parent: [ws]}, unlinked: [{ws, why}], errors: [{ws,
error}]}`.

---

## 13. Workstream dependencies (stage 8)

```
# Brief: what each {PROJECT} workstream needs first

## Why
The plan review grouped every open gap into workstreams (WS-NNN), each owned by a plan and placed in a
phase. {OWNER} wants the work graph: which workstreams are long poles, which are linchpins that unlock many
others, which can run in parallel, and which wait on a person, a vendor, a date or a decision. You are one
of {N} agents and own only the workstreams in your slice. Accuracy beats volume: a wrong edge sends work in
the wrong order; a missing weak edge costs little.

## Inputs (read-only)
- Your slice: a JSON list of workstreams {id, title, why, phase, size, owner, owner_title, features,
  depends_on_text (old free-text notes), gaps (open gaps with severity, cause, summary, evidence)}.
- The index of every workstream: {INDEX} (id | phase | size | owner plan | features | title). Every edge
  names an id from it.
- The owner plans, the roadmap ({PHASES}), {FM}/features.json (feature links), {PRINCIPLES}, the code.

## Decide, per workstream
1. needs: workstreams that should land first, each {ws, kind, why}.
   - blocks: this one cannot be built, or cannot ship correctly, until that one lands (it calls an API,
     table, job or helper the other builds; it implements a decision the other settles; two migrations on
     one table in order).
   - enables: this one could ship first, but is cheaper, safer or needs less rework after that one.
   - why: one sentence, at most 200 characters, naming the concrete thing. Check the plans and the code
     when the link is not obvious. Never link by topic, shared feature or same plan alone. Usually 0 to 3
     needs. Turn each old depends_on_text note into an id edge if it still holds, or drop it.
2. waits: things outside the graph, each {kind, what, ref}: human (a step only {OWNER} can take: a console
   action, a signature, a promotion, a customer call), external (a vendor, a customer, a third party), date
   (what = the date and why), decision (an open question; ref = plans/<file>.md#heading).
3. who: agent (an agent builds, tests and opens the PR with no human step beyond review and merge),
   agent+human (an agent, plus one human step), or human.
4. notes: optional, at most 200 characters, only if surprising (already built, wrong phase, should split).

## Output
One JSON array at {OUT}, one object per workstream:
{"ws": "WS-248", "needs": [{"ws": "WS-095", "kind": "blocks", "why": "..."}], "waits": [], "who": "agent", "notes": ""}
Rewrite the file after every 10 workstreams. Before finishing: it parses, every slice id appears once,
every needs.ws is in the index and is not the workstream itself. {STYLE}. Edit no repo file.

## Final message
At most 4 lines: workstreams done, edges by kind, waits by kind, who counts.
```

Merging: the lead writes `work.json` with a script (one workstream per line), runs `build-map.mjs
--check` and fixes what it reports. A `blocks` cycle means two agents disagreed about order: read both
whys and drop the weaker edge. Then spot-check the long poles and linchpins by hand, because they steer
the most work; a wrong edge there is the expensive kind.

## 14. Delivery data (stage 8)

```
# Brief: measure how {PROJECT} work actually gets delivered (git, PRs, CI)

## Why
{OWNER} wants to know what the delivery history says about the process: where fixes and rework cluster,
how long work really takes, how much CI churn there is and how long work waits before release. The numbers
also calibrate the Work view's S, M and L day estimates. Measure; do not judge. Read-only: never push,
comment, re-run or change anything.

## Sources
- Git: fetch {INTEGRATION} and {RELEASE}, then work from the remote refs. Note how merges are recorded
  (squash subjects ending in (#NNN), merge commits) and how agent commits are marked (a Co-Authored-By
  or session trailer).
- Feature code paths: {FM}/features.json (code, pages, api); map files to features by path prefix.
- The code host's PR and CI history, through the tools the session has.

## Measure
1. Per feature, last 90 days: commits, fix commits, reverts, files touched, last commit, agent share.
   Rework = fix commits / all commits.
2. Follow-up fixes: for each merged PR, whether a fix touching its files landed within 7 days. Overall,
   per feature (top 15), agent vs not.
3. PR timing: hours open to merge (median, p75, p90); PR size by changed lines, excluding generated files
   (S under 300, M 300 to 1,500, L over); median and p75 days per size.
4. CI, last 30 days: runs, success, failure, cancelled, failure rate without cancelled, minutes if known.
5. Iteration, a sample of 40 recent PRs: pushes per PR, review-bot findings per PR, share needing a fix
   push after the first review.
6. Promotion (only when there is a release branch): days from {INTEGRATION} to {RELEASE} (median, p75),
   unpromoted commits and the oldest one's age.
7. Plans: for done plans with PRs, days from created to the last PR's merge.

## Output
1. {OUT}/git.json in the shape of work.json's git section (references/data-model.md), with notes for any
   number that is limited (missing data, API caps, assumptions).
2. {OUT}/git-findings.md, at most 40 lines: numbers first, one line of meaning each. {STYLE}.

## Final message
At most 5 lines.
```

The lead copies `git.json` into `work.json`'s `git` and sets `size_days` from it and from plan lead
times. PR durations alone cannot size work (they are hours at every size); plan lead time divided by the
workstreams a plan carried usually can.

## 15. Context boundaries (stage 9)

Usually the lead drafts `contexts.json`, because the boundaries are judgement calls the user must review.
On a large repo, give one agent this brief per group of areas and merge.

```
# Brief: draft the context map for {AREAS}

## Why
{OWNER} wants to know which parts of {PROJECT} can be worked on at the same time safely. A context is a
piece of the product with its own code and tables and a small set of files others may import. You draft
the contexts for {AREAS}; the build will measure every import that crosses a boundary.

## Inputs (read-only)
{FM}/features.json (areas, features, code paths), the code under {SCOPE}, the schema file {SCHEMA},
{PRINCIPLES} (it often names the one place a behaviour must live), the plans for these areas.

## Decide
1. Contexts: usually one per area; merge areas that share most code, split one that holds two products.
   id, name, kind (domain unless it is kernel or tooling), summary (one sentence).
2. owns.code: globs that cover every file of these areas, most specific first; carve single files out of
   shared folders by path.
3. owns.tables: every table these contexts write. A table belongs to the one context that defines its rows.
4. interfaces: the files others should import (entry points, service facades, typed clients, route
   helpers), each with what in one sentence. Add {status: missing, what, ref} where the principles or a
   plan call for an interface nobody has built.
5. Note every file you think is in the wrong place, and every import you expect to show up as a reach-in.

## Output
{OUT}: {"contexts": [...], "notes": ["..."]}. {STYLE}.

## Final message
At most 4 lines: contexts, globs, tables, interfaces, notes.
```

Then the lead merges, runs `build-map.mjs --check` until every file and table has exactly one owner, and
reads the reach-in matrix. The first draft always shows too many reach-ins: look at the most-imported
undeclared files (`implicit`) and decide for each whether it is a real interface (declare it) or a leak
(leave it as a reach-in, the untangling backlog).

