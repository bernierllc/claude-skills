# Phase 4: Comment Creation & Management

**Date:** 2025-10-31
**Status:** Ready to implement
**Prerequisites:** Phase 1 ✅ Phase 2 ✅ Phase 3 ✅

## Overview

Phase 4 adds the ability to **create** and **reply to** comments programmatically, enabling full collaborative editing workflows. This transforms the skill from "read and insert" to "intelligent collaborative editing."

## User Value

### Before Phase 4
```python
# Can merge content, but no way to explain what changed
result = inserter.merge_content(doc_url, meeting_notes)
# User has to manually add comment: "Added from meeting on 2025-10-31"
```

### After Phase 4
```python
# Automatically adds contextual comment
result = inserter.merge_content(
    doc_url,
    meeting_notes,
    options=MergeOptions(
        add_source_comment=True,
        source_description="team meeting on 2025-10-31"
    )
)
# → Creates comment: "📝 Added from team meeting on 2025-10-31"
```

## Google Drive API Comment Creation

### API Endpoint
```
POST https://www.googleapis.com/drive/v3/files/{fileId}/comments
```

### Request Body
```json
{
  "content": "This is a comment",
  "anchor": "{\"type\":\"text\",\"r\":\"document/1234\",\"a\":[{\"t\":\"text\",\"s\":10,\"e\":20}]}"
}
```

### Key Fields

**`content`** (string, required)
- The plain text content of the comment
- Example: "Added from team meeting on 2025-10-31"

**`anchor`** (JSON string, required for text selection)
- Defines what text the comment is attached to
- Format: `{"type":"text","r":"document/{doc_id}","a":[{"t":"text","s":START,"e":END}]}`
- `s`: Start character index
- `e`: End character index

### Reply to Comment

```
POST https://www.googleapis.com/drive/v3/files/{fileId}/comments/{commentId}/replies
```

```json
{
  "content": "Acknowledged and updated"
}
```

## Phase 4 Architecture

### Enhanced CommentManager

**New Methods:**
```python
class CommentManager:
    # [Existing methods from Phase 2]
    def get_comments(...) -> List[Comment]

    # [NEW - Phase 4 methods]
    def create_comment(
        self,
        doc_id: str,
        content: str,
        start_index: int,
        end_index: int
    ) -> str:
        """
        Create a new comment on a text range.

        Returns:
            Comment ID of created comment
        """

    def reply_to_comment(
        self,
        doc_id: str,
        comment_id: str,
        content: str
    ) -> str:
        """
        Reply to an existing comment.

        Returns:
            Reply ID
        """

    def resolve_comment(
        self,
        doc_id: str,
        comment_id: str
    ) -> bool:
        """
        Mark a comment as resolved.
        """

    def _build_anchor_json(
        self,
        doc_id: str,
        start_index: int,
        end_index: int
    ) -> str:
        """
        Build the anchor JSON string for text selection.
        """
```

### Enhanced ContentInserter

**Updated merge_content:**
```python
def merge_content(
    self,
    doc_url: str,
    content: str,
    section: Optional[str] = None,
    options: Optional[MergeOptions] = None
) -> Dict[str, Any]:
    """
    [Existing insertion logic]

    # NEW - Phase 4: Add source comment
    if options.add_source_comment and options.source_description:
        # Calculate range of newly inserted content
        new_content_start = insertion_point.index
        new_content_end = insertion_point.index + len(formatted_content)

        # Create comment on the inserted content
        comment_text = f"📝 Added from {options.source_description}"
        new_comment_id = self.editor.comment_manager.create_comment(
            doc_id=doc_id,
            content=comment_text,
            start_index=new_content_start,
            end_index=new_content_end
        )

    return {
        'success': True,
        'new_comment_id': new_comment_id,  # NOW POPULATED!
        ...
    }
```

### New High-Level APIs

**Update and Reply:**
```python
class GoogleDocsEditor:
    def update_commented_text_and_reply(
        self,
        doc_url: str,
        comment_id: str,
        new_text: str,
        reply_content: str
    ) -> Dict[str, Any]:
        """
        Update text that has a comment + reply to the comment.

        Use case: Responding to feedback by updating text and explaining.
        """
```

