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
