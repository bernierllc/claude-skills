"""
Tests for whimsy_injector.py

Tests the WhimsyInjector class which adds personality and creativity
to presentations through metaphors, analogies, and storytelling.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scripts.whimsy_injector import (
    WhimsyInjector,
    PersonalityLevel,
    WhimsyResult
)


class TestWhimsyInjectorInitialization:
    """Test WhimsyInjector initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key creates Anthropic client."""
        injector = WhimsyInjector(anthropic_api_key="test_key")
        assert injector.anthropic_client is not None

    def test_init_without_api_key(self):
        """Test initialization without API key sets client to None."""
        injector = WhimsyInjector()
        assert injector.anthropic_client is None


class TestPersonalityInjection:
    """Test personality injection at different levels."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_inject_minimal_personality(self, mock_anthropic):
        """Test injecting minimal personality (subtle touches)."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ENHANCED: Professional presentation with light touches of personality.

CHANGES:
- Added subtle metaphor in introduction
- Refined transition language
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        result = injector.inject_personality(
            "Dry technical content",
            level=PersonalityLevel.MINIMAL
        )

        assert isinstance(result, WhimsyResult)
        assert "Professional" in result.enhanced_content

    @patch('scripts.whimsy_injector.Anthropic')
    def test_inject_moderate_personality(self, mock_anthropic):
        """Test injecting moderate personality (balanced approach)."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ENHANCED: Engaging content with metaphors and analogies.

CHANGES:
- Added sailing metaphor for journey
- Included relatable analogy
- Enhanced storytelling elements
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        result = injector.inject_personality(
            "Technical content",
            level=PersonalityLevel.MODERATE
        )

        assert "metaphor" in result.enhanced_content.lower()

    @patch('scripts.whimsy_injector.Anthropic')
    def test_inject_maximal_personality(self, mock_anthropic):
        """Test injecting maximal personality (creative and bold)."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ENHANCED: Bold, creative content with vivid storytelling!

CHANGES:
- Transformed into epic hero's journey
- Added colorful metaphors throughout
- Injected humor and surprise elements
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        result = injector.inject_personality(
            "Plain content",
            level=PersonalityLevel.MAXIMAL
        )

        assert "creative" in result.enhanced_content.lower() or "bold" in result.enhanced_content.lower()

    def test_inject_without_api_key_raises_error(self):
        """Test that injection without API key raises ValueError."""
        injector = WhimsyInjector()

        with pytest.raises(ValueError, match="Anthropic API key required"):
            injector.inject_personality("Content", PersonalityLevel.MINIMAL)


class TestAppropriatenessValidation:
    """Test validation of personality appropriateness."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_validate_appropriate_content(self, mock_anthropic):
        """Test validating appropriate personality injection."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
APPROPRIATE: Yes

FEEDBACK:
- Metaphors align with professional context
- Tone matches audience expectations
- Personality enhances, doesn't distract
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        is_appropriate = injector.validate_appropriateness(
            original_content="Technical overview",
            enhanced_content="Technical overview with sailing metaphor",
            audience="Engineers"
        )

        assert is_appropriate is True

    @patch('scripts.whimsy_injector.Anthropic')
    def test_validate_inappropriate_content(self, mock_anthropic):
        """Test detecting inappropriate personality injection."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
APPROPRIATE: No

