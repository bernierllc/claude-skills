# Flow Visualization Reference

Rules for generating flow visualizations (Mermaid diagrams and optional interactive HTML artifact) as comprehension aids for humans. These visualizations consume the flow files and index produced during Phase 2. They show what happens in a flow, who is involved, and where handoffs occur. Deeper verification detail stays in the verification docs.

## Directory Structure and File Naming

```
verification/
├── index.md
├── pages/
├── flows/
├── shared.md
├── findings/
├── logs/
└── visualizations/
    ├── event-lifecycle.md        # Mermaid diagram (mirrors flows/event-lifecycle.md)
    ├── artist-onboarding.md      # One per flow file
    └── app-overview.html         # Interactive HTML artifact (user-chosen name)
```

Mermaid files use the same base name as their source flow file. `flows/event-lifecycle.md` produces `visualizations/event-lifecycle.md`. The HTML artifact file name is `app-overview.html` by default, or a user-chosen name.

## Mermaid Diagram Generation Rules

### Node format

Each node contains a human-readable action description and the page name in italics:

```
A["Admin creates event<br/><i>event-create</i>"]
```

Enough to understand what is happening and where. Nothing more.

### Edge labels

Label edges with the trigger or transition that causes the move to the next step:

```
A -->|"Magic link sent"| B
```

### Color-coding

Colors are assigned deterministically by user type. Sort all user types alphabetically, then map to this fixed palette in order:

| Position | Color Name | Style |
|---|---|---|
| 1st | Blue | `fill:#e8f4f8,stroke:#2d6a8e` |
| 2nd | Purple | `fill:#f0e8f4,stroke:#6a2d8e` |
| 3rd | Green | `fill:#e8f4e8,stroke:#2d8e4f` |
| 4th | Amber | `fill:#f4f0e8,stroke:#8e6a2d` |
| 5th | Red | `fill:#f4e8e8,stroke:#8e2d2d` |
| 6th+ | Cycle | Restart from Blue |

Example: if a project has user types Admin, Artist, Promoter, the assignments are Admin=Blue, Artist=Purple, Promoter=Green. This holds across all visualizations in the project.

### Swimlanes

Use Mermaid subgraphs only when a flow has 3+ user types. For simpler flows (1-2 user types), color-coding alone is sufficient.

### Shared components

Shared components from `shared.md` (nav, toasts, modals) are infrastructure. They do not appear as nodes in diagrams. Exception: if a shared component IS the interaction (e.g., a modal that is the entire step), it can appear as an annotation on the node, not a separate node.

### Decision points and branching

Use diamond-shaped decision nodes for conditional paths:

```
D{{"Deadline expired?"}}
D -->|"Yes"| E["Skip to review<br/><i>event-review</i>"]
D -->|"No"| F["Continue editing<br/><i>event-edit</i>"]
```

### Graph direction

Use `graph TD` (top-down) as default. Use `graph LR` (left-right) only if the flow is linear with 8+ steps, to avoid excessive vertical scrolling.

## Mermaid File Structure Template

Every visualization markdown file follows this structure. The template uses 4-space indentation to show the structure:

    # Flow Visualization: {Flow Name}

    > Visual companion to [{Flow Name}](../flows/{flow-name}.md)

    ## Flow Diagram

    ```mermaid
    graph TD
        A["Action description<br/><i>page-name</i>"] -->|"Transition"| B["Next action<br/><i>page-name</i>"]

        style A fill:#e8f4f8,stroke:#2d6a8e
        style B fill:#f0e8f4,stroke:#6a2d8e
    ```

    ## Legend

    | Color | User Type |
    |---|---|
    | Blue | {first alphabetically} |
    | Purple | {second alphabetically} |

    ## Key Decision Points

    - **After Step N:** {What happens, what to look for}

    <!-- generated-from: flows/{flow-name}.md @ {YYYY-MM-DD} | hash:{first 6 chars of SHA-256} -->

The staleness marker at the bottom is required. See the Change Detection section for how it works.

## Interactive HTML Artifact

### User preference prompt

On first run, or when the `HTML visualization` field is missing from the `verification-docs-config` memory, ask:

> "I can also generate an interactive HTML visualization. What would be most useful?
> - **A. Upgraded flow views** -- Same flows as the Mermaid diagrams but with interactivity (click nodes for details, toggle user types, zoom/pan)
> - **B. Big-picture sitemap** -- All pages, connections, and user types in one view, with drill-down into individual flows
> - **C. Both combined** -- Top-level sitemap with drill-down into flow views
> - **D. Skip** -- Mermaid diagrams are enough for now"

Save the preference to memory as:

```
HTML visualization: [flow-views | sitemap | both | none]
```

Map the answers: A = `flow-views`, B = `sitemap`, C = `both`, D = `none`.

### Constraints

- Self-contained single HTML file -- no external dependencies
- Inline CSS and vanilla JS only (no build step, no CDN links)
- Color-coding matches the Mermaid palette (same deterministic user type assignment)
- Nodes link back to corresponding verification doc files (relative paths)
- Accessible: keyboard navigable, sufficient color contrast, text labels on everything
- The skill does NOT prescribe implementation details beyond these constraints -- the generating agent builds it to fit the project's complexity

## Change Detection

### Staleness marker

Each visualization file includes a comment at the bottom:

```
<!-- generated-from: flows/{flow-name}.md @ {YYYY-MM-DD} | hash:{first 6 chars of SHA-256} -->
```

The hash is the first 6 characters of a SHA-256 of the source flow file's content at generation time. On subsequent runs, the skill reads this marker and compares the hash against the current flow file content.

### When to regenerate

**Mermaid diagram:** Regenerate when any of these are true:

- Source flow file content hash differs from the staleness marker
- Flow file is new (no corresponding visualization exists)
- User explicitly asks

**HTML artifact:** Regenerate when any of these are true:

- Any Mermaid diagram was regenerated
- Flow files were added or removed
- User explicitly asks

### When NOT to regenerate

- Only verification items changed within existing pages (new checklist items, updated expected values)
- Only the findings report changed
- Only logs were updated

### Orphan detection

If a staleness marker references a flow file that no longer exists, flag the visualization as orphaned in the index. Do not auto-delete -- the user may want to review.

## Entry Point Scoping

Visualization generation follows the same scoping as the rest of the verification-writer run:

| Entry point | Visualization scope |
|---|---|
| **New project** | Generate all Mermaid diagrams for all flow files. Ask about HTML preference. |
| **New feature** | Generate/update only visualizations for flows that reference changed pages or were themselves modified |
| **After code changes** | Same as new feature + check all existing visualizations for orphaned source flows |
| **On demand** | Generate/update only visualizations for flows within the user-specified scope |
| **Called by browser-verification** | Skip visualization step |

## Index Section Template

The `index.md` gets a new Visualizations section:

```markdown
## Visualizations
| File | Source Flow | User Types | Last Updated |
|---|---|---|---|
| [Event Lifecycle](visualizations/event-lifecycle.md) | flows/event-lifecycle.md | Admin, Promoter, Artist | 2026-04-04 |
| [Interactive Map](visualizations/app-overview.html) | all flows | all | 2026-04-04 |
```

List all Mermaid visualization files first, then the HTML artifact (if generated). User types column lists the user types that appear in the diagram, sorted alphabetically.
