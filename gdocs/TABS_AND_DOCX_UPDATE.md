# Google Docs Skill - Tabs & Word Document Handling Update

**Date:** 2025-10-31
**Status:** ✅ Documentation Complete - Code Updates Required

## Summary of Updates

This document covers two critical updates to the Google Docs skill:
1. **Word Document Detection** - URL patterns cannot distinguish .docx from Google Docs
2. **Tabs Support** - Documents can have multiple tabs that must be handled properly

---

## Part 1: Word Document Handling (CRITICAL CORRECTION)

### What We Learned

**INCORRECT ASSUMPTION (from earlier today):**
> "Word documents use `drive.google.com/file/d/...` URLs"
> "Google Docs use `docs.google.com/document/d/...` URLs"

**ACTUAL REALITY (verified by user):**
Both Word documents AND Google Docs use **identical URL patterns**:
```
Word document:  https://docs.google.com/document/d/1kkcUPyLdmwcGIeN8byK_iQ-hu1Dx6NWk/edit
Google Doc:     https://docs.google.com/document/d/1xZDW-RvrYEYJ31Ubg3OEv4IsUx2JlCXvGUTE2vLvwWg/edit

Both have: docs.google.com/document/d/...
```

### Why This Happens

When a user uploads a Word document to Google Drive:
- They can view/edit it in Google Docs UI
- Google Drive generates a `docs.google.com/document/d/...` URL
- But the file **remains in .docx format** internally
- MIME type stays: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Google Docs API **cannot edit it** programmatically

### What We Updated in SKILL.md

**Added "File Format Detection" section:**
- **Critical warning:** URL patterns alone CANNOT distinguish file types
- **Detection strategy:** Catch `HttpError 404` when attempting to read document
- **User communication:** Provide helpful error message explaining Word document limitation

**Before (wrong):**
```python
# Check URL pattern
if 'drive.google.com/file/' in url:
    warn_user_about_word_document()
```

**After (correct):**
```python
# Try to read document, catch errors gracefully
try:
    document = editor.get_document(doc_id)
except HttpError as e:
    if e.resp.status == 404:
        inform_user_might_be_word_document()
```

### Updated Files

1. **`~/.claude/skills/gdocs/SKILL.md`**
   - Replaced URL pattern detection section
   - Added error handling guidance
   - Updated workflow checklist

2. **`~/.claude/skills/gdocs/WORD_DOCUMENT_HANDLING.md`**
   - Corrected URL pattern examples
   - Added real user examples
   - Updated detection strategy

3. **`~/.claude/skills/gdocs/SKILL.md` - Known Limitations**
   - Clarified that URL patterns don't indicate file type
   - Added critical warnings

---

## Part 2: Google Docs Tabs Support

### What Are Tabs?

Google Docs now supports **multiple tabs within a single document** (like spreadsheet tabs).

**Example URL with tab:**
```
https://docs.google.com/document/d/DOC_ID/edit?tab=t.82ynznspwjyi
                                               ↑ tab ID parameter
```

### Why This Matters

**Without tabs support:**
- ✅ You only see the FIRST tab's content
- ❌ Content in other tabs is invisible
- ❌ User shares tab 2 URL, but you read tab 1 content

**With tabs support:**
- ✅ Read all tabs in document
- ✅ Target specific tab from URL
- ✅ Insert content into correct tab

### API Changes Required

#### 1. Get Document with Tabs

**Current implementation (missing tabs):**
```python
def get_document(self, doc_url_or_id: str) -> Dict[str, Any]:
    doc_id = self.extract_doc_id(doc_url_or_id)
    document = self.docs_service.documents().get(documentId=doc_id).execute()
    return document
```

**Required implementation:**
```python
def get_document(self, doc_url_or_id: str, include_tabs_content: bool = True) -> Dict[str, Any]:
    doc_id = self.extract_doc_id(doc_url_or_id)
    document = self.docs_service.documents().get(
        documentId=doc_id,
        includeTabsContent=include_tabs_content  # ← NEW
    ).execute()
    return document
```

#### 2. Extract Tab ID from URL

**Add new method:**
```python
@staticmethod
def extract_tab_id(doc_url: str) -> Optional[str]:
    """
    Extract tab ID from URL query parameter.

    Examples:
        >>> extract_tab_id('https://docs.google.com/document/d/ABC/edit?tab=t.123')
        't.123'
        >>> extract_tab_id('https://docs.google.com/document/d/ABC/edit')
        None
    """
    import re
    match = re.search(r'[?&]tab=([^&]+)', doc_url)
    return match.group(1) if match else None
```

