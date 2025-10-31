# Updates Tab Feature Design

**Date:** 2025-10-31
**Status:** Approved for implementation

## Overview

Add automatic update logging to the gdocs skill. When users merge content into Google Docs, the skill will maintain an "Updates" tab or section that tracks what was changed, when, and where.

## User Experience

### First Update to a Document (in session)

When Claude performs the first content merge to a document in a session:

1. **Before merging**, Claude asks the user (in conversation):
   ```
   "Would you like me to create an Updates tab to track changes to this document?
   - Yes, prepend new updates (newest first)
   - Yes, append new updates (newest last)
   - No, don't track updates"
   ```

2. User's choice is remembered for this document **for the current session only**

3. After merging content, Claude automatically logs the update

### Subsequent Updates (same session)

- No questions asked
- Updates logged automatically based on previous choice
- Pattern is followed consistently

### Existing Updates/Changelog Detection

If the document already has an updates tab or section:
- **Skip the user question** entirely
- Detect the existing pattern (prepend vs append)
- Match the existing formatting
- Log updates automatically

## Detection Logic

### Two Detection Mechanisms

**Priority 1: Google Docs Tabs**
- Check for tab named (case-insensitive):
  - "Updates"
  - "Update Log"
  - "Changelog"
  - "Change Log"
  - "Revision History"

**Priority 2: Last Header in Document**
- Check **only the last heading** in the document
- Match against same patterns as above
- Updates are always at the end, never in the middle

### Pattern Analysis (3-entry sample)

When updates location exists with 3+ entries:

1. **Extract first 3 entries** after header/tab
2. **Parse dates** from each entry
   - Supported formats: MM/DD/YYYY, YYYY-MM-DD, "October 31, 2025", etc.
3. **Determine order**:
   - `entry1_date > entry2_date > entry3_date` → **prepend** (newest first)
   - `entry1_date < entry2_date < entry3_date` → **append** (newest last)
4. **Extract formatting** from first entry:
   - Date format and style (bold/italic/plain)
   - Bullet style (dash, asterisk, numbered, none)
   - Indentation level
   - Text styles for different components

### Edge Cases

- **No dates found**: Use first 3 non-empty lines, default to prepend
- **Fewer than 3 entries**: Analyze what exists, default to prepend
- **Mixed date formats**: Parse each format separately, fall back gracefully
- **Empty updates section**: Treat as new, use default template

## Update Entry Format

Each update entry contains:

1. **Date of update** - Today's date when merge occurred
2. **Summary of changes** - Brief description of what was added/modified
3. **Section(s) modified** - Which sections of the document were updated
4. **Source attribution** - Where content came from (e.g., "meeting on 2025-10-31")

### Default Template (for new updates sections)

```
**October 31, 2025**
- Summary: Added market research insights to Market Analysis section
- Sections modified: Market Analysis
- Source: Customer feedback meeting on 10/31/25
```

### Format Matching (for existing updates sections)

When an updates section exists, replicate its exact formatting:
- Copy date format and styling
- Copy bullet/numbering style
- Copy text hierarchy (bold, italic, plain)
- Copy indentation patterns
- Maintain visual consistency

## Architecture

### Core Components

**1. UpdatesTabManager** (new class)
```python
class UpdatesTabManager:
    def __init__(self, editor: GoogleDocsEditor):
        self.editor = editor

    def detect_updates_location(self, doc_id: str) -> Optional[UpdatesLocation]
        """Check for tabs first, then last header"""

    def analyze_pattern(self, doc_id: str, location: UpdatesLocation) -> UpdatesPattern
        """Extract prepend/append and formatting from 3 entries"""

    def create_updates_section(self, doc_id: str, prepend: bool) -> UpdatesLocation
        """Create new updates tab or section"""

    def log_update(self, doc_id: str, update_info: UpdateInfo) -> bool
        """Add update entry following detected/configured pattern"""
```

**2. Session State Tracking** (in-memory dictionary)
```python
_document_state = {
    'doc_id_123': {
        'has_updates_tab': True,
        'prepend': True,
        'asked_user': True,
        'location_type': 'tab'  # or 'header'
    }
}
```

**3. Enhanced ContentInserter.merge_content()**

Modified workflow:
```python
def merge_content(self, doc_url, content, section=None, options=None):
    doc_id = extract_doc_id(doc_url)

    # NEW: Before merging content
    if not self._is_first_update_handled(doc_id):
        self._handle_first_update_prompt(doc_id)

    # EXISTING: Merge content
    result = self._perform_merge(doc_id, content, section, options)

    # NEW: After merging content
    if self._should_log_update(doc_id):
        self._log_update_entry(doc_id, result, options)

    return result
```

### Integration with Existing Workflow

The feature integrates seamlessly into the current interactive workflow:

**Current workflow:**
1. User provides notes and doc URL
2. Claude reads documents
3. Claude proposes synthesis with preview
4. User approves
5. Claude inserts content + adds attribution comment

**Enhanced workflow:**
1. User provides notes and doc URL
2. Claude reads documents
3. **[NEW]** Claude checks if first update to this doc
4. **[NEW]** If first update: Ask user about updates tab preference
5. Claude proposes synthesis with preview
6. User approves
7. Claude inserts content + adds attribution comment
8. **[NEW]** Claude logs update to updates tab/section

## Data Structures

```python
@dataclass
class UpdatesLocation:
    location_type: str  # 'tab' or 'header'
    tab_id: Optional[str]  # If tab
    header_index: Optional[int]  # If header
    header_text: str

@dataclass
class UpdatesPattern:
    prepend: bool  # True = newest first, False = newest last
    format_template: FormatTemplate

@dataclass
class FormatTemplate:
    date_format: str  # e.g., "**MMMM DD, YYYY**"
    date_style: Dict  # {bold: True, italic: False}
    bullet_style: Optional[str]  # '-', '*', '1.', None
    entry_components: List[ComponentStyle]

@dataclass
class ComponentStyle:
    prefix: str  # 'Summary:', 'Sections:', 'Source:'
    style: Dict  # text formatting

@dataclass
class UpdateInfo:
    date: datetime
    summary: str
    sections_modified: List[str]
    source_attribution: str
```

## Implementation Tasks

See implementation plan (to be created in Phase 6).

## Success Criteria

1. **First update prompt works**
   - User is asked on first update to new document
   - Choice is remembered for session
   - No duplicate questions

2. **Existing updates detected**
   - Both tabs and headers recognized
   - Pattern correctly identified (prepend vs append)
   - Formatting matched accurately

3. **Update logging works**
   - Entries contain all 4 required fields
   - Formatting matches existing entries
   - Updates appear in correct order
   - No disruption to existing content

4. **Edge cases handled**
   - Empty updates sections
   - Unparseable dates
   - Missing components
   - Multiple documents in one session

## Future Enhancements (Not in Scope)

- Persistent state across sessions (store user preferences)
- Update entry editing/deletion
- Rollback specific updates
- Bulk update summarization
- Custom update templates

## Questions Resolved

1. **When to ask?** First update only (per document, per session)
2. **Pattern detection?** First 3 entries with dates
3. **Update content?** Date, summary, sections, source
4. **Style matching?** Match existing entries if present

---

**Next Steps:** Create implementation plan and set up worktree
