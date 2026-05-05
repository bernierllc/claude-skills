# Test Generation Patterns Reference

How verification items map to Playwright tests.

## Item-to-Test Mapping

A verification item:
```markdown
- [ ] [standard] **EVT-FRM-TKT-03** Enter ticket_price_min greater than
  ticket_price_max --- Validation error. *Expected: client-side validation error*
```

Becomes a Playwright test:
```typescript
// @begin:EVT-FRM-TKT-03
test('@EVT-FRM-TKT-03 @standard @admin-event-form min price > max price',
  async ({ page }) => {
    await page.goto('/events/new?event_type=music');
    await page.fill('[data-testid="ticket-price-min"]', '50');
    await page.fill('[data-testid="ticket-price-max"]', '25');
    await page.click('[data-testid="submit-event"]');
    // Expected: client-side validation error
    await expect(page.locator('[data-testid="ticket-price-error"]'))
      .toBeVisible();
    await expectNoConsoleErrors(page);
    await expectNoNetworkErrors(page);
  });
// @end:EVT-FRM-TKT-03
```

## Interaction Classification

Before writing any test, classify the verification item into one of the seven interaction types below. Add the type as a comment immediately inside the test function: `// Classification: file-upload`.

The classification locks in the completeness requirement — you cannot stub a test by re-labeling its type. If you classify an item as `file-upload`, the test must contain all `file-upload` must-have elements or carry a valid skip reason.

### The seven types

| Type | Trigger words in verification item | Test MUST contain |
|---|---|---|
| `ui-navigation` | navigate, click link, redirect, see page | `goto` call + assertion that target element is visible or URL is correct |
| `form-input` | enter, fill, submit, validate, error, field, invalid | fill all relevant fields → trigger submit action → assert success element OR error element visible |
| `file-upload` | upload, attach, select file, import, choose file | locate file input → `setInputFiles` with test file (check `.test-assets/` first) → trigger upload → wait for completion signal → assert result state |
| `api-response` | response includes, API returns, endpoint returns, status code, JSON field, payload | `page.request` call to endpoint → assert status code → assert key body fields (not full shape) |
| `state-cascade` | changes when, clears when, updates when, resets when, depends on, conditional on | trigger action on same page → assert each affected field/element in sequence |
| `multi-step-workflow` | then, after, next step, workflow, process, cross-page, followed by; also: form submission that navigates to a different page | execute each step in order → assert intermediate state after each key step → assert final state |
| `auth-boundary` | cannot access, redirected, 403, unauthorized, role required | attempt access without auth OR with insufficient role → assert redirect target or blocked/403 state |

### Classification tiebreaker rules

**State-cascade vs. multi-step-workflow:** If the trigger and all affected assertions occur within a single page view → `state-cascade`. If the trigger is on a different page, step, or navigation event from where the assertions are made → `multi-step-workflow`.

Examples:
- Same form, type dropdown changes → sections hide/show on same page: `state-cascade`
- Step 1 sets a value → step 3 (different page) shows a derived field: `multi-step-workflow`

**Form-input vs. multi-step-workflow:** If fill, submit, and assert all occur on a single page view → `form-input`. If form submission navigates to a different page and the assertion must be made there → `multi-step-workflow`.

Examples:
- Fill event form → submit → validation error on same page: `form-input`
- Fill event form → submit → navigate to event detail → assert record appears: `multi-step-workflow`

## Testid Requirement by Type

Not all interaction types require `data-testid` attributes. Before generating a stub citing "missing testid", confirm whether the type actually needs a DOM selector.

| Type | Testid needed? | Notes |
|---|---|---|
| `ui-navigation` | Sometimes | Needed if asserting element visible; not needed if asserting URL only |
| `form-input` | Usually yes | All fields, submit button, error/success elements; try `getByLabel` for labeled inputs first |
| `file-upload` | Yes (file input) | Also needs result state element; `getByLabel` often works for file inputs |
| `api-response` | **No** | `page.request` — no DOM interaction at all |
| `state-cascade` | Yes (affected fields) | Try `getByRole`/`getByLabel` for form fields before claiming missing |
| `multi-step-workflow` | Varies per step | Evaluate each step independently |
| `auth-boundary` | **Rarely** | URL assertion or `getByText` on static "Access denied" copy is usually sufficient |

