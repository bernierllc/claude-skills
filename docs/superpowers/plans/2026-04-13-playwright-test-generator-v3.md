# playwright-test-generator v3.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `playwright-test-generator` from v2.0.0 to v3.0.0 by adding an interaction classification system, enforcing test completeness with explicit valid/invalid skip reasons, documenting testid strategy, and adding an agent recommendation caveat.

**Architecture:** Two markdown files are edited — `SKILL.md` and `references/test-generation-patterns.md`. No scripts, no code, no tests to run. The "verification" step for each task is a self-review that confirms the written content is complete, internally consistent, and matches the approved spec at `docs/superpowers/specs/2026-04-13-playwright-test-generator-v3-design.md`.

**Tech Stack:** Markdown only. No toolchain. SKILL.md frontmatter version must be bumped in the same commit as all other changes.

---

## File Map

| File | What changes |
|---|---|
| `playwright-test-generator/SKILL.md` | Frontmatter version bump; new Recommended Operator section; new Testid Strategy section; new Test Completeness Standards section; checklist steps 6a, 7 update, 10a; Common Mistakes additions; Red Flags additions; "Missing data-testid handling" paragraph update |
| `playwright-test-generator/references/test-generation-patterns.md` | New Interaction Classification section; new Testid Requirement by Type section; API-VERIFICATION-FLAG composition rules; updated stub template |

---

## Task 1: SKILL.md — Frontmatter version bump + Recommended Operator caveat

**Files:**
- Modify: `playwright-test-generator/SKILL.md` (frontmatter + after Overview section)

- [ ] **Step 1: Bump frontmatter version**

In `SKILL.md`, change the frontmatter `version` field:

```
version: 2.0.0
```
→
```
version: 3.0.0
```

Also update the `description` field to reference v3.0.0:

```
description: Convert verification docs to Playwright tests incrementally. Read verification checklists from docs/verification/, diff against a manifest, and produce or patch Playwright .spec.ts files. Support incremental updates, test pinning, missing data-testid tracking, hook-driven automation, auth-aware test generation, version-tracked derivative metadata, interaction classification, and completeness enforcement. Use when setting up automated regression testing from verification docs, when verification docs change, or when the pending-generation queue has items.
```

- [ ] **Step 2: Add Recommended Operator section after Overview**

After the Overview section (the paragraph ending "...Verification tests are derived artifacts — translate, do not author."), insert:

```markdown
## Recommended Operator

This skill is best operated by the **Playwright Test Writer** agent (`playwright-test-writer`) or another agent with deep Playwright expertise. Agents without Playwright-specific knowledge will produce complete tests for simple interactions but may default to stubs for complex ones.

Place the agent definition in `.claude/agents/` (project-level) or `~/.claude/agents/` (user-level) following Claude standards.
```

- [ ] **Step 3: Self-review**

Confirm:
- Frontmatter version reads `3.0.0`
- Description mentions "interaction classification" and "completeness enforcement"
- Recommended Operator section appears between Overview and Document Ownership Model
- No other section content was accidentally changed

---

## Task 2: SKILL.md — Testid Strategy section

**Files:**
- Modify: `playwright-test-generator/SKILL.md` (new section before Generating Tests)

- [ ] **Step 1: Insert Testid Strategy section before "Generating Tests"**

Insert the following section immediately before the `## Generating Tests` heading:

