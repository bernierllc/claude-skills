# Google Docs Editor Skill - Implementation Plan

**Created:** 2025-10-31
**Goal:** Build a Claude skill for intelligently editing Google Docs with contextual comments
**Priority:** High - Solves real workflow pain point

## Executive Summary

Build a skill that merges content (meeting notes, edits, updates) into Google Docs using:
- **Direct edits** that respect existing formatting and structure
- **Contextual comments** explaining what changed and why (key differentiator!)
- **Smart insertion logic** to find appropriate locations
- **Full document awareness** of existing comments and content

### Why This Approach is Better Than Track Changes
1. **Context over mechanics** - Comments explain WHY something changed, not just WHAT
2. **Collaborative narrative** - Creates conversation threads for discussion
3. **Cleaner documents** - No visual clutter, professional appearance
4. **Flexible review** - Version history + comments = best of both worlds

## API Capabilities & Limitations

### What Google Docs API CAN Do
✅ Read document structure and content
✅ Make direct edits (insert, delete, format text)
✅ Preserve all formatting and styles
✅ Read existing suggestions (view-only)
✅ Add comments and replies (via Drive API)
✅ Batch multiple changes atomically

### What Google Docs API CANNOT Do
❌ Create suggested edits programmatically
❌ Trigger "Suggesting mode" via API

**Decision:** Use direct edits + explanatory comments as a superior alternative

## Core Features

### 1. Document Reading & Analysis
```
Input: Google Docs URL or document ID
Output: Structured understanding of document

Operations:
- Fetch via documents.get(documentId)
- Parse structure: headings, sections, paragraphs, tables
- Read all existing comments via Drive API
- Identify formatting patterns and styles
- Calculate character indices for insertions
```

### 2. Intelligent Content Merging
```
Input: Content to add + context about source
Output: Content inserted at appropriate location

Operations:
- Find logical insertion points based on:
  * Section headers matching context
  * End of specific sections
  * User-specified locations
  * Smart pattern matching
- Match existing formatting (styles, fonts, lists)
- Preserve document structure
- Maintain heading hierarchy
```

### 3. Contextual Comments (Key Innovation!)
```
Input: Change metadata (source, reason, context)
Output: Helpful comments explaining the change

Comment Templates:
- Meeting notes: "Added notes from [date] meeting re: [topic]"
- Updates: "Updated section based on [source] feedback"
- New sections: "New content from [context]"
- Corrections: "Fixed based on [reason]"

Operations:
- Add comments at insertion points
- Reply to relevant existing comments
- Cross-reference related changes
- Include timestamps and attribution
```

### 4. Smart Formatting Preservation
```
Operations:
- Detect existing paragraph styles
- Match font families, sizes, colors
- Preserve bullet/numbered list formatting
- Maintain table formatting
- Keep inline formatting (bold, italic, links)
```

## Primary Use Case: Meeting Notes Workflow

### Current Pain Point
```
User has: Meeting notes (markdown/text)
User has: Existing Google Doc with structure/comments
Problem: Must download as .docx → edit → re-upload
         OR manually copy/paste and format
```

### New Workflow
```python
# Example usage
from gdocs_editor import GoogleDocsEditor

editor = GoogleDocsEditor()  # Handles OAuth on first run

# Your workflow
doc_url = "https://docs.google.com/document/d/DOC_ID/edit"
meeting_notes = """
## Discussion Points from Q4 Planning
- Decided to move forward with Feature X
- Budget approved: $50k
- Timeline: Q1 2026
- Action items: [see below]
"""

# Analyze document
analysis = editor.analyze_document(doc_url)
print(f"Found sections: {analysis.sections}")
print(f"Existing comments: {len(analysis.comments)}")
print(f"Suggested insertion point: {analysis.suggest_location('Meeting Notes')}")

# Preview changes
preview = editor.preview_merge(
    doc_url=doc_url,
    content=meeting_notes,
    source="Team meeting on 2025-10-31",
    section_name="Meeting Notes"
)
print(preview)  # Shows where content will go, what comment will say

# Apply changes
result = editor.merge_content(
    doc_url=doc_url,
    content=meeting_notes,
    source="Team meeting on 2025-10-31",
    insertion_strategy="append_to_section",
    section_name="Meeting Notes",
    add_comment=True,
    comment_text="Added notes from Team meeting on 2025-10-31 discussing Q4 planning and Feature X approval"
)

print(f"✓ Inserted {result.paragraphs_added} paragraphs at index {result.insertion_index}")
print(f"✓ Added comment: '{result.comment_text}'")
print(f"✓ Comment ID: {result.comment_id}")
print(f"✓ View document: {doc_url}")
```

