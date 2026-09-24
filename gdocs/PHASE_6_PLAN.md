# Phase 6: Table Manipulation & Management

**Date:** 2025-11-19
**Status:** Ready to implement
**Prerequisites:** Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ Phase 4 ✅ Phase 5 ✅

## Overview

Phase 6 adds comprehensive table manipulation capabilities to the gdocs skill, enabling creation, modification, and deletion of tables within Google Docs. This transforms the skill from "text-only editing" to "full document structure manipulation."

## Current State

### ✅ What We Have (Read-Only)
```python
# Can search for text within tables
if 'table' in element:
    for row in element['table'].get('tableRows', []):
        for cell in row.get('tableCells', []):
            # Search cell content
```

### ❌ What's Missing (All Table Write Operations)
- Create new tables
- Insert/delete rows
- Insert/delete columns
- Update cell content
- Merge/split cells
- Table styling/formatting
- Delete entire tables

### ⚠️ Current SKILL.md Claims (NOT IMPLEMENTED)
The SKILL.md mentions:
- `InsertTableRowRequest` → `InsertTextRequest` into cells
- Table synthesis patterns

**Reality:** These are NOT implemented in the codebase.

## User Value

### Before Phase 6
```python
# User has to manually create tables in Google Docs
# No programmatic table manipulation
# Cannot synthesize tabular data from meeting notes
```

### After Phase 6
```python
# Example 1: Create comparison table from meeting notes
table_manager.create_table(
    doc_url=doc_url,
    rows=4,
    columns=3,
    location_section="Feature Comparison",
    headers=["Feature", "Current", "Proposed"],
    data=[
        ["AI Prioritization", "None", "GPT-4 based"],
        ["Collaboration", "Limited", "Real-time"],
        ["Mobile Support", "Basic", "Full native"]
    ]
)

# Example 2: Add row to existing table
table_manager.insert_row(
    doc_url=doc_url,
    table_index=0,
    row_position=2,
    cell_data=["Location Reminders", "None", "GPS-based"]
)

# Example 3: Update specific cell
table_manager.update_cell(
    doc_url=doc_url,
    table_index=0,
    row=1,
    column=2,
    content="Updated: Real-time sync"
)
```

## Google Docs API Table Operations

### Available Request Types

Based on official Google Docs API v1 documentation:

#### 1. InsertTableRequest
```json
{
  "insertTable": {
    "rows": 3,
    "columns": 4,
    "location": {
      "index": 1,
      "tabId": "optional_tab_id"
    }
  }
}
```
**Purpose:** Create new table with specified dimensions

#### 2. InsertTableRowRequest
```json
{
  "insertTableRow": {
    "tableCellLocation": {
      "tableStartLocation": { "index": 10 },
      "rowIndex": 1,
      "columnIndex": 0
    },
    "insertBelow": true
  }
}
```
**Purpose:** Insert row above or below specified cell

#### 3. DeleteTableRowRequest
```json
{
  "deleteTableRow": {
    "tableCellLocation": {
      "tableStartLocation": { "index": 10 },
      "rowIndex": 2,
      "columnIndex": 0
    }
  }
}
```
**Purpose:** Delete row at specified location

#### 4. InsertTableColumnRequest
```json
{
  "insertTableColumn": {
    "tableCellLocation": {
      "tableStartLocation": { "index": 10 },
      "rowIndex": 0,
      "columnIndex": 1
    },
    "insertRight": true
  }
}
```
**Purpose:** Insert column left or right of specified cell

#### 5. DeleteTableColumnRequest
```json
{
  "deleteTableColumn": {
    "tableCellLocation": {
      "tableStartLocation": { "index": 10 },
      "rowIndex": 0,
      "columnIndex": 2
    }
  }
}
```
**Purpose:** Delete column at specified location

#### 6. InsertTextRequest (for cell content)
```json
{
  "insertText": {
    "location": {
      "index": 15  // Index within table cell
    },
    "text": "Cell content"
  }
}
```
**Purpose:** Add/update text within table cells

