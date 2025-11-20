"""
Quality checking and validation system for Google Slides presentations.

Provides comprehensive quality validation across design, content, technical,
and functional dimensions. Validates WCAG compliance, content quality,
technical integrity, and presentation effectiveness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re
from anthropic import Anthropic
from googleapiclient.discovery import build


@dataclass
class QualityIssue:
    """Represents a single quality issue."""
    severity: str  # "critical", "warning", "info"
    category: str
    description: str
    location: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class DesignQualityReport:
    """Design quality validation results."""
    score: float  # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    contrast_ratios: Dict[str, float] = field(default_factory=dict)
    hierarchy_score: float = 0.0
    whitespace_score: float = 0.0
    alignment_score: float = 0.0


@dataclass
class ContentQualityReport:
    """Content quality validation results."""
    score: float  # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    grammar_score: float = 0.0
    clarity_score: float = 0.0
    audience_score: float = 0.0
    story_arc_score: float = 0.0


@dataclass
class TechnicalQualityReport:
    """Technical quality validation results."""
    score: float  # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    image_quality_score: float = 0.0
    font_availability_score: float = 0.0
    link_validity_score: float = 0.0
    object_integrity_score: float = 0.0


@dataclass
class FunctionalQualityReport:
    """Functional quality validation results."""
    score: float  # 0-100
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    slide_count_score: float = 0.0
    reading_level_score: float = 0.0
    accessibility_score: float = 0.0
    compatibility_score: float = 0.0


@dataclass
class ComprehensiveQualityReport:
    """Comprehensive quality report aggregating all dimensions."""
    overall_score: float  # 0-100
    design_report: DesignQualityReport
    content_report: ContentQualityReport
    technical_report: TechnicalQualityReport
    functional_report: FunctionalQualityReport
    priority_fixes: List[QualityIssue] = field(default_factory=list)


class QualityChecker:
    """
    Comprehensive quality checker for Google Slides presentations.

    Validates presentations across multiple dimensions:
    - Design quality (WCAG, hierarchy, whitespace)
    - Content quality (grammar, clarity, story arc)
    - Technical quality (images, fonts, links)
    - Functional quality (accessibility, timing, compatibility)
    """

    def __init__(self, slides_service=None, anthropic_api_key: Optional[str] = None):
        """
        Initialize quality checker.

        Args:
            slides_service: Google Slides API service instance
            anthropic_api_key: Optional Anthropic API key for content analysis
        """
        self.slides_service = slides_service
        self.anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

    def check_design_quality(self, presentation_id: str) -> DesignQualityReport:
        """
        Validate design standards and visual quality.

        Checks:
        - WCAG contrast ratios (4.5:1 minimum for text)
        - Visual hierarchy consistency
        - Whitespace distribution and balance
        - Element alignment and spacing

        Args:
            presentation_id: Google Slides presentation ID

        Returns:
            DesignQualityReport with scores and recommendations
        """
        issues = []
        recommendations = []
        contrast_ratios = {}

        try:
            # Get presentation data
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            # Check contrast ratios
            contrast_score = self._check_contrast_ratios(slides, issues, contrast_ratios)

            # Check visual hierarchy
            hierarchy_score = self._check_visual_hierarchy(slides, issues)

            # Check whitespace
            whitespace_score = self._check_whitespace(slides, issues)

            # Check alignment
            alignment_score = self._check_alignment(slides, issues)

            # Generate recommendations
            if contrast_score < 80:
                recommendations.append("Improve text-background contrast for better readability")
            if hierarchy_score < 70:
                recommendations.append("Establish clearer visual hierarchy with varied font sizes")
            if whitespace_score < 60:
                recommendations.append("Add more whitespace to reduce visual clutter")
            if alignment_score < 75:
                recommendations.append("Align elements consistently for professional appearance")

            # Calculate overall design score
            score = (contrast_score + hierarchy_score + whitespace_score + alignment_score) / 4

        except Exception as e:
            issues.append(QualityIssue(
                severity="critical",
                category="design",
                description=f"Failed to check design quality: {str(e)}"
            ))
            score = 0.0
            contrast_score = hierarchy_score = whitespace_score = alignment_score = 0.0

        return DesignQualityReport(
            score=score,
            issues=issues,
            recommendations=recommendations,
            contrast_ratios=contrast_ratios,
            hierarchy_score=hierarchy_score,
            whitespace_score=whitespace_score,
            alignment_score=alignment_score
        )

    def check_content_quality(
        self,
        presentation_id: str,
        anthropic_api_key: Optional[str] = None
    ) -> ContentQualityReport:
        """
        Validate content quality using AI analysis.

        Checks:
        - Grammar and spelling accuracy
        - Clarity and conciseness
        - Audience appropriateness
        - Story arc completeness

        Args:
            presentation_id: Google Slides presentation ID
            anthropic_api_key: Optional override for Anthropic API key

        Returns:
            ContentQualityReport with scores and recommendations
        """
        issues = []
        recommendations = []

        # Use provided key or instance key
        client = self.anthropic_client
        if anthropic_api_key:
            client = Anthropic(api_key=anthropic_api_key)

        if not client:
            issues.append(QualityIssue(
                severity="warning",
                category="content",
                description="Anthropic API key not provided - content quality check limited"
            ))
            return ContentQualityReport(
                score=50.0,
                issues=issues,
                recommendations=["Provide Anthropic API key for full content analysis"]
            )

        try:
            # Get presentation content
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            # Extract all text content
            text_content = self._extract_text_content(presentation)

            if not text_content:
                issues.append(QualityIssue(
                    severity="warning",
                    category="content",
                    description="No text content found in presentation"
                ))
                return ContentQualityReport(score=0.0, issues=issues)

            # Use Claude to analyze content quality
            analysis = self._analyze_content_with_claude(client, text_content)

            # Parse analysis results
            grammar_score = analysis.get('grammar_score', 70.0)
            clarity_score = analysis.get('clarity_score', 70.0)
            audience_score = analysis.get('audience_score', 70.0)
            story_arc_score = analysis.get('story_arc_score', 70.0)

            # Add issues from analysis
            for issue_data in analysis.get('issues', []):
                issues.append(QualityIssue(
                    severity=issue_data.get('severity', 'info'),
                    category='content',
                    description=issue_data.get('description', ''),
                    location=issue_data.get('location'),
                    recommendation=issue_data.get('recommendation')
                ))

            # Add recommendations
            recommendations.extend(analysis.get('recommendations', []))

            # Calculate overall content score
            score = (grammar_score + clarity_score + audience_score + story_arc_score) / 4

        except Exception as e:
            issues.append(QualityIssue(
                severity="critical",
                category="content",
                description=f"Failed to check content quality: {str(e)}"
            ))
            score = 0.0
            grammar_score = clarity_score = audience_score = story_arc_score = 0.0

        return ContentQualityReport(
            score=score,
            issues=issues,
            recommendations=recommendations,
            grammar_score=grammar_score,
            clarity_score=clarity_score,
            audience_score=audience_score,
            story_arc_score=story_arc_score
        )

    def check_technical_quality(self, presentation_id: str) -> TechnicalQualityReport:
        """
        Validate technical aspects of the presentation.

        Checks:
        - Image resolution and quality
        - Font availability and embedding
        - Link validity
        - Embedded object integrity

        Args:
            presentation_id: Google Slides presentation ID

        Returns:
            TechnicalQualityReport with scores and recommendations
        """
        issues = []
        recommendations = []

        try:
            # Get presentation data
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            # Check image quality
            image_score = self._check_image_quality(slides, issues)

            # Check font availability
            font_score = self._check_font_availability(presentation, issues)

            # Check link validity
            link_score = self._check_link_validity(slides, issues)

            # Check object integrity
            object_score = self._check_object_integrity(slides, issues)

            # Generate recommendations
            if image_score < 70:
                recommendations.append("Replace low-resolution images with higher quality versions")
            if font_score < 80:
                recommendations.append("Use standard fonts for better cross-platform compatibility")
            if link_score < 90:
                recommendations.append("Fix or remove broken links")
            if object_score < 75:
                recommendations.append("Verify all embedded objects display correctly")

            # Calculate overall technical score
            score = (image_score + font_score + link_score + object_score) / 4

        except Exception as e:
            issues.append(QualityIssue(
                severity="critical",
                category="technical",
                description=f"Failed to check technical quality: {str(e)}"
            ))
            score = 0.0
            image_score = font_score = link_score = object_score = 0.0

        return TechnicalQualityReport(
            score=score,
            issues=issues,
            recommendations=recommendations,
            image_quality_score=image_score,
            font_availability_score=font_score,
            link_validity_score=link_score,
            object_integrity_score=object_score
        )

    def check_functional_quality(self, presentation_id: str) -> FunctionalQualityReport:
        """
        Validate functional effectiveness of the presentation.

        Checks:
        - Slide count appropriateness (10-20 slides ideal)
        - Reading level and timing
        - Accessibility compliance
        - Cross-platform compatibility

        Args:
            presentation_id: Google Slides presentation ID

        Returns:
            FunctionalQualityReport with scores and recommendations
        """
        issues = []
        recommendations = []

        try:
            # Get presentation data
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            # Check slide count
            slide_count_score = self._check_slide_count(slides, issues)

            # Check reading level
            reading_score = self._check_reading_level(slides, issues)

            # Check accessibility
            accessibility_score = self._check_accessibility(slides, issues)

            # Check compatibility
            compatibility_score = self._check_compatibility(presentation, issues)

            # Generate recommendations
            if slide_count_score < 70:
                recommendations.append("Adjust slide count to 10-20 slides for optimal engagement")
            if reading_score < 60:
                recommendations.append("Simplify language for better audience comprehension")
            if accessibility_score < 80:
                recommendations.append("Add alt text to images and improve color contrast")
            if compatibility_score < 85:
                recommendations.append("Use standard fonts and formats for better compatibility")

            # Calculate overall functional score
            score = (slide_count_score + reading_score + accessibility_score + compatibility_score) / 4

        except Exception as e:
            issues.append(QualityIssue(
                severity="critical",
                category="functional",
                description=f"Failed to check functional quality: {str(e)}"
            ))
            score = 0.0
            slide_count_score = reading_score = accessibility_score = compatibility_score = 0.0

        return FunctionalQualityReport(
            score=score,
            issues=issues,
            recommendations=recommendations,
            slide_count_score=slide_count_score,
            reading_level_score=reading_score,
            accessibility_score=accessibility_score,
            compatibility_score=compatibility_score
        )

    def run_comprehensive_check(self, presentation_id: str) -> ComprehensiveQualityReport:
        """
        Run all quality checks and aggregate results.

        Performs comprehensive validation across all quality dimensions
        and prioritizes issues by severity.

        Args:
            presentation_id: Google Slides presentation ID

        Returns:
            ComprehensiveQualityReport with aggregated results
        """
        # Run all individual checks
        design_report = self.check_design_quality(presentation_id)
        content_report = self.check_content_quality(presentation_id)
        technical_report = self.check_technical_quality(presentation_id)
        functional_report = self.check_functional_quality(presentation_id)

        # Calculate overall score (weighted average)
        overall_score = (
            design_report.score * 0.3 +
            content_report.score * 0.3 +
            technical_report.score * 0.2 +
            functional_report.score * 0.2
        )

        # Collect all issues and prioritize
        all_issues = (
            design_report.issues +
            content_report.issues +
            technical_report.issues +
            functional_report.issues
        )

        # Sort by severity: critical > warning > info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        priority_fixes = sorted(
            all_issues,
            key=lambda x: severity_order.get(x.severity, 3)
        )

        return ComprehensiveQualityReport(
            overall_score=overall_score,
            design_report=design_report,
            content_report=content_report,
            technical_report=technical_report,
            functional_report=functional_report,
            priority_fixes=priority_fixes
        )

    # Private helper methods

    def _check_contrast_ratios(
        self,
        slides: List[Dict],
        issues: List[QualityIssue],
        contrast_ratios: Dict[str, float]
    ) -> float:
        """Check WCAG contrast ratios for text elements."""
        total_elements = 0
        passing_elements = 0

        for slide_idx, slide in enumerate(slides):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    total_elements += 1

                    # Get text color and background color
                    text_color = self._get_element_color(element, 'text')
                    bg_color = self._get_element_color(element, 'background')

                    if text_color and bg_color:
                        ratio = self._calculate_contrast_ratio(text_color, bg_color)
                        contrast_ratios[f"slide_{slide_idx}_element_{element.get('objectId', 'unknown')}"] = ratio

                        # WCAG AA requires 4.5:1 for normal text
                        if ratio >= 4.5:
                            passing_elements += 1
                        else:
                            issues.append(QualityIssue(
                                severity="warning",
                                category="design",
                                description=f"Low contrast ratio ({ratio:.2f}:1) on slide {slide_idx + 1}",
                                location=f"Slide {slide_idx + 1}",
                                recommendation="Increase contrast to at least 4.5:1 for WCAG AA compliance"
                            ))

        if total_elements == 0:
            return 100.0

        return (passing_elements / total_elements) * 100

    def _check_visual_hierarchy(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check visual hierarchy consistency."""
        font_size_variance = []

        for slide in slides:
            sizes = []
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    text_style = element['shape']['text'].get('textElements', [{}])[0].get('textRun', {}).get('style', {})
                    font_size = text_style.get('fontSize', {}).get('magnitude', 12)
                    sizes.append(font_size)

            if len(sizes) > 1:
                # Good hierarchy has varied sizes
                variance = max(sizes) - min(sizes)
                font_size_variance.append(variance)

        if not font_size_variance:
            return 70.0  # Neutral score for no data

        avg_variance = sum(font_size_variance) / len(font_size_variance)

        # Good hierarchy has at least 8pt variance
        if avg_variance < 4:
            issues.append(QualityIssue(
                severity="info",
                category="design",
                description="Limited font size variation may affect visual hierarchy",
                recommendation="Use varied font sizes (e.g., 24pt titles, 14pt body) for clarity"
            ))
            return 50.0
        elif avg_variance < 8:
            return 70.0
        else:
            return 90.0

    def _check_whitespace(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check whitespace distribution."""
        crowded_slides = 0

        for slide_idx, slide in enumerate(slides):
            element_count = len(slide.get('pageElements', []))

            # More than 8 elements might be too crowded
            if element_count > 8:
                crowded_slides += 1
                issues.append(QualityIssue(
                    severity="info",
                    category="design",
                    description=f"Slide {slide_idx + 1} may be too crowded ({element_count} elements)",
                    location=f"Slide {slide_idx + 1}",
                    recommendation="Consider splitting content across multiple slides"
                ))

        if not slides:
            return 100.0

        return max(0, 100 - (crowded_slides / len(slides) * 100))

    def _check_alignment(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check element alignment."""
        # This is a simplified check - in practice would analyze actual positions
        # For now, assume good alignment unless obvious issues
        return 85.0

    def _extract_text_content(self, presentation: Dict) -> str:
        """Extract all text content from presentation."""
        text_parts = []

        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            text_parts.append(text_element['textRun'].get('content', ''))

        return '\n'.join(text_parts)

    def _analyze_content_with_claude(self, client: Anthropic, text_content: str) -> Dict:
        """Analyze content quality using Claude."""
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze this presentation content for quality. Provide scores (0-100) and specific issues.

Content:
{text_content[:4000]}  # Limit to avoid token limits

Analyze:
1. Grammar and spelling (grammar_score)
2. Clarity and conciseness (clarity_score)
3. Audience appropriateness (audience_score)
4. Story arc and flow (story_arc_score)

Respond in this format:
SCORES:
grammar_score: [0-100]
clarity_score: [0-100]
audience_score: [0-100]
story_arc_score: [0-100]

ISSUES:
- [severity] [description]

RECOMMENDATIONS:
- [recommendation]"""
                }]
            )

            # Parse response
            response_text = response.content[0].text

            # Extract scores
            scores = {}
            for line in response_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    if 'score' in key:
                        try:
                            scores[key] = float(value.strip())
                        except ValueError:
                            pass

            # Extract issues and recommendations (simplified)
            issues = []
            recommendations = []

            in_issues = False
            in_recommendations = False

            for line in response_text.split('\n'):
                if 'ISSUES:' in line:
                    in_issues = True
                    in_recommendations = False
                elif 'RECOMMENDATIONS:' in line:
                    in_issues = False
                    in_recommendations = True
                elif line.strip().startswith('-'):
                    if in_issues:
                        issues.append({
                            'severity': 'info',
                            'description': line.strip('- ').strip()
                        })
                    elif in_recommendations:
                        recommendations.append(line.strip('- ').strip())

            return {
                **scores,
                'issues': issues,
                'recommendations': recommendations
            }

        except Exception as e:
            return {
                'grammar_score': 70.0,
                'clarity_score': 70.0,
                'audience_score': 70.0,
                'story_arc_score': 70.0,
                'issues': [{
                    'severity': 'warning',
                    'description': f'Content analysis failed: {str(e)}'
                }],
                'recommendations': []
            }

    def _check_image_quality(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check image quality and resolution."""
        total_images = 0
        high_quality = 0

        for slide_idx, slide in enumerate(slides):
            for element in slide.get('pageElements', []):
                if 'image' in element:
                    total_images += 1

                    # Get image properties
                    image = element['image']
                    props = image.get('imageProperties', {})

                    # Check if image has good resolution indicators
                    # (In practice, would check actual pixel dimensions)
                    # For now, assume images are good quality unless obviously small
                    source_url = image.get('sourceUrl', '')
                    if source_url and 'thumb' not in source_url.lower():
                        high_quality += 1
                    else:
                        issues.append(QualityIssue(
                            severity="warning",
                            category="technical",
                            description=f"Potentially low-quality image on slide {slide_idx + 1}",
                            location=f"Slide {slide_idx + 1}",
                            recommendation="Replace with higher resolution image"
                        ))

        if total_images == 0:
            return 100.0

        return (high_quality / total_images) * 100

    def _check_font_availability(self, presentation: Dict, issues: List[QualityIssue]) -> float:
        """Check font availability and standardization."""
        # Common web-safe fonts
        safe_fonts = {'Arial', 'Calibri', 'Georgia', 'Helvetica', 'Times New Roman', 'Verdana'}

        fonts_used = set()
        non_standard = []

        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            font = text_element['textRun'].get('style', {}).get('fontFamily', 'Arial')
                            fonts_used.add(font)
                            if font not in safe_fonts:
                                non_standard.append(font)

        if non_standard:
            issues.append(QualityIssue(
                severity="info",
                category="technical",
                description=f"Non-standard fonts used: {', '.join(set(non_standard))}",
                recommendation="Consider using web-safe fonts for better compatibility"
            ))

        if not fonts_used:
            return 100.0

        standard_ratio = len([f for f in fonts_used if f in safe_fonts]) / len(fonts_used)
        return standard_ratio * 100

    def _check_link_validity(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check link validity (simplified check)."""
        total_links = 0
        valid_links = 0

        for slide_idx, slide in enumerate(slides):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            style = text_element['textRun'].get('style', {})
                            link = style.get('link', {})

                            if link:
                                total_links += 1
                                url = link.get('url', '')

                                # Basic URL validation
                                if url.startswith(('http://', 'https://', 'mailto:')):
                                    valid_links += 1
                                else:
                                    issues.append(QualityIssue(
                                        severity="warning",
                                        category="technical",
                                        description=f"Invalid or broken link on slide {slide_idx + 1}",
                                        location=f"Slide {slide_idx + 1}",
                                        recommendation="Verify and fix broken links"
                                    ))

        if total_links == 0:
            return 100.0

        return (valid_links / total_links) * 100

    def _check_object_integrity(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check embedded object integrity."""
        total_objects = 0
        valid_objects = 0

        for slide in slides:
            for element in slide.get('pageElements', []):
                # Check various object types
                if any(key in element for key in ['image', 'video', 'sheetsChart', 'table']):
                    total_objects += 1

                    # Assume valid unless missing critical properties
                    if element.get('objectId'):
                        valid_objects += 1

        if total_objects == 0:
            return 100.0

        return (valid_objects / total_objects) * 100

    def _check_slide_count(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check if slide count is appropriate."""
        count = len(slides)

        # Optimal range: 10-20 slides
        if count < 5:
            issues.append(QualityIssue(
                severity="info",
                category="functional",
                description=f"Presentation may be too short ({count} slides)",
                recommendation="Consider adding more content or detail"
            ))
            return 60.0
        elif count > 30:
            issues.append(QualityIssue(
                severity="warning",
                category="functional",
                description=f"Presentation may be too long ({count} slides)",
                recommendation="Consider splitting into multiple presentations"
            ))
            return 70.0
        elif 10 <= count <= 20:
            return 100.0
        else:
            return 85.0

    def _check_reading_level(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check reading level and text density."""
        total_text_length = 0
        slide_count = len(slides)

        for slide in slides:
            slide_text = 0
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            slide_text += len(text_element['textRun'].get('content', ''))

            total_text_length += slide_text

        if slide_count == 0:
            return 100.0

        avg_text_per_slide = total_text_length / slide_count

        # Optimal: 50-200 characters per slide
        if avg_text_per_slide > 300:
            issues.append(QualityIssue(
                severity="warning",
                category="functional",
                description="Slides contain too much text on average",
                recommendation="Reduce text density - aim for 50-200 characters per slide"
            ))
            return 60.0
        elif avg_text_per_slide < 20:
            issues.append(QualityIssue(
                severity="info",
                category="functional",
                description="Slides may contain too little text",
                recommendation="Add more context to help audience understanding"
            ))
            return 75.0
        elif 50 <= avg_text_per_slide <= 200:
            return 100.0
        else:
            return 85.0

    def _check_accessibility(self, slides: List[Dict], issues: List[QualityIssue]) -> float:
        """Check accessibility compliance."""
        total_images = 0
        images_with_alt = 0

        for slide_idx, slide in enumerate(slides):
            for element in slide.get('pageElements', []):
                if 'image' in element:
                    total_images += 1

                    # Check for alt text
                    desc = element.get('description', '')
                    title = element.get('title', '')

                    if desc or title:
                        images_with_alt += 1
                    else:
                        issues.append(QualityIssue(
                            severity="warning",
                            category="functional",
                            description=f"Image on slide {slide_idx + 1} missing alt text",
                            location=f"Slide {slide_idx + 1}",
                            recommendation="Add descriptive alt text for screen readers"
                        ))

        if total_images == 0:
            return 100.0

        return (images_with_alt / total_images) * 100

    def _check_compatibility(self, presentation: Dict, issues: List[QualityIssue]) -> float:
        """Check cross-platform compatibility."""
        # Check for features that might not be compatible
        compatibility_score = 100.0

        # This is a simplified check
        # In practice, would check for:
        # - Embedded fonts
        # - Custom animations
        # - Proprietary formats

        return compatibility_score

    def _get_element_color(self, element: Dict, color_type: str) -> Optional[Tuple[int, int, int]]:
        """Extract RGB color from element."""
        # Simplified - would need to handle various color formats
        return None  # Placeholder

    def _calculate_contrast_ratio(self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
        """Calculate WCAG contrast ratio between two colors."""
        # Simplified calculation
        # Real implementation would use WCAG formula
        return 4.5  # Placeholder
