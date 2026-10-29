# Lessons from the first run

The first run was on a mid-sized SaaS product: well over a hundred features and plans, a few dozen plans
kept in Notion and several hundred tracker rows. It found over a thousand gaps and turned them into a few
hundred workstreams and a couple of dozen new plans. These are the things that cost time or nearly went
wrong, with what to do instead.

## Scope and shape

- **Do not make a row per gap.** The user first asked for a tracker row for every gap, then saw there
  were hundreds and changed course: take them by feature first, then evaluate each feature against its
  plans. The per-feature cut found dozens of plan conflicts and several catch-all plans that no gap list showed.
  Offer the per-feature review at the stage-2 checkpoint, before anyone asks for rows.
- **Gaps that span features must name all of them.** The plan that fixes a gap has to touch every feature
  involved, and a planner looking at one feature must see it. Hence `related`, and the map repeating a gap
  on every feature it touches.
- **Permanent ids from the start.** Gap and workstream ids get cited by plans, rows and commits within
  hours. Allocate them from a counter and never renumber, even after dedupe.
- **Provenance everywhere.** Every new plan and every row says it came from the review, which workstreams
  it carries and which gaps it closes. The user asked for exactly this, so anyone can tell where a tracker row
  came from, and it keeps the learning loop possible.
- **Record the cause of every gap.** A count of gaps by cause (scoped-out, parity, missing-guard and so
  on) turns a gap list into process feedback: "we keep deferring docs parity", "guards get forgotten on
  new routes".
- **Consolidate workstreams.** The first per-feature pass made far too many workstreams, most of them
  holding a single gap. Merging the ones that share an owner and phase and ship together cut the count by
  almost half without losing anything.

## Plans

- **Check "built" claims against the code.** About one plan in twenty were fully built but still open. Close them
  with evidence (PRs or code paths) and update their rows. Agents also claim fixes that are not there, so
  verify before closing.
- **Use the project's statuses.** Agents invented `superseded`, which the plan checker rejected. A plan
  that is superseded gets archived with the project's convention.
- **Archiving has a long tail.** Moving a plan breaks:
  - citations in other plans, docs, verification files and **code comments** (dozens of source files in
    the first run);
  - manifest keys;
  - roadmap lines;
  - `introduced_by` on features;
  - the review data.

  Do it with a script, then run every checker.
- **An agent may move a workstream into a plan without writing it into the plan's body,** or leave a
  line that still says the work is out of scope. After the apply stage, check that every workstream's id
  appears in its owner plan's body, and write the missing sections yourself.
- **Hand-offs go stale between the agents and the lead.** Agents write "this work moved to X" lines before the lead finishes re-owning workstreams, so after the apply stage some archived plans named another archived plan, or said a workstream "needs an owner" that already had one. After re-owning, scan every plan, live and archived, for workstream ids and plan paths in the same paragraph, and make each hand-off name the workstream's current owner.
- **A phase lives on the plan, not the workstream.** A Phase 1 workstream inside a Phase 2 plan disappears from the Phase 1 roadmap. When a plan's workstreams span phases, split the earlier slice into its own plan (with its own tracker row if it has a deadline) instead of letting the roadmap hide it.
- **Citations live outside the plans too.** Archiving also breaks paths in `.env.example`, configs and migrations, which plan checkers rarely scan. Grep the whole repo. Leave applied migrations alone if the project never edits them, and say so.
- **The synthesis needs the principles file.** Several conflicts were really a plan breaking a product
  principle; the reviewers caught them only because the brief said "a plan set that violates one is
  wrong".

## Agents and long sessions

- **Sessions restart.** The worker restarted several times in the first run. Uncommitted work survived, but
  running agents stopped. To cope:
  - commit as soon as checks pass;
  - make every agent write its output file after each step;
  - make tracker writers query before they create;
  - resume a stopped agent from its transcript, sending it a message, instead of re-creating it.
- **Disjoint ownership prevents silent overwrites.** Split plan edits by file and tracker rows by parent
  row, never by "first half, second half" of a list that shares files.
- **Keep data out of your own context.** Read agents' JSON with scripts, and build payloads with scripts.
  The lead's context is for decisions and merges.
- **Another session may be working on the same PR.** Check the branch's remote head before pushing, and
  merge rather than rebase. Do not push over someone else's fixes.

## Shipping

- **Size the PRs.** The project capped the size of a promotion review, and the map and data PR alone came
  close to it, so the applied review went into a second PR, stacked on the first.
- **CI costs money.** Run the project's checks locally before every push, and batch fixes into one push.
- **The map's validation belongs in lint.** Once `build-map.mjs --check` and `check-plans.mjs` run in the
  project's lint, a new plan without tags, or an archived plan still cited, fails the build instead of
  silently drifting.

## Work graph and contexts (second run)

The second run added the Work view and the context map to the same project: a few hundred workstreams and
typed edges, over a thousand source files and nearly a hundred tables.

- **Consolidation can move work out of its milestone.** Merging workstreams moved a dozen launch items into
  later-phase workstreams, so they dropped off the launch critical path. Never merge across phases, and
  after consolidating, check that every item a milestone needs still sits in that milestone's phases.
- **Count with scripts, and recount after every change.** The written review twice gave a count (workstreams
  on a critical path, declared interfaces) that disagreed with the build. Each number in a
  report comes from the build output, re-read just before publishing.
- **Every workstream needs a work record.** A workstream with no record looks ready with nothing before it,
  so the build fails on a missing record instead of guessing.
- **Edges need a concrete why.** Agents link by topic ("both touch billing"). A brief that demands the
  table, route, function or decision behind each edge, and a lead who spot-checks the long poles and
  linchpins, keeps the graph honest.
- **The constraint was a person, not agents.** Three quarters of the launch path waited on the owner (a
  console step, a decision, a promotion). Show the owner's queue first; it is usually the cheapest
  speed-up.
- **The first context draft is too coupled.** It put the app shell inside the kernel and let the kernel
  reach into domains. Moving the shell out and declaring the entry points the code already treats as
  public halved the reach-ins. What remains is the untangling backlog, not noise.
- **Every file and table needs an owner, or it vanishes silently.** A file outside every glob, or a
  table no context claims, drops out of every count. The build fails on both.
- **Read every kind of import.** `import { type X }` is type-only; `const { a } = await import("x")`
  uses `a`. Missing either miscounts reach-ins or shared tables. Review bots found both.
- **A plan reference must resolve.** A missing interface whose `ref` is not a live plan renders as
  dead text. The build checks it the same way the page resolves it.
- **The panel must follow the view.** Switching tabs left the previous tab's item in the side panel, so
  the Contexts view looked like it described a feature. Opening a view selects something that view shows,
  and leaving it returns to where you were.
- **No database yet.** The user asked whether plans and rows belonged in a vector or graph database. The
  JSON files plus scripts answered every question asked (order, coupling, lanes), stay diffable and are
  checked in lint. Revisit only when a question needs similarity search across thousands of free-text items.

