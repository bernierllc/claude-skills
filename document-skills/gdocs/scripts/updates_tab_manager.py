"""
Updates Tab Manager for Google Docs.

Handles detection, pattern analysis, and logging of document updates.
"""

from typing import Optional, List
import re

from .updates_structures import UpdatesLocation, UpdatesPattern, UpdateInfo
from .gdocs_editor import GoogleDocsEditor


class UpdatesTabManager:
    """Manages updates tab/section for document change tracking."""

    # Common update section names (case-insensitive)
    UPDATE_PATTERNS = [
        r'^updates?$',
        r'^update\s+log$',
        r'^changelog$',
        r'^change\s+log$',
        r'^revision\s+history$',
        r'^document\s+update\s+log$',
    ]

    def __init__(self, editor: GoogleDocsEditor):
        """
        Initialize updates tab manager.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor

    def _matches_update_pattern(self, text: str) -> bool:
        """Check if text matches any update section pattern."""
        text = text.strip().lower()
        return any(re.match(pattern, text) for pattern in self.UPDATE_PATTERNS)

    def _detect_updates_tab(self, document: dict, doc_id: str) -> Optional[UpdatesLocation]:
        """
        Detect updates tab in document.

        Args:
            document: Document resource
            doc_id: Document ID

        Returns:
            UpdatesLocation if found, None otherwise
        """
        tabs = document.get('tabs', [])

        for tab in tabs:
            tab_props = tab.get('tabProperties', {})
            title = tab_props.get('title', '')

            if self._matches_update_pattern(title):
                return UpdatesLocation(
                    location_type='tab',
                    tab_id=tab_props.get('tabId'),
                    header_index=None,
                    header_text=title
                )

        return None

    def _detect_updates_header(self, sections: List[dict]) -> Optional[UpdatesLocation]:
        """
        Detect updates header (must be last section).

        Args:
            sections: List of document sections

        Returns:
            UpdatesLocation if last section matches, None otherwise
        """
        if not sections:
            return None

        # Check ONLY the last section
        last_section = sections[-1]
        heading = last_section.get('heading', '')

        if self._matches_update_pattern(heading):
            return UpdatesLocation(
                location_type='header',
                tab_id=None,
                header_index=last_section.get('start_index'),
                header_text=heading
            )

        return None

    def detect_updates_location(self, doc_id: str) -> Optional[UpdatesLocation]:
        """
        Detect updates location (tab first, then header).

        Args:
            doc_id: Document ID

        Returns:
            UpdatesLocation if found, None otherwise
        """
        # Get document
        doc = self.editor.get_document(doc_id, include_tabs_content=True)

        # Priority 1: Check for updates tab
        tab_location = self._detect_updates_tab(doc, doc_id)
        if tab_location:
            return tab_location

        # Priority 2: Check last header
        analysis = self.editor.analyze_document(doc_id, include_comments=False)
        header_location = self._detect_updates_header(analysis.sections)

        return header_location
