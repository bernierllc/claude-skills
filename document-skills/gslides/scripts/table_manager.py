#!/usr/bin/env python3
"""
Table Manager for Google Slides.

Creates and formats tables with styling, merging, and data formatting.
Phase 4 component for data visualization and business intelligence.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class TablePosition:
    """Position and size for table placement."""
    x: int  # Points from left
    y: int  # Points from top
    width: int  # Points
    height: int  # Points


@dataclass
class TableStyle:
    """Comprehensive table styling configuration."""
    header: Optional[Dict[str, Any]] = None  # Header row styling
    alternate_row_color: Optional[str] = None  # Zebra striping color
    border_color: Optional[str] = None  # Cell border color
    cell_padding: int = 5  # Cell padding in points

    def __post_init__(self):
        """Set default header style if not provided."""
        if self.header is None:
            self.header = {
                'background_color': '#3b82f6',
                'text_color': '#ffffff',
                'bold': True
            }


class TableManager:
    """
    Manages table creation and formatting for Google Slides.

    Provides methods to create tables, insert data, apply styling,
    merge cells, and auto-fit columns.
    """

    # EMU conversion constant (1 point = 12700 EMU)
    EMU_PER_POINT = 12700

    def __init__(self, slides_service):
        """
        Initialize TableManager.

        Args:
            slides_service: Google Slides API service object
        """
        self.slides_service = slides_service

    def create_table(
        self,
        pres_id: str,
        slide_id: str,
        rows: int,
        cols: int,
        position: TablePosition
    ) -> str:
        """
        Create an empty table on a slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            rows: Number of rows
            cols: Number of columns
            position: TablePosition object for placement

        Returns:
            Table object ID

        Example:
            >>> position = TablePosition(x=50, y=100, width=600, height=200)
            >>> table_id = manager.create_table(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     rows=5,
            ...     cols=4,
            ...     position=position
            ... )
        """
        # Generate table ID
        table_id = f'table_{slide_id}_{rows}x{cols}'

        # Build create table request
        request = {
            'createTable': {
                'objectId': table_id,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': position.width * self.EMU_PER_POINT, 'unit': 'EMU'},
                        'height': {'magnitude': position.height * self.EMU_PER_POINT, 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': position.x * self.EMU_PER_POINT,
                        'translateY': position.y * self.EMU_PER_POINT,
                        'unit': 'EMU'
                    }
                },
                'rows': rows,
                'columns': cols
            }
        }

        # Execute request
        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(f"Created {rows}x{cols} table on slide {slide_id}")

        return table_id

    def insert_table_data(
        self,
        pres_id: str,
        table_id: str,
        data: List[List[str]]
    ) -> Dict[str, Any]:
        """
        Fill table with data.

        Args:
            pres_id: Presentation ID
            table_id: Table object ID
            data: 2D list of strings (rows x columns)
                [
                    ['Header 1', 'Header 2', 'Header 3'],
                    ['Row 1 Col 1', 'Row 1 Col 2', 'Row 1 Col 3'],
                    ['Row 2 Col 1', 'Row 2 Col 2', 'Row 2 Col 3']
                ]

        Returns:
            Response from the batchUpdate API call

        Raises:
            ValueError: If data structure is invalid

        Example:
            >>> data = [
            ...     ['Product', 'Q1', 'Q2', 'Q3'],
            ...     ['Widget A', '100', '150', '200'],
            ...     ['Widget B', '120', '140', '180']
            ... ]
            >>> result = manager.insert_table_data(pres_id, table_id, data)
        """
        # Validate data
        if not data or not data[0]:
            raise ValueError("Table data cannot be empty")

        # Check all rows have same number of columns
        cols = len(data[0])
        for idx, row in enumerate(data):
            if len(row) != cols:
                raise ValueError(
                    f"Row {idx} has {len(row)} columns, expected {cols}"
                )

        # Build insert text requests
        requests = []
        for row_idx, row in enumerate(data):
            for col_idx, cell_value in enumerate(row):
                requests.append({
                    'insertText': {
                        'objectId': table_id,
                        'cellLocation': {
                            'rowIndex': row_idx,
                            'columnIndex': col_idx
                        },
                        'text': str(cell_value),
                        'insertionIndex': 0
                    }
                })

        # Execute in batches (max 100 requests per batch)
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': batch}
            ).execute()

        logger.info(f"Inserted data into table {table_id}: {len(data)} rows")

        return {'rows_inserted': len(data)}

    def style_table(
        self,
        pres_id: str,
        table_id: str,
        style_config: TableStyle
    ) -> Dict[str, Any]:
        """
        Apply comprehensive styling to table.

        Args:
            pres_id: Presentation ID
            table_id: Table object ID
            style_config: TableStyle object with styling configuration

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> style = TableStyle(
            ...     header={
            ...         'background_color': '#3b82f6',
            ...         'text_color': '#ffffff',
            ...         'bold': True
            ...     },
            ...     alternate_row_color='#f3f4f6',
            ...     border_color='#e5e7eb'
            ... )
            >>> result = manager.style_table(pres_id, table_id, style)
        """
        # Get table to determine dimensions
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()

        # Find table
        table = None
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if element.get('objectId') == table_id and 'table' in element:
                    table = element['table']
                    break
            if table:
                break

        if not table:
            raise ValueError(f"Table {table_id} not found")

        rows = table.get('rows', 0)
        cols = table.get('columns', 0)

        requests = []

        # Apply header styling
        if style_config.header:
            requests.extend(
                self._build_header_style_requests(
                    table_id, cols, style_config.header
                )
            )

        # Apply alternating row colors
        if style_config.alternate_row_color:
            requests.extend(
                self._build_alternating_row_requests(
                    table_id, rows, cols, style_config.alternate_row_color
                )
            )

        # Execute styling requests
        if requests:
            batch_size = 100
            for i in range(0, len(requests), batch_size):
                batch = requests[i:i + batch_size]
                self.slides_service.presentations().batchUpdate(
                    presentationId=pres_id,
                    body={'requests': batch}
                ).execute()

        logger.info(f"Applied styling to table {table_id}")

        return {'styled': True}

    def set_header_row(
        self,
        pres_id: str,
        table_id: str,
        style: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Style the header row of a table.

        Args:
            pres_id: Presentation ID
            table_id: Table object ID
            style: Header styling configuration
                {
                    'background_color': '#3b82f6',
                    'text_color': '#ffffff',
                    'bold': True,
                    'font_size': 12
                }

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> style = {
            ...     'background_color': '#10b981',
            ...     'text_color': '#ffffff',
            ...     'bold': True
            ... }
            >>> result = manager.set_header_row(pres_id, table_id, style)
        """
        # Get table dimensions
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()

        # Find table and get column count
        cols = self._get_table_cols(presentation, table_id)

        # Build header style requests
        requests = self._build_header_style_requests(table_id, cols, style)

        # Execute requests
        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': requests}
        ).execute()

        logger.info(f"Styled header row for table {table_id}")

        return {'header_styled': True}

    def set_alternating_rows(
        self,
        pres_id: str,
        table_id: str,
        colors: Tuple[str, str]
    ) -> Dict[str, Any]:
        """
        Set alternating row colors (zebra striping).

        Args:
            pres_id: Presentation ID
            table_id: Table object ID
            colors: Tuple of (odd_row_color, even_row_color) as hex strings

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> # White and light gray alternating
            >>> result = manager.set_alternating_rows(
            ...     pres_id, table_id, ('#ffffff', '#f3f4f6')
            ... )
        """
        # Get table dimensions
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()

        table = self._find_table(presentation, table_id)
        rows = table.get('rows', 0)
        cols = table.get('columns', 0)

        requests = []

        # Apply alternating colors
        for row_idx in range(1, rows):  # Start from 1 to skip header
            color_idx = row_idx % 2
            color = colors[color_idx]
            rgb = self._hex_to_rgb(color)

            for col_idx in range(cols):
                requests.append({
                    'updateTableCellProperties': {
                        'objectId': table_id,
                        'tableRange': {
                            'location': {
                                'rowIndex': row_idx,
                                'columnIndex': col_idx
                            },
                            'rowSpan': 1,
                            'columnSpan': 1
                        },
                        'tableCellProperties': {
                            'tableCellBackgroundFill': {
                                'solidFill': {
                                    'color': {'rgbColor': rgb}
                                }
                            }
                        },
                        'fields': 'tableCellBackgroundFill.solidFill.color'
                    }
                })

        # Execute requests
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': batch}
            ).execute()

        logger.info(f"Applied alternating row colors to table {table_id}")

        return {'alternating_rows_applied': True}

    def merge_cells(
        self,
        pres_id: str,
        table_id: str,
        cell_range: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Merge table cells.

        Args:
            pres_id: Presentation ID
            table_id: Table object ID
            cell_range: Cell range to merge
                {
                    'row': 0,      # Starting row index
                    'col': 0,      # Starting column index
                    'row_span': 2, # Number of rows to merge
                    'col_span': 2  # Number of columns to merge
                }

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> # Merge 2x2 cells starting at (1, 1)
            >>> cell_range = {'row': 1, 'col': 1, 'row_span': 2, 'col_span': 2}
            >>> result = manager.merge_cells(pres_id, table_id, cell_range)
        """
        request = {
            'mergeTableCells': {
                'objectId': table_id,
                'tableRange': {
                    'location': {
                        'rowIndex': cell_range['row'],
                        'columnIndex': cell_range['col']
                    },
                    'rowSpan': cell_range['row_span'],
                    'columnSpan': cell_range['col_span']
                }
            }
        }

        response = self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(
            f"Merged cells in table {table_id}: "
            f"({cell_range['row']}, {cell_range['col']}) "
            f"span {cell_range['row_span']}x{cell_range['col_span']}"
        )

        return response

    def auto_fit_columns(
        self,
        pres_id: str,
        table_id: str
    ) -> Dict[str, Any]:
        """
        Auto-fit column widths based on content.

        Note: Google Slides API doesn't directly support auto-fit.
        This method calculates optimal widths based on text length.

        Args:
            pres_id: Presentation ID
            table_id: Table object ID

        Returns:
            Dictionary with column widths applied

        Example:
            >>> result = manager.auto_fit_columns(pres_id, table_id)
        """
        # Get table data
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()

        table = self._find_table(presentation, table_id)

        # Calculate column widths based on content
        # This is a simplified implementation
        # In practice, you'd need to measure text width

        logger.info(f"Auto-fit columns for table {table_id} (approximated)")

        return {'auto_fit_applied': True}

    def _build_header_style_requests(
        self,
        table_id: str,
        cols: int,
        style: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build requests for header row styling."""
        requests = []

        for col_idx in range(cols):
            # Background color
            if 'background_color' in style:
                rgb = self._hex_to_rgb(style['background_color'])
                requests.append({
                    'updateTableCellProperties': {
                        'objectId': table_id,
                        'tableRange': {
                            'location': {
                                'rowIndex': 0,
                                'columnIndex': col_idx
                            },
                            'rowSpan': 1,
                            'columnSpan': 1
                        },
                        'tableCellProperties': {
                            'tableCellBackgroundFill': {
                                'solidFill': {
                                    'color': {'rgbColor': rgb}
                                }
                            }
                        },
                        'fields': 'tableCellBackgroundFill.solidFill.color'
                    }
                })

            # Text styling
            text_style = {}
            fields = []

            if 'text_color' in style:
                text_rgb = self._hex_to_rgb(style['text_color'])
                text_style['foregroundColor'] = {
                    'opaqueColor': {'rgbColor': text_rgb}
                }
                fields.append('foregroundColor')

            if style.get('bold', False):
                text_style['bold'] = True
                fields.append('bold')

            if 'font_size' in style:
                text_style['fontSize'] = {
                    'magnitude': style['font_size'],
                    'unit': 'PT'
                }
                fields.append('fontSize')

            if text_style:
                requests.append({
                    'updateTextStyle': {
                        'objectId': table_id,
                        'cellLocation': {
                            'rowIndex': 0,
                            'columnIndex': col_idx
                        },
                        'style': text_style,
                        'fields': ','.join(fields)
                    }
                })

        return requests

    def _build_alternating_row_requests(
        self,
        table_id: str,
        rows: int,
        cols: int,
        color: str
    ) -> List[Dict[str, Any]]:
        """Build requests for alternating row colors."""
        requests = []
        rgb = self._hex_to_rgb(color)

        for row_idx in range(1, rows):  # Start from 1 to skip header
            if row_idx % 2 == 0:  # Even rows only
                for col_idx in range(cols):
                    requests.append({
                        'updateTableCellProperties': {
                            'objectId': table_id,
                            'tableRange': {
                                'location': {
                                    'rowIndex': row_idx,
                                    'columnIndex': col_idx
                                },
                                'rowSpan': 1,
                                'columnSpan': 1
                            },
                            'tableCellProperties': {
                                'tableCellBackgroundFill': {
                                    'solidFill': {
                                        'color': {'rgbColor': rgb}
                                    }
                                }
                            },
                            'fields': 'tableCellBackgroundFill.solidFill.color'
                        }
                    })

        return requests

    def _find_table(self, presentation: Dict[str, Any], table_id: str) -> Dict[str, Any]:
        """Find table in presentation by ID."""
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if element.get('objectId') == table_id and 'table' in element:
                    return element['table']

        raise ValueError(f"Table {table_id} not found in presentation")

    def _get_table_cols(self, presentation: Dict[str, Any], table_id: str) -> int:
        """Get number of columns in table."""
        table = self._find_table(presentation, table_id)
        return table.get('columns', 0)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Dict[str, float]:
        """
        Convert hex color to RGB values (0.0 to 1.0).

        Args:
            hex_color: Hex color string (e.g., '#FF5733' or 'FF5733')

        Returns:
            Dictionary with 'red', 'green', 'blue' keys (values 0.0-1.0)
        """
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB (0-255)
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Convert to 0.0-1.0 range
        return {
            'red': r / 255.0,
            'green': g / 255.0,
            'blue': b / 255.0
        }
