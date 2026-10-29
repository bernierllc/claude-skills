# Trackers

The map and the plans are the source of truth; the tracker is where people pick up work. Read the tracker
three times:
- in stage 1, a snapshot, to tag open rows;
- in stage 2, matching gaps to existing rows;
- in stage 6, one row per workstream.

Find the right section below. If the project uses none of these, stop after stage 5. The plans and the
map still carry everything.

## Rules that hold for every tracker

- **Learn the workspace's rules first.** Look for a sync manifest, a field-reference page or an instruction
  file. Some workspaces keep the backlog and the in-flight work in different databases. Some forbid
  marking work done until it is on the default branch. Follow them.
- **One row per workstream, never per gap.** The gaps go inside the row and in a "Gap ID" property.
- **Provenance on every row.** The first lines of the body: created by the feature-map review on `<date>`
  (link the report), the workstream id, how many gaps it groups, and that each gap keeps its permanent id
  in `gaps.json`.
- **Body.**
  - Owner plan (link) · phase · size.
  - `## Why`: the workstream's why.
  - `## Gaps it closes`: `- [GAP-0123](<map url>#GAP-0123) (severity, cause, found by): summary. Evidence: …`.
  - `## Features`.
  - `## Depends on`, if any.
  - A link to the map.
- **Properties derived from the data:**
  - severity: the highest open gap severity;
  - kind: the majority cause, mapped to the tracker's own kinds, for example:
    - not-built, unplanned, scoped-out, parity: Feature;
    - regression, missing-guard, drift: Bug;
    - debt: Chore;
    - config: Infra;
  - effort: from the size, using the tracker's own scale, for example S=2, M=3, L=4 on a scale of 1 to 5;
  - status: backlog;
  - stage: shaped, since the review shaped it.
- **Build the payloads with a script**, one JSON file per agent, split by owner plan so no two agents edit
  the same parent. Agents create rows verbatim (brief 12). You never paste rows through your own context.
- **Idempotent.** Query before you create; write the output after every batch; resume, don't restart.
- **Shared databases.** Adding a property changes the database for every project in it. Say so to the
  user when you add one, and touch only the rows you create and the parent rows you link.
- **Write back.** Put each row's URL in the workstream's `row` in `reviews.json`, and each gap's row in
  its `tracker` list, then rebuild the map.

## Notion

- **Discover.** Search for the workspace's roadmap or backlog and tracker databases. Fetch the data
  source (`collection://…`) to read the exact property names, types and select options; use the options
  verbatim. Note the title property and any project select (for example `Project = <name>`).
- **Snapshot (stages 1 and 2).** Query the data source, filtered to the project, for id, url, title,
  status, owner, priority, type, due and the plan link. Write `tracker-snapshot.json`.
- **Properties to add** (with `update-data-source`, after telling the user):
  - `Workstream` (text);
  - `Gap ID` (text);
  - optionally `Found by` (select, the found_by set).
- **Create** with `create-pages`, parent `{data_source_id}`, 10 to 15 pages per call and
  `allow_async: false`, so the URLs come back. Property values are strings, select options are exact, and
  numbers are numbers.
- **Parent/child.** If the database has a self-relation (for example `Children` or `Parent`), set it on
  one side only. Read the parent's current list, append the new rows, and write the whole list back,
  because a relation update replaces the list. A plan held as a plain Notion page, not a database row,
  cannot be a parent; leave those rows unlinked and mention the plan page in the body.
- **Plans without a row.** If the workspace says every plan needs a row, create one with the plan's title,
  plan link and status, and write it into the plan's frontmatter and any manifest. If the workspace leaves
  that to a person, leave the rows unlinked and report it.
- **Rate.** Notion calls are slow; four agents of about 80 rows each finish in reasonable time.

## GitHub Issues

- **Snapshot.** List open issues with labels and milestones, using `gh` or the GitHub MCP tools.
- **Rows.** One issue per workstream: title `WS-NNN <title>`, body as above, and labels for `workstream`,
  severity, kind and phase. Keep "Gap ID" in the body and as a hidden marker
  (`<!-- ws: WS-017; gaps: GAP-0244 -->`) so a rerun can find it by searching for the marker.
- **Parent/child.** Use sub-issues under the plan's tracking issue if the repo uses them. Otherwise add a
  task-list line to the plan issue.
- **Idempotent.** Search `in:body "ws: WS-017"` before creating.
- Mind the API rate limits: create in batches, sequentially, per agent.

## Linear

- **Snapshot.** Query the team's open issues, with project, cycle, labels and estimate.
- **Rows.** One issue per workstream in the project or team the plan maps to, with an estimate from the
  size, a priority from the severity, and labels for kind and phase. Put the ws id and the gap ids in the
  description and in a custom field if the workspace has one.
- **Parent/child.** Use sub-issues of the plan's issue, or the project itself as the parent.
- **Idempotent.** Search the description for the ws id before creating.

## No tracker

Skip stage 6. The map's workstream panels and the plans' `## Workstreams` sections are the backlog, and
`reviews.json` has the data if a tracker is added later.
