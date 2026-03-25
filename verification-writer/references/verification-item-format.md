# Verification Item Format Reference

The canonical format for verification checklist items. Browser-verification consumes these items; verification-writer produces them. Both skills must agree on this format exactly.

## Item Syntax

```
- [ ] [depth] **Action** --- Expected result. *Expected: type*
```

### Components

| Component | Required | Description |
|---|---|---|
| `- [ ]` | Yes | Checkbox — browser-verification marks pass/fail |
| `[depth]` | Yes | One of: `smoke`, `standard`, `deep` |
| `**Action**` | Yes | Bold. What to do. Specific and actionable. |
| `---` | Yes | Separator between action and expected result |
| Expected result | Yes | What should happen. Observable, not vague. |
| `*Expected: type*` | Yes | Italic. Categorizes the expected outcome. |
| `*Requires: precondition*` | Optional | Italic. Preconditions that must be true before this item. |

### Examples

```markdown
- [ ] [smoke] **Navigate to /admin/dashboard** --- Page loads, main layout renders, no console errors. *Expected: success*
- [ ] [standard] **Click "Add User" button** --- Modal opens with name, email, role fields. *Expected: success*
- [ ] [standard] **Submit "Add User" with valid data** --- User created, appears in list, success toast. *Expected: success with side effects*
- [ ] [standard] **Click "Delete User" on active user** --- Confirmation dialog with user's name and consequences. Cancel returns to list unchanged. *Expected: warning dialog*
- [ ] [deep] **Submit "Add User" with empty fields** --- Validation errors appear on all required fields. No network request fired. *Expected: client-side validation error*
- [ ] [deep] **Submit "Add User" with duplicate email** --- Server rejects, UI shows "email already exists". No stack trace in console. *Expected: graceful server error*
- [ ] [deep] **Submit "Add User" with 500-char name** --- Truncation or validation error. No server crash. *Expected: client-side validation error*
- [ ] [deep] **Load /admin/users with no users in database** --- Empty state message displays, no broken layout, "Add User" button still visible. *Expected: graceful empty state*
- [ ] [deep] **Access /admin/users as student role** --- Redirect to student dashboard. No flash of admin content. *Expected: auth boundary enforcement*
- [ ] [deep] **Access /admin/users with expired session** --- Redirect to login page. Session-expired message shown. Return URL preserved. *Expected: auth boundary enforcement*
- [ ] [deep] **Submit "Add User" while offline** --- Error message indicating network issue. Form input preserved. Retry available. *Expected: graceful server error*. *Requires: simulate offline by throttling network in devtools*
```

## Depth Tags

### `smoke`

**Purpose:** Does the page load at all? No interaction testing.

**When to generate:**
- Every route gets exactly one smoke item: navigate and confirm it renders
- Smoke items check: page loads, no console errors, no network errors, main layout visible

**Do NOT include in smoke:**
- Clicking buttons, filling forms, testing CRUD
- Edge cases, error paths, auth boundaries
- Any interaction beyond page load

### `standard`

**Purpose:** Walk the primary user flows. Verify the features work.

**When to generate:**
- Every form: submit with valid data
- Every CRUD operation: create, read, update, delete with valid inputs
- Every navigation link: goes where it says
- Every destructive action: confirmation dialog appears
- Every auth boundary: wrong role is denied
- Every data display: populated with real-looking data

**Standard includes all smoke items** — browser-verification runs smoke items when running at standard depth.

### `deep`

**Purpose:** Completionist audit. Edge cases, error paths, boundary values.

**When to generate:**
- Every form: empty submission, invalid input, boundary values (max length, special characters), duplicate data
- Every API call: server error response, timeout, offline
- Every data display: empty state, single item, many items, null fields
- Every auth flow: expired session, concurrent sessions, token refresh
- Every error path that has graceful handling in the code
- Accessibility: keyboard navigation, focus management, screen reader labels

**Deep includes all standard and smoke items.**

