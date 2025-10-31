# Phase 3: Content Insertion with Comment Preservation

**Date:** 2025-10-31
**Status:** Ready to implement
**Prerequisites:** Phase 1 ✅ Phase 2 ✅ Comment preservation strategy verified ✅

## Overview

Phase 3 implements intelligent content insertion that:
1. **Detects** existing comments before insertion
2. **Calculates** safe insertion points that avoid disrupting comments
3. **Preserves** comments using the verified insert-then-delete strategy
4. **Warns** users when operations might affect commented text

## Verified Comment Preservation Strategy

From `COMMENT_PRESERVATION_VERIFIED.md`, we have proven that comments survive when:

1. **Insert new text WITHIN the commented range**
2. **Delete surrounding text AFTER insertion**
3. **Comment transfers to new text**

### Working Example

```python
# Original: "Todo application addressing"
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^ (comment attached)
# Goal: Replace with "making the comment"

requests = [
    # Step 1: Insert within range
    {'insertText': {
        'location': {'index': position_inside_comment},
        'text': 'making the comment '
    }},

    # Step 2: Delete text after insertion
    {'deleteContentRange': {
        'range': {
            'startIndex': after_insertion,
            'endIndex': end_of_comment + len(new_text)
        }
    }},

    # Step 3: Delete text before insertion
    {'deleteContentRange': {
        'range': {
            'startIndex': start_of_comment,
            'endIndex': position_inside_comment
        }
    }}
]
```

**Result:** ✅ Comment survived and transferred to new text

## Phase 3 Architecture

### New Component: `scripts/content_inserter.py`

```python
class ContentInserter:
    """Handles intelligent content insertion with comment awareness."""

    def __init__(self, editor: GoogleDocsEditor):
        self.editor = editor
        self.comment_manager = editor.comment_manager

    # Core Methods
    def find_commented_ranges(self, doc_id: str) -> List[CommentedRange]
    def calculate_insertion_point(self, doc_id: str, section_name: str, strategy: str)
    def insert_content(self, doc_id: str, index: int, content: str, preserve_comments: bool)
    def merge_content(self, doc_url: str, content: str, section: str, options: MergeOptions)
```

### Data Structures

```python
@dataclass
class CommentedRange:
    """A range of text that has a comment attached."""
    start_index: int
    end_index: int
    comment_id: str
    comment_content: str
    anchor_text: str

@dataclass
class InsertionPoint:
    """A calculated position for content insertion."""
    index: int
    section_name: Optional[str]
    safe: bool  # True if no comments will be affected
    affected_comments: List[str]  # Comment IDs that might be affected
    strategy: str  # 'before', 'after', 'within', 'new_section'

@dataclass
class MergeOptions:
    """Options for content merging."""
    preserve_comments: bool = True  # Default: conservative
    comment_strategy: str = 'preserve'  # 'preserve', 'update', 'ask'
    add_source_comment: bool = True  # Add "Added from meeting..." comment
    source_description: Optional[str] = None  # e.g., "meeting on 2025-10-31"
```

## Implementation Tasks

### Task 1: Comment Range Detection
**File:** `scripts/content_inserter.py`

```python
def find_commented_ranges(self, doc_id: str) -> List[CommentedRange]:
    """
    Find all text ranges that have comments attached.

    Returns list of CommentedRange objects with exact start/end indices.
    """
    # 1. Get document structure
    doc = self.editor.get_document(doc_id)

    # 2. Get all comments
    comments = self.comment_manager.get_comments(doc_id)

    # 3. For each comment, find its position in document
    #    - Parse comment.quotedFileContent.value (the anchor text)
    #    - Search document content for exact match
    #    - Calculate startIndex and endIndex

    # 4. Return list of CommentedRange objects
```

**Why important:** Must know where comments exist before calculating insertion points.

### Task 2: Safe Insertion Point Calculator
**File:** `scripts/content_inserter.py`

```python
def calculate_insertion_point(
    self,
    doc_id: str,
    section_name: Optional[str] = None,
    strategy: str = 'safe'
) -> InsertionPoint:
    """
    Calculate optimal insertion point that avoids disrupting comments.

    Strategies:
    - 'safe': Insert before/after sections, avoid commented areas
    - 'update': Can insert within commented ranges using preservation strategy
    - 'ask': Return options and let user decide
    """
    # 1. Parse document structure
    analysis = self.editor.analyze_document(doc_id)

    # 2. Get commented ranges
    commented_ranges = self.find_commented_ranges(doc_id)

    # 3. Find section if specified
    if section_name:
        section_start, section_end = self._find_section_boundaries(
            analysis, section_name
        )

    # 4. Calculate insertion index
    # Safe strategy: Insert at section end, after any comments
    # Update strategy: Can insert within section, using preservation if needed

    # 5. Check if any comments will be affected
    affected = self._check_affected_comments(
        insertion_index, commented_ranges
    )

    # 6. Return InsertionPoint with metadata
```

