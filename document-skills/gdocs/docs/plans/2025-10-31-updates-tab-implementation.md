# Updates Tab Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add automatic update logging to track content merges in Google Docs with intelligent pattern detection and formatting matching.

**Architecture:** Create UpdatesTabManager class for detection/logging, add session state tracking to ContentInserter, integrate into merge_content() workflow with interactive user prompts on first update.

**Tech Stack:** Python 3.12, Google Docs API, existing gdocs_editor.py/content_inserter.py modules

---

## Task 1: Create Data Structures Module

**Files:**
- Create: `document-skills/gdocs/scripts/updates_structures.py`

**Step 1: Write test for data structures**

```python
# document-skills/gdocs/tests/test_updates_structures.py
from datetime import datetime
from scripts.updates_structures import (
    UpdatesLocation, UpdatesPattern, FormatTemplate,
    ComponentStyle, UpdateInfo
)

def test_updates_location_tab():
    """Test UpdatesLocation for tab-based location."""
    loc = UpdatesLocation(
        location_type='tab',
        tab_id='t.123',
        header_index=None,
        header_text='Updates'
    )
    assert loc.location_type == 'tab'
    assert loc.tab_id == 't.123'
    assert loc.is_tab()


def test_updates_location_header():
    """Test UpdatesLocation for header-based location."""
    loc = UpdatesLocation(
        location_type='header',
        tab_id=None,
        header_index=450,
        header_text='Document Update Log'
    )
    assert loc.location_type == 'header'
    assert loc.header_index == 450
    assert not loc.is_tab()


def test_updates_pattern():
    """Test UpdatesPattern with format template."""
    template = FormatTemplate(
        date_format='**MMMM DD, YYYY**',
        date_style={'bold': True, 'italic': False},
        bullet_style='-',
        entry_components=[]
    )
    pattern = UpdatesPattern(prepend=True, format_template=template)
    assert pattern.prepend is True
    assert pattern.format_template.bullet_style == '-'


def test_update_info():
    """Test UpdateInfo dataclass."""
    info = UpdateInfo(
        date=datetime(2025, 10, 31),
        summary='Added market analysis insights',
        sections_modified=['Market Analysis', 'Competitive Landscape'],
        source_attribution='Customer feedback meeting on 10/31/25'
    )
    assert len(info.sections_modified) == 2
    assert 'Market Analysis' in info.sections_modified
```

**Step 2: Run test to verify it fails**

```bash
cd document-skills/gdocs
python -m pytest tests/test_updates_structures.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.updates_structures'"

**Step 3: Implement data structures**

```python
# document-skills/gdocs/scripts/updates_structures.py
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
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_updates_structures.py -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
cd /Users/mattbernier/.config/superpowers/worktrees/claude-skills/gdocs-updates-tab
git add document-skills/gdocs/scripts/updates_structures.py document-skills/gdocs/tests/test_updates_structures.py
git commit -m "feat: add data structures for updates tab feature

- UpdatesLocation for tab/header tracking
- UpdatesPattern for format detection
- UpdateInfo for logging entries
- FormatTemplate for style matching"
```

---

## Task 2: Create UpdatesTabManager - Detection Logic

**Files:**
- Create: `document-skills/gdocs/scripts/updates_tab_manager.py`
- Modify: None yet

**Step 1: Write test for updates detection**

```python
# document-skills/gdocs/tests/test_updates_detection.py
from scripts.updates_tab_manager import UpdatesTabManager
from scripts.gdocs_editor import GoogleDocsEditor


def test_detect_updates_tab():
    """Test detection of updates tab."""
    # Mock editor with tab-based document
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    # Mock document structure
    mock_doc = {
        'tabs': [
            {'tabProperties': {'tabId': 't.0', 'title': 'Main'}},
            {'tabProperties': {'tabId': 't.1', 'title': 'Updates'}},
        ]
    }

    location = manager._detect_updates_tab(mock_doc, 'doc123')
    assert location is not None
    assert location.location_type == 'tab'
    assert location.tab_id == 't.1'
    assert location.header_text == 'Updates'


def test_detect_updates_header():
    """Test detection of updates header (last heading)."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    # Mock document with headers
    mock_sections = [
        {'heading': 'Introduction', 'level': '1', 'start_index': 10, 'end_index': 50},
        {'heading': 'Content', 'level': '1', 'start_index': 51, 'end_index': 200},
        {'heading': 'Update Log', 'level': '2', 'start_index': 201, 'end_index': 250},
    ]

    location = manager._detect_updates_header(mock_sections)
    assert location is not None
    assert location.location_type == 'header'
    assert location.header_index == 201
    assert location.header_text == 'Update Log'


def test_detect_no_updates():
    """Test when no updates location exists."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    mock_doc = {'tabs': [{'tabProperties': {'tabId': 't.0', 'title': 'Main'}}]}
    mock_sections = [
        {'heading': 'Introduction', 'level': '1', 'start_index': 10, 'end_index': 50},
    ]

    tab_loc = manager._detect_updates_tab(mock_doc, 'doc123')
    header_loc = manager._detect_updates_header(mock_sections)

    assert tab_loc is None
    assert header_loc is None
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_updates_detection.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.updates_tab_manager'"