**Batch Comment on Sections:**
```python
class ContentInserter:
    def add_contextual_comments(
        self,
        doc_url: str,
        comments: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Add multiple contextual comments to a document.

        Args:
            comments: [
                {
                    'text_to_find': 'Budget: $30k',
                    'comment': 'Updated from meeting decision'
                },
                ...
            ]

        Returns:
            {
                'created': [comment_id, ...],
                'failed': [error_msg, ...]
            }
        """
```

## Implementation Tasks

### Task 1: Implement create_comment
**File:** `scripts/comment_manager.py`

```python
def create_comment(
    self,
    doc_id: str,
    content: str,
    start_index: int,
    end_index: int
) -> str:
    """
    Create a new comment on a text range.

    Args:
        doc_id: Google Doc ID
        content: Comment text
        start_index: Start character index
        end_index: End character index

    Returns:
        Comment ID of created comment

    Raises:
        HttpError: If API call fails
    """
    try:
        # Build anchor JSON
        anchor_json = self._build_anchor_json(doc_id, start_index, end_index)

        # Create comment via Drive API
        comment_body = {
            'content': content,
            'anchor': anchor_json
        }

        result = self.drive_service.comments().create(
            fileId=doc_id,
            body=comment_body,
            fields='id,content,author,createdTime'
        ).execute()

        return result.get('id')

    except HttpError as e:
        print(f"Error creating comment: {e}")
        raise


def _build_anchor_json(
    self,
    doc_id: str,
    start_index: int,
    end_index: int
) -> str:
    """
    Build the anchor JSON for text selection.

    Format:
    {
        "type": "text",
        "r": "document/{doc_id}",
        "a": [{
            "t": "text",
            "s": start_index,
            "e": end_index
        }]
    }
    """
    import json

    anchor = {
        "type": "text",
        "r": f"document/{doc_id}",
        "a": [{
            "t": "text",
            "s": start_index,
            "e": end_index
        }]
    }

    return json.dumps(anchor)
```

### Task 2: Implement reply_to_comment
**File:** `scripts/comment_manager.py`

```python
def reply_to_comment(
    self,
    doc_id: str,
    comment_id: str,
    content: str
) -> str:
    """
    Reply to an existing comment.

    Args:
        doc_id: Google Doc ID
        comment_id: ID of comment to reply to
        content: Reply text

    Returns:
        Reply ID

    Raises:
        HttpError: If API call fails
    """
    try:
        reply_body = {
            'content': content
        }

        result = self.drive_service.replies().create(
            fileId=doc_id,
            commentId=comment_id,
            body=reply_body,
            fields='id,content,author,createdTime'
        ).execute()

        return result.get('id')

    except HttpError as e:
        print(f"Error replying to comment: {e}")
        raise
```

### Task 3: Implement resolve_comment
**File:** `scripts/comment_manager.py`

```python
def resolve_comment(
    self,
    doc_id: str,
    comment_id: str
) -> bool:
    """
    Mark a comment as resolved.

    Args:
        doc_id: Google Doc ID
        comment_id: ID of comment to resolve

    Returns:
        True if successful
    """
    try:
        self.drive_service.comments().update(
            fileId=doc_id,
            commentId=comment_id,
            body={'resolved': True}
        ).execute()

        return True

    except HttpError as e:
        print(f"Error resolving comment: {e}")
        return False
```

### Task 4: Integrate into merge_content
**File:** `scripts/content_inserter.py`

```python
def merge_content(
    self,
    doc_url: str,
    content: str,
    section: Optional[str] = None,
    options: Optional[MergeOptions] = None
) -> Dict[str, Any]:
    """[Existing implementation]"""

    # [... existing insertion logic ...]

    # NEW - Phase 4: Add source comment
    new_comment_id = None
    if success and options.add_source_comment and options.source_description:
        try:
            # Calculate range of inserted content
            # Note: Need to account for formatting added by _format_content_for_insertion
            formatted_content = self._format_content_for_insertion(content)
            content_start = insertion_point.index
            content_end = insertion_point.index + len(formatted_content)

            # Create comment
            comment_text = f"📝 Added from {options.source_description}"
            new_comment_id = self.editor.comment_manager.create_comment(
                doc_id=doc_id,
                content=comment_text,
                start_index=content_start,
                end_index=content_end
            )

        except Exception as e:
            # Don't fail entire operation if comment creation fails
            print(f"Warning: Could not create source comment: {e}")

    return {
        'success': success,
        'insertion_point': insertion_point,
        'comments_preserved': len(insertion_point.affected_comments),
        'new_comment_id': new_comment_id,  # NOW POPULATED!
        'message': f'Content inserted successfully. {insertion_point.reason}'
    }
```

