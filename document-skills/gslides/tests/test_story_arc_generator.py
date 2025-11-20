"""
Tests for story_arc_generator.py

Tests the StoryArcGenerator class which creates narrative structures
for presentations using proven storytelling frameworks.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scripts.story_arc_generator import (
    StoryArcGenerator,
    StoryArc,
    ArcType,
    ArcSegment
)


class TestStoryArcGeneratorInitialization:
    """Test StoryArcGenerator initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key creates Anthropic client."""
        generator = StoryArcGenerator(anthropic_api_key="test_key")
        assert generator.anthropic_client is not None

    def test_init_without_api_key(self):
        """Test initialization without API key sets client to None."""
        generator = StoryArcGenerator()
        assert generator.anthropic_client is None


class TestGenerateArc:
    """Test generate_arc method for different content types."""

    @patch('scripts.story_arc_generator.Anthropic')
    def test_generate_arc_hero_journey(self, mock_anthropic):
        """Test generating Hero's Journey arc."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Hero's Journey

SEGMENTS:
1. Ordinary World - Current state
2. Call to Adventure - The challenge
3. Transformation - The solution
4. Return - New reality
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc(
            content_summary="Product launch presentation",
            arc_type=ArcType.HERO_JOURNEY
        )

        assert isinstance(arc, StoryArc)
        assert arc.arc_type == ArcType.HERO_JOURNEY
        assert len(arc.segments) == 4

    @patch('scripts.story_arc_generator.Anthropic')
    def test_generate_arc_problem_solution(self, mock_anthropic):
        """Test generating Problem-Solution arc."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Problem-Solution

SEGMENTS:
1. Problem Statement - Define the issue
2. Impact Analysis - Show consequences
3. Solution Overview - Present the fix
4. Benefits - Highlight improvements
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc(
            content_summary="Technical problem presentation",
            arc_type=ArcType.PROBLEM_SOLUTION
        )

        assert arc.arc_type == ArcType.PROBLEM_SOLUTION
        assert len(arc.segments) >= 3

    @patch('scripts.story_arc_generator.Anthropic')
    def test_generate_arc_before_after(self, mock_anthropic):
        """Test generating Before-After arc."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Before-After

SEGMENTS:
1. Before State - Old way
2. Transition - The change
3. After State - New way
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc(
            content_summary="Transformation story",
            arc_type=ArcType.BEFORE_AFTER
        )

        assert arc.arc_type == ArcType.BEFORE_AFTER
        assert len(arc.segments) >= 2

    def test_generate_arc_without_api_key_raises_error(self):
        """Test that arc generation without API key raises ValueError."""
        generator = StoryArcGenerator()

        with pytest.raises(ValueError, match="Anthropic API key required"):
            generator.generate_arc("Test content", ArcType.HERO_JOURNEY)


class TestArcScoring:
    """Test arc scoring and validation."""

    @patch('scripts.story_arc_generator.Anthropic')
    def test_score_arc_high_quality(self, mock_anthropic):
        """Test scoring a well-structured arc."""
        # Mock arc generation
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Hero's Journey

