# Test Route Task Template

**Title**: `{user-type}-route-test-{number} • {route} — Comprehensive Playwright tests`

**Description**:

## Route Information

**Route**: `{route}`
**User Level**: `{user-type}`
**Parent Task**: `AUDIT-{NUMBER}` (Discovery task)
**Linked Explore Task**: `{user-type}-route-explore-{number}`

## Objective

Implement comprehensive Playwright tests for this route based on exploration findings. The exploration task should have provided Playwright code - refine it into proper test structure.

## Prerequisites

- [ ] HELPER-002: Login helper function complete and tested
- [ ] HELPER-004: Profile completion helper complete and tested (if needed)
- [ ] Explore task complete (TEST task created during exploration)
- [ ] Playwright MCP available

## Process

### Step 1: Read Playwright Code from Task Description

The explore task should have pasted all Playwright MCP calls made during exploration. Extract this code.

### Step 2: Refine into Test Structure

Convert exploration code into proper test structure:

```typescript
import { test, expect } from '@playwright/test';
import { signInAs{UserType} } from '../helpers/auth';
import { ensureProfileComplete } from '../helpers/profile';

test.describe('{route} - {user-type}', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: authenticate and ensure profile complete
    await signInAs{UserType}(page);
    await ensureProfileComplete(page);
  });

  test('should load route successfully', async ({ page }) => {
    // Navigation code from exploration
    await page.goto('{base_url}{route}');
    await page.waitForLoadState('networkidle');
    
    // Assertions
    await expect(page).toHaveURL(/.*{route}/);
  });

  test('should display all UI elements', async ({ page }) => {
    // Element verification code from exploration
    // ...
  });

  test('should handle form interactions', async ({ page }) => {
    // Form interaction code from exploration
    // ...
  });

  // Add more tests based on exploration findings
});
```

### Step 3: Implement Coverage Checklist

Ensure all items from exploration coverage checklist are implemented:

- [ ] Route loads successfully
- [ ] Authentication works
- [ ] All UI elements render correctly
- [ ] Form interactions work (if applicable)
- [ ] Navigation works (if applicable)
- [ ] Empty state handled
- [ ] Loading state handled
- [ ] Error states handled (if applicable)

### Step 4: Run Tests

```bash
npx playwright test tests/{user-type}/{normalized-route}.spec.ts
```

### Step 5: Handle Failures

If tests fail:

1. **UI mismatch**: Adjust selectors/flows based on actual UI
2. **Timing issues**: Add robust waits tied to user-visible states
3. **Product bug**: Create BUG-#### task, mark this task blocked
4. **Missing data**: Document data requirements, create HELPER task if needed

### Step 6: Update Task

- Add test file path
- Add run command
- Add test results
- Mark complete if all tests pass

## Acceptance Criteria

- ✅ Test file created: `tests/{user-type}/{normalized-route}.spec.ts`
- ✅ All coverage checklist items implemented
- ✅ Tests pass locally
- ✅ Tests are deterministic (no flaky behavior)
- ✅ Tests use resilient selectors (roles, labels, testIds)
- ✅ Tests use robust waits (not arbitrary sleeps)

## Files to Create/Edit

- `tests/{user-type}/{normalized-route}.spec.ts` (test file)
- Update this task with test results

## References

- Explore task: `{user-type}-route-explore-{number}`
- Guidance: `tests/AUDIT-TASKS-GUIDANCE.md` (project-specific)
- Auth helpers: `tests/playwright-helpers/auth.ts`
- Profile helpers: `tests/playwright-helpers/profile.ts`

## Notes

- Tests should be based on Playwright code from exploration task
- If blockers found, create HELPER or BUG tasks
- Mark task complete only when tests pass

