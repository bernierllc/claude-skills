"""
Data structures for updates tab feature.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class UpdatesLocation:
    """Location of updates section (tab or header)."""
    location_type: str  # 'tab' or 'header'
    tab_id: Optional[str]  # If tab
    header_index: Optional[int]  # If header
    header_text: str  # Display name

    def is_tab(self) -> bool:
        """Check if this is a tab-based location."""
        return self.location_type == 'tab'


@dataclass
class ComponentStyle:
    """Style for a component of an update entry."""
    prefix: str  # 'Summary:', 'Sections:', 'Source:'
    style: Dict  # text formatting {'bold': True, etc}


@dataclass
class FormatTemplate:
    """Template for formatting update entries."""
    date_format: str  # e.g., "**MMMM DD, YYYY**"
    date_style: Dict  # {bold: True, italic: False}
    bullet_style: Optional[str]  # '-', '*', '1.', None
    entry_components: List[ComponentStyle] = field(default_factory=list)


@dataclass
class UpdatesPattern:
    """Pattern detected from existing updates."""
    prepend: bool  # True = newest first, False = newest last
    format_template: FormatTemplate


@dataclass
class UpdateInfo:
    """Information about an update to log."""
    date: datetime
    summary: str
    sections_modified: List[str]
    source_attribution: str