**Why important:** Prevents accidental comment disruption.

### Task 3: Comment-Preserving Insertion
**File:** `scripts/content_inserter.py`

```python
def insert_content(
    self,
    doc_id: str,
    index: int,
    content: str,
    commented_range: Optional[CommentedRange] = None
) -> bool:
    """
    Insert content at specified index, preserving comment if in range.

    If commented_range provided, uses verified preservation strategy.
    Otherwise, simple insertion.
    """
    if commented_range:
        # Use verified insert-then-delete strategy
        return self._insert_with_comment_preservation(
            doc_id, index, content, commented_range
        )
    else:
        # Simple insertion
        return self._simple_insert(doc_id, index, content)

def _insert_with_comment_preservation(
    self,
    doc_id: str,
    index: int,
    new_text: str,
    commented_range: CommentedRange
) -> bool:
    """
    Uses verified strategy from test_comment_preservation.py

    1. Insert new text within commented range
    2. Delete old text after insertion
    3. Delete old text before insertion
    """
    # Build requests using exact pattern from successful test
    requests = self._build_preservation_requests(
        index, new_text, commented_range
    )

    # Execute batchUpdate
    result = self.editor.docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()

    return True
```

**Why important:** Core functionality that applies verified strategy.

### Task 4: High-Level Merge API
**File:** `scripts/content_inserter.py`

```python
def merge_content(
    self,
    doc_url: str,
    content: str,
    section: Optional[str] = None,
    options: Optional[MergeOptions] = None
) -> Dict[str, Any]:
    """
    High-level API: Merge content into document intelligently.

    This is the main entry point for the use case:
    "Merge meeting notes into Google Doc"

    Returns:
    {
        'success': bool,
        'insertion_point': InsertionPoint,
        'comments_preserved': int,
        'new_comment_id': Optional[str]  # If source comment added
    }
    """
    options = options or MergeOptions()

    # 1. Extract doc_id from URL
    doc_id = self.editor._extract_doc_id(doc_url)

    # 2. Calculate insertion point
    insertion_point = self.calculate_insertion_point(
        doc_id,
        section,
        strategy='safe' if options.preserve_comments else 'simple'
    )

    # 3. Warn user if comments affected
    if insertion_point.affected_comments and options.comment_strategy == 'ask':
        # Return info for user decision
        return {
            'success': False,
            'requires_user_decision': True,
            'affected_comments': insertion_point.affected_comments,
            'options': ['insert_before', 'insert_after', 'update_with_preservation']
        }

    # 4. Insert content
    success = self.insert_content(
        doc_id,
        insertion_point.index,
        content,
        commented_range=None  # Or commented range if updating
    )

    # 5. Add source comment (Phase 4 feature, prepared here)
    new_comment_id = None
    if options.add_source_comment and options.source_description:
        # Placeholder for Phase 4
        # Will add: "Added notes from {source_description}"
        pass

    return {
        'success': success,
        'insertion_point': insertion_point,
        'comments_preserved': len(insertion_point.affected_comments),
        'new_comment_id': new_comment_id
    }
```

**Why important:** This is the API that fulfills the user's original request!

## Testing Strategy

### Test 1: Detect Commented Ranges
```python
def test_find_commented_ranges():
    """Test that we correctly identify all commented text."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    inserter = ContentInserter(editor)
    ranges = inserter.find_commented_ranges(doc_id)

    assert len(ranges) == 1
    assert "Todo application addressing" in ranges[0].anchor_text
```

### Test 2: Safe Insertion Point
```python
def test_calculate_safe_insertion():
    """Test that insertion points avoid commented areas."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    inserter = ContentInserter(editor)
    point = inserter.calculate_insertion_point(
        doc_id,
        section="Overview",
        strategy='safe'
    )

    assert point.safe is True
    assert len(point.affected_comments) == 0
```

### Test 3: Insert Before Commented Text
```python
def test_insert_before_comment():
    """Test inserting content before a commented section."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    inserter = ContentInserter(editor)

    # Insert new paragraph before the commented sentence
    success = inserter.insert_content(
        doc_id,
        index=find_position_before_comment(),
        content="\\n**New Section Added**\\nThis was added from meeting.\\n\\n"
    )

    # Verify comment still exists and unchanged
    analysis = editor.analyze_document(doc_id)
    assert len(analysis.comments) == 1
    assert "Todo application addressing" in analysis.comments[0].anchor
```

### Test 4: Insert After Commented Text
```python
def test_insert_after_comment():
    """Test inserting content after a commented section."""
    # Similar to test 3, but insert AFTER the commented range
```

