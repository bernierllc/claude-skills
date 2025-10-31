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
