# Plan Review Report — {{date}}

## Summary
- {{plan_count}} plans found across {{source_count}} sources
- {{correlated_count}} branches correlated
- {{orphan_plan_count}} orphan plans, {{orphan_branch_count}} orphan branches

## Correlation Map

| Plan | Source | Branch | Category | Last Commit |
|------|--------|--------|----------|-------------|
| {{plan_name}} | {{source_path}} | {{branch_name}} | {{category}} | {{last_commit}} |

## Per-Plan Deep Inspection

### {{plan_name}}
- **Source:** {{source_path}}
- **Branch:** {{branch_name}} (last commit: {{last_commit_date}})
- **Overall:** {{completed_phases}}/{{total_phases}} phases complete

| Phase | Plan Status | Actual Status | Evidence |
|-------|-------------|---------------|----------|
| {{phase_name}} | {{claimed_status}} | {{actual_status}} | {{evidence}} |

- **Tests available:** {{test_count}} test files found (not run)
- **Staleness:** Last commit {{days_since_commit}} days ago

### Orphan Branch: {{branch_name}}
- **Changed files:** {{changed_file_count}} files, {{additions}} additions
- **Commit summary:** "{{commit_summary}}"
- **Assessment:** {{assessment}}

### Orphan Plan: {{plan_name}}
- **Artifacts on main?** {{on_main}}
- **Assessment:** {{assessment}}

## Runnable Tests
{{test_files_grouped_by_plan}}
