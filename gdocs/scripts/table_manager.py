#!/usr/bin/env python3
"""
Table Management for Google Docs.

Provides comprehensive table manipulation capabilities including:
- Table discovery and navigation
- Table creation with headers and data
- Row and column operations (insert, delete)
- Cell content management (read, update, bulk operations)
- Table deletion

Usage:
    from scripts.gdocs_editor import GoogleDocsEditor
    from scripts.table_manager import TableManager

    editor = GoogleDocsEditor()
    table_manager = TableManager(editor)

    # Create a table
    result = table_manager.create_table(
        doc_url="https://docs.google.com/document/d/DOC_ID/edit",
        rows=4,
        columns=3,
        headers=["Feature", "Current", "Proposed"],
        data=[
            ["AI Help", "None", "GPT-4"],
            ["Sync", "Daily", "Real-time"],
            ["Mobile", "Basic", "Full native"]
        ]
    )
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TableLocation:
    """
    Represents a table's location and dimensions in a Google Doc.

    Attributes:
        table_index: Zero-based index of table in document (0 = first table)
        start_index: Character index where table starts in document
        end_index: Character index where table ends in document
        rows: Number of rows in the table
        columns: Number of columns in the table
    """
    table_index: int
    start_index: int
    end_index: int
    rows: int
    columns: int


@dataclass
class CellLocation:
    """
    Represents a specific cell's location within a table.

    Attributes:
        table_start_index: Character index where the table starts
        row_index: Zero-based row index within table
        column_index: Zero-based column index within table
        cell_start_index: Character index where cell content starts
        cell_end_index: Character index where cell content ends
    """
    table_start_index: int
    row_index: int
    column_index: int
    cell_start_index: int
    cell_end_index: int


class TableManager:
    """
    Manages table creation, modification, and deletion in Google Docs.

    This class provides comprehensive table manipulation capabilities using
    the Google Docs API v1. All operations handle index tracking carefully
    as tables insert structural characters that affect document indices.

    Example:
        >>> editor = GoogleDocsEditor()
        >>> tm = TableManager(editor)
        >>> tables = tm.find_tables("DOC_ID")
        >>> print(f"Found {len(tables)} tables")
    """

    def __init__(self, editor):
        """
        Initialize the TableManager.

        Args:
            editor: GoogleDocsEditor instance with authenticated API access
        """
        self.editor = editor

    # ========== Table Discovery Methods ==========
    # These methods will be implemented in subsequent tasks

    def find_tables(
        self,
        doc_id: str,
        tab_id: Optional[str] = None
    ) -> List[TableLocation]:
        """
        Find all tables in document.

        Parses document structure to locate all table elements and extract
        their dimensions and positions.

        Args:
            doc_id: Google Doc ID
            tab_id: Optional tab ID for multi-tab documents

        Returns:
            List of TableLocation objects, one for each table found

        Example:
            >>> tables = table_manager.find_tables("DOC_ID")
            >>> for i, table in enumerate(tables):
            ...     print(f"Table {i}: {table.rows}x{table.columns}")
        """
        # Get document with tab support
        document = self.editor.get_document(doc_id, include_tabs_content=True)

        # Get body from appropriate tab
        body = self.editor.get_tab_body(document, tab_id)
        content_elements = body.get('content', [])

        tables = []
        table_index = 0

        # Parse content for table elements
        for element in content_elements:
            if 'table' in element:
                table_element = element['table']

                # Extract table dimensions
                table_rows = table_element.get('tableRows', [])
                num_rows = len(table_rows)

                # Get column count from first row (all rows have same column count)
                num_columns = 0
                if table_rows:
                    first_row = table_rows[0]
                    table_cells = first_row.get('tableCells', [])
                    num_columns = len(table_cells)

                # Extract position indices
                start_index = element.get('startIndex', 0)
                end_index = element.get('endIndex', 0)

                # Create TableLocation object
                table_location = TableLocation(
                    table_index=table_index,
                    start_index=start_index,
                    end_index=end_index,
                    rows=num_rows,
                    columns=num_columns
                )

                tables.append(table_location)
                table_index += 1

        return tables

    def get_table_at_index(
        self,
        doc_id: str,
        table_index: int,
        tab_id: Optional[str] = None
    ) -> Optional[TableLocation]:
        """
        Get specific table by index (0-based).

        Args:
            doc_id: Google Doc ID
            table_index: Zero-based table index (0 = first table)
            tab_id: Optional tab ID for multi-tab documents

        Returns:
            TableLocation if found, None otherwise

        Example:
            >>> table = table_manager.get_table_at_index("DOC_ID", 0)
            >>> if table:
            ...     print(f"First table: {table.rows}x{table.columns}")
        """
        # Find all tables in document
        tables = self.find_tables(doc_id, tab_id)

        # Return table at specified index, or None if index out of range
        if 0 <= table_index < len(tables):
            return tables[table_index]
        return None

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

        Navigates document structure to locate a specific cell and extract
        its content boundaries. Critical for all cell read/update operations.

        Args:
            doc_id: Google Doc ID
            table_index: Zero-based table index
            row: Zero-based row index
            column: Zero-based column index
            tab_id: Optional tab ID for multi-tab documents

        Returns:
            CellLocation with all index information, or None if cell not found

        Example:
            >>> cell = table_manager.find_cell_location("DOC_ID", 0, 1, 2)
            >>> if cell:
            ...     print(f"Cell at row 1, col 2: indices {cell.cell_start_index}-{cell.cell_end_index}")
        """
        # Get document with tab support
        document = self.editor.get_document(doc_id, include_tabs_content=True)
        body = self.editor.get_tab_body(document, tab_id)
        content_elements = body.get('content', [])

        # Find the specified table
        current_table_index = 0
        for element in content_elements:
            if 'table' in element:
                if current_table_index == table_index:
                    # Found the target table
                    table_element = element['table']
                    table_start_index = element.get('startIndex', 0)
                    table_rows = table_element.get('tableRows', [])

                    # Validate row index
                    if row < 0 or row >= len(table_rows):
                        return None

                    # Get the target row
                    target_row = table_rows[row]
                    table_cells = target_row.get('tableCells', [])

                    # Validate column index
                    if column < 0 or column >= len(table_cells):
                        return None

                    # Get the target cell
                    target_cell = table_cells[column]

                    # Extract cell content boundaries
                    # Cell contains content array (usually paragraphs)
                    cell_content = target_cell.get('content', [])

                    if not cell_content:
                        # Empty cell - use cell structure indices
                        cell_start = target_cell.get('startIndex', 0)
                        cell_end = target_cell.get('endIndex', 0)
                    else:
                        # Cell has content - get first and last element indices
                        cell_start = cell_content[0].get('startIndex', 0)
                        cell_end = cell_content[-1].get('endIndex', 0)

                    return CellLocation(
                        table_start_index=table_start_index,
                        row_index=row,
                        column_index=column,
                        cell_start_index=cell_start,
                        cell_end_index=cell_end
                    )

                current_table_index += 1

        # Table not found
        return None

    # ========== Table Creation Methods ==========

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
            >>> result = table_manager.create_table(
            ...     doc_url=url,
            ...     rows=4,
            ...     columns=3,
            ...     headers=["Feature", "Current", "Proposed"],
            ...     data=[
            ...         ["AI Help", "None", "GPT-4"],
            ...         ["Sync", "Daily", "Real-time"],
            ...         ["Mobile", "Basic", "Full native"]
            ...     ]
            ... )
        """
        try:
            # Extract doc_id from URL
            doc_id = self.editor.extract_doc_id(doc_url)

            # Determine insertion location
            insert_index = location_index
            if insert_index is None:
                if section:
                    # Section-based insertion (Task 2.2)
                    insert_index = self._find_section_insertion_point(doc_id, section, tab_id)
                else:
                    # Default: insert at document end
                    document = self.editor.get_document(doc_id, include_tabs_content=True)
                    body = self.editor.get_tab_body(document, tab_id)
                    content = body.get('content', [])
                    if content:
                        # Insert before last element (usually document end marker)
                        insert_index = content[-1].get('endIndex', 1) - 1
                    else:
                        insert_index = 1

            # Build location dict with optional tab_id
            location = {'index': insert_index}
            if tab_id:
                location['tabId'] = tab_id

            # Build InsertTableRequest
            requests = [{
                'insertTable': {
                    'rows': rows,
                    'columns': columns,
                    'location': location
                }
            }]

            # Execute table creation
            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            # Find the newly created table to get its location
            tables = self.find_tables(doc_id, tab_id)

            # The new table should be at the insertion point
            # Find table that starts at or near insert_index
            new_table = None
            for table in tables:
                if table.start_index >= insert_index:
                    new_table = table
                    break

            if new_table is None and tables:
                # Fallback: use last table
                new_table = tables[-1]

            # Populate headers
            if headers and new_table:
                self._populate_header_row(doc_id, new_table, headers, tab_id)

            # Populate data
            if data and new_table:
                # Start from row 1 if we have headers, otherwise row 0
                start_row = 1 if headers else 0
                self._populate_table_data(doc_id, new_table, data, start_row, tab_id)

            return {
                'success': True,
                'table_location': new_table,
                'message': f'Table created successfully ({rows}x{columns})'
            }

        except Exception as e:
            return {
                'success': False,
                'table_location': None,
                'message': f'Failed to create table: {str(e)}'
            }

    def _find_section_insertion_point(
        self,
        doc_id: str,
        section_name: str,
        tab_id: Optional[str] = None
    ) -> int:
        """
        Find insertion point within a named section.

        Searches for a heading element whose text matches the section name,
        then returns an insertion point after that heading. If no matching
        section is found, returns document end as fallback.

        Args:
            doc_id: Google Doc ID
            section_name: Section heading to find (case-insensitive partial match)
            tab_id: Optional tab ID for multi-tab documents

        Returns:
            Character index for insertion after the section heading

        Example:
            >>> # Document has "## Project Timeline" heading at index 50
            >>> idx = table_manager._find_section_insertion_point("DOC_ID", "timeline")
            >>> # Returns index after heading (e.g., 65)
        """
        # Get document with tab support
        document = self.editor.get_document(doc_id, include_tabs_content=True)
        body = self.editor.get_tab_body(document, tab_id)
        content_elements = body.get('content', [])

        # Search for heading that matches section name
        for element in content_elements:
            if 'paragraph' in element:
                para = element['paragraph']
                para_style = para.get('paragraphStyle', {})
                named_style = para_style.get('namedStyleType', '')

                # Check if this is a heading
                if named_style.startswith('HEADING_'):
                    # Extract heading text
                    heading_text = self._extract_paragraph_text(para)

                    # Check for case-insensitive partial match
                    if section_name.lower() in heading_text.lower():
                        # Found matching section - return index after heading
                        # We want to insert after the heading paragraph
                        return element.get('endIndex', 0)

        # Section not found - return document end as fallback
        if content_elements:
            return content_elements[-1].get('endIndex', 1) - 1
        return 1

    def _extract_paragraph_text(self, paragraph: Dict[str, Any]) -> str:
        """
        Extract plain text from a paragraph element.

        Args:
            paragraph: Paragraph element from Google Docs API

        Returns:
            Plain text content without trailing newlines

        Example:
            >>> para = {'elements': [{'textRun': {'content': 'Hello World\\n'}}]}
            >>> text = table_manager._extract_paragraph_text(para)
            >>> # Returns: "Hello World"
        """
        elements = paragraph.get('elements', [])
        text_parts = []

        for elem in elements:
            if 'textRun' in elem:
                text_run = elem['textRun']
                text = text_run.get('content', '')
                text_parts.append(text)

        return ''.join(text_parts).rstrip('\n')

    def _populate_header_row(
        self,
        doc_id: str,
        table_location: TableLocation,
        headers: List[str],
        tab_id: Optional[str] = None
    ) -> None:
        """
        Populate the first row of a table with header values.

        Inserts header text into each cell of row 0 and applies bold formatting.
        If more headers are provided than columns exist, extra headers are ignored.
        If fewer headers are provided, remaining columns are left empty.

        Args:
            doc_id: Google Doc ID
            table_location: TableLocation object for the target table
            headers: List of header strings, one per column
            tab_id: Optional tab ID for multi-tab documents

        Example:
            >>> # Table created with 3 columns
            >>> headers = ["Feature", "Current", "Proposed"]
            >>> table_manager._populate_header_row(doc_id, table, headers)
            >>> # Header row now contains "Feature | Current | Proposed" (bold)
        """
        # Build requests for header population
        requests = []

        # Limit headers to available columns
        num_headers = min(len(headers), table_location.columns)

        for col_idx in range(num_headers):
            # Find cell location for header row (row 0)
            cell = self.find_cell_location(
                doc_id,
                table_location.table_index,
                row=0,
                column=col_idx,
                tab_id=tab_id
            )

            if cell:
                # Build location dict with optional tab_id
                location = {'index': cell.cell_start_index}
                if tab_id:
                    location['tabId'] = tab_id

                # Insert header text
                requests.append({
                    'insertText': {
                        'text': headers[col_idx],
                        'location': location
                    }
                })

                # Apply bold formatting to header text
                # Text range is from cell_start to cell_start + len(header)
                text_range = {
                    'startIndex': cell.cell_start_index,
                    'endIndex': cell.cell_start_index + len(headers[col_idx])
                }
                if tab_id:
                    text_range['tabId'] = tab_id

                requests.append({
                    'updateTextStyle': {
                        'range': text_range,
                        'textStyle': {
                            'bold': True
                        },
                        'fields': 'bold'
                    }
                })

        # Execute all requests in batch
        if requests:
            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

    def _populate_table_data(
        self,
        doc_id: str,
        table_location: TableLocation,
        data: List[List[str]],
        start_row: int = 0,
        tab_id: Optional[str] = None
    ) -> None:
        """
        Populate table rows with data.

        Inserts data into table cells starting from the specified row.
        Each row in the data list corresponds to a table row.
        Each element in a row corresponds to a column.

        Args:
            doc_id: Google Doc ID
            table_location: TableLocation object for the target table
            data: List of rows, where each row is a list of cell values
            start_row: Row index to start populating from (default 0)
            tab_id: Optional tab ID for multi-tab documents

        Example:
            >>> data = [
            ...     ["AI Help", "None", "GPT-4"],
            ...     ["Sync", "Daily", "Real-time"],
            ...     ["Mobile", "Basic", "Full native"]
            ... ]
            >>> table_manager._populate_table_data(doc_id, table, data, start_row=1)
            >>> # Rows 1-3 now contain the data (row 0 reserved for headers)
        """
        # Build requests for data population
        requests = []

        # Iterate through data rows
        for row_idx, row_data in enumerate(data):
            # Calculate actual table row (offset by start_row)
            table_row = start_row + row_idx

            # Skip if we've exceeded table rows
            if table_row >= table_location.rows:
                break

            # Limit columns to available columns
            num_columns = min(len(row_data), table_location.columns)

            for col_idx in range(num_columns):
                # Find cell location
                cell = self.find_cell_location(
                    doc_id,
                    table_location.table_index,
                    row=table_row,
                    column=col_idx,
                    tab_id=tab_id
                )

                if cell:
                    # Build location dict with optional tab_id
                    location = {'index': cell.cell_start_index}
                    if tab_id:
                        location['tabId'] = tab_id

                    # Insert cell text
                    cell_text = str(row_data[col_idx])  # Convert to string in case of numbers
                    requests.append({
                        'insertText': {
                            'text': cell_text,
                            'location': location
                        }
                    })

        # Execute all requests in batch
        if requests:
            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

    # ========== Helper Methods ==========

    def _build_table_cell_location(
        self,
        table_start_index: int,
        row_index: int,
        column_index: int
    ) -> Dict[str, Any]:
        """
        Build tableCellLocation dict for API requests.

        This helper creates the properly formatted tableCellLocation structure
        required by Google Docs API for row/column operations.

        Args:
            table_start_index: Character index where table starts
            row_index: Zero-based row index
            column_index: Zero-based column index

        Returns:
            Dictionary formatted for Google Docs API tableCellLocation
            Format: {
                'tableStartLocation': {'index': table_start_index},
                'rowIndex': row_index,
                'columnIndex': column_index
            }

        Example:
            >>> loc = table_manager._build_table_cell_location(10, 1, 2)
            >>> # Used in API requests like InsertTableRowRequest
        """
        return {
            'tableStartLocation': {
                'index': table_start_index
            },
            'rowIndex': row_index,
            'columnIndex': column_index
        }