#### 7. DeleteContentRangeRequest (for entire table)
```json
{
  "deleteContentRange": {
    "range": {
      "startIndex": 10,
      "endIndex": 150  // Covers entire table
    }
  }
}
```
**Purpose:** Delete entire table by removing content range

### Key API Challenges

1. **Index Tracking:** Tables insert extra characters, requiring careful index management
2. **Cell Location:** Must specify table start location + row/column indices
3. **Tab Support:** Must include tabId when working with multi-tab documents
4. **Content Structure:** Table cells contain structural elements (paragraphs, etc.)

## Phase 6 Architecture

### New Module: TableManager
**File:** `scripts/table_manager.py`

```python
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class TableLocation:
    """Represents a table's location in document."""
    table_index: int  # Which table in document (0-indexed)
    start_index: int  # Character index where table starts
    end_index: int    # Character index where table ends
    rows: int
    columns: int

@dataclass
class CellLocation:
    """Represents a specific cell location."""
    table_start_index: int
    row_index: int
    column_index: int
    cell_start_index: int  # Character index within cell
    cell_end_index: int

class TableManager:
    """Manages table creation, modification, and deletion."""

    def __init__(self, editor):
        """
        Initialize table manager.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor

    # ========== Table Discovery ==========

    def find_tables(
        self,
        doc_id: str,
        tab_id: Optional[str] = None
    ) -> List[TableLocation]:
        """
        Find all tables in document.

        Returns:
            List of TableLocation objects
        """

    def get_table_at_index(
        self,
        doc_id: str,
        table_index: int,
        tab_id: Optional[str] = None
    ) -> Optional[TableLocation]:
        """
        Get specific table by index (0-based).
        """

    def find_cell_location(
        self,
        doc_id: str,
        table_index: int,
        row: int,
        column: int,
        tab_id: Optional[str] = None
    ) -> Optional[CellLocation]:
        """
        Find exact indices for a specific cell.

        Returns:
            CellLocation with all index information
        """

    # ========== Table Creation ==========

    def create_table(
        self,
        doc_url: str,
        rows: int,
        columns: int,
        location_index: Optional[int] = None,
        section: Optional[str] = None,
        headers: Optional[List[str]] = None,
        data: Optional[List[List[str]]] = None,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new table with optional headers and data.

        Args:
            doc_url: Google Doc URL or ID
            rows: Number of rows
            columns: Number of columns
            location_index: Specific index to insert (optional)
            section: Section name to insert into (optional)
            headers: List of header values (optional)
            data: List of row data (optional)
            tab_id: Tab ID for multi-tab docs (optional)

        Returns:
            {
                'success': bool,
                'table_location': TableLocation,
                'message': str
            }

        Example:
            result = table_manager.create_table(
                doc_url=url,
                rows=4,
                columns=3,
                section="Feature Comparison",
                headers=["Feature", "Current", "Proposed"],
                data=[
                    ["AI Help", "None", "GPT-4"],
                    ["Sync", "Daily", "Real-time"],
                    ["Mobile", "Basic", "Full"]
                ]
            )
        """

    # ========== Row Operations ==========

    def insert_row(
        self,
        doc_url: str,
        table_index: int,
        row_position: int,
        insert_below: bool = True,
        cell_data: Optional[List[str]] = None,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Insert a row into existing table.

        Args:
            doc_url: Google Doc URL or ID
            table_index: Which table (0-indexed)
            row_position: Insert relative to this row
            insert_below: True to insert below, False for above
            cell_data: Optional data for new row cells
            tab_id: Tab ID for multi-tab docs

        Returns:
            {
                'success': bool,
                'new_row_index': int,
                'message': str
            }
        """

    def delete_row(
        self,
        doc_url: str,
        table_index: int,
        row_index: int,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete a row from table.
        """

    # ========== Column Operations ==========

    def insert_column(
        self,
        doc_url: str,
        table_index: int,
        column_position: int,
        insert_right: bool = True,
        cell_data: Optional[List[str]] = None,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Insert a column into existing table.
        """

    def delete_column(
        self,
        doc_url: str,
        table_index: int,
        column_index: int,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete a column from table.
        """

    # ========== Cell Operations ==========

    def update_cell(
        self,
        doc_url: str,
        table_index: int,
        row: int,
        column: int,
        content: str,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update content of a specific cell.

        Process:
        1. Find cell location (indices)
        2. Delete existing cell content
        3. Insert new content

        Args:
            doc_url: Google Doc URL or ID
            table_index: Which table (0-indexed)
            row: Row index (0-indexed)
            column: Column index (0-indexed)
            content: New cell content
            tab_id: Tab ID for multi-tab docs

        Returns:
            {
                'success': bool,
                'cell_location': CellLocation,
                'message': str
            }
        """

    def get_cell_content(
        self,
        doc_url: str,
        table_index: int,
        row: int,
        column: int,
        tab_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Read content from a specific cell.
        """

    def update_cells_bulk(
        self,
        doc_url: str,
        table_index: int,
        updates: List[Dict[str, Any]],
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update multiple cells in one batch operation.

        Args:
            updates: [
                {'row': 0, 'column': 0, 'content': 'Header 1'},
                {'row': 1, 'column': 2, 'content': 'Data'},
                ...
            ]

        Returns:
            {
                'success': bool,
                'cells_updated': int,
                'failed': List[Dict]
            }
        """

    # ========== Table Deletion ==========

    def delete_table(
        self,
        doc_url: str,
        table_index: int,
        tab_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete entire table from document.

        Process:
        1. Find table boundaries (start/end indices)
        2. Use DeleteContentRangeRequest

        Args:
            doc_url: Google Doc URL or ID
            table_index: Which table to delete (0-indexed)
            tab_id: Tab ID for multi-tab docs

        Returns:
            {
                'success': bool,
                'message': str
            }
        """

    # ========== Helper Methods ==========

    def _build_table_cell_location(
        self,
        table_start_index: int,
        row_index: int,
        column_index: int
    ) -> Dict[str, Any]:
        """
        Build tableCellLocation dict for API requests.

        Returns:
            {
                'tableStartLocation': {'index': table_start_index},
                'rowIndex': row_index,
                'columnIndex': column_index
            }
        """

    def _extract_table_data(
        self,
        table_element: Dict[str, Any]
    ) -> List[List[str]]:
        """
        Extract all cell content from table element.

        Returns:
            2D array of cell contents
        """

    def _format_as_table_string(
        self,
        table_data: List[List[str]]
    ) -> str:
        """
        Format table data as human-readable string.

        For debugging and display purposes.
        """
```

