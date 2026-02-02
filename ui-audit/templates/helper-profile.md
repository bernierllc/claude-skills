# Helper Task Template (Profile Completion)

**Title**: `HELPER-004: Create ensureProfileComplete helper function`

**Description**:

## Objective

Create a reusable helper function that ensures user profile is complete. This is often a blocking gate that redirects users from any route back to profile completion form.

## Process

### Step 1: Analyze Profile Form

Examine profile completion form:
- Form fields required
- Custom implementations (e.g., custom checkboxes)
- Validation rules
- Submit flow

### Step 2: Implement Helper Function

Create `tests/playwright-helpers/profile.ts`:

```typescript
import { Page } from '@playwright/test';

export async function ensureProfileComplete(page: Page) {
  // Check if profile form is visible
  const profileForm = page.locator('[data-testid="profile-form"]');
  
  if (await profileForm.isVisible()) {
    // Fill out form based on form implementation
    // Handle custom checkboxes, autocomplete, etc.
    
    // Example for custom checkbox (click text label):
    await page.getByText('I accept the Privacy Policy').click();
    await page.getByText('I accept the Terms of Service').click();
    
    // Fill other fields
    await page.fill('[name="firstName"]', 'Test');
    await page.fill('[name="lastName"]', 'User');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Wait for form to disappear
    await profileForm.waitFor({ state: 'hidden' });
  }
}
```

### Step 3: Test Helper

Create test script to verify helper works:

```typescript
import { test } from '@playwright/test';
import { signInAsRegular } from './helpers/auth';
import { ensureProfileComplete } from './helpers/profile';

test('profile completion helper works', async ({ page }) => {
  await signInAsRegular(page);
  await ensureProfileComplete(page);
  // Verify profile complete (check for dashboard, no redirect loop)
});
```

### Step 4: Document Usage

Update guidance document with helper usage examples and known issues (e.g., custom checkbox implementation).

### Step 5: Mark Complete

- Helper function implemented
- Helper tested and working
- Documentation updated
- Mark complete

## Acceptance Criteria

- ✅ Helper function implemented in `tests/playwright-helpers/profile.ts`
- ✅ Helper handles all form fields correctly
- ✅ Helper handles custom implementations (e.g., custom checkboxes)
- ✅ Helper tested and verified working
- ✅ Documentation updated

## Files to Create/Edit

- `tests/playwright-helpers/profile.ts` (helper function)
- `tests/playwright-helpers/profile.test.ts` (test for helper)
- Update `tests/AUDIT-TASKS-GUIDANCE.md` with usage and known issues

## References

- Guidance: `tests/AUDIT-TASKS-GUIDANCE.md`
- Known issues: See project-specific guidance for custom checkbox implementations

## Notes

- This helper blocks TEST tasks - must be complete before tests can run
- Pay special attention to custom form implementations (checkboxes, autocomplete, etc.)
- Helper should handle cases where profile is already complete