### Task 5: Add high-level update_and_reply API
**File:** `scripts/gdocs_editor.py`

```python
def update_commented_text_and_reply(
    self,
    doc_url: str,
    comment_id: str,
    new_text: str,
    reply_content: str
) -> Dict[str, Any]:
    """
    Update text that has a comment + reply to the comment.

    This combines:
    1. Finding the commented text
    2. Replacing it (using preservation strategy)
    3. Replying to the comment

    Use case: Responding to review feedback programmatically

    Args:
        doc_url: Google Doc URL or ID
        comment_id: ID of comment to respond to
        new_text: New text to replace commented text
        reply_content: Reply message for the comment

    Returns:
        {
            'success': bool,
            'comment_preserved': bool,
            'reply_id': str,
            'message': str
        }
    """
    self._ensure_authenticated()
    doc_id = self.extract_doc_id(doc_url)

    try:
        # Get the comment to find its location
        comments = self.comment_manager.get_comments(doc_id)
        target_comment = next(
            (c for c in comments if c.comment_id == comment_id),
            None
        )

        if not target_comment:
            return {
                'success': False,
                'message': f'Comment {comment_id} not found'
            }

        # Use ContentInserter to update text with preservation
        from .content_inserter import ContentInserter, CommentedRange

        inserter = ContentInserter(self)

        # Build CommentedRange from comment
        # [Implementation would need to find exact indices]

        # Update text (preserves comment)
        # [Implementation would use insert_with_comment_preservation]

        # Reply to comment
        reply_id = self.comment_manager.reply_to_comment(
            doc_id=doc_id,
            comment_id=comment_id,
            content=reply_content
        )

        return {
            'success': True,
            'comment_preserved': True,
            'reply_id': reply_id,
            'message': 'Text updated and reply added'
        }

    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }
```

## Testing Strategy

### Test 1: Create Comment on New Content
```python
def test_create_comment_on_insertion():
    """Test creating a comment on newly inserted content."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    # Insert content with source comment
    result = inserter.merge_content(
        doc_url=doc_id,
        content="\\n## Test Section\\nThis is test content.\\n",
        options=MergeOptions(
            add_source_comment=True,
            source_description="automated test on 2025-10-31"
        )
    )

    assert result['success'] is True
    assert result['new_comment_id'] is not None

    # Verify comment exists
    comments = editor.comment_manager.get_comments(doc_id)
    new_comment = next(
        (c for c in comments if c.comment_id == result['new_comment_id']),
        None
    )

    assert new_comment is not None
    assert "automated test" in new_comment.content
```

### Test 2: Reply to Existing Comment
```python
def test_reply_to_comment():
    """Test replying to an existing comment."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    # Get first comment
    comments = editor.comment_manager.get_comments(doc_id)
    assert len(comments) > 0

    comment_id = comments[0].comment_id

    # Reply to it
    reply_id = editor.comment_manager.reply_to_comment(
        doc_id=doc_id,
        comment_id=comment_id,
        content="This has been addressed in the latest update"
    )

    assert reply_id is not None

    # Verify reply appears
    comments_after = editor.comment_manager.get_comments(doc_id)
    comment_with_reply = next(
        (c for c in comments_after if c.comment_id == comment_id),
        None
    )

    assert len(comment_with_reply.replies) > 0
```

### Test 3: Update Text and Reply
```python
def test_update_and_reply():
    """Test updating commented text while replying."""
    doc_url = "https://docs.google.com/document/d/ABC123/edit"

    result = editor.update_commented_text_and_reply(
        doc_url=doc_url,
        comment_id="COMMENT_ID",
        new_text="Budget approved: $50k",
        reply_content="Updated per team meeting decision"
    )

    assert result['success'] is True
    assert result['comment_preserved'] is True
    assert result['reply_id'] is not None
```

