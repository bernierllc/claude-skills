# Word Document Handling in Google Drive

**Date:** 2025-10-31
**Purpose:** Explain how Word documents differ from Google Docs and what our skill needs to handle them

## The Critical Difference

### Google Docs API ≠ Word Document API

**Key Finding:** The Google Docs API **CANNOT** edit Word (.docx) files directly.

- ✅ **Google Docs API** works with: `application/vnd.google-apps.document`
- ❌ **Google Docs API** does NOT work with: `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx)

### What Happens in Google Drive

When a user uploads a Word document to Google Drive, there are **two scenarios**:

#### Scenario 1: Upload Without Conversion
```
User uploads "report.docx" to Drive
├─ MIME type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
├─ File retains .docx format
├─ Can be viewed/edited in Google Docs UI
├─ Changes save back to .docx format
├─ URL: https://docs.google.com/document/d/ABC123/edit ← SAME PATTERN!
└─ ❌ Google Docs API CANNOT edit this file programmatically
```

#### Scenario 2: Upload With Conversion
```
User uploads "report.docx" with conversion
├─ MIME type: application/vnd.google-apps.document
├─ File converted to Google Docs format
├─ No longer a .docx file
├─ Lives as native Google Doc
├─ URL: https://docs.google.com/document/d/XYZ789/edit ← SAME PATTERN!
└─ ✅ Google Docs API CAN edit this file
```

**CRITICAL FINDING:** Both scenarios use **identical URL patterns**!
- Word doc: `docs.google.com/document/d/ABC123/edit`
- Google Doc: `docs.google.com/document/d/XYZ789/edit`

**You cannot distinguish them by URL alone.**

## The Problem for Our Skill

**Current behavior:**
```python
def get_document(self, doc_url_or_id: str) -> Dict[str, Any]:
    doc_id = self.extract_doc_id(doc_url_or_id)
    document = self.docs_service.documents().get(documentId=doc_id).execute()
    return document
```

**What happens if user provides a .docx file URL:**
```
1. User: "Merge notes: https://docs.google.com/document/d/ABC123/edit"
   (This is a Word doc, but URL looks identical to Google Docs!)