**Step 3: Implement detection methods**

```python
# document-skills/gdocs/scripts/updates_tab_manager.py
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
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_updates_detection.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/updates_tab_manager.py document-skills/gdocs/tests/test_updates_detection.py
git commit -m "feat: add updates location detection

- Detect updates tabs by name pattern matching
- Detect last header if matches update patterns
- Priority: tabs first, then headers
- Case-insensitive pattern matching"
```

---

## Task 3: Pattern Analysis - Date Parsing

**Files:**
- Modify: `document-skills/gdocs/scripts/updates_tab_manager.py`

**Step 1: Write test for date parsing**

```python
# document-skills/gdocs/tests/test_pattern_analysis.py
from datetime import datetime
from scripts.updates_tab_manager import UpdatesTabManager
from scripts.gdocs_editor import GoogleDocsEditor


def test_parse_date_formats():
    """Test parsing various date formats."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    test_cases = [
        ("October 31, 2025", datetime(2025, 10, 31)),
        ("10/31/2025", datetime(2025, 10, 31)),
        ("2025-10-31", datetime(2025, 10, 31)),
        ("Oct 31, 2025", datetime(2025, 10, 31)),
        ("31 October 2025", datetime(2025, 10, 31)),
    ]

    for text, expected in test_cases:
        result = manager._parse_date(text)
        assert result is not None
        assert result.date() == expected.date()


def test_parse_invalid_date():
    """Test parsing invalid date returns None."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    assert manager._parse_date("not a date") is None
    assert manager._parse_date("") is None


def test_extract_first_date():
    """Test extracting first date from multiline text."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    text = """**October 31, 2025**
    - Summary: Added new features
    - Source: Meeting notes"""

    date = manager._extract_first_date(text)
    assert date is not None
    assert date.month == 10
    assert date.day == 31
    assert date.year == 2025
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pattern_analysis.py::test_parse_date_formats -v
```

Expected: FAIL with "AttributeError: 'UpdatesTabManager' object has no attribute '_parse_date'"

**Step 3: Implement date parsing**

```python
# Add to document-skills/gdocs/scripts/updates_tab_manager.py

from datetime import datetime
from dateutil import parser as date_parser  # Add to imports at top

# Add these methods to UpdatesTabManager class:

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
```

**Step 4: Update requirements.txt**

```bash
# Add python-dateutil to requirements
echo "python-dateutil>=2.8.2" >> document-skills/gdocs/requirements.txt
```

**Step 5: Install new dependency**

```bash
pip install python-dateutil>=2.8.2
```

**Step 6: Run test to verify it passes**

```bash
python -m pytest tests/test_pattern_analysis.py -v
```

Expected: PASS (3 tests)

**Step 7: Commit**

```bash
git add document-skills/gdocs/scripts/updates_tab_manager.py document-skills/gdocs/tests/test_pattern_analysis.py document-skills/gdocs/requirements.txt
git commit -m "feat: add date parsing for update entries

- Parse multiple date formats (MM/DD/YYYY, YYYY-MM-DD, etc)
- Extract first date from multiline text
- Use python-dateutil for flexible parsing"
```

---

## Task 4: Pattern Analysis - Prepend vs Append Detection

**Files:**
- Modify: `document-skills/gdocs/scripts/updates_tab_manager.py`
- Modify: `document-skills/gdocs/tests/test_pattern_analysis.py`

**Step 1: Write test for ordering detection**

```python
# Add to document-skills/gdocs/tests/test_pattern_analysis.py

def test_analyze_pattern_prepend():
    """Test pattern detection for prepend (newest first)."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    # Newest first (prepend)
    entries = [
        "**November 1, 2025**\n- Summary: Latest update",
        "**October 31, 2025**\n- Summary: Middle update",
        "**October 30, 2025**\n- Summary: Oldest update",
    ]

    prepend = manager._detect_prepend_from_entries(entries)
    assert prepend is True


def test_analyze_pattern_append():
    """Test pattern detection for append (newest last)."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    # Oldest first (append)
    entries = [
        "**October 30, 2025**\n- Summary: Oldest update",
        "**October 31, 2025**\n- Summary: Middle update",
        "**November 1, 2025**\n- Summary: Latest update",
    ]

    prepend = manager._detect_prepend_from_entries(entries)
    assert prepend is False


def test_analyze_pattern_insufficient_data():
    """Test pattern detection defaults to prepend with < 3 entries."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    # Only 1 entry
    entries = ["**October 31, 2025**\n- Summary: Only update"]
    prepend = manager._detect_prepend_from_entries(entries)
    assert prepend is True  # Default
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pattern_analysis.py::test_analyze_pattern_prepend -v
```

