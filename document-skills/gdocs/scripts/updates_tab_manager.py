"""
Updates Tab Manager for Google Docs.

Handles detection, pattern analysis, and logging of document updates.
"""

from typing import Optional, List
import re
from datetime import datetime
from dateutil import parser as date_parser

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

    def _parse_date(self, text: str) -> Optional[datetime]:
        """
        Parse date from text using multiple formats.

        Args:
            text: Text potentially containing date

        Returns:
            datetime object if parsed, None otherwise
        """
        if not text:
            return None

        try:
            # Use dateutil parser for flexible date parsing
            return date_parser.parse(text, fuzzy=True)
        except (ValueError, TypeError):
            return None

    def _extract_first_date(self, text: str) -> Optional[datetime]:
        """
        Extract first date found in multiline text.

        Args:
            text: Multiline text

        Returns:
            First date found, or None
        """
        for line in text.split('\n'):
            date = self._parse_date(line)
            if date:
                return date
        return None

    def _detect_prepend_from_entries(self, entries: List[str]) -> bool:
        """
        Detect if updates are prepended (newest first) or appended (newest last).

        Args:
            entries: List of entry texts (at least 3 preferred)

        Returns:
            True if prepend (newest first), False if append (newest last)
        """
        if len(entries) < 3:
            # Default to prepend (most common for changelogs)
            return True

        # Extract dates from first 3 entries
        dates = []
        for entry in entries[:3]:
            date = self._extract_first_date(entry)
            if date:
                dates.append(date)

        if len(dates) < 2:
            # Not enough dates to determine pattern
            return True  # Default

        # Check if dates are descending (newest first = prepend)
        # or ascending (oldest first = append)
        if dates[0] > dates[1]:
            return True  # Prepend (newest first)
        else:
            return False  # Append (oldest first)

    def _format_update_entry_default(self, info: UpdateInfo) -> str:
        """
        Format update entry using default template.

        Args:
            info: UpdateInfo with entry details

        Returns:
            Formatted text for update entry
        """
        # Format date
        date_str = info.date.strftime('%B %d, %Y')  # "October 31, 2025"

        # Format sections list
        sections_str = ', '.join(info.sections_modified)

        # Build entry
        entry_parts = [
            f"**{date_str}**",
            f"- Summary: {info.summary}",
            f"- Sections modified: {sections_str}",
            f"- Source: {info.source_attribution}",
            ""  # Blank line after entry
        ]

        return '\n'.join(entry_parts)