```markdown
## Testid Strategy

### When testids belong in the codebase

Testids are a **development artifact, not a testing artifact**. They should be added when a component is built, not retroactively when tests fail. The standard: every interactive element, dynamic state container, and structural landmark gets a `data-testid` as part of component development — the same way accessible `aria-label` attributes are required on icon buttons.

**Elements that always need a testid:**
- Every interactive element (buttons, inputs, selects, file inputs, links that trigger behavior)
- Every element that displays dynamic state (error messages, success banners, empty states, loading indicators, count badges, status fields)
- Structural landmarks (sidebar, header, main content area, modal container, form containers)

**Elements that do not need a testid:**
- Static decorative elements (icons, dividers, static copy)
- Elements reliably targetable by stable accessible role + name (e.g., a labeled `<button>Submit</button>` is targetable via `getByRole('button', { name: 'Submit' })`)

### The anti-pattern this skill must not reinforce

Generating stubs and treating "testid will be added later" as an acceptable holding state. Stubs accumulate. The correct path when a testid is missing: exhaust stable alternative selectors first (see Test Completeness Standards), generate a `.skip()` stub only if all alternatives fail, document which alternatives were tried, and record the gap in `testid-gaps.md`.

### Upstream ownership

Testid enforcement belongs upstream in the workflow:
- **Frontend development rules** (CLAUDE.md, cursor rules) — require testids as part of "done" for any component
- **Frontend agent definitions** — agents that write components must add testids to all interactive and state-displaying elements before declaring a component complete
- **verification-writer skill** — may note expected testids alongside verification items

**This skill's position:** for new feature development, testids should already exist when this skill runs. `testid-gaps.md` is not deprecated — it remains active as the retrofit backlog for existing code that predates the testid standard, and as the fallback until upstream enforcement is fully in place. Gaps on *new features* are an upstream process failure. Gaps on *existing code* are expected and tracked here.
```

- [ ] **Step 2: Self-review**

Confirm:
- Section appears between Derivative Metadata Docs (or the section immediately preceding Generating Tests) and Generating Tests
- "testid-gaps.md is not deprecated" is explicit
- Upstream ownership lists three owners
- No existing section heading was altered

---

## Task 3: SKILL.md — Test Completeness Standards section

**Files:**
- Modify: `playwright-test-generator/SKILL.md` (new section after Auth-Aware Test Generation)

- [ ] **Step 1: Insert Test Completeness Standards section after "Auth-Aware Test Generation"**

Insert the following section immediately after the `## Auth-Aware Test Generation` section (after the auth strategy table):

```markdown
## Test Completeness Standards

### What "complete" means

A complete test executes the full interaction described in the verification item, asserts the expected outcome, and runs without `.skip()`. A stub is only acceptable when a specific infrastructure blocker prevents execution.

### Valid skip reasons (exhaustive — exactly four)

Only these four reasons justify a `.skip()` stub:

1. **`auth.ready = false`** in the metadata doc — the auth helper for the required user type is not implemented
2. **`data_setup.ready = false`** in the metadata doc — the seed/fixture infrastructure to create required test data is not implemented. "Requires test data setup" is never a skip reason on its own — only the metadata flag is.
3. **Testid genuinely missing AND no stable alternative selector exists** — see stable alternative priority order below. **Not applicable to `api-response` or `auth-boundary` types**, which use `page.request` or navigation assertions and require no DOM selector. Claiming missing testid as a skip reason for these types is a misclassification.
4. **Item explicitly marked `manual-only`** in the verification doc

### Invalid skip reasons — these are interaction types, not blockers

| This is NOT a valid skip reason | What to do instead |
|---|---|
| "Multi-step interaction" | Classify as `multi-step-workflow`, implement each step |
| "Involves file upload" | Classify as `file-upload`, use `setInputFiles` |
| "Requires waiting for API response / network" | Use `waitForResponse` or `page.request` |
| "API-level test / backend-only" | Classify as `api-response`, use `page.request` |
| "Complex workflow" | Classify by type, implement the steps |
| "Requires test data setup" | Check `data_setup.ready` in metadata — if true, implement setup in `beforeEach` |
| "Too many steps" | Not a skip reason under any circumstance |
| "Involves navigation between pages" | Classify as `multi-step-workflow` |

### Stable alternative selector order (for skip reason 3)

Before claiming a testid is missing and no alternative exists, attempt these in order:

1. `getByRole` with an accessible name — e.g., `getByRole('button', { name: 'Upload' })`
2. `getByLabel` — for form controls with an associated visible label
3. `getByText` — **only for static UI copy** (button labels, column headers, field labels, section titles). **Not valid for dynamic data values** (status strings, counts, user-generated content, locale-sensitive strings). If the text changes based on data, this selector is not stable.
4. `getByPlaceholder` — **only for static placeholder text**, not programmatically-set values

Only if all applicable options are exhausted is the element untargetable without a testid. See `references/test-generation-patterns.md` for the required stub comment format.

### Two completeness checkpoints

**Checkpoint A — Per-item classification (before writing each test):**
Classify the verification item by interaction type. Confirm the test will contain all must-have elements for that type. Then write the test. See `references/test-generation-patterns.md` for the classification system.

**Checkpoint B — Post-generation audit (gates the Report step):**
After all tests are written, before declaring generation complete:
1. Count complete tests vs. stubs
2. For every stub, verify it carries one of the four valid skip reasons above
3. Any stub with an invalid reason must be reclassified and implemented
4. Only after every stub has a valid reason may the Report step proceed
```