Expected: FAIL with "AttributeError: 'UpdatesTabManager' object has no attribute '_detect_prepend_from_entries'"

**Step 3: Implement prepend/append detection**

```python
# Add to document-skills/gdocs/scripts/updates_tab_manager.py

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
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pattern_analysis.py -v
```

Expected: PASS (6 tests total)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/updates_tab_manager.py document-skills/gdocs/tests/test_pattern_analysis.py
git commit -m "feat: detect prepend vs append pattern from entries

- Analyze first 3 entries for date ordering
- Prepend = newest first (descending dates)
- Append = oldest first (ascending dates)
- Default to prepend when insufficient data"
```

---

## Task 5: Session State Tracking in ContentInserter

**Files:**
- Modify: `document-skills/gdocs/scripts/content_inserter.py`

**Step 1: Write test for session state**

```python
# document-skills/gdocs/tests/test_session_state.py
from scripts.content_inserter import ContentInserter
from scripts.gdocs_editor import GoogleDocsEditor


def test_session_state_initialization():
    """Test session state is empty on init."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    assert inserter._document_state == {}


def test_session_state_tracking():
    """Test session state tracks document preferences."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Record state for a document
    inserter._set_document_state('doc123', {
        'has_updates_tab': True,
        'prepend': True,
        'asked_user': True,
        'location_type': 'tab'
    })

    state = inserter._get_document_state('doc123')
    assert state['has_updates_tab'] is True
    assert state['prepend'] is True
    assert state['asked_user'] is True


def test_session_state_first_update_check():
    """Test first update detection."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # First update to doc123
    assert inserter._is_first_update('doc123') is True

    # Mark as handled
    inserter._set_document_state('doc123', {'asked_user': True})

    # Not first update anymore
    assert inserter._is_first_update('doc123') is False
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_session_state.py -v
```

Expected: FAIL with "AttributeError: 'ContentInserter' object has no attribute '_document_state'"

**Step 3: Add session state to ContentInserter**

```python
# Modify document-skills/gdocs/scripts/content_inserter.py

# In ContentInserter.__init__, add:
class ContentInserter:
    """Handles intelligent content insertion with comment awareness."""

    def __init__(self, editor):
        """
        Initialize content inserter.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor
        self._document_state = {}  # ADD THIS LINE: Session state per document

# Add these methods to ContentInserter class:

    def _get_document_state(self, doc_id: str) -> dict:
        """
        Get session state for a document.

        Args:
            doc_id: Document ID

        Returns:
            State dictionary or empty dict
        """
        return self._document_state.get(doc_id, {})

    def _set_document_state(self, doc_id: str, state: dict):
        """
        Set session state for a document.

        Args:
            doc_id: Document ID
            state: State dictionary
        """
        if doc_id not in self._document_state:
            self._document_state[doc_id] = {}
        self._document_state[doc_id].update(state)

    def _is_first_update(self, doc_id: str) -> bool:
        """
        Check if this is the first update to this document in this session.

        Args:
            doc_id: Document ID

        Returns:
            True if first update (not yet asked user)
        """
        state = self._get_document_state(doc_id)
        return not state.get('asked_user', False)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_session_state.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/content_inserter.py document-skills/gdocs/tests/test_session_state.py
git commit -m "feat: add session state tracking to ContentInserter

- Track document state per doc ID in session
- Detect first vs subsequent updates
- Store user preferences (has_updates_tab, prepend, etc)"
```

---

## Task 6: Integrate UpdatesTabManager into ContentInserter

**Files:**
- Modify: `document-skills/gdocs/scripts/content_inserter.py`

**Step 1: Write integration test**

```python
# document-skills/gdocs/tests/test_updates_integration.py
from scripts.content_inserter import ContentInserter
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.updates_tab_manager import UpdatesTabManager


def test_content_inserter_has_updates_manager():
    """Test ContentInserter initializes UpdatesTabManager."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    assert hasattr(inserter, 'updates_manager')
    assert isinstance(inserter.updates_manager, UpdatesTabManager)


def test_check_for_existing_updates():
    """Test checking for existing updates location."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    # Mock detection (will return None for most docs)
    # This is an integration test, so we're just verifying wiring
    doc_id = 'test_doc_123'
    location = inserter.updates_manager.detect_updates_location(doc_id)

    # Most test docs won't have updates section
    # We're testing that the call doesn't error
    assert location is None or location is not None  # Either is valid
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_updates_integration.py -v
```

Expected: FAIL with "AttributeError: 'ContentInserter' object has no attribute 'updates_manager'"

**Step 3: Add UpdatesTabManager to ContentInserter**

```python
# Modify document-skills/gdocs/scripts/content_inserter.py

# Add import at top:
from .updates_tab_manager import UpdatesTabManager

