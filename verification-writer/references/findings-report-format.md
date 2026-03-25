# Findings Report Format Reference

The findings report is produced by verification-writer after every analysis run. It's a point-in-time snapshot of verifiability health.

## File Location

```
docs/verification/findings/YYYY-MM-DD-analysis.md
```

Use the current date. If multiple runs happen in a day, append a sequence number: `YYYY-MM-DD-analysis-2.md`.

## Full Template

```markdown
# Verification Analysis Findings - YYYY-MM-DD

## Run Context
- **Entry point:** [new project | new feature | after code changes | on demand | browser-verification callback]
- **Scope:** [full project | specific routes/features | specific role]
- **Trigger:** [user request | browser-verification detected staleness | git diff analysis]

## Summary
- Routes analyzed: X
- User types found: X ([list them])
- Interaction points found: X
- Error handling status:
  - Fully handled: X (Y%)
  - Partial: X (Y%)
  - Missing: X (Y%)
- Actions taken:
  - Auto-fixed: X
  - Logged as gap (needs manual fix): X
  - Logged as systemic (needs architecture discussion): X
- Verification docs generated/updated: X files

## Verification Docs Generated

| File | Sections | Items | New/Updated |
|---|---|---|---|
| docs/verification/admin.md | X | Y | new |
| docs/verification/educator.md | X | Y | updated (3 sections changed) |
| ... | | | |

## Auto-Fixes Applied

### Fix: [Short description]
- **Route:** /path/to/route
- **What was missing:** [Specific gap: no validation, no error boundary, etc.]
- **Files changed:** [list with line counts]
- **Lines changed:** X
- **Tests:** [passed | new tests added | existing tests updated]
- **Verification doc updated:** [yes — item now documents expected behavior]

### Fix: [Next fix]
...

(If no fixes applied: "No auto-fixes applied — all gaps exceed fix thresholds or require manual review.")

## Gaps Requiring Manual Fix

### Gap: [Route] — [What's missing]
- **Severity:** high | medium | low
- **Route(s):** /path/to/route
- **Interaction:** [form submit, API call, navigation, etc.]
- **Affected user types:** [list]
- **What happens now:** [Describe current behavior — crash, generic error, no handling]
- **What should happen:** [Describe desired graceful behavior]
- **Why it can't be auto-fixed:** [exceeds line threshold | touches shared code | needs pattern decision | etc.]
- **Suggested approach:** [Specific technical suggestion]
- **Verification doc status:** [item written as TODO | item deferred until fix]

### Gap: [Next gap]
...

(If no gaps: "No gaps found — all interaction points have graceful error handling.")

## Systemic Issues

Issues that affect multiple routes or require architectural decisions.

### Issue: [Description]
- **Affected scope:** X routes across Y user types
- **Pattern:** [What's happening consistently — e.g., no error boundaries anywhere, all API calls unhandled]
- **Impact:** [What users experience — crashes, white screens, lost data]
- **Root cause:** [Why this is systemic — no established pattern, missing shared component, etc.]
- **Recommended approach:** [Architectural suggestion — create shared hook, add error boundary to root layout, etc.]
- **Effort estimate:** [small: < 1 day | medium: 1-3 days | large: > 3 days]

### Issue: [Next issue]
...

(If no systemic issues: "No systemic issues found.")

## Coverage Gaps

Routes or user types with notably low verification coverage.

| Route | User Type | Smoke | Standard | Deep | Gap Reason |
|---|---|---|---|---|---|
| /admin/settings | admin | 1 | 0 | 0 | No interactive elements analyzed — page is config-heavy, needs manual review |
| /api/webhooks | n/a | 0 | 0 | 0 | API-only route, no UI — needs separate API verification |

## Staleness Check

If this run was triggered by code changes or browser-verification callback:

### Items Confirmed Current
- X items verified against current code — no changes needed

### Items Updated
- [route/section]: [what changed and why]
  - Old: `**Submit form** --- Shows success message`
  - New: `**Submit form** --- Shows success toast with undo option for 5 seconds`

### Items Removed
- [route/section]: [what was removed and why]
  - Removed: `**Click Export button** --- CSV downloads` (Export feature removed in commit abc1234)

### Items Added
- [route/section]: [what was added and why]
  - New: `**Click "Bulk Import" button** --- File picker opens, accepts CSV` (New feature added in commit def5678)

## Next Steps

Prioritized list of what to do with these findings:

1. **Fix high-severity gaps first:** [list the high-severity gaps by route]
2. **Address systemic issues:** [if any — these unblock many gaps at once]
3. **Fix medium-severity gaps:** [list]
4. **Run browser-verification:** After fixes, run at [suggested depth] to confirm
5. **Low-severity gaps:** [can be addressed in normal development]
```

## Severity Guidelines

### High — Fix before next deploy

- User-facing crash (white screen, unhandled exception visible)
- Data loss risk (destructive action with no confirmation)
- Security boundary missing (unauthorized access not prevented)
- Form accepts and processes invalid data that corrupts state

### Medium — Fix within current sprint

- Poor error UX (generic "something went wrong", lost form input)
- Missing loading states (content pops in, layout shifts)
- Missing empty states (blank page when no data)
- Partial validation (client-side only, server accepts anything)

### Low — Fix when convenient

- Missing confirmation on non-destructive actions
- Inconsistent error message style across routes
- Minor UX gaps (no focus management, missing keyboard shortcuts)
- Edge cases that require unusual input to trigger

## Report Tone

The report is a technical document for developers, not a blame assignment. State facts:

- What the code does now
- What it should do instead
- Why (user impact)
- How to fix it (technical approach)

Do not editorialize. Do not say "unfortunately" or "it appears that someone forgot to." Just describe the gap and the fix.