### Result
- Meeting notes appear in correct section
- Formatting matches existing document style
- Comment explains what was added and when
- User can review via version history or comments
- No manual formatting needed

## Implementation Phases

### Phase 1: Authentication & Basic Reading (Days 1-2)
**Goal:** Can authenticate and read a Google Doc

Tasks:
- [ ] Set up Google Cloud project
- [ ] Enable Google Docs API and Drive API
- [ ] Configure OAuth 2.0 consent screen
- [ ] Create OAuth client credentials
- [ ] Implement OAuth flow with token storage
- [ ] Handle token refresh automatically
- [ ] Test: Successfully read a sample document
- [ ] Test: Token refresh works correctly

**Deliverables:**
- `auth_manager.py` - OAuth token management
- `credentials.json.example` - Template for setup
- `oauth_setup.md` - Step-by-step auth guide
- Working authentication flow

### Phase 2: Document Analysis (Days 2-3)
**Goal:** Can parse document structure and identify insertion points

Tasks:
- [ ] Parse documents.get JSON response
- [ ] Build document structure tree (sections, headings)
- [ ] Extract all text content
- [ ] Calculate character indices for elements
- [ ] Identify section boundaries
- [ ] Detect formatting patterns
- [ ] Read all comments via Drive API
- [ ] Associate comments with document locations
- [ ] Test: Parse complex multi-section document
- [ ] Test: Accurately identify section boundaries

**Deliverables:**
- `document_analyzer.py` - Structure parsing
- `DocumentStructure` class - Document model
- Analysis output format

### Phase 3: Content Insertion (Days 3-4)
**Goal:** Can insert content at appropriate locations

Tasks:
- [ ] Implement insertion point finder
  - By section name
  - By heading match
  - By character index
  - At document end
- [ ] Build batchUpdate request builder
- [ ] Implement InsertTextRequest
- [ ] Implement CreateParagraphBulletsRequest (for lists)
- [ ] Implement UpdateTextStyleRequest (for formatting)
- [ ] Implement InsertTableRequest (if source has tables)
- [ ] Handle formatting preservation
- [ ] Test: Insert into empty section
- [ ] Test: Insert at end of populated section
- [ ] Test: Insert with various content types
- [ ] Test: Batch updates apply atomically

**Deliverables:**
- `content_merger.py` - Insertion logic
- `BatchUpdateBuilder` class
- Insertion strategy implementations

### Phase 4: Comment Management (Days 4-5)
**Goal:** Can add contextual comments explaining changes

Tasks:
- [ ] Set up Drive API client for comments
- [ ] Implement comment creation
- [ ] Implement comment reply functionality
- [ ] Build comment templates system
- [ ] Add support for custom comment text
- [ ] Link comments to specific text ranges
- [ ] Test: Create comment on new content
- [ ] Test: Reply to existing comment
- [ ] Test: Comment appears at correct location

**Deliverables:**
- `comment_manager.py` - Comment operations
- Comment template system
- Comment association logic

### Phase 5: Formatting Intelligence (Days 5-6)
**Goal:** New content looks native to the document

Tasks:
- [ ] Detect existing paragraph styles
- [ ] Match font families and sizes
- [ ] Preserve color schemes
- [ ] Match list formatting styles
- [ ] Detect and match table styles
- [ ] Handle heading level inheritance
- [ ] Implement style application
- [ ] Test: Content matches document style
- [ ] Test: Various formatting scenarios
- [ ] Test: Complex nested formatting

**Deliverables:**
- Style detection and matching logic
- Format application utilities
- Style inheritance rules

### Phase 6: Polish & Production Readiness (Days 6-7)
**Goal:** Production-ready skill with error handling and docs

