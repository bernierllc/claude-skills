# Discovery Task Template

**Title**: `AUDIT-{NUMBER}: Discover {USER_TYPE} user routes`

**Description**:

## IMPORTANT: Prerequisites and Exploration Strategy

**CRITICAL**: Read the complete guidance document: `tests/AUDIT-TASKS-GUIDANCE.md` (project-specific guidance)

**User Type**: {USER_TYPE}
**Credentials**: {USER_CREDENTIALS}
**Base URL**: {BASE_URL}

## Goal

Discover navigable routes for {USER_TYPE} user level and UPSERT normalized routes into SQLite (status='discovered'). **MANDATORY**: Create EXPLORE tasks for each discovered route.

## Process

### Step 1: Bootstrap (if not already done)
```bash
node CONTEXT_CACHE/ui-audit-bootstrap.mjs --user-level {USER_TYPE}
```

### Step 2: Discover Routes
1. Seed candidates from route constants or sitemap if available
2. Authenticate as {USER_TYPE} user
3. Traverse UI using Playwright MCP:
   - Click all likely navigations: links, buttons, cards, list rows, breadcrumbs, modal actions
   - Follow all navigation paths
4. Normalize routes:
   - Lowercase all routes
   - Strip trailing slashes
   - Replace volatile segments (IDs, UUIDs, slugs) with `:id`/`:slug`
   - Example: `/users/123` → `/users/:id`

### Step 3: Store Routes
- UPSERT each route into SQLite database (`CONTEXT_CACHE/ui_audit.db`)
- Table: `routes`
- Columns: `user_level`, `route`, `status='discovered'`, `discovered_at`
- Use normalized route format

### Step 4: Create EXPLORE Tasks (MANDATORY COMPLETION STEP)

**CRITICAL**: Discovery is NOT complete until all EXPLORE tasks are created!

For EACH discovered route:

1. **Check de-duplication**: 
   - Path: `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{normalized-route}/route.txt`
   - If file exists → skip (task already created)
   - If file does NOT exist → proceed

2. **Create EXPLORE task via Vibe-Kanban MCP**:
   ```javascript
   // Example task creation with rate limiting
   const taskName = `{user-type}-route-explore-{number}`; // e.g., "super-admin-route-explore-001"
   const taskDescription = `...`; // Use explore-route.md template
   
   // Rate limiting: sleep(1) between creations
   await sleep(1000);
   
   // Handle 429 errors with exponential backoff
   let delay = 1000;
   let retries = 0;
   while (retries < 3) {
     try {
       const task = await createTask(projectId, taskName, taskDescription);
       break; // Success
     } catch (error) {
       if (error.status === 429) {
         delay += 500; // Increase by 0.5 seconds
         await sleep(delay * 2); // Wait double on error
         retries++;
       } else {
         throw error; // Re-throw non-429 errors
       }
     }
   }
   ```

3. **Write route.txt file**:
   - Create directory: `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{normalized-route}/`
   - Write task ID to `route.txt` file
   - This prevents duplicate task creation

4. **Track in parent task**:
   - Add route and task ID to checklist in this task description

### Step 5: Update Parent Task
- Add checklist of all created EXPLORE tasks
- Format: `| Route | Task Name | Status |`
- Mark discovery task complete ONLY after all EXPLORE tasks created

## Completion Checklist

- [ ] All routes discovered from code constants + Playwright traversal
- [ ] All routes normalized (lowercase, no trailing slash, IDs replaced with `:id`/`:slug`)
- [ ] All routes stored in SQLite database (status='discovered')
- [ ] For EACH route: Created `{user-type}-route-explore-{number}` task via Vibe-Kanban MCP
- [ ] For EACH route: Wrote `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt` with task ID
- [ ] Rate limiting handled (1s delay between creations, 429 errors handled with exponential backoff)
- [ ] Updated parent task with checklist of all created EXPLORE tasks
- [ ] Verified all EXPLORE tasks created successfully

## Acceptance Criteria

- ✅ All routes discovered and stored in SQLite
- ✅ EXPLORE tasks created for every discovered route
- ✅ No duplicate tasks created (de-duplication files exist)
- ✅ Rate limiting implemented correctly
- ✅ Parent task updated with complete checklist

## Files to Create/Edit

- `CONTEXT_CACHE/ui_audit.db` (SQLite database)
- `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt` (one per route)
- Discovery artifact: `CONTEXT_CACHE/{USER_TYPE}/discovery.json` (optional, for reference)

## References

- Plan: `docs/testing/generalized-ui-testing-plan.md` (project-specific)
- Bootstrap: `CONTEXT_CACHE/ui-audit-bootstrap.mjs`
- DB schema: `CONTEXT_CACHE/schema.sql`
- Explore task template: `.claude/skills/ui-audit/templates/explore-route.md`

## Notes

- Use CONTEXT_CACHE DB for de-duplication; avoid Vibe-Kanban searches
- If Vibe-Kanban MCP is not running, ask human to run: `npx vibe-kanban` in another terminal
- **CRITICAL**: Do NOT mark this task complete until all EXPLORE tasks are created
- **CRITICAL**: Do NOT list "next steps" - create the actual tasks as completion step

