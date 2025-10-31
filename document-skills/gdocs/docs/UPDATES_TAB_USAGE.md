# Updates Tab - User Interaction Pattern

This document describes how Claude (in conversation) should interact with users when the updates tab feature is active.

## When to Prompt

Claude should prompt the user about the updates tab on the **first content merge** to a document in the session, IF:
1. No updates tab/section is detected in the document
2. User hasn't been asked yet this session

Use `ContentInserter._should_prompt_for_updates(doc_id)` to check.

## Prompt Format

When prompting is needed, Claude should ask:

```
Would you like me to create an Updates tab to track changes to this document?

Options:
1. Yes, prepend new updates (newest first) - Most common for changelogs
2. Yes, append new updates (newest last) - Chronological order
3. No, don't track updates
```

## Handling User Response

Store the response in session state:

**Option 1 (Prepend):**
```python
inserter._set_document_state(doc_id, {
    'prepend': True,
    'asked_user': True,
    'user_wants_updates': True
})
```

**Option 2 (Append):**
```python
inserter._set_document_state(doc_id, {
    'prepend': False,
    'asked_user': True,
    'user_wants_updates': True
})
```

**Option 3 (No tracking):**
```python
inserter._set_document_state(doc_id, {
    'asked_user': True,
    'user_wants_updates': False
})
```

## Existing Updates Detection

If `_check_existing_updates()` finds an updates location:
- Skip the user prompt entirely
- Detect pattern automatically
- Log updates following the existing pattern

## Logging Updates

After successful `merge_content()`:

```python
if state.get('user_wants_updates', False):
    from datetime import datetime
    from scripts.updates_structures import UpdateInfo

    info = UpdateInfo(
        date=datetime.now(),
        summary="Brief description of changes",
        sections_modified=[options.target_section or "Document"],
        source_attribution=options.source_description or "content merge"
    )

    location = state.get('location')  # or create new
    prepend = state.get('prepend', True)

    inserter.updates_manager.log_update(doc_id, location, info, prepend)
```

## Example Workflows

### First Update (No Existing Updates)

```
Claude: "This is the first update to this document. Would you like me to
         create an Updates tab?"

User: "Yes, prepend"

Claude: "✓ Content merged
         ✓ Update logged to new Updates section"
```

### First Update (Existing Updates Found)

```
Claude: "I found an existing 'Update Log' section. I'll automatically
         log updates there following your established pattern (newest first).

         ✓ Content merged
         ✓ Update logged to Update Log"
```

### Subsequent Updates

```
Claude: "✓ Content merged
         ✓ Update logged to Updates section"
```
