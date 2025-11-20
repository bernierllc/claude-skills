"""
Tests for quality_checker.py

Tests the QualityChecker class which validates presentation quality
across design, content, technical, and functional dimensions.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scripts.quality_checker import (
    QualityChecker,
    DesignQualityReport,
    ContentQualityReport,
    TechnicalQualityReport,
    FunctionalQualityReport,
    ComprehensiveQualityReport,
    QualityIssue
)


@pytest.fixture
def mock_slides_service():
    """Create mock Google Slides service."""
    service = Mock()
    presentations = Mock()
    service.presentations.return_value = presentations
    return service


@pytest.fixture
def sample_presentation():
    """Create sample presentation data."""
    return {
        'presentationId': 'test_presentation_id',
        'pageSize': {
            'width': {'magnitude': 720, 'unit': 'PT'},
            'height': {'magnitude': 540, 'unit': 'PT'}
        },
        'slides': [
            {
                'objectId': 'slide1',
                'pageElements': [
                    {
                        'objectId': 'element1',
                        'shape': {
                            'text': {
                                'textElements': [
                                    {
                                        'textRun': {
                                            'content': 'Sample text',
                                            'style': {
                                                'fontSize': {'magnitude': 24, 'unit': 'PT'}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            },
            {
                'objectId': 'slide2',
                'pageElements': [
                    {
                        'objectId': 'element2',
                        'image': {
                            'sourceUrl': 'https://example.com/image.png'
                        }
                    }
                ]
            }
        ]
    }


class TestQualityCheckerInitialization:
    """Test QualityChecker initialization."""

    def test_init_with_services(self, mock_slides_service):
        """Test initialization with API services."""
        checker = QualityChecker(
            slides_service=mock_slides_service,
            anthropic_api_key="test_key"
        )
        assert checker.slides_service is not None
        assert checker.anthropic_client is not None

    def test_init_without_anthropic_key(self, mock_slides_service):
        """Test initialization without Anthropic API key."""
        checker = QualityChecker(slides_service=mock_slides_service)
        assert checker.anthropic_client is None


class TestDesignQualityCheck:
    """Test design quality validation."""

    def test_check_design_quality_success(self, mock_slides_service, sample_presentation):
        """Test successful design quality check."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        assert isinstance(report, DesignQualityReport)
        assert 0 <= report.score <= 100
        assert isinstance(report.issues, list)
        assert isinstance(report.recommendations, list)

    def test_check_contrast_ratios(self, mock_slides_service, sample_presentation):
        """Test WCAG contrast ratio checking."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        # Should have contrast ratio data
        assert isinstance(report.contrast_ratios, dict)

    def test_check_visual_hierarchy(self, mock_slides_service, sample_presentation):
        """Test visual hierarchy validation."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        assert 0 <= report.hierarchy_score <= 100

    def test_check_whitespace(self, mock_slides_service, sample_presentation):
        """Test whitespace distribution checking."""
        # Create crowded slide
        crowded_presentation = sample_presentation.copy()
        crowded_presentation['slides'][0]['pageElements'] = [
            {'objectId': f'element{i}'} for i in range(10)
        ]

        mock_slides_service.presentations().get().execute.return_value = crowded_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        # Should detect crowding
        crowding_issues = [i for i in report.issues if 'crowded' in i.description.lower()]
        assert len(crowding_issues) > 0

    def test_design_quality_error_handling(self, mock_slides_service):
        """Test error handling in design quality check."""
        mock_slides_service.presentations().get().execute.side_effect = Exception("API Error")

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        # Should return report with error issue
        assert report.score == 0.0
        assert any('Failed to check' in i.description for i in report.issues)


class TestContentQualityCheck:
    """Test content quality validation."""

    @patch('scripts.quality_checker.Anthropic')
    def test_check_content_quality_with_api_key(
        self,
        mock_anthropic,
        mock_slides_service,
        sample_presentation
    ):
        """Test content quality check with Anthropic API."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        # Mock Anthropic response
        mock_response = Mock()
        mock_response.content = [Mock(text="""
SCORES:
grammar_score: 85
clarity_score: 90
audience_score: 80
story_arc_score: 75

ISSUES:
- Minor grammar issue

RECOMMENDATIONS:
- Improve clarity
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        checker = QualityChecker(
            slides_service=mock_slides_service,
            anthropic_api_key="test_key"
        )
        report = checker.check_content_quality('test_id')

        assert isinstance(report, ContentQualityReport)
        assert 0 <= report.score <= 100
        assert report.grammar_score > 0
        assert report.clarity_score > 0

    def test_check_content_quality_without_api_key(self, mock_slides_service):
        """Test content quality check without Anthropic API key."""
        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_content_quality('test_id')

        # Should return limited report
        assert isinstance(report, ContentQualityReport)
        assert any('API key not provided' in i.description for i in report.issues)

    @patch('scripts.quality_checker.Anthropic')
    def test_content_quality_empty_presentation(
        self,
        mock_anthropic,
        mock_slides_service
    ):
        """Test content quality check with no text content."""
        empty_presentation = {
            'slides': [{'pageElements': []}]
        }
        mock_slides_service.presentations().get().execute.return_value = empty_presentation

        checker = QualityChecker(
            slides_service=mock_slides_service,
            anthropic_api_key="test_key"
        )
        report = checker.check_content_quality('test_id')

        # Should detect no content
        assert any('No text content' in i.description for i in report.issues)