### Integration with ContentInserter

**Enhanced merge_content for tables:**
```python
def merge_content(
    self,
    doc_url: str,
    content: str,
    section: Optional[str] = None,
    options: Optional[MergeOptions] = None
) -> Dict[str, Any]:
    """Enhanced with table synthesis."""

    # [Existing content analysis and synthesis]

    # NEW - Phase 6: Detect if content should be a table
    if self._should_create_table(content, document_context):
        # Extract table structure from content
        table_data = self._extract_table_structure(content)

        # Create table instead of text
        result = self.table_manager.create_table(
            doc_url=doc_url,
            rows=len(table_data),
            columns=len(table_data[0]),
            section=section,
            headers=table_data[0],
            data=table_data[1:],
            tab_id=tab_id
        )

        return result

    # [Existing text insertion logic]
```

### New MergeOptions Fields
```python
@dataclass
class MergeOptions:
    # [Existing fields]

    # NEW - Phase 6:
    prefer_table_format: bool = False  # Force table creation
    table_has_headers: bool = True     # First row is headers
    table_style: Optional[str] = None  # Future: table styling
```

## Implementation Tasks

### Task 1: Implement TableManager Core
**File:** `scripts/table_manager.py`

**Estimated Time:** 3-4 hours

#### Subtasks:
1. Create TableManager class structure
2. Implement `find_tables()` - Parse document for table elements
3. Implement `get_table_at_index()` - Get specific table
4. Implement `find_cell_location()` - Calculate cell indices
5. Add helper methods for index calculations

