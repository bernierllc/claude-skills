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
| `*API-only*` | Conditional | Italic. Required when the item can only be verified via API (no UI exists). Must be accompanied by an `<!-- API-VERIFICATION-FLAG -->` comment. |
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

## API-Only Flag

When a verification item can only be tested via API (no browser UI exists for the functionality), it must be tagged with `*API-only*` and include an HTML comment with metadata:

```markdown
- [ ] [standard] **Send POST to /api/webhooks/stripe with valid signature** --- Returns 200, event processed, database updated. *Expected: success* *API-only*
<!-- API-VERIFICATION-FLAG: reason=[webhook endpoint], durability=[permanent], note=[Stripe webhooks have no UI — always API-only] -->

- [ ] [standard] **Send POST to /api/events with valid event data** --- Returns 201, event created. *Expected: success* *API-only*
<!-- API-VERIFICATION-FLAG: reason=[no UI available], durability=[temporary], note=[Create Event form is planned for sprint 12 — rewrite as browser item when UI ships] -->

- [ ] [deep] **Call GET /api/admin/reports/export with admin token** --- Returns CSV file download. *Expected: success* *API-only*
<!-- API-VERIFICATION-FLAG: reason=[no UI available], durability=[needs-review], note=[Unclear if export should have a UI button — flag for human review] -->
```

**Durability values:**
- `permanent` — No UI by design (webhooks, cron handlers, internal APIs). Stop checking.
- `temporary` — UI is planned. Re-check on next verification-writer run and convert to browser item when UI exists.
- `needs-review` — Unclear if UI should exist. Keep flagging until human resolves.

**Browser-first rule:** If a UI form, button, or page exercises the same API endpoint, the item MUST be written as a browser interaction. The API call is verified via the network tab during browser-verification, not called directly. Example:

```markdown
# WRONG — UI exists for this
- [ ] [standard] **POST to /api/events with valid data** --- Returns 201. *Expected: success* *API-only*

# RIGHT — test through the UI
- [ ] [standard] **Fill and submit the Create Event form with name="Test Event", date="2026-04-01"** --- Event created, appears in event list, success toast shown. Network tab shows POST /api/events returning 201. *Expected: success with side effects*
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

The doc location and structure are determined by verification-writer on first run and stored in memory (see SKILL.md "Memory Integration"). Common patterns:

**Multi-role apps** — one file per role:
```
<verification-path>/
├── index.md, admin.md, educator.md, student.md, shared.md
├── findings/    └── logs/
```

**Single-role apps** — one file per feature area:
```
<verification-path>/
├── index.md, authentication.md, dashboard.md, settings.md, shared.md
├── findings/    └── logs/
```

**Large apps** — subdirectories per role or product area:
```
<verification-path>/
├── index.md, admin/user-management.md, admin/settings.md, ...
├── findings/    └── logs/
```

**API-only** — one file per API domain:
```
<verification-path>/
├── index.md, auth-endpoints.md, user-endpoints.md, ...
├── findings/    └── logs/
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
