# Comment Preservation Strategy for Google Docs

## How Google Docs Comments Work

Comments in Google Docs are anchored to a **range of text** (not specific character positions). This has important implications for content insertion.

## Comment Survival Rules

A comment will survive as long as **ANY text from the original highlighted range remains**.

### Rule 1: Keep Original Text
If any part of the originally highlighted text survives, the comment persists.

**Example:**
```
Original: "Budget approved: $30k"
          └─ Comment: "Needs update"

After edit: "Budget approved: $50k"
            └─ Comment SURVIVES (some original text remains)
```

### Rule 2: Insert Within Highlight
You can insert NEW text within the highlighted range, then delete surrounding text, and the comment will anchor to whatever remains.

**Example:**
```
Original: "The budget is $30k for this project"
          └─ Comment: "Check with finance"

Step 1 - Insert: "The budget is $50k updated in Q4 meeting for this project"
                 └─ Comment still there

Step 2 - Delete surrounding: "$50k updated in Q4 meeting"
                              └─ Comment SURVIVES on new text!
```

### Rule 3: Delete Everything = Comment Lost
If you delete ALL text from the highlighted range, the comment is lost.

**Example:**
```
Original: "Budget: $30k"
          └─ Comment: "Update this"

After complete deletion: [empty]
                         └─ Comment LOST ❌
```

## Implications for Phase 3-4 Implementation

### Strategy A: Conservative (Preserve Original)
**When to use:** You want to keep existing context intact

**Approach:**
1. Read document and identify commented sections
2. Insert new content AROUND commented text (before/after)
3. Keep original commented text unchanged
4. Add new comment explaining the addition

**Example - Meeting Notes Addition:**
```
Original:
"## Q4 Goals
Budget: $30k"
└─ Comment: "Pending approval"

After insertion:
"## Q4 Goals
Budget: $30k
└─ Comment: "Pending approval" (PRESERVED)

**Meeting Notes from 2025-10-31:**
- Budget approved at $50k
- Timeline: Q1 2026"
└─ New comment: "Added from team meeting on 2025-10-31"
```

### Strategy B: Aggressive (Update Within Highlight)
**When to use:** You want to update the commented content itself

**Approach:**
1. Identify commented text range
2. Insert new content within that range
3. Optionally delete surrounding old text
4. Comment survives on new content

**Example - Budget Update:**
```
Original:
"Budget approved: $30k"
└─ Comment: "Needs revision"

Step 1 - Insert within highlight:
"Budget approved: $50k (updated from $30k)"
└─ Comment: "Needs revision" (still there!)

Step 2 - Clean up:
"Budget approved: $50k"
└─ Comment: "Needs revision" (PRESERVED on new amount!)
```

## Implementation Considerations for Phase 3

### Comment-Aware Insertion
When inserting content, we should:

1. **Check for comments** in insertion area
2. **Ask user** which strategy to use:
   - Preserve original + add nearby
   - Update within comment range
3. **Calculate safe insertion points**:
   - Before commented range
   - After commented range
   - Within commented range (if updating)

### API Design Proposal

```python
# Phase 3 API concept
editor.merge_content(
    doc_url="DOC_URL",
    content="Meeting notes...",
    section="Budget",

    # Comment preservation strategy
    preserve_comments=True,  # Default: be conservative

    # Options:
    # - "preserve": Insert around commented text
    # - "update": Insert within commented ranges
    # - "ask": Prompt user when comments detected
    comment_strategy="preserve"
)
```

### Phase 4 Enhancement

When we can CREATE comments, we can be even smarter:

```python
result = editor.merge_content(
    doc_url="DOC_URL",
    content="Updated budget: $50k",
    section="Budget",

    # Update commented text AND add explanation
    comment_strategy="update",
    add_comment=True,
    comment_text="Updated from team meeting on 2025-10-31. Old value: $30k"
)

# Result:
# - Original comment: "Needs revision" (PRESERVED)
# - New comment: "Updated from team meeting..." (ADDED)
# - Both comments on same text!
```

## Real-World Scenarios

### Scenario 1: Meeting Notes Addition
**Goal:** Add meeting notes without disrupting discussions

**Strategy:** Preserve (insert around)

```python
# Original doc has comments throughout
analysis = editor.analyze_document('DOC_URL')

print(f"Found {len(analysis.comments)} existing comments")
# → "Found 5 existing comments"

# Add meeting notes in new section (preserves all comments)
editor.merge_content(
    doc_url='DOC_URL',
    content=meeting_notes,
    section="Meeting Notes",
    preserve_comments=True  # Safe insertion
)
```

### Scenario 2: Budget Update
**Goal:** Update a specific value that has a comment

**Strategy:** Update within highlight

```python
# Find the commented budget line
analysis = editor.analyze_document('DOC_URL')

budget_comment = next(
    c for c in analysis.comments
    if "$30k" in c.anchor
)

print(f"Comment on budget: {budget_comment.content}")
# → "Comment on budget: Needs revision"

# Update the budget value WITHIN the commented text
editor.update_commented_text(
    doc_url='DOC_URL',
    comment_id=budget_comment.comment_id,
    new_text="Budget approved: $50k",
    preserve_comment=True  # Keep comment on new value
)

# Comment survives on "$50k"!
```

### Scenario 3: Responding to Comments
**Goal:** Address a comment by updating the text it references

**Strategy:** Update within + reply

```python
for comment in analysis.comments:
    if "needs revision" in comment.content.lower():
        # Update the text
        editor.update_commented_text(
            doc_url='DOC_URL',
            comment_id=comment.comment_id,
            new_text=f"[Updated: {new_value}]",
            preserve_comment=True
        )

        # Reply to the comment
        editor.reply_to_comment(
            doc_url='DOC_URL',
            comment_id=comment.comment_id,
            content="Updated based on Q4 meeting decision"
        )
```

## Testing Strategy

### Test Cases for Phase 3

1. **Insert before commented text**
   - Verify comment survives
   - Verify anchor text unchanged

2. **Insert after commented text**
   - Verify comment survives
   - Verify anchor text unchanged

3. **Insert within commented range**
   - Verify comment survives
   - Verify anchor includes new text

4. **Delete part of commented text**
   - Verify comment survives on remaining text
   - Verify anchor text updated

5. **Replace all commented text**
   - This is the tricky one!
   - Must insert new text BEFORE deleting old
   - Verify comment transfers to new text

## Key Takeaway

The **order of operations matters**:

❌ **WRONG (comment lost):**
```
1. Delete old text
2. Insert new text
   → Comment lost because all original text gone!
```

✅ **CORRECT (comment preserved):**
```
1. Insert new text within highlighted range
2. Delete old surrounding text
   → Comment survives on new text!
```

## Implementation Priority

**Phase 3:**
- Focus on Strategy A (preserve - insert around)
- Safe, conservative, preserves all context

**Phase 4:**
- Add Strategy B (update within)
- Requires more sophisticated range manipulation
- But enables powerful update workflows

## Questions for Phase 3 Implementation

1. Should we detect comments automatically and warn user?
2. Should we default to "safe" insertion (avoid commented areas)?
3. Should we provide a "dry run" showing where insertion will happen?
4. Should we show which comments might be affected?

All of these questions can be addressed as we build Phase 3!

---

**This understanding is CRITICAL for building a truly useful Google Docs editing tool!** 🎯