## Expectation Types

### `success`

The happy path works as intended. The action completes, the UI updates, no errors.

```markdown
- [ ] [standard] **Click "Save" on profile form with valid data** --- Profile updated, success toast shown. *Expected: success*
```

### `success with side effects`

The action succeeds AND causes observable downstream effects beyond the immediate UI update.

```markdown
- [ ] [standard] **Submit "Add User" with valid data** --- User created, appears in list, success toast. Audit log entry created. Welcome email sent (check Mailpit). *Expected: success with side effects*
```

### `warning dialog`

A destructive or significant action triggers a warning/confirmation before executing.

```markdown
- [ ] [standard] **Click "Delete User" on active user** --- Confirmation dialog appears showing user's name, active session count, and consequences. Cancel returns to list unchanged. *Expected: warning dialog*
```

### `client-side validation error`

Bad input is caught by client-side validation BEFORE any network request.

```markdown
- [ ] [deep] **Submit login form with empty email** --- Inline validation error on email field. No network request in network tab. *Expected: client-side validation error*
```

### `graceful server error`

Server rejects the request. UI handles the rejection with a meaningful message, no crashes, no exposed stack traces.

```markdown
- [ ] [deep] **Submit "Add User" with duplicate email** --- Server returns 409. UI shows "Email already in use" message. Form preserves input. No console stack trace. *Expected: graceful server error*
```

### `auth boundary enforcement`

Access control prevents unauthorized access. No flash of protected content. Appropriate redirect.

```markdown
- [ ] [standard] **Access /admin/users as student role** --- Redirect to /student/dashboard. No momentary flash of admin UI. *Expected: auth boundary enforcement*
```

### `graceful empty state`

A view that normally shows data renders appropriately when there is no data.

```markdown
- [ ] [deep] **Load /admin/users with no users in database** --- Empty state message: "No users yet." "Add User" button still accessible. Table headers still visible. *Expected: graceful empty state*
```

## Document Structure

### File organization

One file per user type/role:

```
docs/verification/
├── index.md              # Master index, prerequisites, credentials
├── admin.md              # All routes accessible by admin
├── educator.md           # All routes accessible by educator
├── student.md            # All routes accessible by student
├── guardian.md            # All routes accessible by guardian
├── shared.md             # Cross-role components, public pages
├── findings/
│   └── YYYY-MM-DD-analysis.md
└── logs/
    └── YYYY-MM-DD-verification-run.md  (generated by browser-verification)
```

### Section structure within a file

```markdown
# Verification: [Role Name]

## Prerequisites
- Account: [email]
- Requires: [services, seed data, etc.]

## [Feature Name] ([route])

- [ ] [smoke] ...
- [ ] [standard] ...
- [ ] [standard] ...
- [ ] [deep] ...
- [ ] [deep] ...
- [ ] [deep] ...

## [Next Feature] ([route])
...

## Auth Boundaries
(Cross-cutting auth checks for this role attempting to access other roles' routes)
...
```

### Ordering within a section

1. Smoke items first (page load)
2. Standard items next (happy path flows, ordered by typical user workflow)
3. Deep items last (edge cases, error paths, grouped by the interaction they test)

## Writing Good Items

### Action must be specific and reproducible

Bad: `**Test the form**`
Good: `**Submit "Add User" form with name="Test User", email="test@example.com", role="Student"**`

### Expected result must be observable

Bad: `--- It should work.`
Good: `--- User appears at top of user list. Success toast: "User created." Network tab shows POST /api/users returning 201.`

### Error items must specify what NOT to see

Bad: `--- Error is handled.`
Good: `--- UI shows "Email already in use" inline on email field. No console stack trace. No white screen. Form input preserved.`

### Include enough context for browser-verification to act

The agent running these items has never seen this codebase before. It needs:
- Exact text to type or click
- Exact location (route, button label, form name)
- Exact expected outcome (what appears, what disappears, what logs)