Tasks:
- [ ] Implement rate limit handling (exponential backoff)
- [ ] Add network error retries
- [ ] Create clear error messages
- [ ] Add validation before applying changes
- [ ] Implement preview mode (dry-run)
- [ ] Add confirmation prompts
- [ ] Write skill documentation (SKILL.md)
- [ ] Create setup guide (README.md)
- [ ] Write example workflows
- [ ] Add usage examples
- [ ] Test: Rate limit handling
- [ ] Test: Network failure recovery
- [ ] Test: Invalid input handling
- [ ] Integration test: Full workflow end-to-end

**Deliverables:**
- Complete error handling
- User documentation
- Example workflows
- Production-ready code

## File Structure

```
document-skills/gdocs/
├── SKILL.md                      # Main skill documentation
├── README.md                     # Setup and usage guide
├── LICENSE.txt                   # License (match docx skill)
│
├── auth/
│   ├── oauth_setup.md           # OAuth configuration guide
│   ├── credentials.json.example # Template for OAuth setup
│   └── .gitignore               # Ignore tokens and credentials
│
├── scripts/
│   ├── __init__.py
│   ├── gdocs_editor.py          # Main API (user-facing)
│   ├── auth_manager.py          # OAuth token management
│   ├── document_analyzer.py     # Structure parsing
│   ├── content_merger.py        # Insertion logic
│   ├── comment_manager.py       # Comment operations
│   ├── style_matcher.py         # Formatting intelligence
│   └── utilities.py             # Shared utilities
│
├── examples/
│   ├── meeting_notes_merge.py   # Primary use case example
│   ├── section_update.py        # Update existing section
│   ├── append_content.py        # Add to end of document
│   └── comment_based_edit.py    # Comment-only workflow
│
└── tests/
    ├── test_auth.py             # Authentication tests
    ├── test_analysis.py         # Document parsing tests
    ├── test_insertion.py        # Content merging tests
    └── test_comments.py         # Comment management tests
```

## Technical Architecture

### APIs Used
- **Google Docs API v1** - Document reading and editing
- **Google Drive API v3** - Comment and file management

### Python Dependencies
```
google-auth>=2.30.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.140.0
requests>=2.31.0
```

### Key Classes

```python
# Main user-facing API
class GoogleDocsEditor:
    def __init__(self, credentials_path=None)
    def analyze_document(self, doc_url_or_id) -> DocumentAnalysis
    def preview_merge(self, doc_url_or_id, content, **kwargs) -> MergePreview
    def merge_content(self, doc_url_or_id, content, **kwargs) -> MergeResult

# Document structure representation
class DocumentAnalysis:
    doc_id: str
    title: str
    sections: List[Section]
    comments: List[Comment]
    formatting_patterns: FormattingProfile
    def suggest_location(self, section_name) -> InsertionPoint

# Merge operation result
class MergeResult:
    success: bool
    insertion_index: int
    paragraphs_added: int
    comment_id: str
    comment_text: str
    error: Optional[str]
```

### Authentication Flow
```
1. User runs skill for first time
2. OAuth flow opens browser
3. User grants permissions
4. Tokens saved to ~/.claude-skills/gdocs/tokens.json
5. Subsequent runs use saved tokens
6. Automatic refresh when tokens expire
```

## Configuration

### Required Google Cloud Setup
1. Create Google Cloud project
2. Enable APIs:
   - Google Docs API
   - Google Drive API
3. Configure OAuth consent screen
4. Create OAuth 2.0 Client ID (Desktop app)
5. Download credentials.json

### OAuth Scopes Required
```
https://www.googleapis.com/auth/documents          # Read and write docs
https://www.googleapis.com/auth/drive.file         # Access docs via Drive
https://www.googleapis.com/auth/drive.comments     # Manage comments
```

## Error Handling Strategy

### Rate Limits
- Google Docs API: 60 requests/minute/user
- Strategy: Exponential backoff with jitter
- Max retries: 3
- Show clear message if limit exceeded

### Network Errors
- Retry transient errors (500, 503)
- Don't retry client errors (400, 404)
- Timeout: 30 seconds per request
- Show helpful error messages

### Validation
- Check document exists before editing
- Verify insertion point is valid
- Validate content format
- Confirm user has edit permissions

## Testing Strategy

### Unit Tests
- Authentication flow
- Document parsing
- Insertion point calculation
- Comment creation
- Style matching

### Integration Tests
- Full workflow: read → analyze → insert → comment
- Multiple content types
- Various document structures
- Error scenarios

