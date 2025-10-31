# Attribution Approach for Google Docs Skill

**Date:** 2025-10-31
**Status:** Implemented and Production-Ready

## The Challenge

When synthesizing meeting notes into Google Docs, we want to clearly attribute which content came from which source. Ideally, we would:

1. Insert synthesized content
2. Create a comment **highlighting that specific text**
3. Comment content: "Synthesized from meeting with Alex Rivera (10/31/25)"

This would make it immediately clear which parts of the document were synthesized vs. original.

## What We Tried

### Attempt 1: Text-Range Comments via API

```python
# What we wanted to do
comment_body = {
    'content': 'Synthesized from meeting...',
    'anchor': {
        'r': 'kix.abc123',  # Text range reference
        'text': 'Recent customer research...'  # Anchor text
    }
}
```

**Result:** ❌ Does not work

**Research findings:**
- Google Drive API documentation mentions `anchor` field for comments
- Stack Overflow confirms: anchor field **only works for PDFs and images**
- For Google Docs, comments created via API are **always document-level**
- No workaround available via API

**Source:** [Stack Overflow - Google Drive API Comments](https://stackoverflow.com/questions/tagged/google-drive-api+comments)

### Attempt 2: Apps Script Workaround

**Consideration:** Use Google Apps Script to create text-range comments

**Why we didn't pursue:**
- Adds complexity (separate Apps Script deployment)
- Requires additional OAuth scopes
- Users would need to deploy script to their account
- Not worth the overhead for marginal improvement

## What We Implemented: Document-Level Attribution

### Current Approach

```python
# After inserting synthesized content
comment_id = editor.comment_manager.create_comment(
    doc_id=doc_id,
    content="📊 Enhanced with insights from customer feedback (10/31/25)"
)
```

**Result:**
- ✅ Comment appears in document comments panel
- ✅ Links to document (not specific text range)
- ✅ Provides timestamp and source attribution
- ✅ Reliable and works every time
- ✅ Users can manually highlight text and add comment if desired

### Example Attribution Comments

**Format:** `📊 [Action] from [Source] ([Date])`

**Examples:**
```
📊 Enhanced with insights from customer feedback (10/31/25)
📝 Added from team meeting on product roadmap (11/01/25)
🔍 Updated based on user research session (10/28/25)
💡 Synthesized from Q4 planning discussion (11/02/25)
```

**What We Include:**
- Emoji indicator (📊 for synthesis, 📝 for addition, etc.)
- Action verb (Enhanced, Added, Updated, Synthesized)
- Source description (meeting name, research session, etc.)
- Date in short format (MM/DD/YY)

**Optional additions:**
- Section name: "Synthesized content at Market Analysis section"
- Attendees: "Meeting with Alex Rivera"
- Link to full notes: "Full notes: [link]"

## Comparison: API vs Manual

### Document-Level Comment (API) - Current Approach

**Pros:**
- ✅ Automated (no user action needed)
- ✅ Always works reliably
- ✅ Provides clear source attribution
- ✅ Shows up in comments panel
- ✅ Can be reviewed/resolved/discussed

**Cons:**
- ❌ Doesn't highlight specific text
- ❌ User must infer which content was synthesized

### Text-Range Comment (Manual) - Optional User Step

**Pros:**
- ✅ Highlights exactly which text was synthesized
- ✅ Visual indicator in document
- ✅ Can be done by user after merge

**Cons:**
- ❌ Requires manual action
- ❌ Extra step after automation
- ❌ User might forget to do it

## Recommended Workflow

### Base Workflow (Always)
```
1. Claude analyzes document and notes
2. Claude synthesizes content
3. Claude shows preview to user
4. User approves
5. System executes:
   - Insert synthesized content
   - Set NORMAL_TEXT formatting
   - Create document-level attribution comment ← WE DO THIS
6. Result: Professional integration with source tracking
```

### Optional Enhancement (User Choice)
```
7. User manually adds text-range comment:
   - Open Google Doc
   - Select synthesized text
   - Right-click → Comment
   - Add: "Synthesized from [source]"
```

**When to do manual step:**
- Document has multiple contributors who need clarity
- Legal/compliance requires explicit attribution
- User prefers visual highlighting

**When to skip manual step:**
- Personal documents
- Team already knows about merge
- Version history is sufficient

## Decision Rationale

### Why We Chose Document-Level Comments

1. **Reliability:** Works 100% of the time via API
2. **Automation:** No manual steps required
3. **Sufficient:** Provides source tracking for most use cases
4. **Simple:** One approach, easy to understand
5. **Maintainable:** No complex workarounds to maintain

### Alternative We Rejected

**Inline Text Styling for Attribution**
- Could use text color/highlighting to mark synthesized content
- **Rejected because:** Changes document appearance, not presentation-ready

**Footnotes/Endnotes**
- Could add footnote markers
- **Rejected because:** Clutters document, academic style not appropriate

**Separate Attribution Section**
- Could maintain "Sources" section listing all merges
- **Rejected because:** Disconnects attribution from content

## Implementation Details

### Comment Creation Code

```python
# In content_inserter.py
if options.add_source_comment and options.source_description:
    comment_text = f"📝 Added from {options.source_description}"
    new_comment_id = self.editor.comment_manager.create_comment(
        doc_id=doc_id,
        content=comment_text
    )
```

### MergeOptions Configuration

```python
options = MergeOptions(
    preserve_comments=True,        # Keep existing comments
    add_source_comment=True,       # Create attribution comment
    source_description="meeting on 2025-10-31",  # Source info
)
```

### Comment Manager Method

```python
def create_comment(self, doc_id: str, content: str) -> str:
    """
    Create a new document-level comment.

    Args:
        doc_id: Google Doc ID
        content: Comment text

    Returns:
        Comment ID

    Note: Comments created via API are document-level only.
          Cannot create text-range comments reliably via API.
    """
    comment_body = {
        'content': content
    }

    result = self.drive_service.comments().create(
        fileId=doc_id,
        body=comment_body,
        fields='id,content,author,createdTime'
    ).execute()

    return result.get('id')
```

## User Communication

### What to Tell Users

**In documentation:**
> "Source attribution is provided via document-level comments. After merging,
> you'll see a comment in the document's comment panel citing the source and
> date. If you want to highlight the specific text that was synthesized, you
> can manually select it and add a comment."

**In conversation:**
```
Claude: "I've merged the content and added a comment citing the source. The
comment appears in the document's comment panel. If you'd like to highlight
the specific text that was synthesized, you can select it and add a comment
yourself."
```

### Setting Expectations

**What we do automatically:**
- ✅ Insert synthesized content
- ✅ Set proper formatting
- ✅ Create attribution comment (document-level)
- ✅ Preserve existing comments

**What requires manual action (optional):**
- Highlight specific text with comment (if desired)

## Future Possibilities

### If Google API Changes

If Google ever adds reliable text-range comment support to the Docs API:

1. **Detection:** Check API documentation and test
2. **Implementation:** Update `CommentManager.create_comment()` to accept range parameters
3. **Migration:** Existing code would continue to work (document-level fallback)
4. **Enhancement:** New code could use text-range when available

**Code would look like:**
```python
def create_comment_on_range(
    self,
    doc_id: str,
    content: str,
    start_index: int,
    end_index: int
) -> str:
    """
    Create comment on specific text range.
    Note: Only works if Google API adds support.
    """
    # Implementation here
```

## Testing

### How to Verify Attribution Works

1. Run merge with `add_source_comment=True`
2. Open Google Doc
3. Click comments panel (💬 icon)
4. Verify comment exists with correct content
5. Click comment → Should show creation time and author

### Test Cases Covered

- ✅ Create comment after insertion
- ✅ Comment content matches source description
- ✅ Comment appears in document
- ✅ Multiple merges create multiple comments
- ✅ Comments don't interfere with content

## Summary

**Current State:** Document-level attribution via comments

**Pros:**
- Reliable automation
- Clear source tracking
- Works in all scenarios
- No user intervention needed

**Cons:**
- Doesn't highlight specific text
- Users must infer which content was synthesized

**Recommendation:** Ship with current approach. It provides 90% of the value with 100% reliability.

**Optional Enhancement:** Document that users can manually add text-range comments if needed.

**Future:** Monitor Google API updates for text-range comment support.

---

**Status:** ✅ Production-Ready
**Implementation:** Complete
**User Impact:** Minimal (most won't need text-range highlighting)
**Maintainability:** Simple and reliable