If an item's type does not need a testid and a `.skip()` stub was generated citing "missing testid", this is a misclassification. Classify the item correctly, then implement the test.

## Tag Format

Every generated test gets three tags in its test name:

- `@EVT-FRM-TKT-03` — item ID (surgical test selection via `--grep`)
- `@standard` — depth tier (filter by smoke/standard/deep)
- `@admin-event-form` — page file name (run all tests for a page)

These tags enable Playwright's `--grep` to select exactly the right tests for any change scope.

## Marker Format

Each test is wrapped in comments:
```
// @begin:ITEM-ID
test('@ITEM-ID ...', async ({ page }) => { ... });
// @end:ITEM-ID
```

`sync-tests.js` uses these markers to locate and patch individual tests without parsing TypeScript. The content between markers is what `generated_hash` is computed from.

## Parsing Verification Items

The regex pattern for extracting verification items from markdown:
```
/^- \[ \] \[(\w+)\] \*\*([A-Z0-9-]+)\*\* (.+?) --- (.+)\. \*Expected: (.+)\*/
```

Capture groups:
1. Depth: `smoke`, `standard`, or `deep`
2. Item ID: e.g., `EVT-FRM-TKT-03`
3. Action text: what to do
4. Expected result: what should happen
5. Expected type: `success`, `client-side validation error`, etc.

## Annotation-to-Test Mapping

### STATE-DEPENDENCY annotations

```markdown
<!-- STATE-DEPENDENCY:
  trigger: eventType field change to non-music type
  affected_fields: [flyer_uploader_id, responsibility_person_id]
  expected_cascade: [clear flyer_uploader_id, clear responsibility selections, hide artist/promoter sections]
  code_ref: EventForm.tsx:useEffect watching eventType
  failure_mode: FK constraint violation if stale ID submitted
-->
```

Maps to test code:
- `trigger` → setup sequence (the actions before assertions)
- `affected_fields` → assertion targets (each field is checked)
- `expected_cascade` → ordered `expect()` calls, one per step
- `code_ref` → code comment: `// Source: EventForm.tsx:useEffect watching eventType`
- `failure_mode` → assertion strategy:
  - `FK constraint violation` → assert form prevents submission or shows validation error (not a 500)
  - `data corruption` → assert the submitted payload does not contain stale references
  - `UI crash` → assert no console errors after the action

### BUSINESS-CONTEXT annotations

```markdown
<!-- BUSINESS-CONTEXT:
  rule: Confirmation deadline is 72 hours from event creation
  valid_range: Timer value must be <= 72 hours and >= 0
  cross_reference: [Deadline date badge should match timer target]
  red_flags: [Timer > 72h means wrong source; Timer at 0 but status not "expired"]
-->
```

Maps to:
- `rule` → code comment with the business rule
- `valid_range` → bounds check assertions on displayed values
- `cross_reference` → assertions comparing related values on the same page
- `red_flags` → negative assertions (values that should never appear)

### API-VERIFICATION-FLAG annotations

Items tagged `*API-only*` with this annotation generate tests that:
- Call the API endpoint directly (no browser interaction)
- Assert response status, shape, and key values
- Check `durability` field: `permanent` = always API-only, `temporary` = check if UI now exists

### Composition with `api-response` interaction type

When an item carries an `API-VERIFICATION-FLAG` annotation, use this table to determine how classification and the annotation compose:

| Annotation state | Classification | What to generate |
|---|---|---|
| `*API-only*` tag + `durability: permanent` | `api-response` | `page.request` test against the endpoint |
| `*API-only*` tag + `durability: temporary` | `api-response` for now | `page.request` test; record in `testid-gaps.md`: "UI may eventually exist — reclassify when UI is added" |
| `API-VERIFICATION-FLAG` present, no `*API-only*` tag | Driven by item text | Generate test for resolved type; embed `endpoint` as code comment regardless: `// API ref: POST /events/create`. Ignore `durability` unless type resolves to `api-response`. |
| No annotation, item text matches `api-response` triggers | `api-response` | `page.request` test; no durability consideration |

