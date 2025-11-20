#!/usr/bin/env python3
"""
Story Arc Generator for Google Slides.

This module returns structured prompt templates for Claude to fulfill.
When used as a Claude skill, Claude generates the content directly.
No external API calls or API keys required.

Implements Visual Storyteller principles to create compelling narrative
structures for presentations. Transforms flat content into engaging stories
with proper dramatic arc and audience engagement.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class ArcStage(Enum):
    """Stages of the Visual Storyteller narrative arc."""
    HOOK = "hook"                     # Capture attention, create curiosity
    CONTEXT = "context"               # Set the stage, establish baseline
    CONFLICT = "conflict"             # Present the problem/challenge
    RESOLUTION = "resolution"         # Offer the solution/outcome
    CALL_TO_ACTION = "call_to_action" # What happens next


@dataclass
class NarrativeSlide:
    """A slide with its position in the story arc."""
    arc_stage: str                    # Which stage of the arc
    slide_number: int                 # Position in presentation
    title: str
    content: List[str]                # Bullet points or paragraphs
    narrative_purpose: str            # What this slide accomplishes in the story
    emotional_tone: Optional[str] = None    # e.g., "urgent", "optimistic", "analytical"
    transition_to_next: Optional[str] = None # How to bridge to next slide
    speaker_guidance: Optional[str] = None   # Delivery tips for storytelling

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'arc_stage': self.arc_stage,
            'slide_number': self.slide_number,
            'title': self.title,
            'content': self.content,
            'narrative_purpose': self.narrative_purpose,
            'emotional_tone': self.emotional_tone,
            'transition_to_next': self.transition_to_next,
            'speaker_guidance': self.speaker_guidance
        }


@dataclass
class StoryArc:
    """Complete narrative structure for a presentation."""
    title: str
    hook: List[NarrativeSlide]
    context: List[NarrativeSlide]
    conflict: List[NarrativeSlide]
    resolution: List[NarrativeSlide]
    call_to_action: List[NarrativeSlide]
    total_slides: int
    narrative_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'title': self.title,
            'hook': [s.to_dict() for s in self.hook],
            'context': [s.to_dict() for s in self.context],
            'conflict': [s.to_dict() for s in self.conflict],
            'resolution': [s.to_dict() for s in self.resolution],
            'call_to_action': [s.to_dict() for s in self.call_to_action],
            'total_slides': self.total_slides,
            'narrative_summary': self.narrative_summary
        }

    def get_all_slides(self) -> List[NarrativeSlide]:
        """Get all slides in narrative order."""
        return (
            self.hook +
            self.context +
            self.conflict +
            self.resolution +
            self.call_to_action
        )


@dataclass
class ArcAnalysis:
    """Analysis of an existing presentation's narrative structure."""
    current_arc_quality: float        # 0-100 score
    identified_stages: Dict[str, List[int]]  # stage -> slide numbers
    missing_elements: List[str]       # What's missing from the arc
    improvements: List[str]           # Specific suggestions
    strengths: List[str]              # What works well
    reordering_suggestions: Optional[List[Dict[str, Any]]] = None


