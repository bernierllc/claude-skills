# Design: playwright-test-generator v3.0.0

**Date:** 2026-04-13
**Status:** Approved
**Version bump:** 2.0.0 → 3.0.0 (breaking behavioral change)

## Problem

Agents using the v2 skill produced incomplete test suites in three systematic ways:

1. **Multi-step interactions stubbed** — tests involving file uploads, form sequences with wait-for-response, or multi-page workflows were marked `.skip()` citing complexity, not a real blocker.
2. **API tests omitted** — verification items describing API response shapes were labeled "backend-only" and skipped, even though Playwright's `page.request` API handles these directly.
3. **Stubs never converted** — stubs generated when testids were missing were never updated after testids were added, because the un-skip path was only mechanical (`sync-tests.js`) and agents didn't verify completeness before declaring generation done.

Root cause: the skill provided too many acceptable escape hatches. "Missing testid", "multi-step", and "API-level" were all treated as valid skip reasons without being challenged.

## Decisions

### 1. Test completeness lives in the skill; Playwright knowledge lives in the agent

The skill defines *what must be tested and to what standard*. The agent brings *how to write excellent Playwright tests*. The skill does not become a Playwright tutorial.

A new agent recommendation caveat points users to a Playwright Test Writer agent for best results.

### 2. Interaction classification system (in test-generation-patterns.md)

Every verification item is classified into one of seven interaction types before test generation begins. The classification determines what a complete test for that type must contain. Classifying an item locks in the completeness requirement — agents cannot escape by re-labeling a `file-upload` item as "too complex."

The classification step is the primary breaking change in v3. V2 had no classification step; agents went directly from verification item to test generation. V3 requires classification first, which produces a mandatory completeness contract per item before any code is written. A v2 agent cannot satisfy v3 compliance because it skips this step entirely.

### 3. Valid vs. invalid skip reasons (explicit and closed)

Exactly four reasons justify a `.skip()` stub:

1. `auth.ready = false` in the metadata doc
2. `data_setup.ready = false` in the metadata doc (mirrors the existing metadata frontmatter — this is an infrastructure readiness gate, not a test complexity issue)
3. Testid genuinely missing AND no stable alternative selector exists (see "Stable alternative" definition below). **Not applicable to `api-response` or `auth-boundary` types** — these use `page.request` or navigation assertions and require no DOM selector at all. Claiming missing testid as a skip reason for these types is a misclassification.
4. Item explicitly marked `manual-only` in the verification doc

Everything else — multi-step, file upload, API response, network wait, requires navigation — is an interaction type, not a skip reason.

**Stable alternative definition (for skip reason 3):**
Before claiming a testid is missing and no alternative exists, the agent must attempt selectors in this priority order:
1. `getByRole` with an accessible name (e.g., `getByRole('button', { name: 'Upload' })`)
2. `getByLabel` for form controls associated with a visible label
3. `getByText` — **only valid when the text is static UI copy** (button labels, column headers, field labels, section titles). Not valid when the text is a dynamic data value (status strings, counts, user-generated content, locale-sensitive strings). If an element's text changes based on data, `getByText` is not a stable selector.
4. `getByPlaceholder` — **only valid when the placeholder is static UI copy**, not a dynamic or programmatically-set value.

Only if all applicable options are exhausted is the element untargetable without a testid. The agent must document which alternatives were tried and why each was rejected in the stub comment.

**Updated stub template** (replaces the existing template in `references/test-generation-patterns.md`):

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

The stub template in `references/test-generation-patterns.md` is updated to match this format. The Checkpoint B audit checks that every stub with skip reason 3 has a populated "Alternatives tried" block — a stub that omits it is non-compliant.

**`requires data setup` clarification:**
"Requires test data setup" is never a skip reason by itself. It is a characteristic of certain interaction types (particularly `multi-step-workflow` and `state-cascade`). If `data_setup.ready = false` in the metadata doc, the test is skipped because the *infrastructure* to seed that data isn't implemented — not because the test is complex. If `data_setup.ready = true`, the data setup is the agent's responsibility to implement in `beforeEach`.