### Test 5: Update Within Comment (Preservation)
```python
def test_update_with_preservation():
    """Test updating commented text using preservation strategy."""
    doc_id = "1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI"

    inserter = ContentInserter(editor)
    commented_ranges = inserter.find_commented_ranges(doc_id)

    # Update the commented text
    success = inserter.insert_content(
        doc_id,
        index=commented_ranges[0].start_index,
        content="updated text with new content",
        commented_range=commented_ranges[0]
    )

    # Verify comment survived on new text
    analysis_after = editor.analyze_document(doc_id)
    assert len(analysis_after.comments) == 1
    assert "updated text with new content" in analysis_after.comments[0].anchor
```

### Test 6: Full Merge Workflow
```python
def test_merge_meeting_notes():
    """Test the complete merge workflow (user's primary use case)."""
    doc_url = "https://docs.google.com/document/d/1rW2_vw5GzsTIbj_5fxXLnFnJ1-htCYt__AHI0u4FZTI/edit"

    meeting_notes = """
## Meeting Notes - 2025-10-31

**Attendees:** Alice, Bob, Charlie

**Key Decisions:**
- Budget approved: $50k
- Timeline: Q1 2026
- Next meeting: 2025-11-15
"""

    inserter = ContentInserter(editor)
    result = inserter.merge_content(
        doc_url=doc_url,
        content=meeting_notes,
        section="Overview",  # Insert in Overview section
        options=MergeOptions(
            preserve_comments=True,
            add_source_comment=True,
            source_description="team meeting on 2025-10-31"
        )
    )

    assert result['success'] is True
    assert result['comments_preserved'] >= 0

    # Verify all original comments still exist
    analysis = editor.analyze_document(doc_url)
    assert len(analysis.comments) >= 1  # Original comment(s) preserved
```

## File Structure After Phase 3

```
document-skills/gdocs/
├── scripts/
│   ├── auth_manager.py         [existing]
│   ├── gdocs_editor.py         [existing]
│   ├── comment_manager.py      [existing]
│   ├── content_inserter.py     [NEW - ~400 lines]
│   └── __init__.py             [update exports]
│
├── examples/
│   ├── test_auth.py            [existing]
│   ├── read_document.py        [existing]
│   ├── read_comments.py        [existing]
│   ├── insert_content.py       [NEW - basic insertion example]
│   └── merge_meeting_notes.py  [NEW - full workflow example]
│
└── tests/
    ├── test_commented_ranges.py     [NEW]
    ├── test_insertion_points.py     [NEW]
    └── test_content_insertion.py    [NEW]
```

## Success Metrics

✅ Can detect all commented ranges in a document
✅ Can calculate safe insertion points that avoid comments
✅ Can insert content before commented sections
✅ Can insert content after commented sections
✅ Can update commented text using preservation strategy
✅ High-level `merge_content()` API works end-to-end
✅ All existing comments preserved during insertion
✅ User can merge meeting notes without manual intervention

## Known Limitations

### Current Design Decisions
- **Default strategy:** Conservative (insert around comments)
- **No automatic text replacement:** Phase 3 focuses on insertion, not replacement
- **Section detection:** Basic header-based section finding
- **No formatting intelligence yet:** Plain text insertion (Phase 5)

### Deferred to Phase 4
- Creating new comments with context
- Replying to existing comments
- "Added from meeting on..." automated comments

### Deferred to Phase 5
- Matching existing document formatting
- Smart styling during insertion
- Rich text formatting preservation

## API Preview

Here's what the final Phase 3 API will look like:

```python
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions

# Initialize
editor = GoogleDocsEditor()
inserter = ContentInserter(editor)

# User's primary use case: Merge meeting notes
result = inserter.merge_content(
    doc_url="https://docs.google.com/document/d/ABC123/edit",
    content=meeting_notes_text,
    section="Project Updates",  # Optional: target section
    options=MergeOptions(
        preserve_comments=True,      # Default: safe
        comment_strategy='preserve',  # 'preserve', 'update', 'ask'
        add_source_comment=True,     # Phase 4 feature (prepared)
        source_description="team meeting on 2025-10-31"
    )
)

print(f"Success: {result['success']}")
print(f"Inserted at: {result['insertion_point'].section_name}")
print(f"Comments preserved: {result['comments_preserved']}")
```

## Ready to Implement

All prerequisites complete:
- ✅ OAuth authentication working
- ✅ Document reading working
- ✅ Comment reading working
- ✅ Comment preservation strategy verified
- ✅ Test infrastructure in place

**Estimated Time:** 3-4 hours
**Risk Level:** Low (strategy proven)
**User Value:** HIGH (enables primary use case!)

Let's build Phase 3! 🚀