SEGMENTS:
1. Setup - Detailed setup
2. Conflict - Clear conflict
3. Resolution - Strong resolution
""")]

        # Mock scoring response
        mock_score_response = Mock()
        mock_score_response.content = [Mock(text="SCORE: 85\nStrong narrative flow")]

        mock_client = Mock()
        mock_client.messages.create.side_effect = [mock_response, mock_score_response]
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc("Content", ArcType.HERO_JOURNEY)

        # Score the arc
        score = generator.score_arc(arc)

        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    @patch('scripts.story_arc_generator.Anthropic')
    def test_score_arc_low_quality(self, mock_anthropic):
        """Test scoring a poorly structured arc."""
        mock_response = Mock()
        mock_response.content = [Mock(text="ARC: Generic\nSEGMENTS:\n1. Vague point")]

        mock_score_response = Mock()
        mock_score_response.content = [Mock(text="SCORE: 45\nWeak structure")]

        mock_client = Mock()
        mock_client.messages.create.side_effect = [mock_response, mock_score_response]
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc("Content", ArcType.PROBLEM_SOLUTION)

        score = generator.score_arc(arc)
        assert score < 60


class TestArcImprovement:
    """Test narrative flow improvements."""

    @patch('scripts.story_arc_generator.Anthropic')
    def test_improve_arc_flow(self, mock_anthropic):
        """Test improving arc narrative flow."""
        # Initial arc
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Basic

SEGMENTS:
1. Start
2. Middle
3. End
""")]

        # Improved arc
        mock_improve_response = Mock()
        mock_improve_response.content = [Mock(text="""
ARC: Improved

SEGMENTS:
1. Compelling Start - Hook the audience
2. Engaging Middle - Build tension
3. Strong End - Clear resolution
""")]

        mock_client = Mock()
        mock_client.messages.create.side_effect = [mock_response, mock_improve_response]
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        original_arc = generator.generate_arc("Content", ArcType.HERO_JOURNEY)

        improved_arc = generator.improve_arc(original_arc)

        assert isinstance(improved_arc, StoryArc)
        assert len(improved_arc.segments) >= len(original_arc.segments)

    @patch('scripts.story_arc_generator.Anthropic')
    def test_improve_arc_with_feedback(self, mock_anthropic):
        """Test improving arc with specific feedback."""
        mock_response = Mock()
        mock_response.content = [Mock(text="ARC: Basic\nSEGMENTS:\n1. Weak")]

        mock_improve_response = Mock()
        mock_improve_response.content = [Mock(text="""
ARC: Strengthened

SEGMENTS:
1. Strong Opening - Address feedback
""")]

        mock_client = Mock()
        mock_client.messages.create.side_effect = [mock_response, mock_improve_response]
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc("Content", ArcType.PROBLEM_SOLUTION)

        improved = generator.improve_arc(arc, feedback="Make opening stronger")

        # Verify improvement was attempted
        assert improved is not None


class TestArcSegments:
    """Test arc segment handling."""

    def test_arc_segment_creation(self):
        """Test creating individual arc segments."""
        segment = ArcSegment(
            title="Introduction",
            description="Set the stage",
            key_points=["Point 1", "Point 2"],
            slide_count=2
        )

        assert segment.title == "Introduction"
        assert len(segment.key_points) == 2
        assert segment.slide_count == 2

    @patch('scripts.story_arc_generator.Anthropic')
    def test_arc_segment_parsing(self, mock_anthropic):
        """Test parsing segments from API response."""
        mock_response = Mock()
        mock_response.content = [Mock(text="""
ARC: Test

SEGMENTS:
1. First Segment - Description
   - Key point 1
   - Key point 2

2. Second Segment - Another description
   - Key point A
   - Key point B
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")
        arc = generator.generate_arc("Content", ArcType.HERO_JOURNEY)

        # Verify segments were parsed correctly
        assert len(arc.segments) == 2
        assert all(isinstance(seg, ArcSegment) for seg in arc.segments)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('scripts.story_arc_generator.Anthropic')
    def test_empty_content_summary(self, mock_anthropic):
        """Test handling empty content summary."""
        generator = StoryArcGenerator(anthropic_api_key="test_key")

        with pytest.raises(ValueError, match="Content summary cannot be empty"):
            generator.generate_arc("", ArcType.HERO_JOURNEY)

    @patch('scripts.story_arc_generator.Anthropic')
    def test_invalid_arc_type(self, mock_anthropic):
        """Test handling invalid arc type."""
        generator = StoryArcGenerator(anthropic_api_key="test_key")

        # Should handle gracefully
        with pytest.raises((ValueError, AttributeError)):
            generator.generate_arc("Content", "INVALID_TYPE")

    @patch('scripts.story_arc_generator.Anthropic')
    def test_api_error_handling(self, mock_anthropic):
        """Test handling API errors gracefully."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")

        with pytest.raises(Exception, match="API Error"):
            generator.generate_arc("Content", ArcType.HERO_JOURNEY)

    @patch('scripts.story_arc_generator.Anthropic')
    def test_very_long_content_summary(self, mock_anthropic):
        """Test handling very long content summaries."""
        mock_response = Mock()
        mock_response.content = [Mock(text="ARC: Test\nSEGMENTS:\n1. Summary")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        generator = StoryArcGenerator(anthropic_api_key="test_key")

        # Very long summary
        long_summary = " ".join(["content"] * 5000)

        arc = generator.generate_arc(long_summary, ArcType.HERO_JOURNEY)
        assert isinstance(arc, StoryArc)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
