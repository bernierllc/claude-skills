# Diagnosis Patterns Reference

How to read Playwright failure output and trace to root causes.

## JSON Reporter Failure Structure

Each failure in Playwright's JSON reporter output contains:

```json
{
  "title": ["test.describe title", "test title"],
  "file": "tests/verification-playwright/pages/admin-event-form.spec.ts",
  "line": 42,
  "status": "failed",
  "duration": 12345,
  "errors": [
    {
      "message": "expect(locator).toBeVisible()\n\nLocator: getByTestId('event-type-select')\nExpected: visible\nReceived: <element not found>",
      "stack": "Error: ...\n    at /path/to/test.spec.ts:45:5\n    ..."
    }
  ]
}
```

Key fields for diagnosis:
- `errors[].message` — the primary diagnostic signal
- `errors[].stack` — traces to the exact test line that failed
- `duration` — if near the timeout value, likely a timing issue
- `status: "timedOut"` vs `status: "failed"` — different root causes

## Error Message Patterns

### Selector / Element Not Found

| Error pattern | Likely cause | Investigation steps |
|---|---|---|
| `Locator: getByTestId('X')` + `<element not found>` | Testid was removed or renamed | 1. Grep source for `data-testid="X"` 2. Check git log for recent changes to the component 3. If renamed, update test; if removed, check if element was replaced |
| `strict mode violation` + `resolved to N elements` | Selector matches multiple elements | 1. Make selector more specific (add parent scope) 2. Use `nth()` if elements are in a list 3. Add a unique testid if no other option |
| `waiting for getByTestId('X')` + timeout | Element exists but not visible, or conditional render | 1. Check if element is behind a loading state 2. Check if element requires specific data/state to render 3. Add `waitForLoadState('networkidle')` or explicit condition wait |

### Assertion Mismatches

| Error pattern | Likely cause | Investigation steps |
|---|---|---|
| `Expected: "Active"` + `Received: "Pending"` | App state differs from expected | 1. Is the test's expected value correct per verification doc? 2. Was the data setup correct (seed, beforeEach)? 3. Did a recent code change alter the state machine? |
| `Expected: visible` + `Received: hidden` | Element exists but display:none or similar | 1. Check CSS conditions 2. Check if a parent container is collapsed 3. Check if the element requires an action to become visible |
| `Expected: N` + `Received: M` (numeric) | Count/value mismatch | 1. Check if seed data changed 2. Check if a filter/sort changed the visible items 3. Check if pagination affects the count |
| `expect(page).toHaveURL(X)` + different URL | Navigation changed or redirect logic changed | 1. Check route definitions 2. Check if auth redirect is intercepting 3. Check if URL structure changed |

### Network / Connection Errors

| Error pattern | Likely cause | Investigation steps |
|---|---|---|
| `ECONNREFUSED` | Dev server not running or wrong port | 1. Check if server is running (`lsof -i :<port>`) 2. Check `baseURL` in playwright config 3. Check if server crashed during test |
| `net::ERR_CONNECTION_REFUSED` | Same as above but from Chromium | Same investigation steps |
| `408 Request Timeout` or `504 Gateway Timeout` | Server is too slow or hanging | 1. Check server logs for errors 2. Check if database is accessible 3. Increase test timeout temporarily to confirm |
| `401 Unauthorized` or `403 Forbidden` | Auth session expired or invalid | 1. Check auth helper is setting cookies/tokens correctly 2. Check if session storage was cleared between tests 3. Check if auth endpoint changed |
| `404 Not Found` | Route removed or URL changed | 1. Check route definitions 2. Check if API endpoint was renamed 3. Check if the resource being accessed exists in seed data |

### Timing Issues

| Error pattern | Likely cause | Investigation steps |
|---|---|---|
| Test duration ≈ timeout value | Explicit timeout hit | 1. What was the test waiting for? 2. Add targeted `waitFor` before the failing assertion 3. Check if a network request is slow/hanging |
| Same test passes and fails across runs | Race condition | 1. Add `waitForLoadState('networkidle')` after navigation 2. Use `waitForResponse` for API-dependent assertions 3. Use `toBeVisible()` with extended timeout before interacting |
| `Target page, context or browser has been closed` | Page navigation during assertion | 1. Check if a redirect interrupts the test flow 2. Add `waitForURL` after actions that trigger navigation 3. Check if `beforeEach` cleanup is racing with test execution |

## Diagnosis Decision Tree

```
Read error message
├── Contains "not found" / "0 elements" / "strict mode"
│   → SELECTOR issue → grep source for testid/element
├── Contains "Expected:" and "Received:" with real values
│   → ASSERTION mismatch → check verification doc for correct value
├── Contains "ECONNREFUSED" / "ERR_CONNECTION"
│   → ENVIRONMENT issue → check server status
├── Contains "401" / "403" / "login" / "redirect"
│   → AUTH issue → check helpers/auth.ts
├── Contains "timeout" / duration ≈ timeout
│   → TIMING issue → add waits, check for slow operations
├── Contains "Cannot read properties of null/undefined"
│   → APP BUG → trace stack to source file, add null check
├── Contains "404" / "No rows" / "empty"
│   → DATA issue → check seed/fixture setup
└── Error is in test setup (beforeAll/beforeEach)
    → INFRASTRUCTURE issue → fix setup, all tests in describe benefit
```

## Reading Stack Traces

Stack traces in Playwright errors show both test code and app code (if the error originated in the browser). Key lines to look for:

1. **Test file line** — the `expect()` or `locator` call that failed. This is WHERE the failure was detected.
2. **App file line** (in browser errors) — if the error originated in app code (React error boundary, unhandled exception), the browser console will contain the app stack. Read console messages via the test's `page.on('console')` output or by adding `await page.evaluate(() => console.log(...))`.

Always read both the test file AND the source file before implementing a fix. A test failure is a symptom — the root cause may be in either location.

## Multi-Failure Correlation

When multiple tests fail, look for shared patterns before fixing individually:

| Pattern | Root cause | Fix once |
|---|---|---|
| All tests in one describe block fail | `beforeEach` or `beforeAll` setup is broken | Fix the setup function |
| All tests that navigate to `/admin/*` fail | Auth helper or admin route guard changed | Fix auth or route config |
| All tests with `@deep` tag fail, others pass | Deep tests depend on data that wasn't seeded | Fix seed data or `beforeAll` |
| All tests fail with same timeout | Server is slow or down | Fix environment, not tests |
| Tests fail in order (later tests fail more) | State leak between tests — earlier test leaves dirty state | Add cleanup in `afterEach`, ensure test isolation |

## Re-Run Strategy

After implementing a fix, re-run strategically:

| Scenario | Command |
|---|---|
| Fixed one test | `npx playwright test --grep "TEST-ID"` |
| Fixed shared setup (beforeEach/auth) | `npx playwright test <file>` (run entire file) |
| Fixed app code used by multiple tests | `npx playwright test --grep "TAG"` (run all tests for that page) |
| Fixed environment issue | Full suite run |

Minimize re-run scope to get fast feedback, then expand to catch regressions.
