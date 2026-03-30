# Handling Document Structures - Technical Reference

## Overview

Google Docs contain various structural elements. This reference provides complete technical details for detecting and working with document structures.

## Understanding Google Docs Elements

### Structural Elements You'll Encounter

1. **Paragraphs** - Plain text terminated by newlines
2. **Tables** - Rows and columns with cells containing content
3. **Lists** - Bulleted or numbered lists (with nesting levels)
4. **Headers/Footers** - Document-level containers
5. **Section Breaks** - Layout divisions
6. **Table of Contents** - Auto-generated outlines

## Detection Strategy

When analyzing a document, check the structure:

```python
doc = editor.get_document(doc_id)
body = doc.get('body', {})
content_elements = body.get('content', [])

for element in content_elements:
    if 'paragraph' in element:
        # Handle paragraph content
        paragraph = element['paragraph']
        has_bullet = 'bullet' in paragraph

    elif 'table' in element:
        # Handle table content
        table = element['table']
        rows = table.get('tableRows', [])

    elif 'sectionBreak' in element:
        # Handle section breaks
        pass
```

## Insertion Decision Tree

**BEFORE inserting ANY content, determine the target context:**

### If Target is a TABLE

- ✅ **Add new row:** Use `InsertTableRowRequest` then `InsertTextRequest` into cells
- ✅ **Add to existing row:** Insert text into specific cell index
- ❌ **Don't:** Insert paragraph text at table index (will break structure)

**Example:**
```python
# Add row to table
requests = [
    {
        'insertTableRow': {
            'tableCellLocation': {
                'tableStartLocation': {'index': table_start_index},
                'rowIndex': last_row_index,
                'columnIndex': 0
            },
            'insertBelow': True
        }
    },
    {
        'insertText': {
            'location': {'index': new_cell_index},
            'text': 'New row content'
        }
    }
]
```

### If Target is a LIST

- ✅ **Add list item:** Insert paragraph + apply bullets with `CreateParagraphBulletsRequest`
- ✅ **Match nesting:** Count leading tabs to match existing nesting level
- ❌ **Don't:** Insert plain text (loses list formatting)

**Example:**
```python
# Add bullet to existing list
requests = [
    {
        'insertText': {
            'location': {'index': after_last_item},
            'text': '\nNew list item text'
        }
    },
    {
        'createParagraphBullets': {
            'range': {
                'startIndex': after_last_item,
                'endIndex': after_last_item + len('New list item text')
            },
            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'  # Match existing
        }
    }
]
```

### If Target is PLAIN PARAGRAPH

- ✅ **Insert paragraph:** Use current `_simple_insert` method
- ✅ **Apply NORMAL_TEXT:** Prevents header inheritance
- ✅ **Add attribution:** Inline purple text

## Structure-Aware Synthesis

When synthesizing content, match the target structure:

### Target is Executive Summary (plain paragraphs)
```
Input:  Detailed meeting notes
Output: 2-3 polished sentences
Format: Plain paragraph with NORMAL_TEXT style
```

### Target is Feature List (bulleted list)
```
Input:  Feature discussions
Output: Bullet points, one per feature
Format: Bulleted list with matched nesting
```

### Target is Timeline Table
```
Input:  Schedule updates
Output: New table row(s)
Format: Table row with cells (Milestone | Date | Owner)
```

### Target is Technical Specs (numbered list)
```
Input:  Technical decisions
Output: Numbered items
Format: Numbered list with proper ordering
```

## Analysis Workflow

1. **Read target section:**
   ```python
   analysis = editor.analyze_document(doc_id)
   # Find target section
   target_section = next(s for s in analysis.sections
                         if section_name in s['heading'])
   ```

2. **Detect structure at insertion point:**
   ```python
   doc = editor.get_document(doc_id)
   element_at_insertion = find_element_at_index(doc, insertion_index)

   if 'table' in element_at_insertion:
       strategy = 'insert_table_row'
   elif 'paragraph' in element_at_insertion:
       if 'bullet' in element_at_insertion['paragraph']:
           strategy = 'insert_list_item'
       else:
           strategy = 'insert_paragraph'
   ```

3. **Synthesize matching structure:**
   - If table → synthesize row data
   - If list → synthesize bullet points
   - If paragraph → synthesize prose

4. **Insert with correct API calls:**
   - Use structure-specific requests
   - Maintain formatting consistency
   - Preserve existing structure

## Common Patterns by Document Type

### Executive Proposal
- Mostly paragraphs with NORMAL_TEXT
- Occasional tables for data
- Headers for major sections
- **Synthesis:** Prose-focused

### Technical Specification
- Heavy use of numbered lists
- Code blocks or formatted text
- Tables for parameters/configs
- **Synthesis:** Structured, precise

### Project Plan
- Timeline tables (Milestone | Date | Owner)
- Task lists (bulleted or numbered)
- Status sections (paragraphs)
- **Synthesis:** Data + narrative mix

### Meeting Notes Template
- Agenda (numbered list)
- Discussion (paragraphs)
- Action items (bulleted list with checkboxes)
- **Synthesis:** Structured + formatted

## Error Prevention

### Before Inserting Checklist
- [ ] Detected target element type (paragraph/table/list)?
- [ ] Chosen correct insertion method?
- [ ] Matched existing formatting?
- [ ] Will structure remain valid after insertion?

### Red Flags
- ❌ Inserting paragraph at table index → breaks table
- ❌ Inserting plain text where list expected → loses formatting
- ❌ Wrong bullet style → inconsistent appearance
- ❌ Ignoring nesting level → wrong list hierarchy