class StoryArcGenerator:
    """
    Generate compelling narrative structures for presentations.

    Returns structured prompt templates for Claude to fulfill directly.
    Implements Visual Storyteller principles to transform flat content
    into engaging stories with proper dramatic arc. Uses the five-stage
    narrative structure: Hook, Context, Conflict, Resolution, Call to Action.

    This class generates prompts that Claude will execute when the skill is invoked,
    eliminating the need for external API calls.
    """

    def __init__(self):
        """
        Initialize the Story Arc Generator.

        No API key required - prompts are fulfilled by Claude directly.
        """
        pass

    def generate_story_arc(
        self,
        topic: str,
        key_messages: List[str],
        audience: str,
        slide_count: int = 12,
        presentation_goal: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for creating a narrative arc structure.

        Returns a prompt template for creating a complete story structure following
        Visual Storyteller principles. Organizes content into Hook, Context, Conflict,
        Resolution, and Call to Action stages.

        Args:
            topic: Main topic of presentation
            key_messages: Essential messages to convey
            audience: Target audience description
            slide_count: Total number of slides
            presentation_goal: What you want audience to do/feel/know
            constraints: Optional constraints (time, style, tone, etc.)

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> generator = StoryArcGenerator()
            >>> prompt_template = generator.generate_story_arc(
            ...     topic="Adopting AI in Enterprise",
            ...     key_messages=["AI increases productivity", "Implementation is easier than expected"],
            ...     audience="CTOs and technical leaders",
            ...     slide_count=15
            ... )
            >>> # Claude will generate story arc structure
        """
        constraints_text = ""
        if constraints:
            constraints_text = "\n\nCONSTRAINTS:\n"
            for key, value in constraints.items():
                constraints_text += f"- {key}: {value}\n"

        goal_text = f"\n\nPRESENTATION GOAL: {presentation_goal}" if presentation_goal else ""
        messages_text = "\n".join(f"- {msg}" for msg in key_messages)

        prompt = f"""You are a master storyteller and presentation strategist.
Create a compelling narrative structure using the Visual Storyteller framework.

NARRATIVE ARC STRUCTURE:

1. HOOK (1-2 slides) - Capture attention immediately
   - Surprising fact or statistic
   - Provocative question
   - Compelling visual or story
   - Create curiosity and engagement

2. CONTEXT (2-3 slides) - Set the stage
   - Establish baseline/current state
   - Define key terms and scope
   - Build common understanding
   - Connect to audience's world

3. CONFLICT (3-5 slides) - Present the challenge
   - The problem or opportunity
   - Why it matters (stakes)
   - Obstacles and complications
   - Tension and urgency

4. RESOLUTION (3-5 slides) - Offer the solution
   - How to overcome the challenge
   - Evidence and proof points
   - Benefits and outcomes
   - Address objections

5. CALL TO ACTION (1-2 slides) - What's next
   - Specific next steps
   - Clear ask of audience
   - Inspiration and motivation
   - Memorable closing

STORYTELLING PRINCIPLES:
- Start strong, end strong
- Create emotional connection
- Use concrete examples
- Build logical progression
- Maintain momentum
- Surprise and delight

TOPIC: {topic}

KEY MESSAGES:
{messages_text}

AUDIENCE: {audience}

SLIDE COUNT: {slide_count} slides{goal_text}{constraints_text}

OUTPUT FORMAT:
TITLE: [Presentation Title]
NARRATIVE_SUMMARY: [One paragraph describing the story arc]

HOOK
SLIDE 1
TITLE: [Title]
CONTENT:
- [Bullet 1]
- [Bullet 2]
NARRATIVE_PURPOSE: [What this accomplishes in the story]
EMOTIONAL_TONE: [urgent/curious/optimistic/etc.]
TRANSITION: [How to bridge to next slide]
SPEAKER_GUIDANCE: [Delivery tips]
---

[Continue for all slides through CALL_TO_ACTION...]

Generate a compelling story arc that engages the audience and delivers the key messages effectively."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Generate narrative arc structure for presentation',
            'schema': {
                'title': 'str',
                'narrative_summary': 'Optional[str]',
                'stages': {
                    'hook': ['NarrativeSlide'],
                    'context': ['NarrativeSlide'],
                    'conflict': ['NarrativeSlide'],
                    'resolution': ['NarrativeSlide'],
                    'call_to_action': ['NarrativeSlide']
                }
            }
        }

    def map_content_to_arc(
        self,
        content_blocks: List[Dict[str, Any]],
        presentation_goal: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for mapping content blocks to narrative arc.

        Returns a prompt template for taking unorganized content and organizing it
        into a coherent narrative following the five-stage arc.

        Args:
            content_blocks: List of content blocks with 'title' and 'content'
            presentation_goal: What the presentation should achieve

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> content = [
            ...     {'title': 'Current State', 'content': ['...']},
            ...     {'title': 'The Problem', 'content': ['...']},
            ...     {'title': 'Our Solution', 'content': ['...']}
            ... ]
            >>> prompt_template = generator.map_content_to_arc(content)
            >>> # Claude will map content to narrative arc
        """
        goal_text = f"\nPRESENTATION GOAL: {presentation_goal}" if presentation_goal else ""

        content_text = ""
        for i, block in enumerate(content_blocks, 1):
            content_text += f"\nSLIDE {i}\n"
            content_text += f"TITLE: {block.get('title', 'Untitled')}\n"
            content_text += "CONTENT:\n"
            if isinstance(block.get('content'), list):
                for item in block['content']:
                    content_text += f"- {item}\n"
            else:
                content_text += f"{block.get('content', '')}\n"
            content_text += "---\n"

        prompt = f"""You are a narrative structure expert.
Map existing content to the Visual Storyteller five-stage arc:
HOOK → CONTEXT → CONFLICT → RESOLUTION → CALL_TO_ACTION

MAPPING PRINCIPLES:
- Hook: Attention-grabbing content, surprising facts, questions
- Context: Background, definitions, current state, landscape
- Conflict: Problems, challenges, gaps, opportunities
- Resolution: Solutions, approaches, results, benefits
- Call to Action: Next steps, asks, inspiration, closing

For each content block, determine:
1. Which arc stage it best fits
2. If it needs to be split across stages
3. If content is missing for a complete arc{goal_text}

EXISTING CONTENT:
{content_text}

OUTPUT FORMAT:
ARC_STAGE: HOOK
SLIDE: [Original slide number]
TITLE: [Title]
CONTENT: [Content from original]
NARRATIVE_PURPOSE: [Why it fits this stage]
---

[Continue for all content blocks...]

MISSING_ELEMENTS:
- [Stage or content type that's missing]

Organize the content into the five-stage arc and identify any missing elements."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Map existing content to narrative arc structure',
            'schema': {
                'mapped_stages': {
                    'hook': ['MappedSlide'],
                    'context': ['MappedSlide'],
                    'conflict': ['MappedSlide'],
                    'resolution': ['MappedSlide'],
                    'call_to_action': ['MappedSlide']
                },
                'missing_elements': ['str']
            }
        }

    def suggest_arc_improvements(
        self,
        current_slides: List[Dict[str, Any]],
        presentation_goal: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate prompt template for analyzing presentation narrative.

        Returns a prompt template for evaluating how well current slides follow
        narrative arc principles and providing specific, actionable improvement
        suggestions.

        Args:
            current_slides: List of slide dicts with 'title' and 'content'
            presentation_goal: What the presentation should achieve

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> slides = [{'title': 'Intro', 'content': ['...']}]
            >>> prompt_template = generator.suggest_arc_improvements(slides)
            >>> # Claude will analyze and suggest improvements
        """
        goal_text = f"\nPRESENTATION GOAL: {presentation_goal}" if presentation_goal else ""

        slides_text = ""
        for i, slide in enumerate(current_slides, 1):
            slides_text += f"\nSLIDE {i}\n"
            slides_text += f"TITLE: {slide.get('title', 'Untitled')}\n"
            content = slide.get('content', [])
            if isinstance(content, list):
                for item in content:
                    slides_text += f"- {item}\n"
            else:
                slides_text += f"{content}\n"
            slides_text += "---\n"

        prompt = f"""You are a presentation narrative analyst.
Evaluate presentations against Visual Storyteller principles and provide
actionable improvement suggestions.

ANALYSIS CRITERIA:
1. Arc Completeness: Are all five stages present?
2. Flow and Transitions: Does the story flow logically?
3. Hook Strength: Does opening capture attention?
4. Conflict Clarity: Is the problem/challenge clear?
5. Resolution Impact: Is the solution compelling?
6. Call to Action: Is the ask clear and motivating?{goal_text}

CURRENT SLIDES:
{slides_text}

OUTPUT FORMAT:
ARC_QUALITY_SCORE: [0-100]

IDENTIFIED_STAGES:
HOOK: Slides [numbers]
CONTEXT: Slides [numbers]
CONFLICT: Slides [numbers]
RESOLUTION: Slides [numbers]
CALL_TO_ACTION: Slides [numbers]

MISSING_ELEMENTS:
- [What's missing from the arc]

STRENGTHS:
- [What works well]

IMPROVEMENTS:
- [Specific, actionable suggestion 1]
- [Specific, actionable suggestion 2]

REORDERING_SUGGESTIONS:
- Move slide [X] to position [Y] because [reason]

Provide detailed analysis and specific improvement suggestions following this format."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Analyze presentation narrative and suggest improvements',
            'schema': {
                'arc_quality_score': 'float',
                'identified_stages': 'Dict[str, List[int]]',
                'missing_elements': ['str'],
                'strengths': ['str'],
                'improvements': ['str'],
                'reordering_suggestions': 'Optional[List[Dict[str, Any]]]'
            }
        }

    def create_narrative_flow(
        self,
        raw_content: str,
        topic: str,
        audience: str,
        slide_count: int = 12
    ) -> Dict[str, Any]:
        """
        Generate prompt template for transforming raw content into narrative.

        Returns a prompt template for taking unstructured content and creating
        a complete story arc with proper flow, transitions, and emotional pacing.

        Args:
            raw_content: Unstructured content (notes, outline, data)
            topic: Presentation topic
            audience: Target audience
            slide_count: Target number of slides

        Returns:
            Dict with prompt template for Claude to fulfill

        Example:
            >>> raw = "Product XYZ solves problem ABC. Features: 1, 2, 3..."
            >>> prompt_template = generator.create_narrative_flow(
            ...     raw,
            ...     topic="Product Launch",
            ...     audience="potential customers",
            ...     slide_count=10
            ... )
            >>> # Claude will create narrative structure
        """
        prompt = f"""You are a master storyteller who transforms raw information
into compelling narratives following the Visual Storyteller framework.

TRANSFORMATION PRINCIPLES:
1. Find the human story in the data
2. Create emotional connection
3. Build dramatic tension
4. Provide satisfying resolution
5. Inspire action

Follow the five-stage arc:
HOOK → CONTEXT → CONFLICT → RESOLUTION → CALL_TO_ACTION

Make the content memorable, engaging, and persuasive while maintaining
professional credibility.

TOPIC: {topic}
AUDIENCE: {audience}
TARGET SLIDES: {slide_count}

RAW CONTENT:
{raw_content}

OUTPUT FORMAT (use the same format as generate_story_arc):
TITLE: [Presentation Title]
NARRATIVE_SUMMARY: [One paragraph describing the story arc]

HOOK
SLIDE 1
TITLE: [Title]
CONTENT:
- [Bullet 1]
- [Bullet 2]
NARRATIVE_PURPOSE: [What this accomplishes]
EMOTIONAL_TONE: [Tone]
TRANSITION: [Bridge to next]
SPEAKER_GUIDANCE: [Delivery tips]
---

[Continue for all slides...]

Create a story arc that engages the audience emotionally while delivering
the key information effectively."""

        return {
            'prompt': prompt,
            'format': 'structured_text',
            'instruction': 'Transform raw content into compelling narrative structure',
            'schema': {
                'title': 'str',
                'narrative_summary': 'Optional[str]',
                'stages': {
                    'hook': ['NarrativeSlide'],
                    'context': ['NarrativeSlide'],
                    'conflict': ['NarrativeSlide'],
                    'resolution': ['NarrativeSlide'],
                    'call_to_action': ['NarrativeSlide']
                }
            }
        }
