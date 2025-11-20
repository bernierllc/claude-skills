"""
Tests for content_synthesizer.py

Tests the ContentSynthesizer class which transforms raw notes into
polished presentation content using Claude AI.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scripts.content_synthesizer import ContentSynthesizer, SynthesisResult


class TestContentSynthesizerInitialization:
    """Test ContentSynthesizer initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key creates Anthropic client."""
        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")
        assert synthesizer.anthropic_client is not None

    def test_init_without_api_key(self):
        """Test initialization without API key sets client to None."""
        synthesizer = ContentSynthesizer()
        assert synthesizer.anthropic_client is None


class TestSynthesizeFromNotes:
    """Test synthesize_from_notes method."""

    @patch('scripts.content_synthesizer.Anthropic')
    def test_synthesize_with_valid_notes(self, mock_anthropic):
        """Test synthesis with valid input notes produces expected output."""
        # Mock Anthropic response
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Test Presentation

SLIDES:
1. Introduction
   - Welcome message
   - Overview

2. Main Content
   - Key point 1
   - Key point 2

3. Conclusion
   - Summary
   - Next steps
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        # Create synthesizer and test
        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")
        result = synthesizer.synthesize_from_notes(
            "Raw notes about presentation topic",
            audience="General",
            tone="Professional"
        )

        # Verify result
        assert isinstance(result, SynthesisResult)
        assert result.title == "Test Presentation"
        assert len(result.slides) == 3
        assert result.slides[0].title == "Introduction"
        assert len(result.slides[0].bullets) == 2

    def test_synthesize_without_api_key_raises_error(self):
        """Test that synthesis without API key raises ValueError."""
        synthesizer = ContentSynthesizer()

        with pytest.raises(ValueError, match="Anthropic API key required"):
            synthesizer.synthesize_from_notes("Test notes")

    @patch('scripts.content_synthesizer.Anthropic')
    def test_synthesize_with_empty_notes(self, mock_anthropic):
        """Test synthesis with empty notes handles gracefully."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        with pytest.raises(ValueError, match="Notes cannot be empty"):
            synthesizer.synthesize_from_notes("")

    @patch('scripts.content_synthesizer.Anthropic')
    def test_synthesize_with_custom_parameters(self, mock_anthropic):
        """Test synthesis respects custom audience and tone parameters."""
        mock_response = Mock()
        mock_response.content = [Mock(text="TITLE: Custom\n\nSLIDES:\n1. Test")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")
        result = synthesizer.synthesize_from_notes(
            "Notes",
            audience="Executives",
            tone="Formal"
        )

        # Verify API was called with correct parameters
        call_args = mock_client.messages.create.call_args
        assert "Executives" in str(call_args)
        assert "Formal" in str(call_args)

    @patch('scripts.content_synthesizer.Anthropic')
    def test_synthesize_handles_api_error(self, mock_anthropic):
        """Test synthesis handles API errors gracefully."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        with pytest.raises(Exception, match="API Error"):
            synthesizer.synthesize_from_notes("Test notes")


class TestSynthesisResultParsing:
    """Test parsing of synthesis results."""

    @patch('scripts.content_synthesizer.Anthropic')
    def test_parse_multi_level_bullets(self, mock_anthropic):
        """Test parsing of multi-level bullet points."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Test

SLIDES:
1. Main Point
   - Level 1 bullet
     - Level 2 bullet
     - Another level 2
   - Another level 1
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")
        result = synthesizer.synthesize_from_notes("Notes")

        # Verify nested structure
        assert len(result.slides[0].bullets) >= 2

    @patch('scripts.content_synthesizer.Anthropic')
    def test_parse_malformed_response(self, mock_anthropic):
        """Test parsing handles malformed API responses."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Invalid format without proper structure")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        # Should handle gracefully without crashing
        result = synthesizer.synthesize_from_notes("Notes")
        assert isinstance(result, SynthesisResult)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch('scripts.content_synthesizer.Anthropic')
    def test_very_long_notes(self, mock_anthropic):
        """Test synthesis with very long input notes."""
        mock_response = Mock()
        mock_response.content = [Mock(text="TITLE: Test\n\nSLIDES:\n1. Summary")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        # Create very long notes (10,000 words)
        long_notes = " ".join(["word"] * 10000)

        result = synthesizer.synthesize_from_notes(long_notes)
        assert isinstance(result, SynthesisResult)

    @patch('scripts.content_synthesizer.Anthropic')
    def test_special_characters_in_notes(self, mock_anthropic):
        """Test synthesis handles special characters in notes."""
        mock_response = Mock()
        mock_response.content = [Mock(text="TITLE: Test\n\nSLIDES:\n1. Content")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        # Notes with special characters
        special_notes = "Notes with special chars: @#$%^&*()"

        result = synthesizer.synthesize_from_notes(special_notes)
        assert isinstance(result, SynthesisResult)

    @patch('scripts.content_synthesizer.Anthropic')
    def test_unicode_in_notes(self, mock_anthropic):
        """Test synthesis handles Unicode characters."""
        mock_response = Mock()
        mock_response.content = [Mock(text="TITLE: Test\n\nSLIDES:\n1. Content")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        synthesizer = ContentSynthesizer(anthropic_api_key="test_key")

        # Notes with Unicode
        unicode_notes = "Notes with émojis 🎉 and spëcial çharacters"

        result = synthesizer.synthesize_from_notes(unicode_notes)
        assert isinstance(result, SynthesisResult)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