#### 3. Find Tab by ID

**Add helper method:**
```python
@staticmethod
def find_tab_by_id(tabs: List[dict], tab_id: str) -> Optional[dict]:
    """
    Find tab by ID, searching recursively through child tabs.

    Args:
        tabs: List of tab objects
        tab_id: Tab ID to find (e.g., 't.0', 't.82ynznspwjyi')

    Returns:
        Tab object if found, None otherwise
    """
    for tab in tabs:
        if tab.get('tabProperties', {}).get('tabId') == tab_id:
            return tab

        # Search child tabs recursively
        child_tabs = tab.get('childTabs', [])
        if child_tabs:
            found = GoogleDocsEditor.find_tab_by_id(child_tabs, tab_id)
            if found:
                return found

    return None
```

#### 4. Get Tab Body

**Add helper method:**
```python
def get_tab_body(self, document: dict, tab_id: Optional[str] = None) -> dict:
    """
    Get body content from specific tab or first tab.

    Args:
        document: Document resource with tabs
        tab_id: Optional tab ID to target specific tab

    Returns:
        Body content from target tab
    """
    tabs = document.get('tabs', [])

    if not tabs:
        # Legacy: No tabs, use document body
        return document.get('body', {})

    if tab_id:
        # Find specific tab
        target_tab = self.find_tab_by_id(tabs, tab_id)
        if target_tab:
            return target_tab.get('documentTab', {}).get('body', {})

    # Default to first tab
    return tabs[0].get('documentTab', {}).get('body', {})
```

#### 5. Update analyze_document()

