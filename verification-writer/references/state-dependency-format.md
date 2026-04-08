# State Dependency Annotation Format Reference

Layer 3e produces `<!-- STATE-DEPENDENCY -->` annotations on verification items that test cross-field state dependencies in forms. These annotations carry the analysis context from verification-writer (which reads the code) to playwright-test-generator (which produces executable tests).

## Annotation Syntax

```markdown
- [ ] [deep] **EVT-FRM-SD-01** Add promoter, set as flyer uploader,
  then change event type to Private --- Promoter-dependent flyer config
  is cleared or form prevents submission. *Expected: success*
<!-- STATE-DEPENDENCY:
  trigger: eventType field change to non-music type
  affected_fields: [flyer_uploader_id, responsibility_person_id]
  expected_cascade: [clear flyer_uploader_id, clear responsibility selections, hide artist/promoter sections]
  code_ref: EventForm.tsx:useEffect watching eventType
  failure_mode: FK constraint violation if stale ID submitted
-->
```

## Annotation Fields

### `trigger`

**What it captures:** The field change or user action that initiates the state cascade.

**Format:** `<field_name> field change to <value or condition>`. Be specific about the value or condition --- "eventType field change to non-music type" is better than "eventType changes."

**How playwright-test-generator consumes it:** Becomes the **setup** action in the test. The generator fills or selects the trigger value as the first interaction after any prerequisite state is established.

### `affected_fields`

**What it captures:** All fields whose state depends on the trigger. Listed as an array of field identifiers matching the form's field names or IDs.

**Format:** `[field_name_1, field_name_2, ...]`. Use the field names from the form schema or DOM, not display labels.

**How playwright-test-generator consumes it:** Each affected field becomes an **assertion target**. The generator creates `expect` statements checking each field's state after the trigger fires.

### `expected_cascade`

**What it captures:** The ordered sequence of state changes that should occur when the trigger fires. Each entry describes a single expected change to a specific field or section.

**Format:** `[action field_or_section, action field_or_section, ...]`. Actions are verbs: `clear`, `hide`, `disable`, `revalidate`, `reset to default`, `update options`.

**How playwright-test-generator consumes it:** Becomes **ordered `expect` statements** in the test. The generator asserts each cascade step in the listed order, which matters when one cascade step depends on a prior one completing (e.g., "hide section" must happen before "clear field within section" can be verified).

### `code_ref`

**What it captures:** The file and the specific hook, effect, or handler that implements the dependency. This is a code-reading artifact --- it tells maintainers where to look when a test fails.

**Format:** `<FileName>:<hook or function name>`. E.g., `EventForm.tsx:useEffect watching eventType` or `useEventForm.ts:resetDependentFields()`.

**How playwright-test-generator consumes it:** Embedded as a **comment** in the generated test file, linking the test to its source logic. Not used for assertion generation.

### `failure_mode`

**What it captures:** What goes wrong in production if the cascade does not fire correctly. This is the "why this test matters" field --- it explains the consequence of the dependency being broken.

**Format:** Plain language description of the failure. Common patterns:
- `FK constraint violation if stale ID submitted`
- `Orphaned records in junction table`
- `Silent data corruption --- hidden field value included in payload`
- `UI inconsistency --- cleared field re-appears on next render`
- `Validation bypass --- required field hidden but value still empty in state`

**How playwright-test-generator consumes it:** Determines the **assertion strategy**. FK/data corruption failure modes produce strict assertions (fail immediately). UI inconsistency failure modes produce softer assertions (screenshot comparison, visual diff).

## Severity Elevation Rule

Most state dependency items default to `[deep]` --- they test field combinations and state transitions that go beyond standard happy-path verification.

**Elevation to `[standard]`:** When the `failure_mode` indicates one of these consequences, elevate the item to `[standard]`:
- FK constraint violation (database rejects the submission)
- Data corruption (invalid data is silently persisted)
- Orphaned records (junction table entries reference deleted entities)
- Security bypass (hidden field allows unauthorized data modification)

These are not edge cases --- they are data integrity failures that affect production users. A form that submits a stale foreign key reference will cause a server error or corrupt data on every occurrence, not just under unusual conditions.

**Items that stay `[deep]`:**
- UI inconsistency (field flickers, section briefly visible then hidden)
- State desync that self-corrects on next render
- Cosmetic issues (wrong placeholder after cascade)

## Relationship to Existing Annotations

### `<!-- BUSINESS-CONTEXT -->`

Business context annotations (from Layer 3d) describe what a displayed value *should be* based on business rules. State dependency annotations describe what should *happen to related fields* when a field changes. They are complementary:

- A countdown timer gets a `BUSINESS-CONTEXT` annotation explaining the 72-hour rule
- A form section that hides when event type changes gets a `STATE-DEPENDENCY` annotation explaining the cascade

An item can have both annotations if a computed value is also part of a state dependency chain (e.g., a calculated total that should update when a dependent field is cleared).

### `<!-- API-VERIFICATION-FLAG -->`

API verification flags mark items that can only be tested via API. State dependency items are always browser-testable (they involve form interactions), so `API-VERIFICATION-FLAG` and `STATE-DEPENDENCY` should not appear on the same item. If a state dependency can only be verified by inspecting the API payload (not observable in the UI), the item should instruct the verifier to check the network request body --- it is still a browser interaction, not an API-only test.

## Item ID Convention

State dependency items use the suffix `-SD-` in their ID to distinguish them from other form items:

```
{PAGE-ABBREV}-FRM-SD-{NUMBER}
```

Examples: `EVT-FRM-SD-01`, `USR-FRM-SD-03`, `MLK-FRM-SD-01`

This makes it easy to filter for all state dependency items across verification docs (grep for `-SD-`).