**Test Coverage:**
- [ ] Can find all tables in document
- [ ] Can get table by index
- [ ] Can locate specific cells
- [ ] Index calculations are accurate

### Task 2: Implement Table Creation
**File:** `scripts/table_manager.py`

**Estimated Time:** 2-3 hours

#### Subtasks:
1. Implement `create_table()` base functionality
2. Add header row support
3. Add data population support
4. Add section-based insertion
5. Add tab support

**Test Coverage:**
- [ ] Can create empty table
- [ ] Can create table with headers
- [ ] Can create table with data
- [ ] Can insert into specific section
- [ ] Works with multi-tab documents

### Task 3: Implement Row Operations
**File:** `scripts/table_manager.py`

**Estimated Time:** 2 hours

#### Subtasks:
1. Implement `insert_row()` with data
2. Implement `delete_row()`
3. Add batch row operations

**Test Coverage:**
- [ ] Can insert row above
- [ ] Can insert row below
- [ ] Can insert row with data
- [ ] Can delete row
- [ ] Indices remain accurate after operations

### Task 4: Implement Column Operations
**File:** `scripts/table_manager.py`

**Estimated Time:** 2 hours

#### Subtasks:
1. Implement `insert_column()` with data
2. Implement `delete_column()`
3. Add batch column operations

**Test Coverage:**
- [ ] Can insert column left
- [ ] Can insert column right
- [ ] Can insert column with data
- [ ] Can delete column
- [ ] Indices remain accurate after operations

### Task 5: Implement Cell Operations
**File:** `scripts/table_manager.py`

**Estimated Time:** 2-3 hours

#### Subtasks:
1. Implement `get_cell_content()` - Read cell
2. Implement `update_cell()` - Write cell
3. Implement `update_cells_bulk()` - Batch updates
4. Handle cell content structure (paragraphs, etc.)

**Test Coverage:**
- [ ] Can read cell content
- [ ] Can update cell content
- [ ] Can batch update multiple cells
- [ ] Handles empty cells
- [ ] Preserves cell formatting

### Task 6: Implement Table Deletion
**File:** `scripts/table_manager.py`

**Estimated Time:** 1 hour

#### Subtasks:
1. Implement `delete_table()`
2. Add safety checks (confirmation)
3. Handle edge cases

**Test Coverage:**
- [ ] Can delete table
- [ ] Properly updates document structure
- [ ] Doesn't affect other content

### Task 7: Integrate with ContentInserter
**File:** `scripts/content_inserter.py`

**Estimated Time:** 2-3 hours

#### Subtasks:
1. Add table detection in `merge_content()`
2. Implement `_should_create_table()` logic
3. Implement `_extract_table_structure()` from content
4. Add table synthesis to workflow

**Test Coverage:**
- [ ] Detects when content should be table
- [ ] Correctly extracts table structure
- [ ] Creates appropriate table
- [ ] Handles non-table content correctly

### Task 8: Update SKILL.md Documentation
**File:** `SKILL.md`

**Estimated Time:** 1-2 hours

#### Subtasks:
1. Add "Working with Tables" section
2. Document all table operations
3. Add table synthesis patterns
4. Add examples for common use cases
5. Update "Document Structures" section

**Sections to Add:**
- Table creation patterns
- Row/column management
- Cell content updates
- Table synthesis from meeting notes
- Common table patterns by document type

### Task 9: Create Examples
**Files:** `examples/table_*.py`

**Estimated Time:** 2 hours

#### Examples to Create:
1. `examples/create_comparison_table.py` - Feature comparison
2. `examples/update_project_timeline.py` - Update table rows
3. `examples/build_budget_table.py` - Financial table
4. `examples/synthesize_meeting_table.py` - Meeting to table

### Task 10: Testing
**File:** `tests/test_table_manager.py`

**Estimated Time:** 3-4 hours

