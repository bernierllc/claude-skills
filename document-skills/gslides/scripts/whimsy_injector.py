#!/usr/bin/env python3
"""
Whimsy Injector for Google Slides.

This module returns structured prompt templates for Claude to fulfill.
When used as a Claude skill, Claude generates the content directly.
No external API calls or API keys required.

Adds delightful, memorable elements to presentations while maintaining
professionalism. Creates visual metaphors, memorable quotes, engaging
transitions, and personality-infused content that resonates with audiences.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class PersonalityLevel(Enum):
    """Level of personality and whimsy to inject."""
    MINIMAL = "minimal"       # Subtle, professional
    MODERATE = "moderate"     # Balanced personality
    HIGH = "high"            # Bold, memorable


class ContextType(Enum):
    """Type of presentation context."""
    FORMAL = "formal"                 # Board meeting, compliance, legal
    BUSINESS = "business"             # Standard business presentation
    CREATIVE = "creative"             # Marketing, design, innovation
    EDUCATIONAL = "educational"       # Training, teaching
    INSPIRATIONAL = "inspirational"   # Keynote, motivation


@dataclass
class VisualMetaphor:
    """A visual metaphor suggestion."""
    concept: str                      # The abstract concept
    metaphor: str                     # The concrete metaphor
    visual_description: str           # How to represent it visually
    explanation: str                  # Why this metaphor works
    slide_suggestion: Optional[str] = None  # Where/how to use it

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'concept': self.concept,
            'metaphor': self.metaphor,
            'visual_description': self.visual_description,
            'explanation': self.explanation,
            'slide_suggestion': self.slide_suggestion
        }


@dataclass
class MemorableQuote:
    """A quote or memorable phrase."""
    quote: str
    attribution: Optional[str]        # Source/author if applicable
    context: str                      # When/why to use it
    placement_suggestion: str         # Where in presentation
    visual_treatment: Optional[str] = None  # How to design it

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'quote': self.quote,
            'attribution': self.attribution,
            'context': self.context,
            'placement_suggestion': self.placement_suggestion,
            'visual_treatment': self.visual_treatment
        }


@dataclass
class TransitionSuggestion:
    """Suggested transition between slides."""
    from_slide_title: str
    to_slide_title: str
    transition_text: str              # Verbal bridge
    rationale: str                    # Why this transition works
    delivery_tip: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'from_slide_title': self.from_slide_title,
            'to_slide_title': self.to_slide_title,
            'transition_text': self.transition_text,
            'rationale': self.rationale,
            'delivery_tip': self.delivery_tip
        }


@dataclass
class PersonalityInjection:
    """Content with personality added."""
    original_content: str
    enhanced_content: str
    changes_made: List[str]           # What was changed and why
    personality_elements: List[str]   # Specific personality touches added
    appropriateness_score: float      # 0-100, how well it fits context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'original_content': self.original_content,
            'enhanced_content': self.enhanced_content,
            'changes_made': self.changes_made,
            'personality_elements': self.personality_elements,
            'appropriateness_score': self.appropriateness_score
        }


class WhimsyInjector:
    """
    Add delightful, memorable elements to presentations.

    Returns structured prompt templates for Claude to fulfill directly.
    Enhances presentations with personality while maintaining professionalism.
    Creates visual metaphors, memorable quotes, engaging transitions, and
    personality-infused content. Always provides rationale for suggestions
    to ensure appropriateness.

    This class generates prompts that Claude will execute when the skill is invoked,
    eliminating the need for external API calls.
    """

    def __init__(self, personality_level: str = PersonalityLevel.MODERATE.value):
        """
        Initialize the Whimsy Injector.

        Args:
            personality_level: Amount of personality ('minimal', 'moderate', 'high')

        No API key required - prompts are fulfilled by Claude directly.
        """
        self.personality_level = personality_level

    def suggest_visual_metaphors(
        self,
        slide_content: str,
        concept_to_illustrate: Optional[str] = None,
        audience: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for suggesting creative visual metaphors.

        Returns a prompt template for transforming abstract ideas into concrete,
        relatable visual metaphors that make presentations more memorable and engaging.

        Args:
            slide_content: Content of the slide
            concept_to_illustrate: Specific concept to create metaphor for
            audience: Target audience for context

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> injector = WhimsyInjector()
            >>> prompt_template = injector.suggest_visual_metaphors(
            ...     slide_content="Our security architecture has multiple layers...",
            ...     concept_to_illustrate="layered security"
            ... )
            >>> # Claude will suggest visual metaphors
        """
        audience_text = f"\nAUDIENCE: {audience}" if audience else ""
        concept_text = f"\nCONCEPT TO ILLUSTRATE: {concept_to_illustrate}" if concept_to_illustrate else ""

        prompt = f"""You are a creative visual thinking expert who creates
memorable metaphors that make abstract concepts concrete and relatable.

METAPHOR PRINCIPLES:
1. Universal recognition - Use familiar, everyday objects/experiences
2. Emotional resonance - Connect to audience's experiences
3. Visual clarity - Easy to represent visually
4. Conceptual accuracy - Must genuinely parallel the concept
5. Cultural sensitivity - Avoid culturally specific references

EFFECTIVE METAPHORS:
- Growth → Plant/tree growing
- Complexity → Puzzle or machine with parts
- Security → Fortress, vault, shield
- Speed → Rocket, lightning
- Teamwork → Orchestra, sports team
- Journey → Road, mountain climb{audience_text}{concept_text}

SLIDE CONTENT:
{slide_content}

OUTPUT FORMAT:
METAPHOR 1
CONCEPT: [Abstract concept]
METAPHOR: [Concrete metaphor]
VISUAL_DESCRIPTION: [How to show it visually]
EXPLANATION: [Why this metaphor works - 2-3 sentences]
SLIDE_SUGGESTION: [How to incorporate into slide]
---

[Additional metaphors...]

Provide 2-3 creative visual metaphors that will make this content memorable
and engaging. Explain why each metaphor works."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Suggest creative visual metaphors for abstract concepts',
            'schema': {
                'metaphors': [
                    {
                        'concept': 'str',
                        'metaphor': 'str',
                        'visual_description': 'str',
                        'explanation': 'str',
                        'slide_suggestion': 'Optional[str]'
                    }
                ]
            }
        }

    def add_memorable_quotes(
        self,
        topic: str,
        context: str,
        message_to_reinforce: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for creating memorable quotes or phrases.

        Returns a prompt template for creating or suggesting relevant quotes that
        reinforce key messages and create memorable moments in presentations.

        Args:
            topic: Topic of presentation
            context: Context for the quote
            message_to_reinforce: Specific message to support

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> prompt_template = injector.add_memorable_quotes(
            ...     topic="Innovation",
            ...     context="Encouraging team to take risks",
            ...     message_to_reinforce="Failure is learning"
            ... )
            >>> # Claude will generate memorable quotes
        """
        message_text = f"\nMESSAGE TO REINFORCE: {message_to_reinforce}" if message_to_reinforce else ""

        prompt = f"""You are a master of memorable phrases and impactful quotes.
Create or suggest quotes that stick with audiences and reinforce key messages.

QUOTE PRINCIPLES:
1. Concise - 10-20 words ideal
2. Impactful - Strong verbs, vivid language
3. Relevant - Directly supports the message
4. Authentic - Genuine, not cliché
5. Quotable - People want to repeat it

QUOTE TYPES:
- Existing quotes (with attribution)
- Original memorable phrases
- Provocative questions
- Powerful statistics presented poetically
- Audience-specific wisdom

TOPIC: {topic}
CONTEXT: {context}{message_text}

OUTPUT FORMAT:
QUOTE 1
QUOTE: [The quote or phrase]
ATTRIBUTION: [Source if applicable, or "Original"]
CONTEXT: [When and why to use this]
PLACEMENT: [Where in presentation - opening/middle/closing]
VISUAL_TREATMENT: [How to design the slide - large text, image background, etc.]
---

[Additional quotes...]

Provide 2-3 impactful quotes (existing or original) that will resonate
with the audience and reinforce the message."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Generate memorable quotes for presentation',
            'schema': {
                'quotes': [
                    {
                        'quote': 'str',
                        'attribution': 'Optional[str]',
                        'context': 'str',
                        'placement_suggestion': 'str',
                        'visual_treatment': 'Optional[str]'
                    }
                ]
            }
        }

    def create_engaging_transitions(
        self,
        from_slide: Dict[str, Any],
        to_slide: Dict[str, Any],
        narrative_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for suggesting engaging transitions between slides.

        Returns a prompt template for creating smooth, interesting transitions that
        maintain flow and keep audience engaged between topics.

        Args:
            from_slide: Previous slide with 'title' and optionally 'content'
            to_slide: Next slide with 'title' and optionally 'content'
            narrative_context: Overall presentation narrative

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> prompt_template = injector.create_engaging_transitions(
            ...     from_slide={'title': 'The Problem'},
            ...     to_slide={'title': 'Our Solution'}
            ... )
            >>> # Claude will suggest engaging transition
        """
        context_text = f"\nNARRATIVE CONTEXT: {narrative_context}" if narrative_context else ""

        from_content = from_slide.get('content', [])
        to_content = to_slide.get('content', [])

        from_detail = ""
        if from_content:
            if isinstance(from_content, list):
                from_detail = "\n" + "\n".join(f"- {item}" for item in from_content[:3])
            else:
                from_detail = f"\n{from_content}"

        to_detail = ""
        if to_content:
            if isinstance(to_content, list):
                to_detail = "\n" + "\n".join(f"- {item}" for item in to_content[:3])
            else:
                to_detail = f"\n{to_content}"

        prompt = f"""You are an expert at creating smooth, engaging transitions
between presentation topics.

TRANSITION PRINCIPLES:
1. Acknowledge what was just covered
2. Preview what's coming next
3. Show logical connection
4. Maintain momentum
5. Add interest with personality

TRANSITION TECHNIQUES:
- Cause and effect: "Now that we've seen X, let's explore the result..."
- Problem-solution: "So how do we address this challenge?"
- Question bridge: "You might be wondering..."
- Callback: "Remember when we talked about X? Here's why that matters..."
- Contrast: "We've seen the challenge. Now for the opportunity..."

PERSONALITY LEVEL: {self.personality_level}{context_text}

FROM SLIDE:
TITLE: {from_slide.get('title', 'Untitled')}{from_detail}

TO SLIDE:
TITLE: {to_slide.get('title', 'Untitled')}{to_detail}

OUTPUT FORMAT:
TRANSITION: [The verbal transition text - 1-2 sentences]
RATIONALE: [Why this transition works]
DELIVERY_TIP: [How to deliver it effectively]

Provide a smooth, engaging transition that maintains flow and interest."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Create engaging transition between slides',
            'schema': {
                'transition_text': 'str',
                'rationale': 'str',
                'delivery_tip': 'Optional[str]'
            }
        }

    def inject_personality(
        self,
        content: str,
        brand_voice: Optional[Dict[str, Any]] = None,
        context_type: str = ContextType.BUSINESS.value
    ) -> Dict[str, Any]:
        """
        Generate prompt template for adding personality to content.

        Returns a prompt template for enhancing dry content with personality,
        humor, or warmth while maintaining appropriateness for the context
        and brand voice.

        Args:
            content: Original content to enhance
            brand_voice: Optional brand voice guidelines
            context_type: Type of presentation context (formal/business/creative/etc.)

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> prompt_template = injector.inject_personality(
            ...     content="Revenue increased 15% year over year.",
            ...     context_type="business"
            ... )
            >>> # Claude will add appropriate personality
        """
        brand_text = ""
        if brand_voice:
            brand_text = "\n\nBRAND VOICE:\n"
            for key, value in brand_voice.items():
                brand_text += f"- {key}: {value}\n"

        personality_guidance = {
            PersonalityLevel.MINIMAL.value: "Subtle personality. Professional with slight warmth.",
            PersonalityLevel.MODERATE.value: "Balanced personality. Engaging without being casual.",
            PersonalityLevel.HIGH.value: "Bold personality. Memorable and distinctive."
        }

        context_guidance = {
            ContextType.FORMAL.value: "Maintain formality. Add subtle clarity and warmth only.",
            ContextType.BUSINESS.value: "Professional but engaging. Use active voice and strong verbs.",
            ContextType.CREATIVE.value: "Bold and creative. Use vivid language and unexpected angles.",
            ContextType.EDUCATIONAL.value: "Clear and engaging. Use analogies and accessible language.",
            ContextType.INSPIRATIONAL.value: "Emotional and powerful. Use evocative language."
        }

        prompt = f"""You are an expert at adding personality to content while