FEEDBACK:
- Metaphors too playful for serious context
- Tone mismatch with executive audience
- Personality detracts from message
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        is_appropriate = injector.validate_appropriateness(
            original_content="Financial results",
            enhanced_content="Financial results with silly jokes",
            audience="Board of Directors"
        )

        assert is_appropriate is False

    @patch('scripts.whimsy_injector.Anthropic')
    def test_validate_with_context(self, mock_anthropic):
        """Test validation considers context appropriately."""
        mock_response = Mock()
        mock_response.content = [Mock(text="APPROPRIATE: Yes\nFEEDBACK: Good fit")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        is_appropriate = injector.validate_appropriateness(
            original_content="Team meeting content",
            enhanced_content="Team meeting with casual analogies",
            audience="Internal team",
            context="Informal team meeting"
        )

        # Verify context was passed to API
        call_args = mock_client.messages.create.call_args
        assert "Informal team meeting" in str(call_args)


class TestMetaphorGeneration:
    """Test metaphor and analogy generation."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_generate_metaphor_for_concept(self, mock_anthropic):
        """Test generating metaphor for technical concept."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
METAPHOR: "Like a well-organized library"

EXPLANATION:
Databases are like libraries - they organize information systematically,
have indexes for quick lookup, and require proper cataloging.
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        metaphor = injector.generate_metaphor("database indexing")

        assert isinstance(metaphor, str)
        assert "library" in metaphor.lower()

    @patch('scripts.whimsy_injector.Anthropic')
    def test_generate_multiple_metaphors(self, mock_anthropic):
        """Test generating multiple metaphor options."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
METAPHORS:
1. Like a highway system
2. Like a postal network
3. Like a river flowing
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        metaphors = injector.generate_metaphors("data flow", count=3)

        assert isinstance(metaphors, list)
        assert len(metaphors) >= 1

    @patch('scripts.whimsy_injector.Anthropic')
    def test_generate_domain_specific_metaphor(self, mock_anthropic):
        """Test generating metaphors for specific domains."""
        mock_response = Mock()
        mock_response.content = [Mock(text="METAPHOR: Like a recipe in cooking")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        metaphor = injector.generate_metaphor(
            concept="algorithm",
            domain="cooking"
        )

        assert "recipe" in metaphor.lower() or "cooking" in metaphor.lower()


class TestStorytellingElements:
    """Test storytelling enhancement features."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_add_storytelling_hook(self, mock_anthropic):
        """Test adding compelling opening hooks."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
HOOK: "Imagine a world where..."

This opening immediately engages the audience by prompting visualization.
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        hook = injector.create_hook("We're launching a new product")

        assert isinstance(hook, str)
        assert len(hook) > 0

    @patch('scripts.whimsy_injector.Anthropic')
    def test_add_narrative_transitions(self, mock_anthropic):
        """Test adding narrative transitions between sections."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TRANSITION: "But here's where it gets interesting..."

Creates curiosity and bridges sections smoothly.
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        transition = injector.create_transition(
            from_section="Problem statement",
            to_section="Solution proposal"
        )

        assert isinstance(transition, str)

    @patch('scripts.whimsy_injector.Anthropic')
    def test_add_emotional_elements(self, mock_anthropic):
        """Test adding appropriate emotional elements."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ENHANCED: Content with emotional resonance and human connection.

ELEMENTS ADDED:
- Relatable challenge everyone faces
- Aspirational vision
- Sense of possibility
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        result = injector.add_emotional_elements("Dry facts and figures")

        assert isinstance(result, str)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_empty_content(self, mock_anthropic):
        """Test handling empty content."""
        injector = WhimsyInjector(anthropic_api_key="test_key")

        with pytest.raises(ValueError, match="Content cannot be empty"):
            injector.inject_personality("", PersonalityLevel.MINIMAL)

    @patch('scripts.whimsy_injector.Anthropic')
    def test_very_long_content(self, mock_anthropic):
        """Test handling very long content."""
        mock_response = Mock()
        mock_response.content = [Mock(text="ENHANCED: Summary content")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")

        # Very long content
        long_content = " ".join(["content"] * 10000)

        result = injector.inject_personality(long_content, PersonalityLevel.MINIMAL)
        assert isinstance(result, WhimsyResult)

    @patch('scripts.whimsy_injector.Anthropic')
    def test_special_characters_in_content(self, mock_anthropic):
        """Test handling special characters."""
        mock_response = Mock()
        mock_response.content = [Mock(text="ENHANCED: Content with special chars")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")

        special_content = "Content with @#$%^&*() characters"

        result = injector.inject_personality(special_content, PersonalityLevel.MINIMAL)
        assert isinstance(result, WhimsyResult)

    @patch('scripts.whimsy_injector.Anthropic')
    def test_api_error_handling(self, mock_anthropic):
        """Test graceful handling of API errors."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")

        with pytest.raises(Exception, match="API Error"):
            injector.inject_personality("Content", PersonalityLevel.MINIMAL)

    @patch('scripts.whimsy_injector.Anthropic')
    def test_invalid_personality_level(self, mock_anthropic):
        """Test handling invalid personality level."""
        injector = WhimsyInjector(anthropic_api_key="test_key")

        with pytest.raises((ValueError, AttributeError)):
            injector.inject_personality("Content", "INVALID_LEVEL")


class TestResultMetadata:
    """Test WhimsyResult metadata tracking."""

    @patch('scripts.whimsy_injector.Anthropic')
    def test_result_tracks_changes(self, mock_anthropic):
        """Test that results track what was changed."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ENHANCED: Modified content

CHANGES:
- Added metaphor
- Enhanced opening
- Improved transitions
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        injector = WhimsyInjector(anthropic_api_key="test_key")
        result = injector.inject_personality("Original", PersonalityLevel.MODERATE)

        assert hasattr(result, 'changes') or hasattr(result, 'enhanced_content')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
