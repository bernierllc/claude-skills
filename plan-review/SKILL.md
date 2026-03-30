---
name: plan-review
description: Use when reviewing, auditing, or cleaning up plan files. Discovers plans across the repo and Claude's project directory, correlates them with git branches, performs deep code inspection to determine actual completion state vs. claimed status, and produces a gap analysis report. Also triggered by "review my plans", "what's the state of my plans", "clean up plans", or "status of plan X".
metadata:
  filePattern:
    - "**/plans/**/*.md"
    - "**/specs/**/*.md"
    - "**/plan*.md"
    - "**/docs/**/*.plan.md"
  bashPattern:
    - "git branch"
    - "git log.*plan"
---

# Plan Review

## Overview

Plans lie. Code doesn't. This skill reconciles the two.

Inspect plan files across a project, correlate them with git branches, and perform deep code inspection to determine actual completion state versus claimed status. Produce an honest gap analysis with concrete evidence from the codebase. Adaptive — read the room based on what discovery reveals and offer appropriate next steps including cleanup, test execution, agent handoff, or roadmap generation.

This skill does not couple to any specific agent — it produces artifacts that any PM agent or human can consume.

## Checklist

Complete these in order:

1. **Determine entry point and scope** (full review, single plan, cleanup-only)
2. **Discover plan files** (AEC config → conventions → Claude dir → ask user)
3. **Discover and correlate branches** (match plans ↔ branches, categorize)
4. **Checkpoint** (if 6+ items, confirm with user before proceeding)
5. **Deep inspect each plan/branch pair** (extract artifacts, check code, gap analysis)
6. **Ask report destination** (terminal / file / both)
7. **Generate and present report** (using report template)
8. **Ask what next** (cleanup / tests / handoff / roadmap / nothing)
9. **Execute chosen actions** (with per-item confirmation for cleanup)
10. **Optionally save memory** (project-type summary of review state)

## Entry Points

| Trigger | Behavior |
|---------|----------|
| User invokes skill directly | Full cycle: discover → inspect → report → ask next |
| "review my plans" or similar | Same full cycle |
| "review this plan" / "status of plan X" | Single-plan mode: skip discovery, inspect the named plan only |
| "clean up plans" | Discovery + report, then jump straight to cleanup |
| "what's the state of my plans" | Discovery + report only, then ask what's next |

## Plan Discovery

### Source Resolution

Resolve plan file locations in priority order. Stop expanding sources once a sufficient set is found, but always check at least the first two levels:

1. **AEC config** — Read `AGENTINFO.md` for a plans directory setting (e.g., `plans_dir: docs/plans`). If present, use that path as the primary source.
2. **Convention scan** — Scan the repo root for these directories:
   - `plans/`
   - `docs/plans/`
   - `docs/superpowers/specs/`
   - `docs/superpowers/plans/`
3. **Claude's project directory** — Scan `~/.claude/projects/<project-hash>/` for plan-like `.md` files with plan structure (phase tracking, task lists, implementation steps).
4. **Ask the user** — If nothing found, or if the user might have additional locations, ask before proceeding.

### What Qualifies as a Plan File

Detect plan files using concrete signals. At least 2 must match for a file to qualify:

- **Checkboxes** — presence of `- [ ]` or `- [x]` markdown checkboxes
- **Phase/step headings** — headings matching patterns like `## Phase N`, `## Step N`, `### Task`, `## Implementation`
- **Status markers** — text like `[DONE]`, `[IN PROGRESS]`, `[NOT STARTED]`, `[COMPLETE]`, `Status: `
- **File naming** — `.plan.md` suffix, or file located inside a `plans/` directory
- **Implementation references** — mentions of specific file paths, function names, or `create`/`implement`/`build` verbs in headings

**Exclude** these regardless of signal count:
- Pure design specs with no implementation phases (no checkboxes, no phase headings)
- Memory files (`MEMORY.md`, files in `memory/`)
- READMEs and changelogs

### Discovery Output

Present findings as a table before proceeding:

| Plan Name | Source Location | Claimed Status | Associated Branch |
|-----------|----------------|----------------|-------------------|
| `<filename>` | `<path relative to repo root>` | `<extracted status or "unknown">` | `<branch if detectable from plan content or naming, else "—">` |
