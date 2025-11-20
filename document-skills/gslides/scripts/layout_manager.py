#!/usr/bin/env python3
"""
Layout Manager for Google Slides presentations.

Handles layout selection, recommendation, and application to slides.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class LayoutInfo:
    """Information about a presentation layout."""
    layout_id: str
    layout_name: str
    master_id: str
    element_count: int


class LayoutManager:
    """
    Manages slide layouts for Google Slides presentations.

    Provides methods to discover available layouts, recommend layouts based on
    content type, and apply layouts to slides.
    """

    # Content type to layout name mappings
    LAYOUT_RECOMMENDATIONS = {
        'title': ['TITLE', 'Title Slide', 'Title'],
        'section': ['SECTION_HEADER', 'Section Header', 'Section'],
        'bullets': ['TITLE_AND_BODY', 'Title and Body', 'Bullets'],
        'two_column': ['TITLE_AND_TWO_COLUMNS', 'Title and Two Columns', 'Two Column'],
        'blank': ['BLANK', 'Blank'],
        'title_only': ['TITLE_ONLY', 'Title Only'],
    }

    def __init__(self, slides_service):
        """
        Initialize the LayoutManager.

        Args:
            slides_service: Authenticated Google Slides API service instance.
        """
        self.slides_service = slides_service

    def get_available_layouts(self, pres_id: str) -> List[LayoutInfo]:
        """
        Get all available layouts from a presentation's master.

        Retrieves layout information from the presentation's master slides,
        including layout IDs, names, and structure details.

        Args:
            pres_id: The presentation ID.

        Returns:
            List of LayoutInfo objects with layout details.

        Example:
            >>> layouts = manager.get_available_layouts('1abc...')
            >>> for layout in layouts:
            ...     print(f"{layout.layout_name} (ID: {layout.layout_id})")
        """
        try:
            # Get the full presentation including masters and layouts
            presentation = self.slides_service.presentations().get(
                presentationId=pres_id
            ).execute()

            layouts = []
            masters = presentation.get('masters', [])

            for master in masters:
                master_id = master.get('objectId', '')
                master_layouts = master.get('layouts', [])

                for layout in master_layouts:
                    layout_id = layout.get('objectId', '')
                    # Layout name is stored in layoutProperties
                    layout_props = layout.get('layoutProperties', {})
                    layout_name = layout_props.get('displayName', layout_props.get('name', 'Unnamed Layout'))

                    # Count page elements to understand layout complexity
                    page_elements = layout.get('pageElements', [])
                    element_count = len(page_elements)

                    layouts.append(LayoutInfo(
                        layout_id=layout_id,
                        layout_name=layout_name,
                        master_id=master_id,
                        element_count=element_count
                    ))

            return layouts

        except Exception as e:
            raise RuntimeError(f"Failed to retrieve layouts: {e}")

    def recommend_layout(self, content_type: str, pres_id: str) -> Optional[str]:
        """
        Recommend a layout ID based on content type.

        Matches the content type to common layout names and returns the
        first matching layout ID from the presentation's available layouts.

        Args:
            content_type: Type of content. One of:
                - 'title': Title slide
                - 'section': Section header
                - 'bullets': Title and bullet points
                - 'two_column': Two column layout
                - 'blank': Blank slide
                - 'title_only': Title only
            pres_id: The presentation ID.

        Returns:
            Layout ID if found, None if no matching layout exists.

        Example:
            >>> layout_id = manager.recommend_layout('bullets', '1abc...')
            >>> if layout_id:
            ...     print(f"Recommended layout: {layout_id}")
        """
        if content_type not in self.LAYOUT_RECOMMENDATIONS:
            raise ValueError(
                f"Unknown content type: {content_type}. "
                f"Valid types: {', '.join(self.LAYOUT_RECOMMENDATIONS.keys())}"
            )

        # Get available layouts
        available_layouts = self.get_available_layouts(pres_id)

        # Get preferred layout names for this content type
        preferred_names = self.LAYOUT_RECOMMENDATIONS[content_type]

        # Try to find a matching layout
        for preferred_name in preferred_names:
            for layout in available_layouts:
                if preferred_name.lower() in layout.layout_name.lower():
                    return layout.layout_id

        # If no match found, return None
        return None

    def apply_layout(self, pres_id: str, slide_id: str, layout_id: str) -> Dict[str, Any]:
        """
        Apply a layout to an existing slide.

        Updates the slide to use the specified layout. This will replace the
        slide's existing placeholder structure with the new layout's structure.

        Args:
            pres_id: The presentation ID.
            slide_id: The slide object ID to update.
            layout_id: The layout object ID to apply.

        Returns:
            Response from the batchUpdate API call.

        Example:
            >>> response = manager.apply_layout('1abc...', 'slide123', 'layout456')
            >>> print("Layout applied successfully")
        """
        try:
            # Create the update request
            requests = [{
                'updateSlideProperties': {
                    'objectId': slide_id,
                    'slideProperties': {
                        'layoutObjectId': layout_id
                    },
                    'fields': 'layoutObjectId'
                }
            }]

            # Execute the batch update
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': requests}
            ).execute()

            return response

        except Exception as e:
            raise RuntimeError(f"Failed to apply layout: {e}")

    def get_layout_placeholders(self, pres_id: str, layout_id: str) -> List[Dict[str, Any]]:
        """
        Get placeholder information from a specific layout.

        Retrieves details about placeholders in a layout, which can be used
        to understand where content should be inserted.

        Args:
            pres_id: The presentation ID.
            layout_id: The layout object ID.

        Returns:
            List of placeholder elements with their properties.

        Example:
            >>> placeholders = manager.get_layout_placeholders('1abc...', 'layout456')
            >>> for ph in placeholders:
            ...     print(f"{ph['type']}: {ph.get('index', 'N/A')}")
        """
        try:
            # Get the full presentation
            presentation = self.slides_service.presentations().get(
                presentationId=pres_id
            ).execute()

            # Find the layout
            masters = presentation.get('masters', [])
            for master in masters:
                for layout in master.get('layouts', []):
                    if layout.get('objectId') == layout_id:
                        # Extract placeholder information
                        placeholders = []
                        page_elements = layout.get('pageElements', [])

                        for element in page_elements:
                            if 'shape' in element:
                                shape = element['shape']
                                placeholder = shape.get('placeholder', {})
                                if placeholder:
                                    placeholders.append({
                                        'type': placeholder.get('type', 'UNKNOWN'),
                                        'index': placeholder.get('index'),
                                        'parent_object_id': placeholder.get('parentObjectId'),
                                        'object_id': element.get('objectId'),
                                        'shape_type': shape.get('shapeType', 'UNKNOWN')
                                    })

                        return placeholders

            raise ValueError(f"Layout not found: {layout_id}")

        except Exception as e:
            raise RuntimeError(f"Failed to get layout placeholders: {e}")
