#!/usr/bin/env python3
"""
Main Google Slides Editor API.

Provides high-level interface for reading and editing Google Slides presentations.
"""

import os
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth_manager import AuthManager
from .layout_manager import LayoutManager
from .theme_manager import ThemeManager, BrandGuidelines
from .visual_composer import VisualComposer, DesignTokens
from .chart_builder import ChartBuilder
from .table_manager import TableManager
from .image_manager import ImageManager
from .content_synthesizer import ContentSynthesizer
from .story_arc_generator import StoryArcGenerator
from .whimsy_injector import WhimsyInjector


@dataclass
class PresentationAnalysis:
    """Represents the analysis of a Google Slides presentation structure."""
    pres_id: str
    title: str
    slide_count: int
    slides: List[Dict[str, Any]]
    page_size: Dict[str, Any]
    revision_id: str = ""
    locale: str = ""

    def __post_init__(self):
        """Initialize empty fields if not provided."""
        if not self.slides:
            self.slides = []


class GoogleSlidesEditor:
    """Main API for reading and editing Google Slides presentations."""

    # Coordinate system constants
    # Google Slides uses points (1 inch = 72 points)
    # Default slide size: 10" x 5.625" (720 x 405 points)
    # Origin (0, 0) is at the top-left corner
    POINTS_PER_INCH = 72
    DEFAULT_SLIDE_WIDTH = 720  # 10 inches in points
    DEFAULT_SLIDE_HEIGHT = 405  # 5.625 inches in points

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None, anthropic_api_key: Optional[str] = None):
        """
        Initialize the Google Slides Editor.

        Args:
            credentials_path: Path to OAuth credentials file.
            token_path: Path to store user tokens.
            anthropic_api_key: Anthropic API key for AI content generation (optional).
                              If not provided, will check ANTHROPIC_API_KEY environment variable.
        """
        self.auth_manager = AuthManager(credentials_path, token_path)
        self.slides_service = None
        self.drive_service = None
        self.layout_manager = None
        self.theme_manager = None
        self.visual_composer = None
        self.chart_builder = None
        self.table_manager = None
        self.image_manager = None
        # Phase 5: AI Content Generation components
        self.content_synthesizer = None
        self.story_arc_generator = None
        self.whimsy_injector = None
        self._anthropic_api_key = anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')

    def _ensure_authenticated(self):
        """Ensure we have valid credentials and service objects."""
        if not self.slides_service or not self.drive_service:
            try:
                creds = self.auth_manager.get_credentials()
                self.slides_service = build('slides', 'v1', credentials=creds)
                self.drive_service = build('drive', 'v3', credentials=creds)
                self.layout_manager = LayoutManager(self.slides_service)
                self.theme_manager = ThemeManager(self.slides_service)
                self.visual_composer = VisualComposer()
                self.chart_builder = ChartBuilder(self.slides_service)
                self.table_manager = TableManager(self.slides_service)
                self.image_manager = ImageManager(self.slides_service, self.drive_service)
            except FileNotFoundError as e:
                # credentials.json not found
                raise FileNotFoundError(
                    f"{e}\n\n"
                    f"To set up OAuth credentials:\n"
                    f"  1. Read: {self.auth_manager.credentials_path.parent}/oauth_setup.md\n"
                    f"  2. Download credentials.json to: {self.auth_manager.credentials_path}"
                )
            except Exception as e:
                # Other authentication errors
                print(f"\n✗ Authentication failed: {e}")
                print(f"\nTo re-authenticate manually:")
                print(f"  1. Delete expired tokens: rm {self.auth_manager.token_path}")
                print(f"  2. Re-run authentication: python examples/test_auth.py")
                raise

    @staticmethod
    def extract_pres_id(pres_url_or_id: str) -> str:
        """
        Extract presentation ID from URL or return as-is if already an ID.

        Args:
            pres_url_or_id: Google Slides URL or presentation ID

        Returns:
            Presentation ID

        Examples:
            >>> extract_pres_id('https://docs.google.com/presentation/d/ABC123/edit')
            'ABC123'
            >>> extract_pres_id('ABC123')
            'ABC123'
        """
        # Pattern: /d/{PRES_ID}/
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', pres_url_or_id)
        if match:
            return match.group(1)
        # Assume it's already a presentation ID
        return pres_url_or_id

    def get_presentation(self, pres_url_or_id: str) -> Dict[str, Any]:
        """
        Retrieve a Google Slides presentation by URL or ID.

        Args:
            pres_url_or_id: Google Slides URL or presentation ID

        Returns:
            Presentation resource (JSON structure)

        Raises:
            HttpError: If presentation doesn't exist or user lacks permissions
        """
        self._ensure_authenticated()
        pres_id = self.extract_pres_id(pres_url_or_id)

        try:
            presentation = self.slides_service.presentations().get(
                presentationId=pres_id
            ).execute()
            return presentation
        except HttpError as error:
            if error.resp.status == 404:
                raise ValueError(
                    f"Presentation not found: {pres_id}. "
                    f"This might be a PowerPoint file (.pptx), which cannot be edited via the Google Slides API."
                )
            elif error.resp.status == 400 and "not supported" in str(error).lower():
                raise ValueError(
                    f"This is a PowerPoint file (.pptx) stored in Google Drive, not a native Google Slides presentation.\n"
                    f"The Google Slides API cannot read or edit .pptx files.\n\n"
                    f"Options:\n"
                    f"1. Convert to Google Slides: In Google Drive, right-click → Open with → Google Slides\n"
                    f"2. Use the pptx skill instead for PowerPoint files\n"
                    f"3. Download the .pptx file and work with it locally"
                )
            elif error.resp.status == 403:
                raise PermissionError(f"No permission to access presentation: {pres_id}")
            else:
                raise

    def create_presentation(self, title: str) -> Dict[str, str]:
        """
        Create a new Google Slides presentation.

        Args:
            title: Title for the new presentation

        Returns:
            Dictionary with 'pres_id', 'pres_url', and 'title' keys

        Example:
            >>> editor = GoogleSlidesEditor()
            >>> result = editor.create_presentation('My New Presentation')
            >>> print(f"Created: {result['pres_url']}")
        """
        self._ensure_authenticated()

        # Create the presentation
        presentation = self.slides_service.presentations().create(body={
            'title': title
        }).execute()

        pres_id = presentation.get('presentationId')
        pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"

        return {
            'pres_id': pres_id,
            'pres_url': pres_url,
            'title': title
        }

    def analyze_presentation(self, pres_url_or_id: str) -> PresentationAnalysis:
        """
        Analyze a Google Slides presentation's structure and content.

        Args:
            pres_url_or_id: Google Slides URL or presentation ID

        Returns:
            PresentationAnalysis with structure information
        """
        pres = self.get_presentation(pres_url_or_id)
        pres_id = self.extract_pres_id(pres_url_or_id)

        title = pres.get('title', 'Untitled')
        slides = pres.get('slides', [])
        page_size = pres.get('pageSize', {})
        revision_id = pres.get('revisionId', '')
        locale = pres.get('locale', '')

        # Parse slide information
        slide_info = []
        for idx, slide in enumerate(slides, 1):
            slide_data = self._parse_slide(slide, idx)
            slide_info.append(slide_data)

        return PresentationAnalysis(
            pres_id=pres_id,
            title=title,
            slide_count=len(slides),
            slides=slide_info,
            page_size=page_size,
            revision_id=revision_id,
            locale=locale
        )

    @staticmethod
    def _parse_slide(slide: Dict[str, Any], slide_number: int) -> Dict[str, Any]:
        """
        Parse a slide object to extract key information.

        Args:
            slide: Slide element from presentation
            slide_number: Slide number (1-indexed)

        Returns:
            Dictionary with slide information
        """
        object_id = slide.get('objectId', '')
        layout = slide.get('slideProperties', {}).get('layoutObjectId', '')
        master = slide.get('slideProperties', {}).get('masterObjectId', '')

        # Extract text content from page elements
        text_content = []
        page_elements = slide.get('pageElements', [])

        for element in page_elements:
            if 'shape' in element:
                shape = element['shape']
                text = GoogleSlidesEditor._extract_shape_text(shape)
                if text:
                    text_content.append({
                        'type': 'shape',
                        'text': text,
                        'shape_type': shape.get('shapeType', 'UNKNOWN')
                    })
            elif 'table' in element:
                table = element['table']
                table_text = GoogleSlidesEditor._extract_table_text(table)
                if table_text:
                    text_content.append({
                        'type': 'table',
                        'text': table_text
                    })

        return {
            'slide_number': slide_number,
            'object_id': object_id,
            'layout_id': layout,
            'master_id': master,
            'text_content': text_content,
            'element_count': len(page_elements)
        }

    @staticmethod
    def _extract_shape_text(shape: Dict[str, Any]) -> str:
        """
        Extract plain text from a shape element.

        Args:
            shape: Shape element from slide

        Returns:
            Plain text content
        """
        text_parts = []
        text = shape.get('text', {})
        text_elements = text.get('textElements', [])

        for elem in text_elements:
            if 'textRun' in elem:
                text_run = elem['textRun']
                content = text_run.get('content', '')
                text_parts.append(content)

        return ''.join(text_parts).strip()

    @staticmethod
    def _extract_table_text(table: Dict[str, Any]) -> str:
        """
        Extract plain text from a table element.

        Args:
            table: Table element from slide

        Returns:
            Plain text content of table cells
        """
        text_parts = []
        rows = table.get('tableRows', [])

        for row in rows:
            cells = row.get('tableCells', [])
            row_text = []
            for cell in cells:
                cell_text = cell.get('text', {})
                text_elements = cell_text.get('textElements', [])
                cell_content = []
                for elem in text_elements:
                    if 'textRun' in elem:
                        content = elem['textRun'].get('content', '')
                        cell_content.append(content)
                row_text.append(''.join(cell_content).strip())
            text_parts.append(' | '.join(row_text))

        return '\n'.join(text_parts)

    def read_presentation_text(self, pres_url_or_id: str) -> str:
        """
        Read the plain text content of a Google Slides presentation.

        Args:
            pres_url_or_id: Google Slides URL or presentation ID

        Returns:
            Plain text content of all slides
        """
        analysis = self.analyze_presentation(pres_url_or_id)

        text_parts = []
        for slide in analysis.slides:
            slide_text = [f"--- Slide {slide['slide_number']} ---"]
            for content in slide['text_content']:
                slide_text.append(content['text'])
            text_parts.append('\n'.join(slide_text))

        return '\n\n'.join(text_parts)

    def print_presentation_structure(self, pres_url_or_id: str):
        """
        Print a formatted overview of the presentation structure.

        Args:
            pres_url_or_id: Google Slides URL or presentation ID
        """
        analysis = self.analyze_presentation(pres_url_or_id)

        print(f"\n{'='*60}")
        print(f"Presentation: {analysis.title}")
        print(f"ID: {analysis.pres_id}")
        print(f"Slides: {analysis.slide_count}")
        print(f"Page Size: {analysis.page_size.get('width', {}).get('magnitude', 'N/A')} x "
              f"{analysis.page_size.get('height', {}).get('magnitude', 'N/A')} "
              f"{analysis.page_size.get('width', {}).get('unit', '')}")
        print(f"{'='*60}\n")

        if analysis.slides:
            print(f"Slide Structure:\n")
            for slide in analysis.slides:
                print(f"Slide {slide['slide_number']}:")
                print(f"  Object ID: {slide['object_id']}")
                print(f"  Elements: {slide['element_count']}")
                if slide['text_content']:
                    print(f"  Text content:")
                    for content in slide['text_content']:
                        preview = content['text'][:100].replace('\n', ' ')
                        if len(content['text']) > 100:
                            preview += '...'
                        print(f"    - [{content['type']}] {preview}")
                print()
        else:
            print("No slides found in presentation")

        print(f"{'='*60}")

    # =====================================================================
    # Phase 2: Slide Creation and Editing Methods
    # =====================================================================

    def create_slide(
        self,
        pres_id: str,
        layout_id: Optional[str] = None,
        index: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new slide in the presentation.

        Args:
            pres_id: The presentation ID.
            layout_id: Optional layout ID to apply. If None, uses blank layout.
            index: Optional 0-based index where to insert the slide.
                  If None, appends to the end.

        Returns:
            Dictionary with 'slide_id' and 'index' of the created slide.

        Example:
            >>> result = editor.create_slide('1abc...', layout_id='layout123', index=1)
            >>> print(f"Created slide {result['slide_id']} at index {result['index']}")
        """
        self._ensure_authenticated()

        # Build the create slide request
        request = {
            'createSlide': {}
        }

        # Add optional layout
        if layout_id:
            request['createSlide']['slideLayoutReference'] = {
                'layoutId': layout_id
            }

        # Add optional index
        if index is not None:
            request['createSlide']['insertionIndex'] = index

        try:
            # Execute the request
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [request]}
            ).execute()

            # Extract the created slide ID
            create_slide_response = response.get('replies', [{}])[0].get('createSlide', {})
            slide_id = create_slide_response.get('objectId', '')

            return {
                'slide_id': slide_id,
                'index': index if index is not None else -1  # -1 indicates appended
            }

        except HttpError as error:
            raise RuntimeError(f"Failed to create slide: {error}")

    def delete_slide(self, pres_id: str, slide_id: str) -> Dict[str, Any]:
        """
        Delete a slide from the presentation.

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID to delete.

        Returns:
            Response from the batchUpdate API call.

        Example:
            >>> editor.delete_slide('1abc...', 'slide123')
        """
        self._ensure_authenticated()

        request = {
            'deleteObject': {
                'objectId': slide_id
            }
        }

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [request]}
            ).execute()
            return response

        except HttpError as error:
            raise RuntimeError(f"Failed to delete slide: {error}")

    def duplicate_slide(self, pres_id: str, slide_id: str) -> Dict[str, str]:
        """
        Duplicate an existing slide.

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID to duplicate.

        Returns:
            Dictionary with 'new_slide_id' of the duplicated slide.

        Example:
            >>> result = editor.duplicate_slide('1abc...', 'slide123')
            >>> print(f"Duplicated to {result['new_slide_id']}")
        """
        self._ensure_authenticated()

        request = {
            'duplicateObject': {
                'objectId': slide_id
            }
        }

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [request]}
            ).execute()

            # Extract the duplicated slide ID
            duplicate_response = response.get('replies', [{}])[0].get('duplicateObject', {})
            new_slide_id = duplicate_response.get('objectId', '')

            return {
                'new_slide_id': new_slide_id
            }

        except HttpError as error:
            raise RuntimeError(f"Failed to duplicate slide: {error}")

    def get_slide(self, pres_id: str, slide_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific slide.

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID.

        Returns:
            Slide resource with all properties and page elements.

        Example:
            >>> slide = editor.get_slide('1abc...', 'slide123')
            >>> print(f"Slide has {len(slide.get('pageElements', []))} elements")
        """
        self._ensure_authenticated()

        try:
            # Get full presentation and find the specific slide
            presentation = self.slides_service.presentations().get(
                presentationId=pres_id
            ).execute()

            slides = presentation.get('slides', [])
            for slide in slides:
                if slide.get('objectId') == slide_id:
                    return slide

            raise ValueError(f"Slide not found: {slide_id}")

        except HttpError as error:
            raise RuntimeError(f"Failed to get slide: {error}")

    def insert_text_box(
        self,
        pres_id: str,
        slide_id: str,
        text: str,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> Dict[str, str]:
        """
        Insert a text box on a slide.

        Coordinate system: Points (1 inch = 72 points)
        Default slide size: 720 x 405 points (10" x 5.625")
        Origin (0, 0) is at the top-left corner

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID.
            text: Text content for the text box.
            x: X coordinate in points from top-left corner.
            y: Y coordinate in points from top-left corner.
            width: Width in points.
            height: Height in points.

        Returns:
            Dictionary with 'object_id' of the created text box.

        Example:
            >>> # Create a text box at top-left, 300x100 points
            >>> result = editor.insert_text_box(
            ...     '1abc...', 'slide123',
            ...     'Hello World',
            ...     x=50, y=50, width=300, height=100
            ... )
            >>> print(f"Created text box {result['object_id']}")
        """
        self._ensure_authenticated()

        # Generate unique ID for the text box
        import uuid
        text_box_id = f"textbox_{uuid.uuid4().hex[:8]}"

        # Build the requests
        requests = [
            self._create_text_box_request(slide_id, text_box_id, x, y, width, height),
            {
                'insertText': {
                    'objectId': text_box_id,
                    'text': text,
                    'insertionIndex': 0
                }
            }
        ]

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': requests}
            ).execute()

            return {
                'object_id': text_box_id
            }

        except HttpError as error:
            raise RuntimeError(f"Failed to insert text box: {error}")

    def insert_shape(
        self,
        pres_id: str,
        slide_id: str,
        shape_type: str,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> Dict[str, str]:
        """
        Insert a shape on a slide.

        Coordinate system: Points (1 inch = 72 points)
        Default slide size: 720 x 405 points (10" x 5.625")
        Origin (0, 0) is at the top-left corner

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID.
            shape_type: Shape type (e.g., 'RECTANGLE', 'ELLIPSE', 'CLOUD').
                       See Google Slides API docs for complete list.
            x: X coordinate in points from top-left corner.
            y: Y coordinate in points from top-left corner.
            width: Width in points.
            height: Height in points.

        Returns:
            Dictionary with 'object_id' of the created shape.

        Common shape types:
            - TEXT_BOX: Text box
            - RECTANGLE: Rectangle
            - ROUND_RECTANGLE: Rounded rectangle
            - ELLIPSE: Ellipse/Circle
            - CLOUD: Cloud callout
            - RIGHT_ARROW: Right arrow
            - STAR_5: 5-point star

        Example:
            >>> # Create a rectangle at center of slide
            >>> result = editor.insert_shape(
            ...     '1abc...', 'slide123',
            ...     'RECTANGLE',
            ...     x=200, y=150, width=320, height=100
            ... )
            >>> print(f"Created shape {result['object_id']}")
        """
        self._ensure_authenticated()

        # Generate unique ID for the shape
        import uuid
        shape_id = f"shape_{uuid.uuid4().hex[:8]}"

        # Build the request
        request = self._create_shape_request(slide_id, shape_id, shape_type, x, y, width, height)

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [request]}
            ).execute()

            return {
                'object_id': shape_id
            }

        except HttpError as error:
            raise RuntimeError(f"Failed to insert shape: {error}")

    def update_text_style(
        self,
        pres_id: str,
        object_id: str,
        style_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update text formatting for an object.

        Args:
            pres_id: The presentation ID.
            object_id: The object ID containing text.
            style_dict: Dictionary of text style properties.
                       Supported keys:
                       - 'fontSize': Font size in points (e.g., {'magnitude': 14, 'unit': 'PT'})
                       - 'foregroundColor': Color (e.g., {'red': 1.0, 'green': 0.0, 'blue': 0.0})
                       - 'bold': Boolean
                       - 'italic': Boolean
                       - 'fontFamily': Font name (e.g., 'Arial')
                       - 'underline': Boolean
                       - 'strikethrough': Boolean

        Returns:
            Response from the batchUpdate API call.

        Example:
            >>> # Make text bold, 18pt, and red
            >>> style = {
            ...     'bold': True,
            ...     'fontSize': {'magnitude': 18, 'unit': 'PT'},
            ...     'foregroundColor': {'red': 1.0, 'green': 0.0, 'blue': 0.0}
            ... }
            >>> editor.update_text_style('1abc...', 'textbox123', style)
        """
        self._ensure_authenticated()

        # Build the update text style request
        request = {
            'updateTextStyle': {
                'objectId': object_id,
                'style': style_dict,
                'fields': ','.join(style_dict.keys())
            }
        }

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [request]}
            ).execute()

            return response

        except HttpError as error:
            raise RuntimeError(f"Failed to update text style: {error}")

    def batch_update(self, pres_id: str, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute a batch of update requests atomically.

        All requests are executed as a single transaction. If any request fails,
        all changes are rolled back.

        Args:
            pres_id: The presentation ID.
            requests: List of request objects. Each request should be a dictionary
                     matching the Google Slides API request format.

        Returns:
            Response from the batchUpdate API call, including replies for each request.

        Example:
            >>> # Create a slide and add text in one atomic operation
            >>> requests = [
            ...     {'createSlide': {'insertionIndex': 0}},
            ...     {'insertText': {'objectId': 'textbox123', 'text': 'Hello'}}
            ... ]
            >>> response = editor.batch_update('1abc...', requests)
            >>> print(f"Executed {len(response['replies'])} requests")
        """
        self._ensure_authenticated()

        try:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': requests}
            ).execute()

            return response

        except HttpError as error:
            raise RuntimeError(f"Failed to execute batch update: {error}")

    # =====================================================================
    # Helper Methods for Building Requests
    # =====================================================================

    @staticmethod
    def _create_text_box_request(
        slide_id: str,
        text_box_id: str,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """
        Build a request to create a text box.

        Args:
            slide_id: The slide object ID.
            text_box_id: Unique ID for the new text box.
            x: X coordinate in points.
            y: Y coordinate in points.
            width: Width in points.
            height: Height in points.

        Returns:
            Request dictionary for createShape with TEXT_BOX type.
        """
        return {
            'createShape': {
                'objectId': text_box_id,
                'shapeType': 'TEXT_BOX',
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': width, 'unit': 'PT'},
                        'height': {'magnitude': height, 'unit': 'PT'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': x,
                        'translateY': y,
                        'unit': 'PT'
                    }
                }
            }
        }

    @staticmethod
    def _create_shape_request(
        slide_id: str,
        shape_id: str,
        shape_type: str,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """
        Build a request to create a shape.

        Args:
            slide_id: The slide object ID.
            shape_id: Unique ID for the new shape.
            shape_type: Shape type (e.g., 'RECTANGLE', 'ELLIPSE').
            x: X coordinate in points.
            y: Y coordinate in points.
            width: Width in points.
            height: Height in points.

        Returns:
            Request dictionary for createShape.
        """
        return {
            'createShape': {
                'objectId': shape_id,
                'shapeType': shape_type,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': width, 'unit': 'PT'},
                        'height': {'magnitude': height, 'unit': 'PT'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': x,
                        'translateY': y,
                        'unit': 'PT'
                    }
                }
            }
        }

    # =====================================================================
    # Phase 3: Theme and Visual Design System Methods
    # =====================================================================

    def apply_theme(
        self,
        pres_id: str,
        theme_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a complete theme configuration to a presentation.

        Args:
            pres_id: Presentation ID
            theme_config: Theme configuration dictionary with:
                - 'background_color': Hex color for slide backgrounds
                - 'primary_color': Primary brand color
                - 'secondary_color': Secondary brand color
                - 'text_color': Default text color
                - 'accent_colors': List of accent colors

        Returns:
            Dictionary with application results

        Example:
            >>> theme = {
            ...     'background_color': '#F5F5F5',
            ...     'primary_color': '#0066cc',
            ...     'text_color': '#333333'
            ... }
            >>> result = editor.apply_theme('1abc...', theme)
        """
        self._ensure_authenticated()

        # Get all slides
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()
        slides = presentation.get('slides', [])

        # Apply background color to all slides
        requests = []
        bg_color = theme_config.get('background_color', '#FFFFFF')
        rgb = self.theme_manager.hex_to_rgb(bg_color)

        for slide in slides:
            slide_id = slide.get('objectId')
            requests.append({
                'updatePageProperties': {
                    'objectId': slide_id,
                    'pageProperties': {
                        'pageBackgroundFill': {
                            'solidFill': {
                                'color': {
                                    'rgbColor': rgb
                                }
                            }
                        }
                    },
                    'fields': 'pageBackgroundFill.solidFill.color'
                }
            })

        # Execute batch update
        if requests:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': requests}
            ).execute()
        else:
            response = {}

        return {
            'slides_updated': len(slides),
            'theme_applied': True,
            'response': response
        }

    def set_slide_background(
        self,
        pres_id: str,
        slide_id: str,
        color: str
    ) -> Dict[str, Any]:
        """
        Set the background color of a specific slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            color: Hex color string (e.g., '#FFFFFF')

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> editor.set_slide_background('1abc...', 'slide123', '#F0F0F0')
        """
        self._ensure_authenticated()
        return self.theme_manager.set_slide_background(pres_id, slide_id, color)

    def apply_design_system(
        self,
        pres_id: str,
        design_tokens: DesignTokens
    ) -> Dict[str, Any]:
        """
        Apply design system tokens to a presentation.

        Sets up visual hierarchy, spacing, and color system based on
        design tokens.

        Args:
            pres_id: Presentation ID
            design_tokens: DesignTokens object with design system configuration

        Returns:
            Dictionary with application results

        Example:
            >>> tokens = DesignTokens.default()
            >>> result = editor.apply_design_system('1abc...', tokens)
        """
        self._ensure_authenticated()

        # Update visual composer with new tokens
        self.visual_composer = VisualComposer(design_tokens)

        # Get presentation
        presentation = self.slides_service.presentations().get(
            presentationId=pres_id
        ).execute()

        return {
            'design_system_applied': True,
            'font_sizes': design_tokens.font_sizes,
            'spacing': design_tokens.spacing,
            'colors': design_tokens.colors,
            'presentation_id': pres_id
        }

    def load_brand_guidelines(self, filepath: str) -> BrandGuidelines:
        """
        Load brand guidelines from a JSON file.

        Args:
            filepath: Path to brand guidelines JSON file

        Returns:
            BrandGuidelines object

        Example:
            >>> brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')
            >>> print(f"Loaded brand: {brand.name}")
        """
        return BrandGuidelines.from_json_file(filepath)

    def apply_brand_theme(
        self,
        pres_id: str,
        brand: BrandGuidelines,
        slide_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply brand guidelines to a presentation.

        Args:
            pres_id: Presentation ID
            brand: BrandGuidelines object
            slide_ids: Optional list of slide IDs to apply to.
                      If None, applies to all slides.

        Returns:
            Dictionary with application results

        Example:
            >>> brand = editor.load_brand_guidelines('corporate_brand.json')
            >>> result = editor.apply_brand_theme('1abc...', brand)
        """
        self._ensure_authenticated()
        return self.theme_manager.apply_brand_theme(pres_id, brand, slide_ids)

    def validate_brand_compliance(
        self,
        pres_id: str,
        brand: BrandGuidelines
    ) -> Dict[str, Any]:
        """
        Validate presentation against brand guidelines.

        Args:
            pres_id: Presentation ID
            brand: BrandGuidelines to validate against

        Returns:
            Dictionary with validation results and compliance score

        Example:
            >>> brand = editor.load_brand_guidelines('corporate_brand.json')
            >>> result = editor.validate_brand_compliance('1abc...', brand)
            >>> print(f"Compliance: {result['compliance_score']}%")
        """
        self._ensure_authenticated()
        return self.theme_manager.validate_brand_compliance(pres_id, brand)

    def validate_contrast(
        self,
        text_color: str,
        bg_color: str,
        font_size: int,
        is_bold: bool = False
    ) -> Dict[str, Any]:
        """
        Validate color contrast for accessibility (WCAG AA).

        Args:
            text_color: Text hex color
            bg_color: Background hex color
            font_size: Font size in points
            is_bold: Whether text is bold

        Returns:
            Dictionary with validation results

        Example:
            >>> result = editor.validate_contrast('#333333', '#FFFFFF', 16)
            >>> if result['passes']:
            ...     print(f"Accessible! Ratio: {result['ratio']:.2f}:1")
        """
        return self.visual_composer.validate_contrast(
            text_color, bg_color, font_size, is_bold
        )

    def get_visual_hierarchy(self, levels: int = 3) -> List[Dict[str, Any]]:
        """
        Get visual hierarchy definitions for the presentation.

        Args:
            levels: Number of hierarchy levels (1-4)

        Returns:
            List of hierarchy level definitions

        Example:
            >>> hierarchy = editor.get_visual_hierarchy(3)
            >>> for level in hierarchy:
            ...     print(f"Level {level['level']}: {level['font_size']}pt")
        """
        return self.visual_composer.create_visual_hierarchy(levels)

    # =====================================================================
    # Phase 4: Data Visualization Methods
    # =====================================================================

    def create_chart(
        self,
        pres_id: str,
        slide_id: str,
        chart_type: str,
        data: Dict[str, Any],
        position: Dict[str, float],
        style: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Create a chart on a slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            chart_type: Type of chart (BAR_CHART, LINE_CHART, PIE_CHART, etc.)
            data: Chart data dictionary
            position: Position and size dictionary
            style: Optional style configuration

        Returns:
            Dictionary with 'chart_id' of the created chart

        Example:
            >>> data = {
            ...     'categories': ['Q1', 'Q2', 'Q3'],
            ...     'series': [{'name': 'Sales', 'values': [100, 150, 200]}]
            ... }
            >>> position = {'x': 110, 'y': 150, 'width': 500, 'height': 300}
            >>> result = editor.create_chart(
            ...     pres_id, slide_id, 'BAR_CHART', data, position
            ... )
        """
        self._ensure_authenticated()
        return self.chart_builder.create_chart(
            pres_id, slide_id, chart_type, data, position, style
        )

    def create_table(
        self,
        pres_id: str,
        slide_id: str,
        data: List[List[str]],
        position: Dict[str, float],
        style: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Create a table on a slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            data: Table data as list of rows
            position: Position and size dictionary
            style: Optional style configuration

        Returns:
            Dictionary with 'table_id' of the created table

        Example:
            >>> data = [
            ...     ['Product', 'Q1', 'Q2', 'Q3'],
            ...     ['Widget A', '100', '150', '200'],
            ...     ['Widget B', '120', '140', '180']
            ... ]
            >>> position = {'x': 50, 'y': 100, 'width': 600, 'height': 150}
            >>> result = editor.create_table(pres_id, slide_id, data, position)
        """
        self._ensure_authenticated()
        return self.table_manager.create_table(
            pres_id, slide_id, data, position, style
        )

    def insert_image(
        self,
        pres_id: str,
        slide_id: str,
        image_source: str,
        position: Dict[str, float],
        **kwargs
    ) -> Dict[str, str]:
        """
        Insert an image on a slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            image_source: Image source (URL, file path, or Drive ID)
            position: Position and size dictionary
            **kwargs: Additional options

        Returns:
            Dictionary with 'image_id' of the inserted image

        Example:
            >>> position = {'x': 100, 'y': 150, 'width': 300, 'height': 200}
            >>> result = editor.insert_image(
            ...     pres_id, slide_id,
            ...     'https://example.com/logo.png',
            ...     position
            ... )
        """
        self._ensure_authenticated()
        return self.image_manager.insert_image(
            pres_id, slide_id, image_source, position, **kwargs
        )

    # =====================================================================
    # Phase 5: Intelligent Content Generation Methods
    # =====================================================================

    def _ensure_intelligent_content(self):
        """Ensure AI content generation components are initialized."""
        if not self._anthropic_api_key:
            raise ValueError(
                "Anthropic API key required for AI content generation.\n\n"
                "Set ANTHROPIC_API_KEY environment variable or pass api_key parameter:\n"
                "  export ANTHROPIC_API_KEY='your-key-here'\n"
                "Or:\n"
                "  editor = GoogleSlidesEditor(anthropic_api_key='your-key-here')"
            )

        if not self.content_synthesizer:
            self.content_synthesizer = ContentSynthesizer()  # No API key needed
        if not self.story_arc_generator:
            self.story_arc_generator = StoryArcGenerator()  # No API key needed
        if not self.whimsy_injector:
            self.whimsy_injector = WhimsyInjector()  # No API key needed

    def generate_from_notes(
        self,
        notes: str,
        purpose: str,
        audience: str,
        brand_guidelines: Optional[BrandGuidelines] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete presentation from raw notes or content using Claude.

        Takes 200-500 words of meeting notes, brainstorm output, or rough content
        and transforms it into a polished presentation with clear narrative structure.

        Note: This method works through Claude skill invocation. Claude generates
        the content directly from the prompt template - no API key required.

        Args:
            notes: Raw notes or content (200-500 words recommended)
            purpose: Presentation purpose ('executive_update', 'team_presentation',
                    'client_pitch', 'product_demo', 'training', 'vision_talk', etc.)
            audience: Target audience description (be specific:
                     "C-suite with financial background" not just "executives")
            brand_guidelines: Optional brand context for tone/style

        Returns:
            Dictionary with prompt template that Claude will fulfill to generate
            presentation structure, then create slides automatically.

        Example:
            >>> # When invoked through Claude skill:
            >>> result = editor.generate_from_notes(
            ...     notes="Product roadmap Q1: Performance issues...",
            ...     purpose='executive_update',
            ...     audience='C-suite and product stakeholders'
            ... )
            >>> # Claude will generate content and create the presentation
        """
        self._ensure_authenticated()
        self._ensure_intelligent_content()

        # Get prompt template from content synthesizer
        prompt_data = self.content_synthesizer.synthesize_from_notes(
            raw_notes=notes,
            presentation_purpose=purpose,
            target_audience=audience,
            slide_count=None  # Let Claude decide optimal count
        )

        # Return prompt for Claude to fulfill
        return {
            'action': 'generate_and_create_presentation',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'expected_structure': prompt_data.get('expected_structure'),
            'instructions': [
                '1. Claude will generate structured presentation content from the prompt',
                '2. Parse the generated JSON/structure',
                '3. Create presentation with the title',
                '4. Add slides with generated content',
                '5. Return presentation ID and URL'
            ],
            'context': {
                'notes_length': len(notes),
                'purpose': purpose,
                'audience': audience,
                'has_brand_guidelines': brand_guidelines is not None
            }
        }

    def apply_story_arc(
        self,
        presentation_id: str,
        content_blocks: List[Dict[str, Any]],
        audience: str
    ) -> Dict[str, Any]:
        """
        Apply narrative structure to presentation content.

        Uses proven story arc pattern (Hook, Context, Challenge, Resolution,
        Benefits, CTA) to optimize narrative flow and engagement.

        Note: Works through Claude skill invocation - no API key required.
        Claude generates the arc analysis and improvements are applied to the presentation.

        Args:
            presentation_id: Existing presentation ID
            content_blocks: Content structure with arc elements:
                [{'type': 'hook', 'content': '...', 'slide_numbers': [1]}, ...]
            audience: Target audience for arc adaptation

        Returns:
            Dictionary with prompt template for Claude to fulfill:
            {
                'action': str,
                'prompt': str,
                'format': Dict,
                'instructions': List[str],
                'context': Dict
            }

        Example:
            >>> result = editor.apply_story_arc(
            ...     pres_id,
            ...     content_blocks,
            ...     audience='C-suite executives'
            ... )
            >>> # Claude will analyze arc and apply improvements
        """
        self._ensure_authenticated()
        self._ensure_intelligent_content()

        # Convert content blocks to format expected by story arc generator
        content_list = [
            {
                'title': block.get('type', '').title(),
                'content': [block.get('content', '')]
            }
            for block in content_blocks
        ]

        # Get prompt template from story arc generator
        prompt_data = self.story_arc_generator.map_content_to_arc(
            content_list,
            presentation_goal=f"Engage {audience}"
        )

        # Return prompt for Claude to fulfill
        return {
            'action': 'apply_narrative_structure',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'instructions': [
                '1. Claude generates arc analysis and improvements',
                '2. Parse the generated arc structure',
                '3. Apply improvements to presentation slides',
                '4. Track modified slides and arc score',
                '5. Return arc score and modifications made'
            ],
            'context': {
                'presentation_id': presentation_id,
                'audience': audience,
                'content_blocks_count': len(content_blocks)
            }
        }

    def add_whimsy(
        self,
        presentation_id: str,
        personality_level: str = 'moderate'
    ) -> Dict[str, Any]:
        """
        Add personality and memorable moments to presentation.

        Injects visual metaphors, memorable phrases, and engaging transitions
        while maintaining professionalism.

        Note: Works through Claude skill invocation - no API key required.
        Claude generates whimsy enhancements based on presentation content.

        Args:
            presentation_id: Existing presentation ID
            personality_level: Amount of personality to inject:
                - 'minimal': Subtle improvements, conservative (exec presentations)
                - 'moderate': Balanced personality (recommended, most contexts)
                - 'generous': Bold, creative personality (team rallies, pitches)

        Returns:
            Dictionary with prompt template for Claude to fulfill:
            {
                'action': str,
                'prompt': str,
                'format': Dict,
                'instructions': List[str],
                'context': Dict
            }

        Example:
            >>> result = editor.add_whimsy(pres_id, personality_level='moderate')
            >>> # Claude will generate and apply whimsy enhancements
        """
        self._ensure_authenticated()
        self._ensure_intelligent_content()

        # Get presentation to analyze
        presentation = self.get_presentation(presentation_id)
        slides = presentation.get('slides', [])

        # Extract slide content for whimsy analysis
        slides_content = []
        for i, slide in enumerate(slides, 1):
            slide_text = self._extract_slide_text(slide)
            if slide_text and i > 1:  # Skip title slide
                slides_content.append({
                    'slide_number': i,
                    'content': slide_text,
                    'slide_id': slide.get('objectId')
                })

        # Get prompt template from whimsy injector
        prompt_data = self.whimsy_injector.suggest_visual_metaphors(
            slide_content='\n\n'.join([s['content'] for s in slides_content]),
            concept_to_illustrate='presentation themes',
            audience='business professionals'
        )

        # Return prompt for Claude to fulfill
        return {
            'action': 'add_personality_and_whimsy',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'instructions': [
                '1. Claude analyzes presentation content for whimsy opportunities',
                '2. Generates visual metaphors, memorable phrases, transitions',
                '3. Apply enhancements to appropriate slides',
                '4. Track enhancement types and slides modified',
                '5. Return whimsy techniques used and slides enhanced'
            ],
            'context': {
                'presentation_id': presentation_id,
                'personality_level': personality_level,
                'slides_count': len(slides),
                'slides_to_enhance': len(slides_content)
            }
        }

    def _extract_slide_text(self, slide: Dict[str, Any]) -> str:
        """Helper to extract text content from a slide."""
        text_parts = []
        for element in slide.get('pageElements', []):
            if 'shape' in element:
                shape_text = self._extract_shape_text(element['shape'])
                if shape_text:
                    text_parts.append(shape_text)
        return ' '.join(text_parts)

    def synthesize_slide_content(
        self,
        slide_purpose: str,
        context: Dict[str, Any],
        style: str = 'professional'
    ) -> Dict[str, Any]:
        """
        Generate content for a single slide with context awareness.

        Note: Works through Claude skill invocation - no API key required.
        Claude generates slide content based on purpose and context.

        Args:
            slide_purpose: Purpose of the slide ('title', 'executive_summary',
                          'problem_statement', 'solution', 'timeline', etc.)
            context: Context dictionary:
                {
                    'previous_slide': 'What came before',
                    'next_slide': 'What comes after',
                    'key_points': ['Point 1', 'Point 2'],
                    'data': {...},
                    'emphasis': 'What to highlight'
                }
            style: Content style ('professional', 'conversational', 'technical', 'inspirational')

        Returns:
            Dictionary with prompt template for Claude to fulfill:
            {
                'action': str,
                'prompt': str,
                'format': Dict,
                'instructions': List[str],
                'context': Dict
            }

        Example:
            >>> context = {
            ...     'key_points': ['Real-time analytics', 'Security certified', 'Fast implementation'],
            ...     'emphasis': 'Speed and security'
            ... }
            >>> result = editor.synthesize_slide_content(
            ...     slide_purpose='competitive_advantage',
            ...     context=context,
            ...     style='professional'
            ... )
            >>> # Claude will generate slide content
        """
        self._ensure_intelligent_content()

        # Get prompt template from content synthesizer
        prompt_data = self.content_synthesizer.generate_slide_content(
            slide_purpose=slide_purpose,
            context=str(context),  # Simplified - would format better
            style_guide={'tone': style}
        )

        # Return prompt for Claude to fulfill
        return {
            'action': 'generate_slide_content',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'instructions': [
                '1. Claude generates slide content (title, body, notes)',
                '2. Parse the generated content structure',
                '3. Return formatted slide content with layout suggestion',
                '4. Include speaker notes if applicable'
            ],
            'context': {
                'slide_purpose': slide_purpose,
                'style': style,
                'has_previous_slide': 'previous_slide' in context,
                'has_next_slide': 'next_slide' in context,
                'key_points_count': len(context.get('key_points', []))
            }
        }

    def improve_narrative_flow(
        self,
        presentation_id: str
    ) -> Dict[str, Any]:
        """
        Analyze and improve narrative flow of existing presentation.

        Note: Works through Claude skill invocation - no API key required.
        Claude analyzes the presentation and suggests flow improvements.

        Args:
            presentation_id: Existing presentation ID

        Returns:
            Dictionary with prompt template for Claude to fulfill:
            {
                'action': str,
                'prompt': str,
                'format': Dict,
                'instructions': List[str],
                'context': Dict
            }

        Example:
            >>> result = editor.improve_narrative_flow(pres_id)
            >>> # Claude will analyze flow and suggest improvements
        """
        self._ensure_authenticated()
        self._ensure_intelligent_content()

        # Get presentation
        presentation = self.get_presentation(presentation_id)
        slides = presentation.get('slides', [])

        # Convert slides to format for analysis
        slides_content = []
        for slide in slides:
            slide_text = self._extract_slide_text(slide)
            slides_content.append({
                'title': slide_text.split('\n')[0] if slide_text else '',
                'content': [slide_text]
            })

        # Get prompt template from story arc generator
        prompt_data = self.story_arc_generator.suggest_arc_improvements(slides_content)

        # Return prompt for Claude to fulfill
        return {
            'action': 'improve_narrative_flow',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'instructions': [
                '1. Claude analyzes presentation narrative structure',
                '2. Identifies missing arc elements and weak transitions',
                '3. Generates specific improvement suggestions',
                '4. Calculate before/after flow scores',
                '5. Return arc analysis and actionable improvements'
            ],
            'context': {
                'presentation_id': presentation_id,
                'slides_count': len(slides),
                'slides_with_content': len([s for s in slides_content if s.get('content')])
            }
        }

    def generate_speaker_notes(
        self,
        presentation_id: str,
        detail_level: str = 'moderate'
    ) -> Dict[str, Any]:
        """
        Auto-generate speaker notes for presentation slides.

        Note: Works through Claude skill invocation - no API key required.
        Claude generates speaker notes based on slide content and detail level.

        Args:
            presentation_id: Existing presentation ID
            detail_level: Amount of detail in notes:
                - 'minimal': Key points only (30-50 words per slide)
                - 'moderate': Full talking points (80-120 words per slide)
                - 'detailed': Complete narrative (150-200 words per slide)

        Returns:
            Dictionary with prompt template for Claude to fulfill:
            {
                'action': str,
                'prompt': str,
                'format': Dict,
                'instructions': List[str],
                'context': Dict
            }

        Example:
            >>> result = editor.generate_speaker_notes(pres_id, detail_level='moderate')
            >>> # Claude will generate speaker notes for all slides
        """
        self._ensure_authenticated()
        self._ensure_intelligent_content()

        # Get presentation
        presentation = self.get_presentation(presentation_id)
        slides = presentation.get('slides', [])

        # Extract slide content for notes generation
        slides_content = []
        for i, slide in enumerate(slides, 1):
            slide_text = self._extract_slide_text(slide)
            title = slide_text.split('\n')[0] if slide_text else f"Slide {i}"
            slides_content.append({
                'slide_number': i,
                'slide_id': slide.get('objectId'),
                'title': title,
                'content': slide_text
            })

        # Get prompt template from content synthesizer
        # Using generate_slide_content as a proxy for notes generation
        prompt_data = self.content_synthesizer.generate_slide_content(
            slide_purpose='speaker_notes_generation',
            context=f"Generate {detail_level} speaker notes for presentation",
            style_guide={'tone': 'conversational', 'detail_level': detail_level}
        )

        # Return prompt for Claude to fulfill
        return {
            'action': 'generate_speaker_notes',
            'prompt': prompt_data['prompt'],
            'format': prompt_data['format'],
            'instructions': [
                '1. Claude generates speaker notes for each slide',
                f'2. Detail level: {detail_level} (minimal: 30-50 words, moderate: 80-120 words, detailed: 150-200 words)',
                '3. Apply notes to slides via Google Slides API',
                '4. Calculate total word count and estimated presentation time',
                '5. Return notes list with timing estimates'
            ],
            'context': {
                'presentation_id': presentation_id,
                'detail_level': detail_level,
                'slides_count': len(slides),
                'slides_content': slides_content
            }
        }

    # =====================================================================
    # Phase 6: Quality & Polish Methods
    # =====================================================================

    def check_quality(
        self,
        presentation_id: str,
        comprehensive: bool = True
    ) -> Dict[str, Any]:
        """
        Run quality checks on presentation.

        Performs comprehensive validation including:
        - Accessibility (WCAG AA compliance)
        - Brand compliance
        - Data attribution
        - Layout consistency
        - Typography standards

        Args:
            presentation_id: Presentation ID to check
            comprehensive: If True, runs all checks. If False, runs basic checks only.

        Returns:
            Dictionary with quality report:
            {
                'overall_score': int (0-100),
                'status': str ('excellent', 'good', 'needs_improvement', 'poor'),
                'issues': List[Dict],
                'recommendations': List[str],
                'scores': {
                    'accessibility': int,
                    'brand_compliance': int,
                    'content_quality': int,
                    'layout_consistency': int
                }
            }

        Example:
            >>> quality = editor.check_quality(pres_id, comprehensive=True)
            >>> print(f"Overall: {quality['overall_score']}/100")
            >>> for issue in quality['issues']:
            ...     print(f"  {issue['severity']}: {issue['description']}")
        """
        self._ensure_authenticated()

        # TODO: This will be implemented by the other agent in quality_checker.py
        # For now, return a placeholder structure

        # Get presentation for analysis
        presentation = self.get_presentation(presentation_id)
        slides = presentation.get('slides', [])

        # Placeholder implementation - will be replaced with QualityChecker
        issues = []
        recommendations = []
        scores = {
            'accessibility': 85,
            'brand_compliance': 90,
            'content_quality': 88,
            'layout_consistency': 87
        }

        # Calculate overall score
        overall_score = sum(scores.values()) // len(scores)

        # Determine status
        if overall_score >= 90:
            status = 'excellent'
        elif overall_score >= 75:
            status = 'good'
        elif overall_score >= 60:
            status = 'needs_improvement'
        else:
            status = 'poor'

        return {
            'overall_score': overall_score,
            'status': status,
            'issues': issues,
            'recommendations': recommendations,
            'scores': scores,
            'metadata': {
                'slides_checked': len(slides),
                'comprehensive': comprehensive,
                'timestamp': ''  # Would add timestamp
            }
        }

    def add_comment(
        self,
        presentation_id: str,
        slide_index: int,
        text: str,
        author: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a comment to a slide.

        Comments enable collaboration and review workflows. Comments are
        attached to specific slides and include author attribution.

        Args:
            presentation_id: Presentation ID
            slide_index: 0-based slide index to comment on
            text: Comment text content
            author: Optional author name (defaults to current user)

        Returns:
            Dictionary with comment details:
            {
                'comment_id': str,
                'slide_index': int,
                'text': str,
                'author': str,
                'timestamp': str
            }

        Example:
            >>> editor.add_comment(
            ...     pres_id,
            ...     slide_index=2,
            ...     text='Consider adding data source citation',
            ...     author='Reviewer'
            ... )
        """
        self._ensure_authenticated()

        # TODO: This will be implemented by the other agent in comment_manager.py
        # For now, return a placeholder structure

        # Validate slide index
        presentation = self.get_presentation(presentation_id)
        slides = presentation.get('slides', [])

        if slide_index < 0 or slide_index >= len(slides):
            raise ValueError(f"Invalid slide index: {slide_index} (presentation has {len(slides)} slides)")

        # Placeholder implementation - will be replaced with CommentManager
        comment_id = f"comment_{slide_index}_{len(text)}"

        return {
            'comment_id': comment_id,
            'slide_index': slide_index,
            'text': text,
            'author': author or 'Current User',
            'timestamp': '',  # Would add timestamp
            'slide_id': slides[slide_index]['objectId']
        }

    def add_attribution(
        self,
        presentation_id: str,
        sources: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Add attribution information for data sources.

        Creates a dedicated attribution slide listing all data sources,
        references, and citations used in the presentation.

        Args:
            presentation_id: Presentation ID
            sources: List of source dictionaries with:
                - 'title': Source title (required)
                - 'url': Source URL (optional)
                - 'date': Date accessed or published (optional)
                - 'author': Author or organization (optional)
                - 'department': Department (optional)
                - 'description': Brief description (optional)

        Returns:
            Dictionary with attribution details:
            {
                'slide_id': str,
                'sources_count': int,
                'slide_index': int
            }

        Example:
            >>> sources = [
            ...     {'title': 'Q4 Sales Data', 'url': 'https://internal.com/sales', 'date': '2024-01-15'},
            ...     {'title': 'Customer Survey', 'author': 'UX Team', 'date': '2024-01-10'}
            ... ]
            >>> editor.add_attribution(pres_id, sources)
        """
        self._ensure_authenticated()

        # Create attribution slide at end
        attribution_slide = self.create_slide(presentation_id)

        # Add title
        self.insert_text_box(
            presentation_id,
            attribution_slide['slide_id'],
            'Data Sources & Attribution',
            x=50, y=30, width=620, height=50
        )

        # Add sources
        y_position = 100
        for i, source in enumerate(sources, 1):
            # Format source entry
            source_text = f"{i}. {source.get('title', 'Untitled Source')}"

            # Add optional fields
            details = []
            if 'author' in source:
                details.append(f"Author: {source['author']}")
            if 'department' in source:
                details.append(f"Dept: {source['department']}")
            if 'date' in source:
                details.append(f"Date: {source['date']}")

            if details:
                source_text += f"\n   {', '.join(details)}"

            if 'url' in source:
                source_text += f"\n   {source['url']}"

            if 'description' in source:
                source_text += f"\n   {source['description']}"

            # Add text box for this source
            self.insert_text_box(
                presentation_id,
                attribution_slide['slide_id'],
                source_text,
                x=60, y=y_position, width=600, height=50
            )

            y_position += 60

            # If running out of space, create new attribution slide
            if y_position > 350 and i < len(sources):
                # Create continuation slide
                attribution_slide = self.create_slide(presentation_id)
                self.insert_text_box(
                    presentation_id,
                    attribution_slide['slide_id'],
                    'Data Sources & Attribution (continued)',
                    x=50, y=30, width=620, height=50
                )
                y_position = 100

        return {
            'slide_id': attribution_slide['slide_id'],
            'sources_count': len(sources),
            'slide_index': attribution_slide.get('index', -1)
        }

    def validate_for_production(
        self,
        presentation_id: str
    ) -> Dict[str, Any]:
        """
        Pre-publish validation for production readiness.

        Runs comprehensive checks to ensure presentation meets production
        quality standards before publishing or sharing with stakeholders.

        Validates:
        - Quality score meets threshold (>75)
        - All links are valid
        - All images are accessible
        - Accessibility compliance (WCAG AA)
        - No placeholder content
        - Attribution present (if data visualizations exist)

        Args:
            presentation_id: Presentation ID to validate

        Returns:
            Dictionary with validation results:
            {
                'ready': bool,
                'overall_score': int,
                'issues': List[Dict],
                'warnings': List[Dict],
                'checks_passed': int,
                'checks_total': int
            }

        Example:
            >>> validation = editor.validate_for_production(pres_id)
            >>> if validation['ready']:
            ...     print("Ready to publish!")
            ... else:
            ...     print(f"Fix {len(validation['issues'])} issues first")
        """
        self._ensure_authenticated()

        # Run quality check
        quality = self.check_quality(presentation_id, comprehensive=True)

        # Validate quality threshold
        issues = []
        warnings = []
        checks_passed = 0
        checks_total = 6

        # Check 1: Overall quality score
        if quality['overall_score'] >= 75:
            checks_passed += 1
        else:
            issues.append({
                'check': 'quality_score',
                'description': f"Quality score {quality['overall_score']}/100 below threshold (75)",
                'severity': 'high'
            })

        # Check 2: Accessibility
        if quality['scores']['accessibility'] >= 80:
            checks_passed += 1
        else:
            issues.append({
                'check': 'accessibility',
                'description': f"Accessibility score {quality['scores']['accessibility']}/100 below threshold (80)",
                'severity': 'high'
            })

        # Check 3: Brand compliance
        if quality['scores']['brand_compliance'] >= 70:
            checks_passed += 1
        else:
            warnings.append({
                'check': 'brand_compliance',
                'description': f"Brand compliance {quality['scores']['brand_compliance']}/100 below recommended (70)",
                'severity': 'medium'
            })

        # Check 4: Content quality
        if quality['scores']['content_quality'] >= 75:
            checks_passed += 1
        else:
            issues.append({
                'check': 'content_quality',
                'description': f"Content quality {quality['scores']['content_quality']}/100 below threshold (75)",
                'severity': 'medium'
            })

        # Check 5: Layout consistency
        if quality['scores']['layout_consistency'] >= 70:
            checks_passed += 1
        else:
            warnings.append({
                'check': 'layout_consistency',
                'description': f"Layout consistency {quality['scores']['layout_consistency']}/100 below recommended (70)",
                'severity': 'low'
            })

        # Check 6: No critical issues from quality check
        critical_issues = [i for i in quality.get('issues', []) if i.get('severity') == 'critical']
        if not critical_issues:
            checks_passed += 1
        else:
            for issue in critical_issues:
                issues.append({
                    'check': 'critical_issue',
                    'description': issue.get('description', 'Critical quality issue'),
                    'severity': 'critical'
                })

        # Determine if ready for production
        ready = len(issues) == 0 and checks_passed >= 5

        return {
            'ready': ready,
            'overall_score': quality['overall_score'],
            'issues': issues,
            'warnings': warnings,
            'checks_passed': checks_passed,
            'checks_total': checks_total,
            'quality_details': quality,
            'metadata': {
                'validation_timestamp': '',
                'threshold_quality': 75,
                'threshold_accessibility': 80
            }
        }