maintaining professionalism and appropriateness.

PERSONALITY LEVEL: {self.personality_level}
GUIDANCE: {personality_guidance.get(self.personality_level, personality_guidance[PersonalityLevel.MODERATE.value])}

CONTEXT TYPE: {context_type}
CONTEXT GUIDANCE: {context_guidance.get(context_type, context_guidance[ContextType.BUSINESS.value])}

PERSONALITY TECHNIQUES:
- Active voice over passive
- Strong, specific verbs
- Concrete examples
- Analogies and metaphors
- Conversational connectors
- Rhetorical questions (sparingly)
- Power words that evoke emotion

RULES:
1. Never sacrifice clarity for personality
2. Maintain factual accuracy
3. Respect the context and brand
4. Explain all changes made
5. Provide appropriateness score{brand_text}

ORIGINAL CONTENT:
{content}

OUTPUT FORMAT:
ORIGINAL: [Original content]
ENHANCED: [Enhanced content with personality]
CHANGES_MADE:
- [What was changed and why]
PERSONALITY_ELEMENTS:
- [Specific personality touches added]
APPROPRIATENESS_SCORE: [0-100]
EXPLANATION: [Why this level of personality fits the context]

Enhance with appropriate personality while maintaining professionalism."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Add personality to content while respecting brand and context',
            'schema': {
                'original_content': 'str',
                'enhanced_content': 'str',
                'changes_made': ['str'],
                'personality_elements': ['str'],
                'appropriateness_score': 'float'
            }
        }

    def validate_appropriateness(
        self,
        whimsy_element: str,
        context: str,
        audience: str
    ) -> Dict[str, Any]:
        """
        Generate prompt template for validating whimsy element appropriateness.

        Returns a prompt template for checking proposed whimsy elements (metaphors,
        quotes, personality) against context and audience to ensure appropriateness.

        Args:
            whimsy_element: The element to validate
            context: Presentation context
            audience: Target audience

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> prompt_template = injector.validate_appropriateness(
            ...     whimsy_element="Rocket ship metaphor for growth",
            ...     context="Board meeting financial report",
            ...     audience="Board of directors"
            ... )
            >>> # Claude will validate appropriateness
        """
        prompt = f"""You are an expert at evaluating presentation appropriateness.
Assess whimsy elements for fit with context and audience.

EVALUATION CRITERIA:
1. Context appropriateness (formal/casual match)
2. Audience expectations and norms
3. Cultural sensitivity
4. Professional credibility
5. Clarity vs. confusion risk

SCORING:
90-100: Excellent fit, enhances message
70-89: Good fit, minor adjustments possible
50-69: Acceptable but may need modification
30-49: Questionable fit, significant revision needed
0-29: Poor fit, likely to detract

WHIMSY ELEMENT:
{whimsy_element}

CONTEXT: {context}
AUDIENCE: {audience}

OUTPUT FORMAT:
SCORE: [0-100]
VERDICT: [Excellent/Good/Acceptable/Questionable/Poor]
STRENGTHS: [What works well]
CONCERNS: [Potential issues]
SUGGESTIONS: [How to improve or alternatives]

Provide appropriateness assessment with score and actionable feedback."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Validate whimsy element for appropriateness',
            'schema': {
                'score': 'float',
                'verdict': 'str',
                'strengths': ['str'],
                'concerns': ['str'],
                'suggestions': ['str']
            }
        }