### 4. Interaction type composition with API-VERIFICATION-FLAG

The existing skill has an `API-VERIFICATION-FLAG` annotation pathway with a `durability` field (`permanent` vs. `temporary`). The new `api-response` interaction type and the existing annotation pathway compose as follows:

- Items tagged `*API-only*` with `durability: permanent` → classify as `api-response`, generate `page.request` test
- Items tagged `*API-only*` with `durability: temporary` → classify as `api-response` now, but record in `testid-gaps.md` with a note that UI may eventually exist; when UI appears, reclassify
- Items with `API-VERIFICATION-FLAG` but no `*API-only*` tag → classification is driven by the item text (may be `api-response` or another type). The annotation's `endpoint` field is embedded as a code comment in the generated test for traceability regardless of the resolved type (e.g., `// API ref: POST /events/create`). The `durability` field is only acted on if the classification resolves to `api-response`; otherwise it is ignored.
- Items classified as `api-response` without an `API-VERIFICATION-FLAG` annotation → generate `page.request` test; no durability consideration needed

### 5. Classification tiebreaker rules

**State-cascade vs. multi-step-workflow:**
These two types overlap for STATE-DEPENDENCY annotations that span multiple pages or form steps. Tiebreaker: **if the trigger and all affected assertions occur within a single page view, classify as `state-cascade`. If the trigger is on a different page, step, or navigation event from the assertions, classify as `multi-step-workflow`.**

Examples:
- Event type dropdown changes → artist section hides on the same form → `state-cascade`
- Event type set on step 1 → confirmation email template changes on step 3 (different page) → `multi-step-workflow`

**Form-input vs. multi-step-workflow:**
These overlap when a form submission triggers navigation to a different page. Tiebreaker: **`form-input` applies when the entire interaction — fill, submit, and assert — occurs on a single page view. If the form submission navigates to a different page and the assertion must be made there, classify as `multi-step-workflow`.**

Examples:
- Fill event form → submit → validation error appears on same page → `form-input`
- Fill event form → submit → navigate to event detail page → assert event appears → `multi-step-workflow`

### 6. Two distinct completeness checkpoints

The checklist has two separate checkpoints, not one:

**Checkpoint A — Per-item classification (during generation, before writing each test):**
Classify the item → confirm the interaction type → verify the test being written will contain all must-have elements for that type → write the test.

**Checkpoint B — Post-generation audit (after all tests written, before Report step):**
Count complete tests vs. stubs. For every stub, verify it carries a valid skip reason from the four-item list. Any stub with an invalid reason must be reclassified and implemented before generation is declared complete. This checkpoint gates the Report step — the agent cannot reach "Report" until the audit passes. Placement in checklist: between step 10 (Patch test headers) and step 11 (Report), as step 10a.

### 7. Testids are a development standard, not a testing artifact

The skill documents this position explicitly. Testid enforcement belongs upstream: in frontend development rules, frontend agent definitions, and the verification-writer skill. The skill's position is: "for new feature development, testids should exist when this skill runs."

`testid-gaps.md` is **not deprecated**. It remains active as the retrofit backlog for existing code that predates the testid standard, and as the fallback until upstream enforcement is in place. The repositioning is: gaps on *new features* are a process failure upstream; gaps on *existing code* are expected and tracked here.

## Changes

### SKILL.md