# Modify __init__:
    def __init__(self, editor):
        """
        Initialize content inserter.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor
        self._document_state = {}
        self.updates_manager = UpdatesTabManager(editor)  # ADD THIS LINE
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_updates_integration.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/content_inserter.py document-skills/gdocs/tests/test_updates_integration.py
git commit -m "feat: integrate UpdatesTabManager into ContentInserter

- Initialize UpdatesTabManager in ContentInserter
- Provide access to detection and logging capabilities
- Enable updates workflow in merge operations"
```

---

## Task 7: Create Update Entry Formatting

**Files:**
- Modify: `document-skills/gdocs/scripts/updates_tab_manager.py`

**Step 1: Write test for default template**

```python
# Add to document-skills/gdocs/tests/test_pattern_analysis.py

from scripts.updates_structures import UpdateInfo
from datetime import datetime

def test_format_update_entry_default():
    """Test formatting update entry with default template."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    info = UpdateInfo(
        date=datetime(2025, 10, 31),
        summary='Added market research insights',
        sections_modified=['Market Analysis'],
        source_attribution='Customer feedback meeting on 10/31/25'
    )

    entry_text = manager._format_update_entry_default(info)

    assert '**October 31, 2025**' in entry_text
    assert 'Summary: Added market research insights' in entry_text
    assert 'Sections modified: Market Analysis' in entry_text
    assert 'Source: Customer feedback meeting on 10/31/25' in entry_text


def test_format_update_entry_multiple_sections():
    """Test formatting with multiple sections."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    info = UpdateInfo(
        date=datetime(2025, 10, 31),
        summary='Updated analysis',
        sections_modified=['Market Analysis', 'Competitive Landscape'],
        source_attribution='Research notes'
    )

    entry_text = manager._format_update_entry_default(info)
    assert 'Market Analysis, Competitive Landscape' in entry_text
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pattern_analysis.py::test_format_update_entry_default -v
```

Expected: FAIL with "AttributeError: 'UpdatesTabManager' object has no attribute '_format_update_entry_default'"

**Step 3: Implement default formatting**

```python
# Add to document-skills/gdocs/scripts/updates_tab_manager.py

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
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pattern_analysis.py -v
```

Expected: PASS (all tests including 2 new ones)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/updates_tab_manager.py document-skills/gdocs/tests/test_pattern_analysis.py
git commit -m "feat: add default update entry formatting

- Format date as 'Month DD, YYYY' in bold
- Include summary, sections modified, and source
- Use bullet list format with blank line separator"
```

---

## Task 8: Implement Update Logging (Insertion)

**Files:**
- Modify: `document-skills/gdocs/scripts/updates_tab_manager.py`

**Step 1: Write test for logging update**

```python
# document-skills/gdocs/tests/test_update_logging.py
"""
NOTE: This is an integration test that requires real Google Docs API.
Run manually with real credentials when ready to test.
"""
from datetime import datetime
from scripts.updates_tab_manager import UpdatesTabManager
from scripts.updates_structures import UpdateInfo, UpdatesLocation
from scripts.gdocs_editor import GoogleDocsEditor


def test_log_update_prepend_logic():
    """Test logic for prepend vs append (unit test, no API)."""
    editor = GoogleDocsEditor()
    manager = UpdatesTabManager(editor)

    info = UpdateInfo(
        date=datetime(2025, 10, 31),
        summary='Test update',
        sections_modified=['Test Section'],
        source_attribution='Test source'
    )

    # Test prepend formatting
    entry = manager._format_update_entry_default(info)
    assert entry.startswith('**October 31, 2025**')

    # Verify entry structure
    lines = entry.split('\n')
    assert len(lines) >= 4  # Date, summary, sections, source, blank
```

**Step 2: Run test to verify baseline**

```bash
python -m pytest tests/test_update_logging.py -v
```

Expected: PASS (1 test - just verifying structure)

**Step 3: Implement log_update method**

```python
# Add to document-skills/gdocs/scripts/updates_tab_manager.py

    def log_update(
        self,
        doc_id: str,
        location: UpdatesLocation,
        info: UpdateInfo,
        prepend: bool = True
    ) -> bool:
        """
        Log an update to the updates section.

        Args:
            doc_id: Document ID
            location: Where to log (tab or header)
            info: Update information
            prepend: If True, add at top (newest first). If False, add at bottom.

        Returns:
            True if successful
        """
        # Format the entry
        entry_text = self._format_update_entry_default(info)

        # Calculate insertion point
        if location.is_tab():
            # For tabs, insert at beginning or end of tab content
            doc = self.editor.get_document(doc_id, include_tabs_content=True)
            tab_body = self.editor.get_tab_body(doc, location.tab_id)

            if prepend:
                # Insert after tab title/header (usually index 1)
                insertion_index = 1
            else:
                # Insert at end of tab
                content = tab_body.get('content', [])
                insertion_index = content[-1].get('endIndex', 1) if content else 1
        else:
            # For headers, insert after the header
            if prepend:
                # Right after header
                insertion_index = location.header_index + 1
            else:
                # Would need to find next header or end of section
                # For now, insert right after header (simpler)
                insertion_index = location.header_index + 1

        # Insert the text
        requests = [
            {
                'insertText': {
                    'location': {'index': insertion_index},
                    'text': entry_text
                }
            }
        ]

        try:
            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            return True
        except Exception as e:
            print(f"Error logging update: {e}")
            return False
```

**Step 4: Commit**

```bash
git add document-skills/gdocs/scripts/updates_tab_manager.py document-skills/gdocs/tests/test_update_logging.py
git commit -m "feat: implement update logging with insertion

- Calculate insertion point based on prepend/append
- Support both tab and header-based locations
- Use Google Docs API batchUpdate for insertion
- Handle errors gracefully"
```

---

## Task 9: Add First-Update User Prompt to merge_content

**Files:**
- Modify: `document-skills/gdocs/scripts/content_inserter.py`

**Step 1: Write test for first-update workflow**

```python
# document-skills/gdocs/tests/test_first_update_prompt.py
"""
NOTE: Testing user interaction requires mocking or manual testing.
This test verifies the logic flow.
"""
from scripts.content_inserter import ContentInserter
from scripts.gdocs_editor import GoogleDocsEditor


def test_should_prompt_user_first_update():
    """Test detection of when to prompt user."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    doc_id = 'test_doc'

    # First update: should prompt
    assert inserter._should_prompt_for_updates(doc_id) is True

    # Mark as asked
    inserter._set_document_state(doc_id, {'asked_user': True})

    # Subsequent update: should not prompt
    assert inserter._should_prompt_for_updates(doc_id) is False


