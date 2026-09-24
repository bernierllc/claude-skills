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


def test_content_inserter_has_updates_manager():
    """Test ContentInserter initializes UpdatesTabManager."""
    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    assert hasattr(inserter, 'updates_manager')
    from scripts.updates_tab_manager import UpdatesTabManager
    assert isinstance(inserter.updates_manager, UpdatesTabManager)