class TestTechnicalQualityCheck:
    """Test technical quality validation."""

    def test_check_technical_quality_success(self, mock_slides_service, sample_presentation):
        """Test successful technical quality check."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_technical_quality('test_id')

        assert isinstance(report, TechnicalQualityReport)
        assert 0 <= report.score <= 100
        assert 0 <= report.image_quality_score <= 100
        assert 0 <= report.font_availability_score <= 100

    def test_check_image_quality(self, mock_slides_service, sample_presentation):
        """Test image quality validation."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_technical_quality('test_id')

        # Should have image quality score
        assert isinstance(report.image_quality_score, float)

    def test_check_font_availability(self, mock_slides_service, sample_presentation):
        """Test font availability checking."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_technical_quality('test_id')

        assert isinstance(report.font_availability_score, float)

    def test_check_link_validity(self, mock_slides_service, sample_presentation):
        """Test link validity checking."""
        # Add link to presentation
        presentation_with_links = sample_presentation.copy()
        presentation_with_links['slides'][0]['pageElements'][0]['shape']['text']['textElements'][0]['textRun']['style'] = {
            'link': {'url': 'https://example.com'}
        }

        mock_slides_service.presentations().get().execute.return_value = presentation_with_links

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_technical_quality('test_id')

        # Should check links
        assert isinstance(report.link_validity_score, float)


class TestFunctionalQualityCheck:
    """Test functional quality validation."""

    def test_check_functional_quality_success(self, mock_slides_service, sample_presentation):
        """Test successful functional quality check."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_functional_quality('test_id')

        assert isinstance(report, FunctionalQualityReport)
        assert 0 <= report.score <= 100

    def test_check_slide_count_optimal(self, mock_slides_service, sample_presentation):
        """Test slide count validation - optimal range."""
        # Create presentation with 15 slides (optimal)
        optimal_presentation = sample_presentation.copy()
        optimal_presentation['slides'] = [
            {'objectId': f'slide{i}', 'pageElements': []}
            for i in range(15)
        ]

        mock_slides_service.presentations().get().execute.return_value = optimal_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_functional_quality('test_id')

        # Should have high slide count score
        assert report.slide_count_score >= 85

    def test_check_slide_count_too_few(self, mock_slides_service, sample_presentation):
        """Test slide count validation - too few slides."""
        # Only 2 slides
        few_slides = sample_presentation.copy()
        few_slides['slides'] = few_slides['slides'][:1]

        mock_slides_service.presentations().get().execute.return_value = few_slides

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_functional_quality('test_id')

        # Should flag as potentially too short
        assert any('too short' in i.description.lower() for i in report.issues)

    def test_check_reading_level(self, mock_slides_service, sample_presentation):
        """Test reading level and text density checking."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_functional_quality('test_id')

        assert isinstance(report.reading_level_score, float)

    def test_check_accessibility(self, mock_slides_service, sample_presentation):
        """Test accessibility compliance checking."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_functional_quality('test_id')

        # Should check for alt text on images
        assert isinstance(report.accessibility_score, float)


class TestComprehensiveQualityCheck:
    """Test comprehensive quality validation."""

    @patch('scripts.quality_checker.Anthropic')
    def test_run_comprehensive_check(
        self,
        mock_anthropic,
        mock_slides_service,
        sample_presentation
    ):
        """Test running all quality checks together."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        # Mock Anthropic for content check
        mock_response = Mock()
        mock_response.content = [Mock(text="""
SCORES:
grammar_score: 80
clarity_score: 80
audience_score: 80
story_arc_score: 80
""")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        checker = QualityChecker(
            slides_service=mock_slides_service,
            anthropic_api_key="test_key"
        )
        report = checker.run_comprehensive_check('test_id')

        assert isinstance(report, ComprehensiveQualityReport)
        assert 0 <= report.overall_score <= 100
        assert isinstance(report.design_report, DesignQualityReport)
        assert isinstance(report.content_report, ContentQualityReport)
        assert isinstance(report.technical_report, TechnicalQualityReport)
        assert isinstance(report.functional_report, FunctionalQualityReport)

    def test_comprehensive_check_prioritizes_issues(
        self,
        mock_slides_service,
        sample_presentation
    ):
        """Test that comprehensive check prioritizes issues by severity."""
        mock_slides_service.presentations().get().execute.return_value = sample_presentation

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.run_comprehensive_check('test_id')

        # Priority fixes should be sorted by severity
        if report.priority_fixes:
            severities = [issue.severity for issue in report.priority_fixes]
            # Critical should come before warning, warning before info
            critical_indices = [i for i, s in enumerate(severities) if s == 'critical']
            warning_indices = [i for i, s in enumerate(severities) if s == 'warning']

            if critical_indices and warning_indices:
                assert max(critical_indices) < min(warning_indices)


class TestQualityIssues:
    """Test QualityIssue dataclass."""

    def test_create_quality_issue(self):
        """Test creating quality issues."""
        issue = QualityIssue(
            severity="warning",
            category="design",
            description="Test issue",
            location="Slide 1",
            recommendation="Fix this"
        )

        assert issue.severity == "warning"
        assert issue.category == "design"
        assert issue.description == "Test issue"
        assert issue.location == "Slide 1"
        assert issue.recommendation == "Fix this"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_check_quality_empty_presentation(self, mock_slides_service):
        """Test quality check with empty presentation."""
        empty_presentation = {'slides': []}
        mock_slides_service.presentations().get().execute.return_value = empty_presentation

        checker = QualityChecker(slides_service=mock_slides_service)

        design_report = checker.check_design_quality('test_id')
        assert isinstance(design_report, DesignQualityReport)

    def test_check_quality_api_failure(self, mock_slides_service):
        """Test quality check when API fails."""
        mock_slides_service.presentations().get().execute.side_effect = Exception("API Error")

        checker = QualityChecker(slides_service=mock_slides_service)
        report = checker.check_design_quality('test_id')

        # Should return report with error
        assert report.score == 0.0
        assert len(report.issues) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