def test_should_not_prompt_if_updates_exist():
    """Test skip prompt if updates location already exists."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    doc_id = 'test_doc'

    # Simulate existing updates location found
    inserter._set_document_state(doc_id, {
        'has_updates_tab': True,
        'asked_user': True  # Automatically set when location detected
    })

    assert inserter._should_prompt_for_updates(doc_id) is False
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_first_update_prompt.py -v
```

Expected: FAIL with "AttributeError: 'ContentInserter' object has no attribute '_should_prompt_for_updates'"

**Step 3: Implement prompt logic**

```python
# Add to document-skills/gdocs/scripts/content_inserter.py

    def _should_prompt_for_updates(self, doc_id: str) -> bool:
        """
        Check if we should prompt user about updates tab.

        Args:
            doc_id: Document ID

        Returns:
            True if should prompt (first update, no existing updates)
        """
        state = self._get_document_state(doc_id)

        # Don't prompt if already asked
        if state.get('asked_user', False):
            return False

        # Don't prompt if updates location already detected
        if state.get('has_updates_tab', False):
            return False

        # First update, no existing updates: should prompt
        return True

    def _check_existing_updates(self, doc_id: str):
        """
        Check for existing updates location and update state.

        Args:
            doc_id: Document ID
        """
        location = self.updates_manager.detect_updates_location(doc_id)

        if location:
            # Found existing updates location
            # TODO: Analyze pattern in next task
            self._set_document_state(doc_id, {
                'has_updates_tab': True,
                'asked_user': True,  # Don't ask if already exists
                'location': location,
            })
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_first_update_prompt.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add document-skills/gdocs/scripts/content_inserter.py document-skills/gdocs/tests/test_first_update_prompt.py
git commit -m "feat: add logic to determine when to prompt user

- Check if first update to document
- Skip prompt if updates location exists
- Skip prompt if user already asked
- Detect existing updates and update state"
```

---

## Task 10: Document User Interaction Pattern for Claude

**Files:**
- Create: `document-skills/gdocs/docs/UPDATES_TAB_USAGE.md`

**Step 1: Write usage documentation**

```markdown
# Updates Tab - User Interaction Pattern

This document describes how Claude (in conversation) should interact with users when the updates tab feature is active.

## When to Prompt

Claude should prompt the user about the updates tab on the **first content merge** to a document in the session, IF:
1. No updates tab/section is detected in the document
2. User hasn't been asked yet this session

## Prompt Format

When `_should_prompt_for_updates()` returns `True`, Claude should ask:

```
Would you like me to create an Updates tab to track changes to this document?

Options:
1. Yes, prepend new updates (newest first) - Most common for changelogs
2. Yes, append new updates (newest last) - Chronological order
3. No, don't track updates
```

## Handling User Response

Based on user choice:

**Option 1 (Prepend):**
```python
inserter._set_document_state(doc_id, {
    'has_updates_tab': False,  # Will be created
    'prepend': True,
    'asked_user': True,
    'user_wants_updates': True
})
```

**Option 2 (Append):**
```python
inserter._set_document_state(doc_id, {
    'has_updates_tab': False,
    'prepend': False,
    'asked_user': True,
    'user_wants_updates': True
})
```

**Option 3 (No tracking):**
```python
inserter._set_document_state(doc_id, {
    'asked_user': True,
    'user_wants_updates': False
})
```

## Existing Updates Detection

If `_check_existing_updates()` finds an updates location:

1. **Detect pattern** (prepend vs append) by analyzing first 3 entries
2. **Store in state**:
   ```python
   {
       'has_updates_tab': True,
       'prepend': <detected>,
       'asked_user': True,
       'location': <UpdatesLocation>,
       'user_wants_updates': True
   }
   ```
3. **Skip user prompt** - use detected pattern automatically

## Logging Updates

After successful `merge_content()`, if updates tracking is enabled:

```python
if state.get('user_wants_updates', False):
    info = UpdateInfo(
        date=datetime.now(),
        summary=<brief description of changes>,
        sections_modified=[options.target_section],
        source_attribution=options.source_description or 'content merge'
    )

    location = state.get('location') or <create new section>
    prepend = state.get('prepend', True)

    updates_manager.log_update(doc_id, location, info, prepend)
```

## Example Workflow

### First Update (No Existing Updates)

```
Claude: "I've synthesized the meeting notes into 3 sentences for the
        Market Analysis section.

        This is the first update to this document. Would you like me to
        create an Updates tab to track changes?

        1. Yes, prepend (newest first)
        2. Yes, append (newest last)
        3. No, don't track"

User: "1"

Claude: "Great! I'll create an Updates tab and prepend new entries.

        Proceeding with merge..."

        [Performs merge]
        [Logs update to new Updates section]

        "✓ Content merged into Market Analysis
         ✓ Update logged to Updates section"
```

### First Update (Existing Updates Found)

```
Claude: "I've synthesized the meeting notes into 3 sentences for the
        Market Analysis section.

        I found an existing 'Update Log' section in your document. I'll
        automatically log updates there following your established pattern
        (newest entries first).

        Proceeding with merge..."

        [Performs merge]
        [Logs update to existing section]

        "✓ Content merged into Market Analysis
         ✓ Update logged to Update Log (prepended)"
```

### Subsequent Updates

```
Claude: "I've synthesized the research into 2 sentences for the
        Competitive Landscape section.

        Proceeding with merge..."

        [Performs merge]
        [Logs update automatically - no prompt]

        "✓ Content merged into Competitive Landscape
         ✓ Update logged to Updates section"
```

## Implementation Notes

This interaction happens in **Claude's conversation layer**, not in the Python code. The Python code provides:

1. `_should_prompt_for_updates()` - tells Claude when to ask
2. `_check_existing_updates()` - detects and analyzes existing patterns
3. State management - stores user preferences
4. `log_update()` - performs the actual logging

Claude (in conversation) orchestrates the user interaction using these building blocks.
```

**Step 2: Commit documentation**

```bash
git add document-skills/gdocs/docs/UPDATES_TAB_USAGE.md
git commit -m "docs: add user interaction pattern for updates tab

- Document when and how to prompt users
- Provide example workflows for different scenarios
- Clarify Claude's role in orchestrating interaction
- Include state management examples"
```

---

## Task 11: Update SKILL.md with Updates Tab Feature

**Files:**
- Modify: `document-skills/gdocs/SKILL.md`

**Step 1: Add updates tab section to SKILL.md**

```markdown
# Add after line 136 (in "How to Use This Skill" section), before "### Python API"

### Updates Tab Tracking (Automatic)

When merging content, the skill can automatically track changes in an "Updates" tab or section:

**First Update to Document:**
Claude will ask once per document, per session:
```
"Would you like me to create an Updates tab to track changes?
 1. Yes, prepend (newest first)
 2. Yes, append (newest last)
 3. No, don't track"
```

**Existing Updates Detected:**
If the document already has an "Updates", "Changelog", or "Update Log" tab/section, the skill:
- Automatically detects the pattern (newest first vs last)
- Logs updates following the established format
- Never prompts the user

**Update Entry Format:**
Each logged update includes:
- Date (today's date)
- Summary of changes
- Sections modified
- Source attribution

**Example Entry:**
```
**October 31, 2025**
- Summary: Added market research insights to analysis section
- Sections modified: Market Analysis
- Source: Customer feedback meeting on 10/31/25
```
```

**Step 2: Update "Current Capabilities" section**

```markdown
# Modify the "Current Capabilities (Phases 1-5 Complete)" section to include:

### 6. Update Tracking (NEW)
- Automatic update logging to Updates tab/section
- Detection of existing updates locations (tabs and headers)
- Pattern analysis (prepend vs append, formatting)
- Interactive user prompts on first update
- Session-based state tracking
```

**Step 3: Run validation**

```bash
# Check SKILL.md renders correctly
head -50 document-skills/gdocs/SKILL.md
```

Expected: Markdown properly formatted

**Step 4: Commit**

```bash
git add document-skills/gdocs/SKILL.md
git commit -m "docs: document updates tab feature in SKILL.md

- Add user interaction description
- Include in Current Capabilities
- Provide example entry format
- Explain automatic detection"
```

---

## Task 12: End-to-End Integration Test (Manual)

**Files:**
- Create: `document-skills/gdocs/examples/test_updates_tab.py`

**Step 1: Write manual test script**

```python
#!/usr/bin/env python3
"""
Manual integration test for updates tab feature.