#### Test Suites:
1. Table discovery tests
2. Table creation tests
3. Row operation tests
4. Column operation tests
5. Cell operation tests
6. Table deletion tests
7. Integration tests with ContentInserter
8. Edge case tests

## Testing Strategy

### Test Document Setup
```python
# Create test document with known table structure
doc_id = editor.create_document("Table Manager Tests")

# Create initial table for testing
table_manager.create_table(
    doc_url=doc_id,
    rows=3,
    columns=3,
    headers=["Col1", "Col2", "Col3"],
    data=[
        ["A1", "B1", "C1"],
        ["A2", "B2", "C2"]
    ]
)
```

### Test 1: Create Table
```python
def test_create_table_with_data():
    """Test creating table with headers and data."""
    result = table_manager.create_table(
        doc_url=test_doc_id,
        rows=4,
        columns=3,
        section="Test Section",
        headers=["Feature", "Status", "Owner"],
        data=[
            ["Auth", "Done", "Alice"],
            ["API", "In Progress", "Bob"],
            ["UI", "Planning", "Charlie"]
        ]
    )

    assert result['success'] is True
    assert result['table_location'].rows == 4
    assert result['table_location'].columns == 3

    # Verify content
    cell_content = table_manager.get_cell_content(
        doc_url=test_doc_id,
        table_index=0,
        row=0,
        column=0
    )
    assert cell_content == "Feature"
```

### Test 2: Insert Row
```python
def test_insert_row_with_data():
    """Test inserting row into existing table."""
    result = table_manager.insert_row(
        doc_url=test_doc_id,
        table_index=0,
        row_position=1,
        insert_below=True,
        cell_data=["Database", "Review", "David"]
    )

    assert result['success'] is True

    # Verify new row content
    cell_content = table_manager.get_cell_content(
        doc_url=test_doc_id,
        table_index=0,
        row=2,  # New row index
        column=0
    )
    assert cell_content == "Database"
```

### Test 3: Update Cell
```python
def test_update_cell_content():
    """Test updating specific cell."""
    result = table_manager.update_cell(
        doc_url=test_doc_id,
        table_index=0,
        row=1,
        column=1,
        content="Completed"
    )

    assert result['success'] is True

    # Verify update
    cell_content = table_manager.get_cell_content(
        doc_url=test_doc_id,
        table_index=0,
        row=1,
        column=1
    )
    assert cell_content == "Completed"
```

### Test 4: Bulk Cell Update
```python
def test_bulk_cell_update():
    """Test updating multiple cells at once."""
    updates = [
        {'row': 1, 'column': 1, 'content': 'Completed'},
        {'row': 2, 'column': 1, 'content': 'In Review'},
        {'row': 3, 'column': 1, 'content': 'Started'}
    ]

    result = table_manager.update_cells_bulk(
        doc_url=test_doc_id,
        table_index=0,
        updates=updates
    )

    assert result['success'] is True
    assert result['cells_updated'] == 3
```

### Test 5: Delete Row/Column
```python
def test_delete_row():
    """Test deleting a row."""
    result = table_manager.delete_row(
        doc_url=test_doc_id,
        table_index=0,
        row_index=2
    )

    assert result['success'] is True

    # Verify table now has one less row
    table = table_manager.get_table_at_index(test_doc_id, 0)
    assert table.rows == 3  # Was 4, now 3
```

### Test 6: Table Synthesis
```python
def test_synthesize_meeting_notes_to_table():
    """Test converting meeting notes to table."""
    meeting_notes = """
    Feature Requests from Customer Meeting:
    - AI Prioritization: Not available currently, want GPT-4 based
    - Collaboration: Limited sharing, need real-time
    - Mobile App: Basic features, want full native support
    """

    result = inserter.merge_content(
        doc_url=test_doc_id,
        content=meeting_notes,
        section="Feature Comparison",
        options=MergeOptions(
            prefer_table_format=True,
            table_has_headers=True
        )
    )

    assert result['success'] is True
    assert 'table_location' in result

    # Verify table was created with correct structure
    table = table_manager.get_table_at_index(test_doc_id, 0)
    assert table.rows == 4  # Header + 3 data rows
    assert table.columns == 3  # Feature, Current, Requested
```