**Current implementation (doesn't handle tabs):**
```python
def analyze_document(self, doc_url_or_id: str) -> DocumentAnalysis:
    doc = self.get_document(doc_url_or_id)
    body = doc.get('body', {})  # ← Only gets first tab!
    # ...
```

**Required implementation:**
```python
def analyze_document(self, doc_url_or_id: str) -> DocumentAnalysis:
    doc = self.get_document(doc_url_or_id, include_tabs_content=True)  # ← Enable tabs

    # Extract tab ID from URL
    tab_id = self.extract_tab_id(doc_url_or_id)

    # Get body from target tab
    body = self.get_tab_body(doc, tab_id)  # ← Get correct tab

    # ... rest of analysis
```

#### 6. Update content_inserter.py

**Add tab ID to insertion requests:**
```python
def _simple_insert(
    self,
    doc_id: str,
    index: int,
    content: str,
    tab_id: Optional[str] = None,  # ← NEW parameter
    add_inline_attribution: bool = False,
    attribution_text: str = None
) -> bool:
    """Insert content with optional tab targeting."""

    location = {'index': index}
    if tab_id:
        location['tabId'] = tab_id  # ← Target specific tab

    requests = [
        {
            'insertText': {
                'location': location,  # ← Include tab ID
                'text': content
            }
        },
        # ... rest of formatting requests
    ]
```

### Document Structure Changes

**With `includeTabsContent=True`:**
```python
document = {
    'title': 'My Document',
    'documentId': 'ABC123',
    'tabs': [                        # ← Content here
        {
            'tabProperties': {
                'tabId': 't.0',
                'title': 'Overview',
                'index': 0
            },
            'documentTab': {
                'body': {...},       # ← Tab's content
                'headers': {...},
                'footers': {...}
            },
            'childTabs': [...]       # ← Nested tabs
        }
    ],
    'body': {},                      # ← EMPTY
    'headers': {},                   # ← EMPTY
    'footers': {}                    # ← EMPTY
}
```

### Updated Workflow

**Step-by-step with tabs support:**

1. **Extract tab ID from URL**
   ```python
   tab_id = editor.extract_tab_id(doc_url)  # or None
   ```

2. **Get document with tabs**
   ```python
   doc = editor.get_document(doc_url, include_tabs_content=True)
   ```

3. **Get target tab's body**
   ```python
   body = editor.get_tab_body(doc, tab_id)
   ```

4. **Analyze and synthesize using target tab's content**
   ```python
   # Analyze body (from correct tab)
   # Extract insights
   # Synthesize content
   ```

5. **Insert with tab ID**
   ```python
   inserter._simple_insert(
       doc_id=doc_id,
       index=insertion_index,
       content=synthesized_content,
       tab_id=tab_id,  # ← Ensures correct tab
       add_inline_attribution=True,
       attribution_text=source_description
   )
   ```

### What Was Added to SKILL.md

**New "Working with Document Tabs" section:**
- What are tabs and why they matter
- How to access tabs content (`includeTabsContent=True`)
- Document structure with tabs vs legacy
- Accessing single/multiple/nested tabs
- Detecting which tab user wants (URL parameter)
- Inserting content into specific tab
- Known limitations (can't create tabs)
- Tab detection checklist
- Common mistakes and correct approaches

**Updated Workflow Checklist:**
1. Extract tab ID from URL
2. Read document with tabs support
3. Target correct tab
4. Analyze from target tab's content
5. Show preview mentioning tab name
6. Execute with tab ID in insertion

### Implementation Priority

**HIGH PRIORITY:**
- `get_document()` - Add `includeTabsContent` parameter
- `analyze_document()` - Use tabs API
- Extract and use tab ID from URLs
- Get body from correct tab

**MEDIUM PRIORITY:**
- Helper methods for tab operations
- Tab ID in insertion requests
- List all tabs for user

**LOW PRIORITY:**
- Handle nested child tabs
- Advanced tab navigation

---

## Testing Recommendations

### Test 1: Single Tab Document (Backward Compatibility)
```python
# Should work with old documents (no tabs)
doc_url = "https://docs.google.com/document/d/ABC123/edit"
result = inserter.merge_content(
    doc_url=doc_url,
    content="Test content",
    section="Introduction"
)
assert result['success'] == True
```

### Test 2: Multi-Tab Document (No Tab Specified)
```python
# Should default to first tab
doc_url = "https://docs.google.com/document/d/DEF456/edit"
result = inserter.merge_content(
    doc_url=doc_url,
    content="Test content",
    section="Introduction"
)
# Should insert into first tab
```

### Test 3: Multi-Tab Document (Tab Specified)
```python
# Should use specified tab
doc_url = "https://docs.google.com/document/d/DEF456/edit?tab=t.marketing"
result = inserter.merge_content(
    doc_url=doc_url,
    content="Test content",
    section="Introduction"
)
# Should insert into "Marketing" tab
```

### Test 4: Word Document Detection
```python
# Should gracefully handle .docx files
doc_url = "https://docs.google.com/document/d/1kkcUPyLdmwcGIeN8byK_iQ-hu1Dx6NWk/edit"
try:
    result = inserter.merge_content(doc_url=doc_url, content="Test", section="Intro")
except HttpError as e:
    if e.resp.status == 404:
        # Inform user this might be a Word document
        print("Document might be .docx format - cannot edit via API")
```

---

## Implementation Checklist

### gdocs_editor.py Updates

- [ ] Add `include_tabs_content` parameter to `get_document()`
- [ ] Add `extract_tab_id()` static method
- [ ] Add `find_tab_by_id()` static method
- [ ] Add `get_tab_body()` method
- [ ] Update `analyze_document()` to use tabs API
- [ ] Update error handling for Word documents (HttpError 404)

### content_inserter.py Updates

- [ ] Add `tab_id` parameter to `_simple_insert()`
- [ ] Add `tab_id` parameter to `insert_content()`
- [ ] Extract tab ID from URL in `merge_content()`
- [ ] Pass tab ID through to insertion methods
- [ ] Update all `location` dicts to include `tabId` when present

### Testing

- [ ] Test with single-tab documents (backward compatibility)
- [ ] Test with multi-tab documents without tab parameter
- [ ] Test with multi-tab documents with tab parameter
- [ ] Test with nested child tabs
- [ ] Test Word document error handling

---

## Summary

**✅ Documentation Complete:**
- SKILL.md updated with comprehensive tabs guidance
- Word document handling corrected (URL patterns don't work)
- Workflow checklist updated

**⏳ Code Updates Required:**
- Add tabs support to `gdocs_editor.py`
- Update `content_inserter.py` to pass tab IDs
- Test with real multi-tab documents

**Priority:** HIGH - Tabs are a core Google Docs feature

**Impact:** Without tabs support, skill only works with first tab, missing content in other tabs

---

**Status:** ✅ Documentation ready for implementation
**Next:** Update code to implement tabs support