- [ ] **Step 2: Self-review**

Confirm:
- Section appears after Auth-Aware Test Generation and before Testid Strategy (or Generating Tests if Testid Strategy is not yet inserted — check ordering after both tasks are done)
- All four valid skip reasons are present and numbered
- Invalid skip table has at least 8 rows
- Checkpoint A and Checkpoint B are both present
- "Not applicable to api-response or auth-boundary types" is present on skip reason 3

---

## Task 4: SKILL.md — Update checklist (steps 6a, 7, 10a)

**Files:**
- Modify: `playwright-test-generator/SKILL.md` (Checklist section)

- [ ] **Step 1: Add step 6a after step 6**

Find the checklist step:
```
6. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
```

Change it to:
```
6. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
7. **6a. Classify before writing each test** — for each verification item, classify it by interaction type (see `references/test-generation-patterns.md`), confirm the planned test contains all must-have elements for that type, then write the test (Checkpoint A)
```

Wait — the existing checklist uses numbers 1-11. Insert 6a as a sub-step. Replace step 6 with:

```
6. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
   - **6a. Before writing each test:** classify the verification item by interaction type (see `references/test-generation-patterns.md`), confirm the planned test will contain all must-have elements for that type, then write the test (Checkpoint A — see Test Completeness Standards)
```

- [ ] **Step 2: Update step 7**

Find the checklist step:
```
7. **Handle missing testids** — generate `.skip()` stubs, update `testid-gaps.md`
```

Replace with:
```
7. **Handle missing testids** — exhaust stable alternative selectors first (`getByRole` → `getByLabel` → `getByText` for static copy → `getByPlaceholder` for static copy); generate `.skip()` stub only if all fail and only for types that require DOM selectors (not `api-response` or `auth-boundary`); document alternatives tried in stub comment (see stub template in `references/test-generation-patterns.md`); update `testid-gaps.md`
```

- [ ] **Step 3: Add step 10a after step 10**

Find the checklist step:
```
10. **Patch test headers** — for `header-missing` items, add `@source` and `@metadata` comments to existing test files
```

Insert a new step after it:
```
10. **Patch test headers** — for `header-missing` items, add `@source` and `@metadata` comments to existing test files
   - **10a. Post-generation audit (Checkpoint B — gates step 11):** count complete tests vs. stubs; for every stub verify it carries one of the four valid skip reasons from Test Completeness Standards; reclassify and implement any stub with an invalid reason; do not proceed to step 11 until every stub has a valid reason
```

- [ ] **Step 4: Self-review**

Confirm:
- Step 6 now has a 6a sub-item mentioning "Checkpoint A"
- Step 7 mentions exhausting stable alternatives before generating a stub
- Step 10 now has a 10a sub-item mentioning "Checkpoint B — gates step 11"
- Step 11 (Report) is still present and unchanged

---

## Task 5: SKILL.md — Update "Missing data-testid handling" paragraph + Common Mistakes + Red Flags

**Files:**
- Modify: `playwright-test-generator/SKILL.md` (three locations)

- [ ] **Step 1: Update "Missing data-testid handling" paragraph**

Find the section under Generating Tests:
```
### Missing data-testid handling

On initial runs, many testids will be missing. This is expected and welcomed — the skill surfaces this as a work list.

- Items with missing testids get a test stub with `.skip()` and a TODO comment
```

Replace that paragraph with:
```
### Missing data-testid handling

On initial runs against existing code, some testids may be missing. This is a tracked gap, not a blanket skip reason.

Before generating a skip stub for a missing testid:
1. Confirm the item's interaction type requires DOM selectors (`api-response` and `auth-boundary` often do not)
2. Attempt stable alternative selectors in order: `getByRole` → `getByLabel` → `getByText` (static copy only) → `getByPlaceholder` (static copy only)
3. Only if all applicable alternatives fail, generate a `.skip()` stub
4. The stub comment MUST document which alternatives were tried and why each was rejected (see stub template in `references/test-generation-patterns.md`)
```