## Example Scripts

### Example 1: Create Feature Comparison Table
**File:** `examples/create_comparison_table.py`

```python
#!/usr/bin/env python3
"""Create a feature comparison table from meeting notes."""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.table_manager import TableManager

editor = GoogleDocsEditor()
table_manager = TableManager(editor)

doc_url = "https://docs.google.com/document/d/DOC_ID/edit"

# Create comparison table
result = table_manager.create_table(
    doc_url=doc_url,
    rows=5,
    columns=3,
    section="Competitive Analysis",
    headers=["Feature", "Competitor A", "Our Product"],
    data=[
        ["AI Features", "Basic", "Advanced GPT-4"],
        ["Real-time Sync", "Yes", "Yes"],
        ["Mobile App", "iOS only", "iOS + Android"],
        ["Price", "$9.99/mo", "$7.99/mo"]
    ]
)

print(f"✅ Created comparison table")
print(f"   Location: {result['table_location'].start_index}")
print(f"   Dimensions: {result['table_location'].rows}x{result['table_location'].columns}")
```

### Example 2: Update Project Timeline Table
**File:** `examples/update_project_timeline.py`

```python
#!/usr/bin/env python3
"""Update project timeline table with latest status."""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.table_manager import TableManager

editor = GoogleDocsEditor()
table_manager = TableManager(editor)

doc_url = "PROJECT_DOC_URL"

# Assume table already exists at index 0
# Update multiple cells with project status
updates = [
    {'row': 1, 'column': 2, 'content': 'Completed'},  # Phase 1 status
    {'row': 2, 'column': 2, 'content': 'In Progress'}, # Phase 2 status
    {'row': 3, 'column': 2, 'content': 'Blocked'},     # Phase 3 status
    {'row': 1, 'column': 3, 'content': '2025-11-15'},  # Phase 1 completion
]

result = table_manager.update_cells_bulk(
    doc_url=doc_url,
    table_index=0,
    updates=updates
)

print(f"✅ Updated {result['cells_updated']} cells")
```

### Example 3: Meeting Notes to Table
**File:** `examples/synthesize_meeting_table.py`

```python
#!/usr/bin/env python3
"""Synthesize meeting notes into feature request table."""

from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions

editor = GoogleDocsEditor()
inserter = ContentInserter(editor)

meeting_notes = """
Customer Feedback Meeting - 2025-11-19

Key Feature Requests:
1. AI-powered task prioritization - currently don't have this
2. Better collaboration features - current sharing is too limited
3. Native mobile app - web app doesn't work well on phones
4. Integration with Slack - currently manual
5. Custom workflows - one-size-fits-all now
"""

# Claude will synthesize this into a table
result = inserter.merge_content(
    doc_url="DOC_URL",
    content=meeting_notes,
    section="Feature Roadmap",
    options=MergeOptions(
        prefer_table_format=True,
        table_has_headers=True,
        add_source_comment=True,
        source_description="customer feedback meeting, 2025-11-19"
    )
)

print(f"✅ Created feature request table from meeting notes")
```

## Success Metrics

### Technical ✅
- [ ] All table CRUD operations working
- [ ] Index tracking accurate
- [ ] Tab support working
- [ ] Batch operations optimized
- [ ] Error handling robust

### User Value ✅
- [ ] Can create tables from meeting notes
- [ ] Can update existing tables programmatically
- [ ] Time savings for table creation/updates
- [ ] Professional table formatting
- [ ] Source attribution on synthesized tables

### Quality ✅
- [ ] Tables match document style
- [ ] Proper formatting preserved
- [ ] Cell content well-formatted
- [ ] Natural integration with document flow

## Documentation Updates

### SKILL.md Updates

Add new section: **Working with Tables**

