# Structure-Aware Content Insertion

**Date:** 2025-10-31
**Purpose:** Enable intelligent handling of ALL Google Docs structures

## The Problem We Solved

**Before:** Skill only inserted plain paragraphs
**After:** Skill detects and respects tables, lists, and all structural elements

## What Was Added to SKILL.md

### 1. Understanding Document Structures

Complete documentation of all structural elements Claude will encounter:
- **Paragraphs** - Plain text content
- **Tables** - Rows/columns/cells
- **Lists** - Bulleted or numbered (with nesting)
- **Headers/Footers** - Document-level content
- **Section Breaks** - Layout divisions
- **Table of Contents** - Auto-generated outlines

### 2. Detection Strategy

Code patterns for Claude to detect structure types:
```python
if 'paragraph' in element:
    has_bullet = 'bullet' in paragraph
elif 'table' in element:
    rows = table.get('tableRows', [])
```

### 3. Insertion Decision Tree

Clear rules for Claude to follow:

**If target is TABLE:**
- ✅ Add new row with InsertTableRowRequest
- ❌ Don't insert paragraph text (breaks structure)

**If target is LIST:**
- ✅ Insert paragraph + apply bullets
- ✅ Match existing nesting level
- ❌ Don't insert plain text (loses formatting)

**If target is PLAIN PARAGRAPH:**
- ✅ Use current _simple_insert method
- ✅ Apply NORMAL_TEXT style
- ✅ Add attribution

### 4. Structure-Aware Synthesis

Examples of how to synthesize for different structures:

**Target: Executive Summary (paragraphs)**
```
Input:  Meeting notes
Output: 2-3 polished sentences
Format: Plain paragraph
```

**Target: Feature List (bullets)**
```
Input:  Feature discussions
Output: Bullet points, one per feature
Format: Bulleted list
```

**Target: Timeline Table**
```
Input:  Schedule updates
Output: New table row(s)
Format: Table cells (Milestone | Date | Owner)
```

### 5. Analysis Workflow

Step-by-step process for Claude:
1. Read target section
2. Detect structure at insertion point
3. Synthesize matching that structure
4. Insert with correct API calls

### 6. Common Document Patterns

Examples by document type:

**Executive Proposal:**
- Mostly paragraphs
- Occasional tables
- Synthesis: Prose-focused

**Technical Specification:**
- Heavy use of numbered lists
- Tables for parameters
- Synthesis: Structured, precise

**Project Plan:**
- Timeline tables
- Task lists
- Synthesis: Data + narrative mix

**Meeting Notes:**
- Agenda (numbered)
- Discussion (paragraphs)
- Action items (bullets)

### 7. Error Prevention

Checklist before every insertion:
- [ ] Detected target element type?
- [ ] Chosen correct insertion method?
- [ ] Matched existing formatting?
- [ ] Will structure remain valid?

**Red Flags:**
- ❌ Paragraph at table index → breaks table
- ❌ Plain text where list expected → loses formatting
- ❌ Wrong bullet style → inconsistent
- ❌ Ignoring nesting → wrong hierarchy

## How Claude Will Use This

### Current Behavior (Before Enhancement):
```
User: "Add these features to the doc"
Claude: [Inserts as paragraph text everywhere]
Result: Breaks tables, loses list formatting
```

### New Behavior (After Enhancement):
```
User: "Add these features to the doc"
Claude:
  1. Reads document
  2. Detects target section has bulleted list
  3. Synthesizes as bullet points
  4. Inserts using CreateParagraphBulletsRequest
  5. Matches existing bullet style and nesting
Result: Clean list with proper formatting
```

## Example Scenarios

### Scenario 1: Adding to Timeline Table

**User request:** "Add this milestone to the timeline"

**Claude's process:**
1. Detects target is a table
2. Synthesizes row data: [Milestone | Date | Owner]
3. Uses InsertTableRowRequest
4. Inserts text into each cell
5. Result: New table row with proper structure

### Scenario 2: Adding Feature to List

**User request:** "Add this feature to the features list"

**Claude's process:**
1. Detects target is bulleted list
2. Synthesizes bullet point
3. Inserts paragraph with newline
4. Applies bullets with CreateParagraphBulletsRequest
5. Matches existing bullet style (BULLET_DISC_CIRCLE_SQUARE)
6. Result: New list item matching existing format

### Scenario 3: Adding to Executive Summary

**User request:** "Add this insight to the summary"

**Claude's process:**
1. Detects target is plain paragraphs
2. Synthesizes 2-3 executive-level sentences
3. Uses current _simple_insert method
4. Applies NORMAL_TEXT style
5. Adds inline attribution
6. Result: Professional prose paragraph

## API Documentation Referenced

### Tables
- **Source:** https://developers.google.com/workspace/docs/api/how-tos/tables
- **Key Operations:**
  - InsertTableRequest - Create new table
  - InsertTableRowRequest - Add rows
  - InsertTableColumnRequest - Add columns
  - DeleteTableRowRequest / DeleteTableColumnRequest
  - UpdateTableColumnPropertiesRequest - Adjust widths
  - UpdateTableRowStyleRequest - Modify row appearance

### Lists
- **Source:** https://developers.google.com/docs/api/how-tos/lists
- **Key Operations:**
  - CreateParagraphBulletsRequest - Apply bullets to range
  - DeleteParagraphBulletsRequest - Remove bullets
  - BulletGlyphPreset - Bullet style patterns
  - Nesting: Determined by leading tabs

### Document Structure
- **Source:** https://developers.google.com/workspace/docs/api/concepts/structure
- **Key Concepts:**
  - StructuralElement - Base container
  - ParagraphElement - Text content
  - TextRun - Contiguous styled text
  - startIndex/endIndex - Position tracking (UTF-16 code units)

## Implementation Status

### ✅ Already Working
- Paragraph insertion with proper formatting
- Inline attribution (italic purple)
- Contextual comments (paragraph # + excerpt)
- Comment preservation

### 📝 Added to SKILL.md
- Complete structural element documentation
- Detection strategy and code patterns
- Insertion decision tree
- Structure-aware synthesis examples
- Common document patterns
- Error prevention checklist

### 🔮 Future Enhancements (If Needed)
- Helper functions for table row insertion
- Helper functions for list item insertion
- Automatic bullet style detection
- Nesting level detection
- Table column count validation

## Testing Recommendations

To test structure-aware insertion:

1. **Test with Table:**
   ```
   Create doc with timeline table
   Ask Claude to add milestone
   Verify new row added (not paragraph)
   ```

2. **Test with Bulleted List:**
   ```
   Create doc with feature list
   Ask Claude to add feature
   Verify bullet added (not plain text)
   ```

3. **Test with Numbered List:**
   ```
   Create doc with specs list
   Ask Claude to add spec
   Verify number added with correct ordering
   ```

4. **Test with Mixed Structures:**
   ```
   Create doc with paragraphs + tables + lists
   Ask Claude to add content to each
   Verify correct insertion method for each
   ```

## Summary

The skill now has complete documentation for handling ALL Google Docs structural elements. Claude will:

1. **Detect** what structure exists at insertion point
2. **Synthesize** content matching that structure
3. **Insert** using appropriate API calls
4. **Preserve** existing formatting and structure

This ensures Claude doesn't just "dump text everywhere" but intelligently works with the document's existing structure, whether it's tables, lists, or paragraphs.

---

**Status:** ✅ Documentation complete
**Location:** `~/.claude/skills/gdocs/SKILL.md` (updated)
**Ready For:** Structure-aware insertions across all document types
