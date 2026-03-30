# Working with Document Tabs - Technical Reference

## Overview

Google Docs supports **multiple tabs within a single document** (similar to spreadsheet tabs). This reference provides complete technical details for tab handling.

## What Are Tabs?

Documents can have:
- **Single tab** (default) - all content in one tab
- **Multiple tabs** - organized hierarchically with parent/child relationships

**Example URL with tab:**
```
https://docs.google.com/document/d/DOC_ID/edit?tab=t.82ynznspwjyi
                                               ↑ tab ID parameter
```

## Why Tabs Matter

**If a document has tabs and you don't request them:**
- ✅ You only see the FIRST tab's content
- ❌ Content in other tabs is invisible
- ❌ User asks to merge into "Marketing Plan" tab, but you only read "Overview" tab

**Critical:** Always enable tabs support to see ALL document content.

## How to Access Tabs Content

### API Parameter Required

When calling `documents.get()`, add `includeTabsContent=true`:

```python
# ❌ Old way - only gets first tab
document = docs_service.documents().get(documentId=doc_id).execute()

# ✅ New way - gets ALL tabs
document = docs_service.documents().get(
    documentId=doc_id,
    includeTabsContent=True  # ← REQUIRED for tabs support
).execute()
```

### Document Structure with Tabs

**When `includeTabsContent=True`:**
```python
document = {
    'title': 'My Document',
    'documentId': 'ABC123',
    'tabs': [                        # ← Content now here
        {
            'tabProperties': {
                'tabId': 't.0',
                'title': 'Overview',
                'index': 0
            },
            'documentTab': {
                'body': {...},       # ← First tab's content
                'headers': {...},
                'footers': {...}
            },
            'childTabs': [           # ← Nested tabs
                {
                    'tabProperties': {...},
                    'documentTab': {...}
                }
            ]
        }
    ],
    'body': {},                      # ← EMPTY when using tabs API
    'headers': {},                   # ← EMPTY when using tabs API
    'footers': {}                    # ← EMPTY when using tabs API
}
```

**When `includeTabsContent=False` (legacy):**
```python
document = {
    'title': 'My Document',
    'documentId': 'ABC123',
    'tabs': [],                      # ← EMPTY
    'body': {...},                   # ← Only first tab's content here
    'headers': {...},
    'footers': {...}
}
```

## Accessing Tab Content

### Single Tab Document
```python
# With tabs API
first_tab = document['tabs'][0]
body = first_tab['documentTab']['body']
```

### Multiple Tabs Document
```python
# List all tabs
for tab in document['tabs']:
    tab_id = tab['tabProperties']['tabId']
    tab_title = tab['tabProperties']['title']
    tab_body = tab['documentTab']['body']
    print(f"Tab: {tab_title} (ID: {tab_id})")
```

### Nested (Child) Tabs
```python
# Access child tab
parent_tab = document['tabs'][2]  # Third parent tab
child_tab = parent_tab['childTabs'][0]  # First child
grandchild_tab = child_tab['childTabs'][1]  # Second grandchild

# Access content: Tab 3.1.2
body = document['tabs'][2]['childTabs'][0]['childTabs'][1]['documentTab']['body']
```

## Detecting Which Tab User Wants

**Tab ID in URL:**
```python
url = "https://docs.google.com/document/d/ABC123/edit?tab=t.82ynznspwjyi"

# Extract tab ID
import re
tab_match = re.search(r'[?&]tab=([^&]+)', url)
if tab_match:
    target_tab_id = tab_match.group(1)  # 't.82ynznspwjyi'

# Find matching tab in document
def find_tab_by_id(tabs, tab_id):
    for tab in tabs:
        if tab['tabProperties']['tabId'] == tab_id:
            return tab
        # Search child tabs recursively
        if 'childTabs' in tab:
            found = find_tab_by_id(tab['childTabs'], tab_id)
            if found:
                return found
    return None

target_tab = find_tab_by_id(document['tabs'], target_tab_id)
```

## Inserting Content into Specific Tab

**When using `batchUpdate`, specify tab ID:**

```python
requests = [
    {
        'insertText': {
            'location': {
                'index': insertion_index,
                'tabId': 't.82ynznspwjyi'  # ← Target specific tab
            },
            'text': 'Content for this tab'
        }
    }
]

docs_service.documents().batchUpdate(
    documentId=doc_id,
    body={'requests': requests}
).execute()
```

**If no tab ID specified:** Content goes to the FIRST tab by default.

## Workflow with Tabs

**Step 1: Always request tabs content**
```python
document = editor.get_document(doc_id, include_tabs_content=True)
```

**Step 2: Check if document has tabs**
```python
has_tabs = len(document.get('tabs', [])) > 0
num_tabs = len(document.get('tabs', []))
```

**Step 3: If URL has tab parameter, target that tab**
```python
if tab_id_from_url:
    target_tab = find_tab_by_id(document['tabs'], tab_id_from_url)
    body = target_tab['documentTab']['body']
else:
    # Default to first tab
    body = document['tabs'][0]['documentTab']['body']
```

**Step 4: Analyze and insert content with tab ID**
```python
# Include tab ID in insertion requests
location = {
    'index': insertion_index,
    'tabId': target_tab_id  # ← Ensures correct tab
}
```

## Known Limitations

**Cannot Create Tabs:**
- ❌ Google Docs API cannot create new tabs
- ❌ Cannot rename or delete tabs
- ✅ Can read all tabs
- ✅ Can insert/edit content in existing tabs

**Workaround:** If user wants content in a new tab:
1. Ask user to create the tab manually in Google Docs UI
2. Get the updated document with new tab
3. Insert content into the new tab

## Tab Detection Checklist

**Before analyzing ANY document:**
- [ ] Use `includeTabsContent=True` in API call
- [ ] Check if `document['tabs']` is populated
- [ ] If URL has `?tab=` parameter, extract and find target tab
- [ ] Use correct tab's `documentTab.body` for analysis
- [ ] Include tab ID in all insertion/update requests

## Common Mistakes

❌ **Mistake 1: Forgetting includeTabsContent**
```python
doc = docs_service.documents().get(documentId=doc_id).execute()
# Only sees first tab!
```

❌ **Mistake 2: Using legacy body field**
```python
body = document['body']  # EMPTY when using tabs API!
```

❌ **Mistake 3: Ignoring URL tab parameter**
```
User shares: .../edit?tab=t.marketing
You insert into first tab instead of "Marketing" tab
```

❌ **Mistake 4: No tab ID in batchUpdate**
```python
{'insertText': {'location': {'index': 5}}}
# Goes to first tab, not the tab user is viewing!
```

✅ **Correct Approach:**
```python
# 1. Get document with tabs
doc = docs_service.documents().get(
    documentId=doc_id,
    includeTabsContent=True
).execute()

# 2. Extract tab ID from URL
tab_id = extract_tab_from_url(url)  # or None

# 3. Find target tab
if tab_id:
    target_tab = find_tab_by_id(doc['tabs'], tab_id)
else:
    target_tab = doc['tabs'][0]

# 4. Analyze target tab's content
body = target_tab['documentTab']['body']

# 5. Insert with tab ID
requests = [{
    'insertText': {
        'location': {'index': idx, 'tabId': target_tab['tabProperties']['tabId']},
        'text': content
    }
}]
```