2. Skill extracts ID: "ABC123"
3. Skill calls: docs_service.documents().get(documentId="ABC123")
4. ❌ ERROR: HttpError 404 "Requested entity was not found"
   (Because it's a .docx file, not a Google Doc)
```

**Real example from user:**
```
Word document:  https://docs.google.com/document/d/1kkcUPyLdmwcGIeN8byK_iQ-hu1Dx6NWk/edit
Google Doc:     https://docs.google.com/document/d/1xZDW-RvrYEYJ31Ubg3OEv4IsUx2JlCXvGUTE2vLvwWg/edit

Both have docs.google.com/document/d/ URLs!
Only MIME type reveals: one is .docx, one is native Google Doc.
```

## Detection Solution

### Step 1: Check File Type First

Before calling the Docs API, check the file's MIME type via Drive API:

```python
def detect_file_type(self, file_id: str) -> dict:
    """
    Detect if file is a Google Doc or Word document.

    Returns:
        {
            'file_id': str,
            'name': str,
            'mime_type': str,
            'is_google_doc': bool,
            'is_word_doc': bool,
            'can_edit_directly': bool
        }
    """
    self._ensure_authenticated()

    # Get file metadata from Drive API
    file_metadata = self.drive_service.files().get(
        fileId=file_id,
        fields='id,name,mimeType'
    ).execute()

    mime_type = file_metadata.get('mimeType', '')

    return {
        'file_id': file_id,
        'name': file_metadata.get('name', ''),
        'mime_type': mime_type,
        'is_google_doc': mime_type == 'application/vnd.google-apps.document',
        'is_word_doc': mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'can_edit_directly': mime_type == 'application/vnd.google-apps.document'
    }
```

### Step 2: Handle Conversion if Needed

```python
def ensure_editable_format(self, file_id: str, auto_convert: bool = False) -> dict:
    """
    Ensure file is in editable Google Docs format.

    Args:
        file_id: The file ID to check
        auto_convert: If True, automatically convert Word docs

    Returns:
        {
            'success': bool,
            'file_id': str,  # May be new ID if converted
            'converted': bool,
            'original_mime_type': str,
            'current_mime_type': str,
            'message': str
        }
    """
    file_info = self.detect_file_type(file_id)

    # Already in Google Docs format
    if file_info['can_edit_directly']:
        return {
            'success': True,
            'file_id': file_id,
            'converted': False,
            'original_mime_type': file_info['mime_type'],
            'current_mime_type': file_info['mime_type'],
            'message': 'File is already in Google Docs format'
        }

    # Word document needs conversion
    if file_info['is_word_doc']:
        if not auto_convert:
            return {
                'success': False,
                'file_id': file_id,
                'converted': False,
                'original_mime_type': file_info['mime_type'],
                'current_mime_type': file_info['mime_type'],
                'message': 'File is a Word document. Conversion required for programmatic editing.'
            }

        # Perform conversion via Drive API
        # Copy file with mimeType conversion
        new_file = self.drive_service.files().copy(
            fileId=file_id,
            body={
                'name': f"{file_info['name']} (Google Docs)",
                'mimeType': 'application/vnd.google-apps.document'
            }
        ).execute()

        return {
            'success': True,
            'file_id': new_file['id'],
            'converted': True,
            'original_mime_type': file_info['mime_type'],
            'current_mime_type': 'application/vnd.google-apps.document',
            'message': f"Converted Word document to Google Docs format. New file: {new_file['name']}"
        }

    # Unknown file type
    return {
        'success': False,
        'file_id': file_id,
        'converted': False,
        'original_mime_type': file_info['mime_type'],
        'current_mime_type': file_info['mime_type'],
        'message': f"Unsupported file type: {file_info['mime_type']}"
    }
```

### Step 3: Updated Workflow in Content Inserter

```python
def merge_content(
    self,
    doc_url: str,
    content: str,
    section: str = None,
    options: MergeOptions = None
) -> dict:
    """Merge content with Word document detection and conversion."""

    # Extract file ID
    file_id = self.editor.extract_doc_id(doc_url)

    # Detect file type
    file_info = self.editor.detect_file_type(file_id)

    # Handle Word documents
    if not file_info['can_edit_directly']:
        if file_info['is_word_doc']:
            # Ask user about conversion
            return {
                'success': False,
                'error': 'word_document_requires_conversion',
                'file_name': file_info['name'],
                'message': (
                    f"The file '{file_info['name']}' is a Word document (.docx). "
                    f"The Google Docs API cannot edit Word documents directly. "
                    f"Options:\n"
                    f"1. Convert to Google Docs format (creates a copy)\n"
                    f"2. Manually open in Google Docs and 'Make a copy' to Google Docs format\n"
                    f"3. Use the docx skill instead for Word document editing"
                )
            }
        else:
            return {
                'success': False,
                'error': 'unsupported_file_type',
                'mime_type': file_info['mime_type'],
                'message': f"Unsupported file type: {file_info['mime_type']}"
            }

    # Continue with normal merge workflow...
    # [existing code]
```

## User Experience in Conversations

### Scenario 1: User Provides Word Document

```
User: "Merge these meeting notes into my Word doc:
       https://drive.google.com/file/d/ABC123"

Claude: I've detected that the file is a Word document (.docx).
        The Google Docs API cannot edit Word documents directly.

        You have three options:

        1. I can convert it to Google Docs format (creates a new copy)
           and merge the notes there

        2. You can manually convert it:
           - Open the Word doc in Google Drive
           - File → Save as Google Docs
           - Share the new Google Docs URL with me

        3. I can use the Word document skill instead (if available)
           to edit the .docx file directly

        Which would you prefer?
```

### Scenario 2: User Provides Google Doc (Current Behavior)

```
User: "Merge these meeting notes into my doc:
       https://docs.google.com/document/d/XYZ789/edit"

Claude: [Proceeds with normal workflow - no changes needed]
```

### Scenario 3: Auto-Conversion Enabled

```
User: "Merge these notes, and auto-convert if needed"

Claude: I've detected that the file is a Word document. Converting
        to Google Docs format...

        ✅ Conversion complete!
        New Google Doc: "Q4 Report (Google Docs)"

        Now merging your meeting notes...
        [Continues with merge]
```

## Implementation Checklist

### Phase 1: Detection Only (Recommended First Step)
- [ ] Add `detect_file_type()` method to `GoogleDocsEditor`
- [ ] Update `merge_content()` to check file type first
- [ ] Return helpful error message for Word documents
- [ ] Update SKILL.md with Word document handling instructions

### Phase 2: Conversion Support (Optional)
- [ ] Add `ensure_editable_format()` method with conversion
- [ ] Add `convert_to_google_docs()` helper
- [ ] Add user confirmation before conversion
- [ ] Track original file ID and converted file ID

### Phase 3: Integration (Future Enhancement)
- [ ] Detect if `docx` skill is available
- [ ] Route .docx files to docx skill automatically
- [ ] Provide unified interface for both formats

## SKILL.md Updates Needed

Add new section after "Core Workflow":

```markdown
## File Format Detection

**CRITICAL:** Before attempting to edit any document, detect its file type.

### Supported Formats
- ✅ **Google Docs format** - `application/vnd.google-apps.document`
- ❌ **Word documents (.docx)** - Cannot be edited via Google Docs API

### Detection Workflow

1. **Extract file ID** from URL
2. **Check MIME type** via Drive API
   ```python
   file_info = editor.detect_file_type(file_id)
   ```
3. **Handle based on type:**
   - Google Doc → Proceed with normal workflow
   - Word doc → Inform user, offer conversion
   - Other → Report unsupported

### User Communication for Word Documents

When user provides a Word document URL:

**Say:**
"I've detected this is a Word document (.docx). The Google Docs API
cannot edit Word documents directly. Would you like me to:

1. Convert it to Google Docs format (creates a copy), or
2. Provide instructions for manual conversion?"

**Never:**
- Try to edit without checking file type
- Fail silently with a confusing error
- Assume all Drive URLs are Google Docs

### Error Messages to Expect

- HttpError 404: "Requested entity was not found"
  → Likely a .docx file, not a Google Doc

- Check file type before assuming API failure
```

## Summary

**Critical Point:** Google Docs API and Word documents are incompatible.

**What We Need:**
1. ✅ File type detection before editing
2. ✅ Clear user communication about Word docs
3. ✅ Optional: Conversion workflow
4. ✅ Updated SKILL.md documentation

**Impact on Current Skill:**
- Low complexity to add detection
- Prevents confusing errors
- Better user experience
- Maintains compatibility with existing Google Docs workflow

**Next Steps:**
1. Add `detect_file_type()` to `gdocs_editor.py`
2. Update `merge_content()` in `content_inserter.py`
3. Add Word document handling section to SKILL.md
4. Test with both Google Docs and .docx files

---

**Status:** 📝 Design complete, ready for implementation
**Priority:** HIGH - Prevents user confusion and API errors
