# GDocs Skill Reorganization Plan

## Goal
Reduce main skill file from 1,242 lines to ~750 lines (40% reduction) by removing redundancy and extracting technical reference material.

## Step-by-Step Execution Plan

### Phase 1: Remove Duplicates (HIGH PRIORITY)

#### Task 1.1: Consolidate Quality Checklists
**Problem:** Three overlapping quality checklists
- Lines 163-169: QUALITY GATES (5 items)
- Lines 448-457: Professional Quality Checklist (7 items)
- Lines 525-531: Professional Quality Check in Review (5 questions)

**Action:**
- KEEP: Review Checklist Step 5 (lines 525-531) - most comprehensive
- REMOVE: QUALITY GATES section (lines 163-169)
- REMOVE: Professional Quality Checklist (lines 448-457)
- ADD: Cross-reference in Professional Editor section to Review Checklist

**Savings:** ~15 lines

#### Task 1.2: Remove Duplicate Common Patterns
**Problem:** Common Patterns appears twice
- Lines 789-813: Common Patterns by Document Type (4 types, detailed)
- Lines 1158-1173: Common Patterns (3 types, brief)

**Action:**
- KEEP: Lines 789-813 (more detailed, in context with Document Structures)
- REMOVE: Lines 1158-1173

**Savings:** ~15 lines

#### Task 1.3: Consolidate Workflow Sections
**Problem:** Two workflow sections
- Lines 91-132: Core Workflow (6 steps, concise)
- Lines 1206-1229: Workflow Checklist (14 steps, detailed)

**Action:**
- KEEP: Lines 1206-1229 (detailed checklist)
- REPLACE: Lines 91-132 with brief summary + cross-reference:
  ```markdown
  ## Core Workflow

  **6-Step Process:**
  1. Analyze Document
  2. Analyze Source Material
  3. Synthesize Content
  4. Show Preview & Get Approval
  5. Execute Merge
  6. Review and Verify (MANDATORY)

  **For complete checklist, see Workflow Checklist section below.**
  ```

**Savings:** ~30 lines

### Phase 2: Extract Technical Reference (HIGH PRIORITY)

#### Task 2.1: Extract Tabs Reference
**File:** Create `tabs-reference.md`
**Content:** Lines 829-1102 (Working with Document Tabs)
**Replace with:**
```markdown
## Working with Document Tabs

Google Docs supports multiple tabs within documents. **CRITICAL:** Always use `includeTabsContent=True` when calling `get_document()`.

**Key requirements:**
- Extract tab ID from URL (`?tab=t.xxxxx`)
- Request all tabs with `includeTabsContent=True`
- Include tab ID in all insertion/update requests
- Default to first tab if no tab ID specified

**For complete tab handling details, see `tabs-reference.md`:**
- Tab API patterns
- Document structure with tabs
- Tab detection and extraction
- Code examples
- Common mistakes
```

**Savings:** ~260 lines

####Task 2.2: Extract Document Structures Reference
**File:** Create `document-structures-reference.md`
**Content:** Lines 620-827 (Handling Document Structures)
**Replace with:**
```markdown
## Working with Document Structures

Google Docs contain various structural elements (paragraphs, tables, lists, headers/footers, section breaks).

**Before inserting, detect target structure:**
- **Table:** Use `InsertTableRowRequest`
- **List:** Use `CreateParagraphBulletsRequest`
- **Paragraph:** Use `InsertTextRequest`

**Match structure when synthesizing:**
- Executive Summary → Paragraphs
- Feature List → Bullet points
- Timeline → Table rows
- Technical Specs → Numbered list

**For complete structure handling details, see `document-structures-reference.md`:**
- Detection strategy
- Insertion decision tree
- Structure-aware synthesis
- Code examples by document type
```

**Savings:** ~190 lines

#### Task 2.3: Move File Format Detection to Troubleshooting
**Action:** Move lines 18-89 (File Format Detection) to new "Troubleshooting" section at end
**Rationale:** This is error-handling content, not core workflow
**Savings:** Improves flow (not token savings)

### Phase 3: Condense Color Coding (MEDIUM PRIORITY)

#### Task 3.1: Create Color Coding Reference File
**File:** Create `color-coding-reference.md`
**Content:**
- All 5 complete Python updateTextStyle examples (currently inline)
- Detailed color coding patterns
- Complete API reference

#### Task 3.2: Condense Main Skill Color Coding
**Keep in main skill:**
- ⚠️ MANDATORY COLOR SYSTEM section (critical warnings)
- ONLY THESE COLORS table
- Rationalization table
- ONE complete example (Blue for new content)
- Color Coding Checklist
- Common Mistakes

**Replace with cross-reference:**
```markdown
### API Implementation

**Blue (new content):**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {'rgbColor': {'red': 0.0, 'green': 0.0, 'blue': 1.0}}
            }
        },
        'fields': 'foregroundColor'
    }
}
```

**For complete API code for all 5 colors, see `color-coding-reference.md`**
```

**Savings:** ~80 lines

### Phase 4: Reorganize Sections (LOW PRIORITY)

#### New Structure:
```markdown
1. When to Use This Skill
2. Core Workflow (summary + cross-reference)
3. Professional Standards
   - ANALYZE FIRST
   - EXTRACT INSIGHTS, DON'T DUMP
   - SYNTHESIZE TO MATCH
   - Professional Editor Mindset (condensed)
4. Color Coding System (condensed with reference)
5. Review Checklist (MANDATORY) - complete
6. Complete Example (The Transformation)
7. Working with Tabs (summary + reference)
8. Working with Structures (summary + reference)
9. Technical Setup (brief + reference)
10. Workflow Checklist (detailed)
11. Troubleshooting
    - File Format Detection (Word vs Google Docs)
    - Error Handling
    - Known Limitations
    - Common Patterns by Document Type
12. Success Metrics
```

## Files to Create

1. **tabs-reference.md** (~280 lines)
   - Complete tabs documentation
   - All API examples
   - Tab detection patterns
   - Common mistakes

2. **document-structures-reference.md** (~200 lines)
   - Structure detection
   - Insertion patterns
   - Synthesis by structure type
   - Code examples

3. **color-coding-reference.md** (~120 lines)
   - All 5 Python API examples
   - Visual pattern examples
   - Complete implementation guide

4. **technical-setup.md** (~50 lines)
   - OAuth setup steps
   - Installation
   - Usage in conversation
   - MergeOptions reference

## Expected Results

**Before:**
- Main skill: 1,242 lines (~4,000-5,000 tokens)
- No reference files
- Lots of redundancy
- Technical details mixed with behavioral guidance

**After:**
- Main skill: ~750 lines (~3,000 tokens)
- 4 reference files: ~650 lines total
- No redundancy
- Clear separation: behavior vs technical reference
- Easy to navigate

**Token savings:** ~25-30% in main skill file
**Organization:** Much clearer, easier to scan
**Maintainability:** Each concern in its own file

## Execution Order

1. ✅ Create audit-findings.md (DONE)
2. ✅ Create this REORGANIZATION-PLAN.md (DONE)
3. Remove duplicates (Phase 1) - Start here next
4. Extract tabs reference (Phase 2.1)
5. Extract structures reference (Phase 2.2)
6. Condense color coding (Phase 3)
7. Reorganize sections (Phase 4)
8. Create cross-references throughout
9. Test with subagent to verify organization
10. Update UPDATES-SUMMARY.md with reorganization details
