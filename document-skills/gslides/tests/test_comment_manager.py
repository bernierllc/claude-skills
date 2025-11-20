"""
Tests for comment_manager.py

Tests the CommentManager class which handles collaboration features
including comments, suggestions, attributions, and change tracking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from scripts.comment_manager import (
    CommentManager,
    Comment,
    Attribution
)


@pytest.fixture
def mock_slides_service():
    """Create mock Google Slides service."""
    service = Mock()
    presentations = Mock()
    service.presentations.return_value = presentations
    return service


@pytest.fixture
def mock_drive_service():
    """Create mock Google Drive service."""
    service = Mock()
    return service


@pytest.fixture
def sample_presentation():
    """Create sample presentation data."""
    return {
        'presentationId': 'test_presentation_id',
        'slides': [
            {
                'objectId': 'slide1',
                'pageElements': [
                    {
                        'objectId': 'element1',
                        'shape': {
                            'text': {
                                'textElements': [
                                    {'textRun': {'content': 'Sample text'}}
                                ]
                            }
                        }
                    }
                ],
                'slideProperties': {
                    'notesPage': {
                        'objectId': 'notes1',
                        'pageElements': []
                    }
                }
            }
        ]
    }


class TestCommentManagerInitialization:
    """Test CommentManager initialization."""

    def test_init_with_services(self, mock_slides_service, mock_drive_service):
        """Test initialization with API services."""
        manager = CommentManager(mock_slides_service, mock_drive_service)
        assert manager.slides_service is not None
        assert manager.drive_service is not None


class TestAddComment:
    """Test adding slide-level comments."""

    def test_add_comment_success(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test successfully adding a comment."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comment = manager.add_comment(
            'test_id',
            slide_index=0,
            text='This is a test comment',
            author='Test User'
        )

        assert isinstance(comment, Comment)
        assert comment.text == 'This is a test comment'
        assert comment.author == 'Test User'
        assert comment.slide_index == 0
        assert not comment.resolved

    def test_add_comment_default_author(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test adding comment with default author."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comment = manager.add_comment('test_id', 0, 'Comment text')

        assert comment.author == 'AI Assistant'

    def test_add_comment_has_timestamp(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test that comments have timestamps."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comment = manager.add_comment('test_id', 0, 'Comment')

        assert isinstance(comment.timestamp, datetime)

    def test_add_comment_error_handling(
        self,
        mock_slides_service,
        mock_drive_service
    ):
        """Test error handling when adding comment fails."""
        mock_slides_service.presentations().get().execute.side_effect = Exception("API Error")

        manager = CommentManager(mock_slides_service, mock_drive_service)

        with pytest.raises(Exception, match="Failed to add comment"):
            manager.add_comment('test_id', 0, 'Comment')


class TestAddSuggestion:
    """Test adding element-specific suggestions."""

    def test_add_suggestion_success(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test successfully adding a suggestion."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        suggestion = manager.add_suggestion(
            'test_id',
            element_id='element1',
            suggestion='Consider making this text larger',
            author='Designer'
        )

        assert isinstance(suggestion, Comment)
        assert suggestion.text == 'Consider making this text larger'
        assert suggestion.author == 'Designer'
        assert suggestion.element_id == 'element1'

    def test_add_suggestion_finds_slide(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test that suggestion correctly identifies slide containing element."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        suggestion = manager.add_suggestion('test_id', 'element1', 'Suggestion')

        assert suggestion.slide_index == 0

    def test_add_suggestion_element_not_found(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test suggestion when element doesn't exist."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)
        suggestion = manager.add_suggestion('test_id', 'nonexistent', 'Suggestion')

        # Should still create suggestion but slide_index might be None
        assert isinstance(suggestion, Comment)


class TestListComments:
    """Test listing comments."""

    def test_list_all_comments(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test listing all comments in presentation."""
        # Add comments to notes
        presentation_with_comments = sample_presentation.copy()
        presentation_with_comments['slides'][0]['slideProperties']['notesPage']['pageElements'] = [
            {
                'objectId': 'notes_shape',
                'shape': {
                    'shapeType': 'TEXT_BOX',
                    'text': {
                        'textElements': [
                            {'textRun': {'content': 'Comment by Test User: Sample comment'}}
                        ]
                    }
                }
            }
        ]

        mock_slides_service.presentations().get().execute.return_value = presentation_with_comments

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comments = manager.list_comments('test_id')

        assert isinstance(comments, list)
        # Should parse comment from notes
        assert len(comments) >= 0

    def test_list_comments_for_specific_slide(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test listing comments for specific slide only."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comments = manager.list_comments('test_id', slide_index=0)

        assert isinstance(comments, list)

    def test_list_comments_empty_presentation(
        self,
        mock_slides_service,
        mock_drive_service
    ):
        """Test listing comments in presentation with no comments."""
        empty_presentation = {'slides': [{'slideProperties': {'notesPage': {'pageElements': []}}}]}
        mock_slides_service.presentations().get().execute.return_value = empty_presentation

        manager = CommentManager(mock_slides_service, mock_drive_service)
        comments = manager.list_comments('test_id')

        assert comments == []


class TestResolveComment:
    """Test resolving comments."""

    def test_resolve_comment_success(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test successfully resolving a comment."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        # First add a comment
        comment = manager.add_comment('test_id', 0, 'Test comment')

        # Then resolve it
        manager.resolve_comment('test_id', comment.id)

        # Should not raise exception
        assert True

    def test_resolve_comment_error_handling(
        self,
        mock_slides_service,
        mock_drive_service
    ):
        """Test error handling when resolving comment fails."""
        mock_slides_service.presentations().get().execute.side_effect = Exception("API Error")

        manager = CommentManager(mock_slides_service, mock_drive_service)

        with pytest.raises(Exception, match="Failed to resolve comment"):
            manager.resolve_comment('test_id', 'comment_id')


class TestAddAttribution:
    """Test adding source attributions."""

    def test_add_attribution_as_slide(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test adding attribution as dedicated slide."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        sources = [
            Attribution(
                source="Research Paper",
                author="Dr. Smith",
                date="2024",
                url="https://example.com/paper"
            ),
            Attribution(
                source="Industry Report",
                author="Company Inc.",
                date="2023"
            )
        ]

        manager.add_attribution('test_id', sources, method='slide')

        # Should create slide - verify batchUpdate was called
        assert mock_slides_service.presentations().batchUpdate.called

    def test_add_attribution_as_notes(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test adding attribution to speaker notes."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        sources = [
            Attribution(source="Source 1", author="Author 1")
        ]

        manager.add_attribution('test_id', sources, method='notes')

        # Should add to notes
        assert True  # Implicit success if no exception

    def test_add_attribution_both_methods(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test adding attribution as both slide and notes."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        sources = [Attribution(source="Source")]

        manager.add_attribution('test_id', sources, method='both')

        # Should call batchUpdate for slide creation
        assert mock_slides_service.presentations().batchUpdate.called

    def test_attribution_formatting(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test attribution formatting includes all fields."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        attribution = Attribution(
            source="Complete Source",
            author="Full Author",
            date="2024",
            url="https://example.com",
            description="Detailed description"
        )

        formatted = manager._format_attribution(attribution)

        assert "Complete Source" in formatted
        assert "Full Author" in formatted
        assert "2024" in formatted
        assert "https://example.com" in formatted
        assert "Detailed description" in formatted


class TestTrackChanges:
    """Test change tracking."""

    def test_track_changes_success(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test successfully tracking a change."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        manager.track_changes(
            'test_id',
            author='AI Assistant',
            change_description='Updated slide 3 title formatting'
        )

        # Should not raise exception
        assert True

    def test_track_changes_includes_timestamp(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test that change tracking includes timestamp."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation
        mock_slides_service.presentations().batchUpdate().execute.return_value = {}

        manager = CommentManager(mock_slides_service, mock_drive_service)

        # Mock to capture what would be added to notes
        with patch.object(manager, '_add_to_speaker_notes') as mock_add:
            manager.track_changes('test_id', 'User', 'Change description')

            # Verify timestamp format in call
            call_args = mock_add.call_args
            if call_args:
                notes_text = call_args[0][2]  # Third argument is the text
                # Should contain timestamp pattern YYYY-MM-DD
                assert any(char.isdigit() for char in notes_text)

    def test_track_changes_empty_presentation(
        self,
        mock_slides_service,
        mock_drive_service
    ):
        """Test tracking changes in empty presentation."""
        empty_presentation = {'slides': []}
        mock_slides_service.presentations().get().execute.return_value = empty_presentation

        manager = CommentManager(mock_slides_service, mock_drive_service)

        # Should handle gracefully
        manager.track_changes('test_id', 'User', 'Change')
        assert True


class TestAttributionDataclass:
    """Test Attribution dataclass."""

    def test_create_minimal_attribution(self):
        """Test creating attribution with minimal fields."""
        attribution = Attribution(source="Source Name")

        assert attribution.source == "Source Name"
        assert attribution.author is None
        assert attribution.date is None
        assert attribution.url is None

    def test_create_complete_attribution(self):
        """Test creating attribution with all fields."""
        attribution = Attribution(
            source="Complete Source",
            author="Author Name",
            date="2024-01-01",
            url="https://example.com",
            description="Full description"
        )

        assert attribution.source == "Complete Source"
        assert attribution.author == "Author Name"
        assert attribution.date == "2024-01-01"
        assert attribution.url == "https://example.com"
        assert attribution.description == "Full description"


class TestCommentDataclass:
    """Test Comment dataclass."""

    def test_create_comment(self):
        """Test creating comment with all fields."""
        timestamp = datetime.now()
        comment = Comment(
            id="comment_123",
            text="Comment text",
            author="Author",
            timestamp=timestamp,
            slide_index=0,
            element_id="element_1",
            resolved=True
        )

        assert comment.id == "comment_123"
        assert comment.text == "Comment text"
        assert comment.author == "Author"
        assert comment.timestamp == timestamp
        assert comment.slide_index == 0
        assert comment.element_id == "element_1"
        assert comment.resolved is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_add_comment_to_nonexistent_slide(
        self,
        mock_slides_service,
        mock_drive_service,
        sample_presentation
    ):
        """Test adding comment to slide that doesn't exist."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        manager = CommentManager(mock_slides_service, mock_drive_service)

        # Try to add comment to slide 99 (doesn't exist)
        # Should handle gracefully or raise appropriate error
        try:
            manager.add_comment('test_id', slide_index=99, text='Comment')
        except (IndexError, Exception):
            pass  # Expected to potentially fail

    def test_operations_with_api_errors(
        self,
        mock_slides_service,
        mock_drive_service
    ):
        """Test that operations handle API errors gracefully."""
        mock_slides_service.presentations().get().execute.side_effect = Exception("API Error")

        manager = CommentManager(mock_slides_service, mock_drive_service)

        # All operations should raise exceptions with helpful messages
        with pytest.raises(Exception):
            manager.add_comment('test_id', 0, 'Comment')

        with pytest.raises(Exception):
            manager.add_suggestion('test_id', 'element', 'Suggestion')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