Keep the rest of the section (the gap logging and `testid-gaps.md` format) unchanged.

- [ ] **Step 2: Add rows to Common Mistakes table**

Find the `## Common Mistakes` section and add these rows to the existing table:

```
| Stubbing a `file-upload` item as "too complex" | `file-upload` is an interaction type, not a skip reason — locate the file input, use `setInputFiles`, trigger upload, wait for completion signal, assert result |
| Skipping API response items as "backend-only" | Classify as `api-response` and use `page.request` — API response assertions are Playwright tests |
| Stubbing `multi-step-workflow` items | Multi-step is an interaction type, not a skip reason — execute each step in sequence, assert intermediate and final states |
| Generating a testid-missing stub without trying stable alternatives | Try `getByRole`, `getByLabel`, `getByText` (static only), `getByPlaceholder` (static only) before generating a stub; document what was tried |
| Claiming "missing testid" for `api-response` or `auth-boundary` items | These types use `page.request` or URL/navigation assertions — they do not need DOM selectors; this is a misclassification |
| Declaring generation complete while stubs with invalid skip reasons exist | Checkpoint B (step 10a) must pass before reporting — every stub must have a valid skip reason from the four-item list |
```

- [ ] **Step 3: Add Red Flags**

Find the `## Red Flags — STOP` section and add these items to the list:

```
- More than 20% of generated tests are stubs with invalid skip reasons — the classification system is being bypassed
- Declaring generation complete (step 11 Report) while any stub has an invalid skip reason — Checkpoint B must pass first
```

- [ ] **Step 4: Self-review**

Confirm:
- "Missing data-testid handling" paragraph now describes the alternatives-first approach
- Common Mistakes table has 6 new rows covering file-upload, API tests, multi-step, alternatives-not-tried, api-response/auth-boundary misclassification, incomplete audit
- Red Flags section has 2 new items

---

## Task 6: test-generation-patterns.md — Interaction Classification section

**Files:**
- Modify: `playwright-test-generator/references/test-generation-patterns.md`

- [ ] **Step 1: Insert Interaction Classification section after Item-to-Test Mapping**

After the `## Item-to-Test Mapping` section (after the code example and before `## Tag Format`), insert:

```markdown
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
```

- [ ] **Step 2: Self-review**

Confirm:
- Section is positioned after Item-to-Test Mapping and before Tag Format
- Table has exactly 7 rows
- Both tiebreaker rules have examples
- "add type as a comment inside the test function" instruction is present

---

## Task 7: test-generation-patterns.md — Testid Requirement by Type + API-VERIFICATION-FLAG composition + stub template

**Files:**
- Modify: `playwright-test-generator/references/test-generation-patterns.md`

- [ ] **Step 1: Insert Testid Requirement by Type section after Interaction Classification**

Insert immediately after the Interaction Classification section (before `## Tag Format`):

```markdown
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
```

- [ ] **Step 2: Add API-VERIFICATION-FLAG composition rules**

Find the existing `### API-VERIFICATION-FLAG annotations` section. At the end of that section (after the existing content), append:

```markdown
### Composition with `api-response` interaction type

When an item carries an `API-VERIFICATION-FLAG` annotation, use this table to determine how classification and the annotation compose:

| Annotation state | Classification | What to generate |
|---|---|---|
| `*API-only*` tag + `durability: permanent` | `api-response` | `page.request` test against the endpoint |
| `*API-only*` tag + `durability: temporary` | `api-response` for now | `page.request` test; record in `testid-gaps.md`: "UI may eventually exist — reclassify when UI is added" |
| `API-VERIFICATION-FLAG` present, no `*API-only*` tag | Driven by item text | Generate test for resolved type; embed `endpoint` as code comment regardless: `// API ref: POST /events/create`. Ignore `durability` unless type resolves to `api-response`. |
| No annotation, item text matches `api-response` triggers | `api-response` | `page.request` test; no durability consideration |
```

- [ ] **Step 3: Update the missing testid stub template**

Find the existing stub template under `## Missing Testid Handling`:

```typescript
// @begin:EVT-FRM-SD-01
test.skip('@EVT-FRM-SD-01 @deep @admin-event-form state cascade on type change',
  async ({ page }) => {
    // TODO: Missing data-testid for: event-type-select, flyer-uploader-field
    // Add data-testid attributes to the components, then remove .skip()
  });
// @end:EVT-FRM-SD-01
```

Replace it with:

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

Also update the surrounding prose in that section to match. Replace:
```
- Items with missing testids get a test stub with `.skip()` and a TODO comment:
```
With:
```
- Items with missing testids get a test stub with `.skip()` only after stable alternatives are exhausted. The stub MUST include: the skip reason number, the interaction classification, which alternatives were tried and why each failed, and the TODO to add the testid:
```

A stub with skip reason 3 that omits the "Alternatives tried" block fails the Checkpoint B audit.

- [ ] **Step 4: Self-review**

Confirm:
- Testid Requirement by Type table has 7 rows with `api-response` and `auth-boundary` marked "No" / "Rarely"
- API-VERIFICATION-FLAG composition table has 4 rows covering all cases
- Stub template includes "SKIP REASON", "Classification", "Alternatives tried" block, and "TODO"
- Prose above stub template mentions exhausting alternatives first

---

## Task 8: Final pass + commit

**Files:**
- Modify: both `SKILL.md` and `references/test-generation-patterns.md` (review only, no new content)

- [ ] **Step 1: Verify the Changes table from the spec is fully consumed**

Open `docs/superpowers/specs/2026-04-13-playwright-test-generator-v3-design.md` and go through the Changes tables for both files. Verify every row maps to a specific edit that exists in the modified files. Check:

SKILL.md changes table (9 rows):
- [ ] After Overview: Recommended Operator paragraph present
- [ ] After Auth-Aware Test Generation: Test Completeness Standards section present
- [ ] Before Generating Tests: Testid Strategy section present
- [ ] Checklist step 6: step 6a sub-item present mentioning Checkpoint A
- [ ] Checklist step 7: updated wording (stable alternatives, document tried)
- [ ] "Missing data-testid handling" paragraph: updated to require alternatives-first
- [ ] Checklist step 10: step 10a sub-item present mentioning Checkpoint B, gating step 11
- [ ] Common Mistakes: 6 new rows present
- [ ] Red Flags: 2 new items present
- [ ] Frontmatter: version reads 3.0.0

test-generation-patterns.md changes table (4 rows):
- [ ] After Item-to-Test Mapping: Interaction Classification section present with 7-type table and tiebreaker rules
- [ ] After Interaction Classification: Testid Requirement by Type section present
- [ ] API-VERIFICATION-FLAG section: composition table appended
- [ ] Stub template: updated with SKIP REASON, Classification, Alternatives tried, TODO

- [ ] **Step 2: Verify section ordering in SKILL.md**

The section order should be:
1. Overview
2. Recommended Operator ← new
3. Document Ownership Model
4. Execution Model
5. Entry Points
6. Checklist
7. Generated Test Structure
8. Derivative Metadata Docs
9. Test File Headers
10. Auth-Aware Test Generation
11. Test Completeness Standards ← new
12. Testid Strategy ← new
13. Generating Tests
14. Version Check Script
15. Tiered Test Execution
16. Cross-Skill Integration
17. Common Mistakes
18. Red Flags — STOP

- [ ] **Step 3: Commit**

```bash
git add playwright-test-generator/SKILL.md playwright-test-generator/references/test-generation-patterns.md
git commit -m "feat(playwright-test-generator): v3.0.0 — interaction classification and completeness enforcement

- add interaction classification system (7 types, must-contain checklists, tiebreaker rules)
- add test completeness standards with 4 valid skip reasons (exhaustive, closed list)
- add testid strategy section with upstream ownership model
- add recommended operator caveat (Playwright Test Writer agent)
- add checkpoint A (per-item classification) and checkpoint B (post-generation audit)
- update checklist steps 6a, 7, 10a
- update missing-testid stub template to require alternatives-tried documentation
- add api-verification-flag composition rules for api-response type
- add testid requirement by type clarification
- update common mistakes and red flags

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Spec reference

Full approved spec: `docs/superpowers/specs/2026-04-13-playwright-test-generator-v3-design.md`
