# Helper Task Template (Login)

**Title**: `HELPER-002: Create login helper function for {auth-method} authentication`

**Description**:

## Objective

Create a reusable login helper function that authenticates users using {auth-method} (detected from codebase analysis). This helper blocks TEST tasks until complete.

## Auth Method Detected

**Method**: {auth-method}
- Magic Link
- OAuth (Google, GitHub, etc.)
- Username/Password
- Session-based
- Other: {specify}

## Process

### Step 1: Analyze Auth Implementation

Examine codebase to understand auth flow:
- Auth service/provider location
- Login flow steps
- Credentials/test accounts
- Session management

### Step 2: Implement Helper Function

Create `tests/playwright-helpers/auth.ts`:

```typescript
import { Page } from '@playwright/test';

export async function signInAsRegular(page: Page) {
  // Implement auth flow based on detected method
  // Example for magic link:
  // 1. Navigate to /auth
  // 2. Enter email
  // 3. Click "Send Magic Link"
  // 4. Extract code from Mailpit
  // 5. Enter code
  // 6. Wait for redirect
}

export async function signInAsAdmin(page: Page) {
  // Similar implementation for admin
}

export async function signInAsSuperAdmin(page: Page) {
  // Similar implementation for super admin
}
```

### Step 3: Test Helper

Create test script to verify helper works:

```typescript
import { test } from '@playwright/test';
import { signInAsRegular } from './helpers/auth';

test('login helper works', async ({ page }) => {
  await signInAsRegular(page);
  // Verify logged in (check for user menu, dashboard, etc.)
});
```

### Step 4: Document Usage

Update guidance document with helper usage examples.

### Step 5: Mark Complete

- Helper function implemented
- Helper tested and working
- Documentation updated
- Mark complete

## Acceptance Criteria

- ✅ Helper function implemented in `tests/playwright-helpers/auth.ts`
- ✅ Helper tested and verified working
- ✅ Documentation updated
- ✅ All user types supported (regular, admin, super-admin)

## Files to Create/Edit

- `tests/playwright-helpers/auth.ts` (helper function)
- `tests/playwright-helpers/auth.test.ts` (test for helper)
- Update `tests/AUDIT-TASKS-GUIDANCE.md` with usage

## References

- Guidance: `tests/AUDIT-TASKS-GUIDANCE.md`
- Auth detection: See auth detection script output

## Notes

- This helper blocks TEST tasks - must be complete before tests can run
- Helper should handle all edge cases (invalid credentials, network errors, etc.)