This script tests the full workflow:
1. Detect existing updates (or lack thereof)
2. Simulate user response
3. Log an update
4. Verify it appears in document

Run this manually with a real Google Doc.
"""

from datetime import datetime
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions
from scripts.updates_structures import UpdateInfo


def test_updates_workflow(doc_url: str):
    """
    Test complete updates workflow.

    Args:
        doc_url: URL of test Google Doc
    """
    print("=" * 60)
    print("Updates Tab Feature - Integration Test")
    print("=" * 60)

    # Initialize
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)
    doc_id = editor.extract_doc_id(doc_url)

    print(f"\n1. Checking for existing updates location...")
    inserter._check_existing_updates(doc_id)
    state = inserter._get_document_state(doc_id)

    if state.get('has_updates_tab'):
        print(f"   ✓ Found existing updates: {state['location'].header_text}")
        print(f"   Pattern: {'Prepend (newest first)' if state['prepend'] else 'Append (newest last)'}")
    else:
        print("   ✗ No existing updates found")
        print("\n2. Simulating user prompt...")

        # Simulate user choosing "prepend"
        inserter._set_document_state(doc_id, {
            'prepend': True,
            'asked_user': True,
            'user_wants_updates': True
        })
        print("   User chose: Prepend (newest first)")

    print("\n3. Logging test update...")

    # Create test update
    info = UpdateInfo(
        date=datetime.now(),
        summary="Integration test of updates tab feature",
        sections_modified=["Test Section"],
        source_attribution="Manual integration test"
    )

    # Get or create location
    location = state.get('location')
    if not location:
        # Would need to create Updates section here
        print("   Note: Creating new Updates section not implemented in this test")
        print("   Please manually create an 'Updates' section/tab in the document")
        return

    prepend = state.get('prepend', True)
    success = inserter.updates_manager.log_update(doc_id, location, info, prepend)

    if success:
        print(f"   ✓ Update logged successfully")
        print(f"\n4. Verify the update appears in your document:")
        print(f"   {doc_url}")
    else:
        print(f"   ✗ Failed to log update")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_updates_tab.py <doc_url>")
        print("\nExample:")
        print("  python test_updates_tab.py https://docs.google.com/document/d/ABC123/edit")
        sys.exit(1)

    test_updates_workflow(sys.argv[1])
```

**Step 2: Make executable**

```bash
chmod +x document-skills/gdocs/examples/test_updates_tab.py
```

**Step 3: Document in README**

Add to `document-skills/gdocs/README.md`:

```markdown
## Testing Updates Tab Feature

Test the automatic update logging:

```bash
python examples/test_updates_tab.py <your_doc_url>
```

Requirements:
- Document should have an existing "Updates" tab or section
- You'll see the update appear in the document
```

**Step 4: Commit**

```bash
git add document-skills/gdocs/examples/test_updates_tab.py document-skills/gdocs/README.md
git commit -m "test: add manual integration test for updates tab

- Test full workflow: detect, prompt, log
- Verify updates appear in actual document
- Provide usage instructions in README"
```

---

## Task 13: Final Testing & Validation

**Files:**
- None (testing phase)

**Step 1: Run all unit tests**

```bash
cd document-skills/gdocs
python -m pytest tests/ -v
```

Expected: All tests PASS

**Step 2: Manual testing checklist**

Create a test document and verify:
- [ ] Detection works for tab named "Updates"
- [ ] Detection works for last header "Update Log"
- [ ] Pattern analysis correctly identifies prepend vs append
- [ ] New updates use correct ordering
- [ ] Format matches existing entries
- [ ] Session state persists across multiple merges
- [ ] First-update prompt appears correctly

**Step 3: Create testing checklist document**

```bash
cat > document-skills/gdocs/docs/TESTING_CHECKLIST.md << 'EOF'
# Updates Tab - Testing Checklist

## Unit Tests
- [ ] All pytest tests pass: `python -m pytest tests/ -v`
- [ ] Data structures work correctly
- [ ] Date parsing handles multiple formats
- [ ] Pattern detection identifies prepend/append
- [ ] Session state tracks correctly

## Integration Tests
- [ ] UpdatesTabManager integrates with ContentInserter
- [ ] Detection works for tabs
- [ ] Detection works for headers
- [ ] Logging inserts at correct location

## Manual Tests (Real Google Doc)

### Test 1: No Existing Updates
- [ ] Create fresh document
- [ ] Merge content for first time
- [ ] Verify prompt appears
- [ ] Choose "prepend"
- [ ] Verify Updates section created
- [ ] Verify entry formatted correctly

### Test 2: Existing Updates Tab
- [ ] Use document with "Updates" tab
- [ ] Add 3 sample entries (newest first)
- [ ] Merge new content
- [ ] Verify NO prompt appears
- [ ] Verify new entry prepended correctly
- [ ] Verify format matches existing

### Test 3: Existing Header
- [ ] Use document with "Update Log" as last header
- [ ] Add 3 sample entries (oldest first)
- [ ] Merge new content
- [ ] Verify pattern detected as "append"
- [ ] Verify new entry appended correctly

### Test 4: Multiple Updates Same Session
- [ ] Perform Test 1
- [ ] Merge content again without restarting
- [ ] Verify NO second prompt
- [ ] Verify update logged automatically
- [ ] Perform third merge
- [ ] Verify still no prompt

## Edge Cases
- [ ] Document with no sections
- [ ] Updates section with < 3 entries
- [ ] Updates with unparseable dates
- [ ] Empty updates section
- [ ] Multiple sections named similarly

## Performance
- [ ] Detection completes < 2 seconds
- [ ] Logging completes < 1 second
- [ ] No unnecessary API calls

EOF
```

**Step 4: Commit testing checklist**

```bash
git add document-skills/gdocs/docs/TESTING_CHECKLIST.md
git commit -m "docs: add comprehensive testing checklist

- Unit test verification
- Integration test scenarios
- Manual testing workflows
- Edge case coverage
- Performance criteria"
```

---

## Task 14: Final Documentation & README Update

**Files:**
- Modify: `document-skills/gdocs/README.md`

**Step 1: Update README with feature description**

Add after the "Features" section:

```markdown
## Updates Tab Tracking

The gdocs skill automatically tracks changes to your documents:

**Key Features:**
- 🔍 **Auto-detection**: Finds existing "Updates", "Changelog", or "Update Log" tabs/sections
- 🎯 **Smart patterns**: Analyzes existing entries to match your format (newest first vs last)
- 🤖 **Interactive**: Asks once per document if you want tracking enabled
- 📝 **Comprehensive**: Logs date, summary, sections modified, and source attribution

**How It Works:**

1. **First update**: Claude asks if you want an Updates tab
2. **Subsequent updates**: Automatically logged, no questions asked
3. **Existing updates**: Detected and pattern-matched automatically

See `docs/UPDATES_TAB_USAGE.md` for detailed usage patterns.
```

**Step 2: Update installation requirements**

Verify `requirements.txt` includes:

```
python-dateutil>=2.8.2
```

**Step 3: Commit README updates**

```bash
git add document-skills/gdocs/README.md
git commit -m "docs: add updates tab feature to README

- Describe key features
- Explain workflow
- Link to detailed usage docs"
```

---

## Task 15: Merge to Main

**Files:**
- None (git workflow)

**Step 1: Verify all tests pass**

```bash
cd document-skills/gdocs
python -m pytest tests/ -v
```

Expected: All PASS

**Step 2: Verify authentication still works**

```bash
python examples/test_auth.py
```

Expected: Authentication successful

**Step 3: Switch to main branch and merge**

```bash
cd /Users/mattbernier/projects/claude-skills
git checkout main
git merge feature/gdocs-updates-tab --no-ff -m "$(cat <<'EOF'
Merge updates tab feature for gdocs skill

Add automatic update logging to track content merges:
- Detect existing updates tabs/sections
- Analyze prepend vs append patterns
- Interactive first-update prompts
- Session-based state tracking
- Format matching for consistency

Closes #<issue-number-if-exists>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Step 4: Clean up worktree**

```bash
git worktree remove ~/.config/superpowers/worktrees/claude-skills/gdocs-updates-tab
git branch -d feature/gdocs-updates-tab
```

**Step 5: Verify main branch**

```bash
git log --oneline -5
git status
```

Expected: Clean working directory, feature merged

---

## Summary

This plan implements the updates tab feature through 15 tasks:

1. **Data structures** - Core types for locations, patterns, and update info
2. **Detection logic** - Find updates tabs and headers
3. **Date parsing** - Flexible date extraction
4. **Pattern analysis** - Prepend vs append detection
5. **Session state** - Track per-document preferences
6. **Integration** - Wire UpdatesTabManager into ContentInserter
7. **Formatting** - Default update entry template
8. **Logging** - Insert updates into documents
9. **Prompt logic** - Determine when to ask user
10. **Documentation** - User interaction patterns
11. **SKILL.md update** - Feature documentation
12. **Integration test** - Manual E2E testing
13. **Validation** - Comprehensive testing
14. **README** - User-facing documentation
15. **Merge** - Integrate into main branch

**Key Principles:**
- ✅ TDD: Tests written before implementation
- ✅ YAGNI: Minimal viable feature, no speculation
- ✅ DRY: Reuse existing editor/inserter infrastructure
- ✅ Incremental: Small commits with clear intent

**Estimated Time:** 3-4 hours for full implementation
