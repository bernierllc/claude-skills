# Explore Route Task Template

**Title**: `{user-type}-route-explore-{number} • {route} — Manual exploration`

**Description**:

## Route Information

**Route**: `{route}`
**User Level**: `{user-type}`
**Parent Task**: `AUDIT-{NUMBER}` (Discovery task)

## Objective

Manually explore this route as {user-type} user using Playwright MCP. Document all UI elements, interactions, and states. Create TEST task during exploration with Playwright code.

## Prerequisites

- [ ] HELPER-002: Login helper function available (if needed)
- [ ] HELPER-004: Profile completion helper available (if needed)
- [ ] Vibe-Kanban MCP running (`npx vibe-kanban`)
- [ ] Playwright MCP available

## Process

### Step 1: Start Browser Session
```javascript
// Use Playwright MCP to start browser
const browser = await playwright.launch({ headless: false });
const page = await browser.newPage();
```

### Step 2: Authenticate
```javascript
// Use appropriate auth helper
// Example: await signInAs{UserType}(page);
// Or: await ensureProfileComplete(page);
```

### Step 3: Navigate to Route
```javascript
await page.goto('{base_url}{route}');
await page.waitForLoadState('networkidle');
```

### Step 4: Explore and Document

**Record ALL Playwright MCP calls made** - you'll need these for the TEST task!

#### 4.1: Document UI Elements
- All buttons (text, role, location)
- All links (text, href, location)
- All forms (fields, validation, submit buttons)
- All inputs (type, name, placeholder, required/optional)
- All dropdowns/selects (options, default selection)
- All modals/popups (trigger, content, actions)
- All tables/lists (columns, data, pagination)
- All navigation elements (breadcrumbs, menus, tabs)

#### 4.2: Document Interactions
- Click actions and their results
- Form submissions and responses
- Navigation flows
- State changes (empty → loading → populated → error)

#### 4.3: Document States
- Empty state (what appears when no data)
- Loading state (spinners, skeletons)
- Populated state (data displayed)
- Error states (validation errors, API errors)
- Success states (confirmations, redirects)

#### 4.4: Document Data Requirements
- What data is needed for this route?
- What API calls are made?
- What dependencies exist?

### Step 5: Check for New Routes

For each link/navigation found:

1. Extract the URL
2. Normalize it (lowercase, strip trailing slash, replace IDs with `:id`)
3. Check SQLite database: Is this route already discovered?
   ```sql
   SELECT * FROM routes WHERE user_level = '{user-type}' AND route = '{normalized-route}';
   ```
4. If NOT discovered:
   - Add route to database (status='discovered')
   - Create new EXPLORE task: `{user-type}-route-explore-{next-number}`
   - Write `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt`

### Step 6: Create TEST Task

**During exploration**, create the TEST task with all Playwright code:

**Task Name**: `{user-type}-route-test-{number}`

**Task Description**:
```markdown
## Route: {route}
## User Level: {user-type}

## Playwright Code from Exploration

\`\`\`javascript
// Paste ALL Playwright MCP calls made during exploration
{paste_all_playwright_code_here}
\`\`\`

## Coverage Checklist

- [ ] Route loads successfully
- [ ] Authentication works
- [ ] All UI elements render correctly
- [ ] Form interactions work (if applicable)
- [ ] Navigation works (if applicable)
- [ ] Empty state handled
- [ ] Loading state handled
- [ ] Error states handled (if applicable)

## Edge Cases

- {list_edge_cases_discovered}

## Data Requirements

- {list_data_requirements}

## Notes

- {any_notes_from_exploration}
```

### Step 7: Update This Task

Add summary of findings:
- Number of UI elements found
- Number of interactions tested
- Number of new routes discovered (if any)
- Link to TEST task created

### Step 8: Mark Complete

- All exploration complete
- TEST task created
- This task updated with findings
- Mark as complete

## Acceptance Criteria

- ✅ Successfully authenticated as {user-type}
- ✅ Navigated to route
- ✅ Documented all UI elements
- ✅ Documented all interactions
- ✅ Documented all states
- ✅ Checked for new routes (created EXPLORE tasks if found)
- ✅ Created TEST task with Playwright code
- ✅ Updated this task with findings summary

## Files to Create/Edit

- `CONTEXT_CACHE/ui_audit.db` (update route status, add new routes)
- `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt` (if new routes found)
- TEST task created in Vibe-Kanban

## References

- Guidance: `tests/AUDIT-TASKS-GUIDANCE.md` (project-specific)
- Auth helpers: `tests/playwright-helpers/auth.ts`
- Profile helpers: `tests/playwright-helpers/profile.ts`
- Test template: `.claude/skills/ui-audit/templates/test-route.md`

## Notes

- **CRITICAL**: Record ALL Playwright MCP calls - they go into the TEST task
- **CRITICAL**: Create TEST task during exploration, not after
- Use Playwright MCP for all browser interactions
- Document everything - the TEST task depends on your documentation