### Test 4: Resolve Comment
```python
def test_resolve_comment():
    """Test marking a comment as resolved."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    # Get an unresolved comment
    comments = editor.comment_manager.get_comments(doc_id, include_resolved=False)
    assert len(comments) > 0

    comment_id = comments[0].comment_id

    # Resolve it
    success = editor.comment_manager.resolve_comment(doc_id, comment_id)
    assert success is True

    # Verify it's resolved
    all_comments = editor.comment_manager.get_comments(doc_id, include_resolved=True)
    resolved_comment = next(
        (c for c in all_comments if c.comment_id == comment_id),
        None
    )

    assert resolved_comment.resolved is True
```

## Example Scripts

### Example 1: Merge with Source Comment
**File:** `examples/merge_with_comments.py`

```python
#!/usr/bin/env python3
"""Example: Merge content and add source comment."""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions
from datetime import datetime

editor = GoogleDocsEditor()
inserter = ContentInserter(editor)

meeting_notes = """
## Meeting Notes - 2025-10-31
...
"""

result = inserter.merge_content(
    doc_url="DOC_URL",
    content=meeting_notes,
    options=MergeOptions(
        preserve_comments=True,
        add_source_comment=True,
        source_description=f"team meeting on {datetime.now().strftime('%Y-%m-%d')}"
    )
)

print(f"✅ Content merged")
print(f"   Comment ID: {result['new_comment_id']}")
```

### Example 2: Reply to Comments
**File:** `examples/reply_to_comments.py`

```python
#!/usr/bin/env python3
"""Example: Reply to all unresolved comments."""

from scripts.gdocs_editor import GoogleDocsEditor

editor = GoogleDocsEditor()
doc_id = "DOC_ID"

# Get unresolved comments
comments = editor.comment_manager.get_comments(doc_id, include_resolved=False)

for comment in comments:
    if "needs update" in comment.content.lower():
        # Reply
        editor.comment_manager.reply_to_comment(
            doc_id=doc_id,
            comment_id=comment.comment_id,
            content="Updated in latest revision"
        )

        # Resolve
        editor.comment_manager.resolve_comment(doc_id, comment.comment_id)

print(f"✅ Replied to {len(comments)} comment(s)")
```

## Success Metrics

✅ Can create comments on text ranges
✅ Can reply to existing comments
✅ Can resolve comments
✅ Source comments automatically added during merge
✅ Comment creation integrated into workflow
✅ Update-and-reply workflow working
✅ All tests passing

## User Value Summary

### Collaborative Editing Workflows Enabled

**Workflow 1: Meeting Notes with Context**
```python
# Before Phase 4: Manual comment needed
# After Phase 4: Automatic source tracking
result = inserter.merge_content(..., options=MergeOptions(
    add_source_comment=True,
    source_description="team meeting on 2025-10-31"
))
# → Comment created: "📝 Added from team meeting on 2025-10-31"
```

**Workflow 2: Respond to Feedback**
```python
# Someone comments: "This budget needs updating"
# Phase 4 enables programmatic response:
editor.update_commented_text_and_reply(
    doc_url=doc_url,
    comment_id=comment_id,
    new_text="Budget: $50k",
    reply_content="Updated per team meeting"
)
# → Text updated, comment preserved, reply added
```

**Workflow 3: Batch Processing**
```python
# Process all review comments
for comment in unresolved_comments:
    if needs_update(comment):
        editor.update_commented_text_and_reply(...)
    else:
        editor.comment_manager.reply_to_comment(...)
        editor.comment_manager.resolve_comment(...)
```

## Ready to Implement

All prerequisites complete:
- ✅ Can read documents (Phase 1)
- ✅ Can read comments (Phase 2)
- ✅ Can insert content preserving comments (Phase 3)
- ✅ OAuth scope includes Drive API (`drive`)
- ✅ Drive API service initialized

**Estimated Time:** 2-3 hours
**Risk Level:** Medium (new API territory)
**User Value:** VERY HIGH (enables full collaboration)

Let's build Phase 4! 🚀