```markdown
## Working with Tables

### Table Creation Patterns

#### From Meeting Notes to Comparison Table
**Input:** Meeting notes with feature requests
**Output:** Professional comparison table

**Synthesis Pattern:**
1. Identify tabular data in notes
2. Extract column structure (Feature, Current, Proposed)
3. Create table with headers
4. Populate with synthesized rows
5. Add source attribution comment

#### Timeline Tables
**Use Case:** Project timelines, roadmaps, schedules
**Pattern:** Milestone | Date | Owner | Status

#### Budget/Financial Tables
**Use Case:** Budget proposals, financial reports
**Pattern:** Item | Cost | Category | Notes

### Table Operations

#### Creating Tables
[Examples of create_table() usage]

#### Updating Tables
[Examples of insert_row(), update_cell(), etc.]

#### Table Synthesis
[Examples of meeting notes → tables]

### Common Table Patterns by Document Type

**Executive Proposal:**
- Feature comparison tables
- Budget summaries
- Timeline/roadmap tables

**Technical Specification:**
- API endpoint tables
- Parameter reference tables
- Error code tables

**Project Plan:**
- Task assignment tables
- Timeline tables
- Resource allocation tables

**Meeting Notes:**
- Action item tables
- Decision log tables
- Attendee tables
```

### Add Table Examples to Skill
- Feature comparison tables
- Project timeline tables
- Budget/cost tables
- Meeting action items table

## Timeline

**Total Estimated Time:** 18-22 hours

### Week 1 (Core Implementation)
- Day 1-2: TableManager core + table discovery (4-5 hours)
- Day 3: Table creation (2-3 hours)
- Day 4: Row/column operations (4 hours)
- Day 5: Cell operations + deletion (3-4 hours)

### Week 2 (Integration & Testing)
- Day 1: ContentInserter integration (2-3 hours)
- Day 2: Testing suite (3-4 hours)
- Day 3: Examples + documentation (3-4 hours)
- Day 4: Final testing + polish (2-3 hours)

## Risks & Mitigations

### Risk 1: Index Tracking Complexity
**Risk:** Tables insert extra characters, making index tracking difficult
**Mitigation:**
- Comprehensive helper methods
- Extensive testing
- Clear documentation of index calculations

### Risk 2: API Limitations
**Risk:** API may not support all desired operations
**Mitigation:**
- Research API thoroughly before implementation
- Have fallback strategies
- Document limitations clearly

### Risk 3: Performance
**Risk:** Batch operations on large tables may be slow
**Mitigation:**
- Optimize batch update logic
- Implement pagination for large operations
- Add progress indicators

### Risk 4: Tab Support Complexity
**Risk:** Multi-tab documents add complexity
**Mitigation:**
- Build on existing tab support from Phase 5
- Test thoroughly with multi-tab documents
- Clear error messages for tab issues

## Future Enhancements (Phase 7+)

1. **Table Styling**
   - Border styles
   - Cell background colors
   - Header row styling
   - Alternating row colors

2. **Cell Merging/Splitting**
   - Merge cells horizontally
   - Merge cells vertically
   - Split merged cells

3. **Advanced Operations**
   - Sort table rows
   - Filter table data
   - Transpose table
   - Copy table structure

4. **Smart Table Templates**
   - Pre-defined table templates by use case
   - Template library (comparison, timeline, budget, etc.)
   - Custom template creation

5. **Table Extraction & Export**
   - Extract table as CSV
   - Extract table as JSON
   - Export to spreadsheet

## Conclusion

Phase 6 transforms the gdocs skill into a comprehensive document manipulation tool, adding full table support to complement the existing text synthesis capabilities.

**Ready to Implement:** All prerequisites met, API research complete

**User Value:** Massive - enables programmatic table creation/updates

**Complexity:** Medium-High - Index tracking is tricky but manageable

**Recommendation:** Proceed with implementation in 2-week sprint

---

**Next Steps:**
1. Create `scripts/table_manager.py` skeleton
2. Implement table discovery (find_tables)
3. Build table creation (create_table)
4. Iterate through remaining operations
5. Test thoroughly with real documents
6. Update documentation

**Last Updated:** 2025-11-19