| Location | Change |
|---|---|
| After Overview | New "Recommended Operator" paragraph — Playwright Test Writer agent caveat |
| After Auth-Aware Test Generation | New "Test Completeness Standards" section: completeness definition, valid skip reasons (4, exhaustive), stable-alternative priority order, invalid skip examples, two-checkpoint structure |
| Before Generating Tests | New "Testid Strategy" section: when testids belong in the codebase, anti-pattern, upstream ownership, `testid-gaps.md` remains active as retrofit fallback |
| Checklist step 6 | Add step 6a before writing each test: classify item by interaction type, confirm must-contain elements are present in the planned test |
| Checklist step 7 | Update wording: "Handle missing testids — exhaust stable alternative selectors first (getByRole → getByLabel → getByText for static copy → getByPlaceholder for static copy); generate `.skip()` stub only if all fail; document alternatives tried in stub comment; update testid-gaps.md" |
| "Missing data-testid handling" paragraph (under Generating Tests) | Update to reflect v3 requirement: agent must attempt stable alternatives before generating a stub; stub comment must document which alternatives were tried and why each was rejected |
| Checklist step 10 | Add step 10a after step 10 (before step 11 Report): post-generation audit — count complete tests vs. stubs, verify every stub has a valid skip reason from the four-item list, reclassify and implement any stub with an invalid reason before proceeding |
| Common Mistakes table | Add rows: stubbing file uploads, skipping API tests as backend-only, stubbing multi-step flows, not checking for newly-added testids, using missing-testid as skip for api-response/auth-boundary types, skipping without documenting alternatives tried |
| Red Flags — STOP | Add: >20% of stubs have invalid skip reasons; generation reported complete but stubs with invalid reasons exist |
| Frontmatter | Version 2.0.0 → 3.0.0 |

### references/test-generation-patterns.md

| Location | Change |
|---|---|
| After Item-to-Test Mapping | New "Interaction Classification" section: 7 types, trigger words, must-contain checklists, state-cascade vs. multi-step tiebreaker rule |
| After Interaction Classification | New "Testid Requirement by Type" clarification: api-response and auth-boundary rarely need testids; stable-alternative order before claiming missing |
| Existing API-VERIFICATION-FLAG section | Add composition rules for how API-VERIFICATION-FLAG and api-response interaction type compose |
| Missing testid stub template | Update stub comment format to require documentation of which stable alternative selectors were tried and why each was rejected |

## Interaction Types (classification system)

| Type | Trigger words | Must contain |
|---|---|---|
| `ui-navigation` | navigate, click link, redirect, see page | `goto`, assert target element visible or URL correct |
| `form-input` | enter, fill, submit, validate, error | fill all relevant fields → trigger submit → assert success or error element visible |
| `file-upload` | upload, attach, select file, import | locate file input → provide test file from `.test-assets/` if available → trigger upload → wait for completion → assert result state |
| `api-response` | response includes, API returns, endpoint returns, status code | `page.request` call → status code assertion → body field assertions (key fields, not full shape) |
| `state-cascade` | changes when, clears when, updates when, dependent on | trigger action on same page → assert each affected field/element in sequence. If trigger is on a different page from assertions, reclassify as `multi-step-workflow`. |
| `multi-step-workflow` | then, after, next step, workflow, process, cross-page; also form submission that navigates to a different page | each step executed in order → intermediate state asserted → final state asserted |
| `auth-boundary` | cannot access, redirected, 403, unauthorized, role required | attempt access without auth or with wrong role → assert redirect target or blocked state |

## Version Rationale

3.0.0 is correct. The primary breaking change is the mandatory classification step: v2 agents went directly from verification item to test generation; v3 requires classification first, establishing a completeness contract per item before any code is written. A v2 agent cannot satisfy v3 compliance because it skips this step entirely — it's not a matter of producing non-compliant stubs, it's a structurally different generation process. Secondary breaking changes: four valid skip reasons replace the previously open-ended list, and the post-generation audit is a new mandatory step with no v2 equivalent.

## Out of Scope

- Playwright interaction pattern catalog (belongs in Playwright Test Writer agent definition)
- Changes to `sync-tests.js`, `check-versions.js`, or manifest schema
- Changes to hook templates or tier configuration
- Verification-writer skill changes (separate skill, separate ownership)
- Frontend agent definition (being written separately by the user)
- Deprecation of `testid-gaps.md` (remains active as retrofit fallback)
