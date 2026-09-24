from datetime import datetime
from scripts.updates_tab_manager import UpdatesTabManager
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.updates_structures import UpdateInfo


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