### Manual Testing Checklist
- [ ] Simple text insertion
- [ ] Inserting lists
- [ ] Inserting tables
- [ ] Formatting preservation
- [ ] Comment creation
- [ ] Comment replies
- [ ] Multiple batch updates
- [ ] Large documents (100+ pages)
- [ ] Documents with existing comments
- [ ] Documents with existing suggestions

## Success Criteria

### Functional Requirements
✓ Can authenticate via OAuth 2.0
✓ Can read any Google Doc
✓ Can analyze document structure
✓ Can find appropriate insertion points
✓ Can insert content with preserved formatting
✓ Can add contextual comments
✓ Can reply to existing comments
✓ Changes apply atomically

### User Experience Requirements
✓ Setup takes < 5 minutes
✓ First use requires OAuth (one-time)
✓ Subsequent uses require no auth
✓ Clear preview before applying changes
✓ Helpful error messages
✓ Fast operation (< 5 seconds for typical edit)

### Code Quality Requirements
✓ Type hints throughout
✓ Comprehensive error handling
✓ Clear function documentation
✓ Example workflows included
✓ Tests pass

## Risks & Mitigations

### Risk: OAuth complexity confuses users
**Mitigation:**
- Detailed setup guide with screenshots
- Example credentials.json
- Clear error messages during auth flow

### Risk: Finding insertion points is unreliable
**Mitigation:**
- Multiple strategies (section name, heading, index)
- Preview mode shows where content will go
- Fallback to manual index specification

### Risk: Formatting doesn't match document style
**Mitigation:**
- Analyze existing formatting patterns
- Use document's default styles
- Allow manual style override

### Risk: API rate limits hit during large operations
**Mitigation:**
- Batch multiple changes together
- Implement exponential backoff
- Show progress for large operations

## Future Enhancements (Post-MVP)

### Phase 2 Features
- [ ] Support for images and drawings
- [ ] Table manipulation (add rows/columns)
- [ ] Named ranges for reliable anchoring
- [ ] Smart conflict resolution
- [ ] Multi-document operations

### Advanced Features
- [ ] AI-powered insertion point selection
- [ ] Automatic content summarization in comments
- [ ] Diff visualization before applying
- [ ] Undo/rollback support
- [ ] Collaborative editing with other users

### Integrations
- [ ] Slack integration (post meeting → auto-update doc)
- [ ] Calendar integration (meeting → doc mapping)
- [ ] Email parsing (extract notes from email → doc)

## Timeline

**Total Estimated Time:** 7 days

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 1: Auth & Reading | 2 days | Day 1 | Day 2 |
| Phase 2: Analysis | 1 day | Day 2 | Day 3 |
| Phase 3: Insertion | 1 day | Day 3 | Day 4 |
| Phase 4: Comments | 1 day | Day 4 | Day 5 |
| Phase 5: Formatting | 1 day | Day 5 | Day 6 |
| Phase 6: Polish | 1 day | Day 6 | Day 7 |

**Buffer:** 1-2 days for unexpected complexity

## References

### Documentation
- [Google Docs API Overview](https://developers.google.com/workspace/docs/api/how-tos/overview)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
- [Drive API Comments](https://developers.google.com/drive/api/guides/manage-comments)
- [BatchUpdate Reference](https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate)

### Similar Work
- Existing @document-skills/docx skill (for reference on skill structure)
- Google Docs mail merge sample (for template patterns)

## Decision Log

**2025-10-31:** Decided on direct edits + comments approach over waiting for suggestion API support
**2025-10-31:** Chose Python to match existing docx skill language
**2025-10-31:** Prioritized meeting notes use case for MVP
**2025-10-31:** Comments as key differentiator vs. traditional track changes

## Questions for User

Before starting implementation, clarify:

1. **Authentication preference:**
   - One-time OAuth with saved tokens? ✓ (recommended)
   - Per-session authentication?
   - Service account (for automation)?

2. **Primary language:**
   - Python? ✓ (matches docx skill)
   - Node.js?

3. **Initial scope:**
   - Focus on text + basic formatting? ✓ (recommended for MVP)
   - Need tables/images support immediately?

4. **Comment style preference:**
   - Formal: "Content added on [date] from [source]"
   - Casual: "Added meeting notes from yesterday's sync"
   - User configurable?

---

**Status:** Ready to begin implementation
**Next Step:** Confirm approach and start Phase 1