## Selector Verification (live tests only)

A live test (non-`.skip()`) must use a selector confirmed against component source. Before writing the test:

1. Use `manifest/import-index.json` to map the route → source file.
2. Read the component file(s) rendered for that route.
3. For each selector, confirm one of:
   - exact `data-testid` attribute present in JSX
   - exact `getByRole` + accessible name present in JSX
   - exact `getByLabel` association present in JSX
   - exact static text/placeholder literal present in JSX

If verification fails, emit a `.skip()` stub with skip reason 3 (selector unverified) using this template:

```typescript
// @begin:PUB-07
test.skip('@PUB-07 @standard @public-home article cards visible',
  async ({ page }) => {
    // SKIP REASON: missing data-testid (skip reason 3) — selector unverified
    // Component read: components/PublicHome/ArticleList.tsx
    // Alternatives tried:
    //   data-testid="article-card": not found in component source
    //   getByRole('article'): component renders <div>, not <article>
    //   getByText: card content is dynamic data, not static copy
    // TODO: Add data-testid="article-card" to ArticleCard.tsx, then remove .skip()
  });
// @end:PUB-07
```

**Forbidden in live tests** (these patterns indicate a guess, not a verification):

- `[data-testid*="..."]` — substring matching is a guess that the testid contains a word; the actual attribute may not exist.
- `locator('form').first()`, `nav a`, `article`, `.card` — generic CSS that assumes markup shape.
- `OR-chains` like `[data-testid*="x"], article, .x` — stacking guesses does not produce a verified selector; it produces a more tolerant guess.
- `getByText(/dynamic regex/i)` against data values that vary per environment.

If you find yourself writing one of these because you cannot read the source, that's the signal to emit a stub instead.

## Live Data Dependencies

When a verification item asserts presence of dynamic content (e.g., cards, feed entries, table rows), the test depends on seeded data.

**Generation pattern when `data_setup.ready = true`:**

```typescript
// @begin:PUB-07
test('@PUB-07 @standard @public-home article cards visible',
  async ({ page }) => {
    // Classification: ui-navigation (with data dependency)
    // Required data: ≥1 published article (see metadata/public-home.md)
    await seedArticles({ count: 3 });
    await page.goto('/');
    await expect(page.getByTestId('article-card').first()).toBeVisible();
  });
// @end:PUB-07
```

**Generation pattern when `data_setup.ready = false`:**

```typescript
// @begin:PUB-07
test.skip('@PUB-07 @standard @public-home article cards visible',
  async ({ page }) => {
    // SKIP REASON: data_setup.ready = false (skip reason 2)
    // Required data: ≥1 published article
    // TODO: Implement helpers/seed.ts#seedArticles, set data_setup.ready=true in metadata/public-home.md
  });
// @end:PUB-07
```

**Anti-pattern (do not generate this):**

```typescript
// WRONG — masks real assertion failures
const hasCards = await page.locator('[data-testid*="article-card"], article').count() > 0;
const hasEmptyState = await page.getByText(/no articles yet/i).isVisible().catch(() => false);
expect(hasCards || hasEmptyState).toBe(true);
```

The `hasContent || hasEmptyState` fallback is only valid when the verification item itself is explicitly typed `graceful empty state` — i.e., the *expected outcome* under test is the empty state. For items asserting content presence, the only valid outcomes are: seeded + assertion, or stubbed.

## Missing Testid Handling

When a verification item references UI elements without `data-testid` attributes:

1. Items with missing testids get a stub only after stable alternatives are exhausted. The stub MUST include: the skip reason number, which alternatives were tried and why each failed, and the TODO to add the testid:
```typescript
// @begin:EVT-FRM-SD-01
test.skip('@EVT-FRM-SD-01 @deep @admin-event-form state cascade on type change',
  async ({ page }) => {
    // SKIP REASON: missing data-testid (skip reason 3)
    // Alternatives tried:
    //   getByRole: no accessible role distinguishes this element
    //   getByLabel: element has no associated label
    //   getByText: text is dynamic data value (status string), not static copy
    //   getByPlaceholder: not an input with placeholder
    // TODO: Add data-testid="event-type-select" to EventForm.tsx, then remove .skip()
  });
// @end:EVT-FRM-SD-01
```

2. Log the gap to `testid-gaps.md`. Every skip-reason-3 stub gets an entry — both *confirmed-missing* (component read, testid not present) and *unverified* (selector guessed because source could not be confirmed). The `Status` column distinguishes them so component owners can prioritize:

```markdown
# Verification Playwright: Missing data-testids

> Generated: 2026-04-07T18:00:00Z
> Total items: 432 | Active tests: 298 | Skipped (missing testids): 134

## Priority: High (standard depth items)

| Item ID | Description | Suggested testid | Component file | Status |
|---------|-------------|------------------|----------------|--------|
| EVT-FRM-TKT-04 | Negative price validation | `ticket-price-min-error` | EventForm.tsx | confirmed-missing |
| PUB-07 | Article cards visible | `article-card` | ArticleCard.tsx | confirmed-missing |
| ADM-CORE-04 | Recent activity panel | `recent-activity` | AdminDashboard.tsx | unverified (component not located via import-index) |

## Priority: Normal (deep depth items)

| Item ID | Description | Suggested testid | Component file | Status |
|---------|-------------|------------------|----------------|--------|
| EVT-FRM-SD-01 | State cascade on type change | `event-type-select` | EventForm.tsx | confirmed-missing |
```

**Status values:**
- `confirmed-missing` — component source was read; the suggested testid (or any stable alternative) is not present. Add the testid.
- `unverified` — component source could not be confidently located or read. The testid may or may not exist; needs human disambiguation. Pair with a note in the Description column explaining what blocked verification.

3. On subsequent runs, grep the codebase for previously-missing testids. If found, remove `.skip()` and update status to `active`. For `unverified` rows, re-attempt source location before grepping — the gap may resolve once `import-index.json` is corrected.

4. **Data-dependency stubs (skip reason 2) do NOT belong in `testid-gaps.md`.** They go in a separate `data-setup-gaps.md` (or a labeled section within the same report) keyed by required seed shape. Mixing them obscures which component owners need to act vs. which seed authors do.

## Test Pinning

Detect manual edits by comparing actual file content (between `@begin`/`@end` markers) against `generated_hash` in `items.json`.

- Hash matches → test is generated, safe to overwrite
- Hash differs → developer edited the test, set `pinned: true`
- Pinned tests: never overwritten, reported as "pinned (manually edited)"
- Un-pin: set `"pinned": false` in items.json, or use `--force`

## First Run Behavior

The first run in a project is a discovery and generation phase:

1. Walk each verification page doc section by section
2. Report progress: "Processing admin-event-form.md (36 items) → 22 tests generated, 14 skipped (missing testids)"
3. Generate `testid-gaps.md` with the full gap report
4. Build the complete import index by tracing routes to source files
5. Create `manifest/config.json` with default tier configuration (ask user to customize)

The first run will take time and produce a large testid gap report. This is expected and welcomed — the report is the prioritized work list for adding test infrastructure.

## Expectation Type Mapping

| Expected type | Test assertion pattern |
|---|---|
| `success` | No errors, expected element visible/present |
| `warning dialog` | Dialog/modal appears with expected text |
| `client-side validation error` | Error message element visible, form not submitted |
| `graceful server error` | Error toast/message visible, no raw error objects, no console errors |
| `auth boundary enforcement` | Redirect to login or 403 page |
| `success with side effects` | Primary action succeeds AND downstream effects verified |
| `graceful empty state` | Empty state component visible, no errors |
