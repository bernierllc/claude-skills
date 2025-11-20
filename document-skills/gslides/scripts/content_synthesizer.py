#!/usr/bin/env python3
"""
Content Synthesizer for Google Slides.

This module returns structured prompt templates for Claude to fulfill.
When used as a Claude skill, Claude generates the content directly.
No external API calls or API keys required.

Transforms raw notes, transcripts, and brief outlines into polished
presentation content with proper structure and speaker notes.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class DetailLevel(Enum):
    """Level of detail for content expansion."""
    BRIEF = "brief"           # Concise bullet points
    MODERATE = "moderate"     # Standard detail
    DETAILED = "detailed"     # Comprehensive explanations
    EXECUTIVE = "executive"   # High-level summary


class PresentationPurpose(Enum):
    """Common presentation purposes for context-aware generation."""
    PITCH = "pitch"                   # Sales pitch or proposal
    TRAINING = "training"             # Educational/training content
    REPORT = "report"                 # Status or analytics report
    STRATEGY = "strategy"             # Strategic planning
    ANNOUNCEMENT = "announcement"     # Company announcements
    GENERAL = "general"              # General presentation


@dataclass
class SlideContent:
    """Structured slide content with metadata."""
    title: str
    body: List[str]                    # Bullet points or paragraphs
    speaker_notes: Optional[str] = None
    suggested_layout: Optional[str] = None
    visual_suggestions: Optional[List[str]] = None
    confidence_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'body': self.body,
            'speaker_notes': self.speaker_notes,
            'suggested_layout': self.suggested_layout,
            'visual_suggestions': self.visual_suggestions,
            'confidence_score': self.confidence_score
        }


@dataclass
class PresentationStructure:
    """Complete presentation content structure."""
    title: str
    subtitle: Optional[str]
    slides: List[SlideContent]
    total_slides: int
    target_duration_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'subtitle': self.subtitle,
            'slides': [slide.to_dict() for slide in self.slides],
            'total_slides': self.total_slides,
            'target_duration_minutes': self.target_duration_minutes
        }


class ContentSynthesizer:
    """
    AI-powered content generation for Google Slides presentations.

    Returns structured prompt templates for Claude to fulfill directly.
    Transforms raw notes, transcripts, and brief outlines into polished
    presentation content with proper structure, speaker notes, and visual suggestions.

    This class generates prompts that Claude will execute when the skill is invoked,
    eliminating the need for external API calls.
    """

    def __init__(self):
        """
        Initialize the Content Synthesizer.

        No API key required - prompts are fulfilled by Claude directly.
        """
        pass

    def synthesize_from_notes(
        self,
        raw_notes: str,
        presentation_purpose: str = PresentationPurpose.GENERAL.value,
        target_audience: str = "general business audience",
        slide_count: Optional[int] = None,
        duration_minutes: Optional[int] = None,
        key_messages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for synthesizing notes into presentation structure.

        Returns a prompt template that Claude will fulfill to transform unstructured
        content (meeting notes, transcripts, brainstorm sessions) into well-organized
        presentation slides with titles, bullets, and speaker notes.

        Args:
            raw_notes: Unstructured text (notes, transcript, outline)
            presentation_purpose: Purpose/type of presentation
            target_audience: Description of intended audience
            slide_count: Suggested number of slides (None for auto)
            duration_minutes: Target presentation duration
            key_messages: Must-include messages/points

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> synthesizer = ContentSynthesizer()
            >>> notes = "Meeting notes: Need to present Q4 results..."
            >>> prompt_template = synthesizer.synthesize_from_notes(
            ...     notes,
            ...     presentation_purpose="report",
            ...     target_audience="executives",
            ...     slide_count=8
            ... )
            >>> # Claude will fulfill this prompt and generate structured content
        """
        key_messages_text = ""
        if key_messages:
            key_messages_text = "\n\nKEY MESSAGES TO INCLUDE:\n" + "\n".join(
                f"- {msg}" for msg in key_messages
            )

        slide_count_text = ""
        if slide_count:
            slide_count_text = f"\nTarget slide count: {slide_count} slides"

        duration_text = ""
        if duration_minutes:
            duration_text = f"\nTarget duration: {duration_minutes} minutes"

        prompt = f"""You are an expert presentation designer and content strategist.
Transform the following raw notes into a structured presentation.

CRITICAL REQUIREMENTS:
1. Create clear, concise slide titles (5-8 words max)
2. Use bullet points for body content (3-5 bullets per slide)
3. Each bullet should be a complete thought (8-12 words)
4. Generate helpful speaker notes with key talking points
5. Suggest visual elements where appropriate
6. Maintain logical flow between slides

PRESENTATION DETAILS:
Purpose: {presentation_purpose}
Audience: {target_audience}{slide_count_text}{duration_text}{key_messages_text}

RAW NOTES:
{raw_notes}

OUTPUT FORMAT (use exactly this structure):
TITLE: [Presentation Title]
SUBTITLE: [Optional Subtitle]

SLIDE 1
TITLE: [Slide Title]
BODY:
- [Bullet point 1]
- [Bullet point 2]
- [Bullet point 3]
SPEAKER_NOTES: [2-3 sentences with talking points, context, transitions]
VISUAL_SUGGESTIONS: [Optional: chart, image, diagram suggestions]
---

SLIDE 2
[Continue same format...]

Generate a well-structured presentation following this output format."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Generate structured presentation content from raw notes',
            'schema': {
                'title': 'str',
                'subtitle': 'Optional[str]',
                'slides': [
                    {
                        'title': 'str',
                        'body': ['str'],
                        'speaker_notes': 'Optional[str]',
                        'visual_suggestions': 'Optional[List[str]]'
                    }
                ]
            }
        }

    def generate_slide_content(
        self,
        slide_purpose: str,
        context: str,
        style_guide: Optional[Dict[str, Any]] = None,
        previous_slide: Optional[str] = None,
        next_slide: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for single slide content with context awareness.

        Returns a prompt template for creating focused slide content based on purpose
        and surrounding context. Useful for filling in missing slides or expanding
        existing presentations.

        Args:
            slide_purpose: What this slide should accomplish
            context: Overall presentation context
            style_guide: Optional style preferences (tone, length, format)
            previous_slide: Content of previous slide for flow
            next_slide: Content of next slide for transitions

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> prompt_template = synthesizer.generate_slide_content(
            ...     slide_purpose="Explain the problem we're solving",
            ...     context="Product pitch for enterprise security software",
            ...     style_guide={'tone': 'professional', 'bullets': 4}
            ... )
            >>> # Claude will fulfill this prompt
        """
        style_text = ""
        if style_guide:
            style_text = "\n\nSTYLE GUIDE:\n"
            for key, value in style_guide.items():
                style_text += f"- {key}: {value}\n"

        context_text = ""
        if previous_slide:
            context_text += f"\n\nPREVIOUS SLIDE:\n{previous_slide}"
        if next_slide:
            context_text += f"\n\nNEXT SLIDE:\n{next_slide}"

        prompt = f"""You are an expert presentation slide designer.
Create focused, impactful slide content that serves a specific purpose.

REQUIREMENTS:
1. Clear, descriptive title (5-8 words)
2. 3-5 concise bullet points
3. Speaker notes with delivery tips
4. Visual suggestions if appropriate
5. Smooth transitions if context provided

SLIDE PURPOSE: {slide_purpose}

PRESENTATION CONTEXT: {context}{style_text}{context_text}

OUTPUT FORMAT:
TITLE: [Slide Title]
BODY:
- [Bullet 1]
- [Bullet 2]
- [Bullet 3]
SPEAKER_NOTES: [Talking points and delivery tips]
VISUAL_SUGGESTIONS: [Optional visual recommendations]
LAYOUT: [Suggested layout: title_only, title_body, title_body_image, etc.]

Generate focused slide content following this format."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Generate single slide content with context awareness',
            'schema': {
                'title': 'str',
                'body': ['str'],
                'speaker_notes': 'Optional[str]',
                'visual_suggestions': 'Optional[List[str]]',
                'suggested_layout': 'Optional[str]'
            }
        }

    def expand_bullet_points(
        self,
        brief_points: List[str],
        detail_level: str = DetailLevel.MODERATE.value,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for expanding brief bullet points into fuller content.

        Returns a prompt template for transforming terse bullets into complete,
        well-formed bullet points with appropriate detail level.

        Args:
            brief_points: List of brief/terse bullets to expand
            detail_level: How detailed to make expansions (brief/moderate/detailed)
            context: Optional context about the topic

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> brief = ["Rev up 15%", "Costs down 8%", "Margin improved"]
            >>> prompt_template = synthesizer.expand_bullet_points(
            ...     brief,
            ...     detail_level="moderate",
            ...     context="Q4 financial results"
            ... )
            >>> # Claude will expand bullets to proper detail level
        """
        detail_instructions = {
            DetailLevel.BRIEF.value: "Keep concise (8-10 words). Add minimal context.",
            DetailLevel.MODERATE.value: "Standard detail (10-15 words). Complete thoughts.",
            DetailLevel.DETAILED.value: "Full detail (15-20 words). Include context and implications.",
            DetailLevel.EXECUTIVE.value: "Executive summary style (12-15 words). Focus on business impact."
        }

        context_text = f"\n\nCONTEXT: {context}" if context else ""
        bullets_text = "\n".join(f"- {point}" for point in brief_points)

        prompt = f"""You are a presentation content expert.
Expand brief bullet points into well-formed, professional bullet points.

DETAIL LEVEL: {detail_level}
INSTRUCTIONS: {detail_instructions.get(detail_level, detail_instructions[DetailLevel.MODERATE.value])}

RULES:
1. Maintain the original meaning and order
2. Use active voice and strong verbs
3. Be specific and concrete
4. Avoid jargon unless necessary
5. Each bullet should be a complete thought{context_text}

BRIEF BULLETS:
{bullets_text}

OUTPUT FORMAT:
- [Expanded bullet 1]
- [Expanded bullet 2]
- [Expanded bullet 3]

Provide expanded bullets following this format."""

        return {
            'prompt': prompt,
            'format': 'bullet_list',
            'instruction': 'Expand brief bullets to specified detail level',
            'schema': {
                'expanded_bullets': ['str']
            }
        }

    def summarize_for_executive(
        self,
        detailed_content: str,
        max_slides: int = 5,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for creating executive summary slides.

        Returns a prompt template for distilling comprehensive content into
        high-level executive-friendly slides focusing on key insights,
        decisions, and actions.

        Args:
            detailed_content: Full detailed presentation or document
            max_slides: Maximum slides for executive summary
            focus_areas: Optional areas to emphasize (e.g., "financials", "risks")

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> detailed = "Full 30-slide technical deep dive..."
            >>> prompt_template = synthesizer.summarize_for_executive(
            ...     detailed,
            ...     max_slides=5,
            ...     focus_areas=["key metrics", "recommendations"]
            ... )
            >>> # Claude will generate executive summary
        """
        focus_text = ""
        if focus_areas:
            focus_text = "\n\nFOCUS AREAS:\n" + "\n".join(
                f"- {area}" for area in focus_areas
            )

        prompt = f"""You are an executive communications expert.
Create high-level summary slides for C-level executives.

EXECUTIVE SUMMARY PRINCIPLES:
1. Lead with the "so what" - business impact first
2. Focus on decisions, actions, and outcomes
3. Use metrics and concrete results
4. Eliminate technical details unless critical
5. Highlight risks and opportunities
6. Clear call to action

SLIDE STRUCTURE:
- Overview/Situation (1 slide)
- Key Insights/Findings (1-2 slides)
- Recommendations/Actions (1-2 slides)

REQUIREMENTS:
- Maximum {max_slides} slides
- Focus on business impact and decisions
- Executive audience (C-level){focus_text}

DETAILED CONTENT:
{detailed_content}

OUTPUT FORMAT:
TITLE: [Executive Summary Title]
SUBTITLE: [Context/timeframe]

SLIDE 1
TITLE: [Slide Title]
BODY:
- [High-level bullet 1]
- [High-level bullet 2]
- [High-level bullet 3]
SPEAKER_NOTES: [Executive talking points]
---

[Continue for remaining slides...]

Generate executive summary following this format."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Create executive summary from detailed content',
            'schema': {
                'title': 'str',
                'subtitle': 'Optional[str]',
                'slides': [
                    {
                        'title': 'str',
                        'body': ['str'],
                        'speaker_notes': 'Optional[str]'
                    }
                ]
            }
        }

