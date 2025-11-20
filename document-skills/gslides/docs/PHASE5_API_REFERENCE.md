# Phase 5 API Reference: Intelligent Content

Complete API documentation for AI-powered content generation and narrative optimization.

## 🎉 Phase 5: No API Key Required!

**Major Update**: All Phase 5 methods now work through Claude skill invocation:
- ✅ **No `api_key` parameter** needed on any method
- ✅ **Zero external costs** - FREE AI content generation
- ✅ **No configuration** required
- ✅ **Real-time generation** through Claude Code

## Table of Contents

- [Overview](#overview)
- [GoogleSlidesEditor AI Methods](#googleslideseditor-ai-methods)
  - [generate_from_notes()](#generate_from_notes)
  - [apply_story_arc()](#apply_story_arc)
  - [add_whimsy()](#add_whimsy)
  - [synthesize_slide_content()](#synthesize_slide_content)
  - [improve_narrative_flow()](#improve_narrative_flow)
  - [generate_speaker_notes()](#generate_speaker_notes)
- [ContentSynthesizer API](#contentsynthesizer-api)
- [StoryArcGenerator API](#storyarcgenerator-api)
- [WhimsyInjector API](#whimsyinjector-api)
- [Data Structures](#data-structures)
- [Error Handling](#error-handling)
- [Integration Examples](#integration-examples)

## Overview

Phase 5 adds AI-powered intelligent content generation to Google Slides presentations. All methods now work through Claude skill invocation - no external API required!

### ~~Prerequisites~~ NO LONGER NEEDED!

```python
# No API key setup required!
# Phase 5 works through Claude skill invocation
```

### Quick Start

```python
from scripts.gslides_editor import GoogleSlidesEditor

# No API key needed!
editor = GoogleSlidesEditor()

# Generate presentation from notes
result = editor.generate_from_notes(
    notes="Meeting notes here...",
    purpose='executive_update',
    audience='C-suite'
    # No api_key parameter needed!
)

print(f"Created: {result['pres_url']}")
```

## GoogleSlidesEditor AI Methods

### generate_from_notes()

Generate a complete presentation from raw notes or content.

```python
def generate_from_notes(
    notes: str,
    purpose: str,
    audience: str,
    brand_guidelines: Optional[BrandGuidelines] = None
    # api_key parameter removed - no longer needed!
) -> Dict[str, Any]
```

**Parameters:**

- `notes` (str): Raw notes or content (200-500 words recommended)
  - Can be meeting notes, brainstorm output, rough outline
  - Quality of input affects quality of output
  - Include key facts, data points, decisions

- `purpose` (str): Presentation purpose, one of:
  - `'executive_update'` - Board or C-suite update
  - `'team_presentation'` - Internal team meeting
  - `'client_pitch'` - External sales presentation
  - `'product_demo'` - Feature demonstration
  - `'training'` - Educational content
  - `'vision_talk'` - Strategic/inspirational presentation
  - `'status_report'` - Project status update
  - `'design_review'` - Design or architecture review

- `audience` (str): Target audience description
  - Be specific: "Engineering team leads" not "engineers"
  - Include context: "C-suite with financial background"
  - Mention expertise level: "Non-technical stakeholders"

- `brand_guidelines` (BrandGuidelines, optional): Brand context for tone/style
  - Uses brand voice, colors, and style guide
  - Ensures brand-appropriate language
  - See `load_brand_guidelines()` to load from file

- ~~`api_key`~~ **REMOVED** - No longer needed! Works through Claude skill invocation

**Returns:**

```python
{
    'pres_id': 'abc123...',           # Presentation ID
    'pres_url': 'https://...',        # Google Slides URL
    'slide_count': 8,                  # Number of slides created
    'slides': [                        # Slide details
        {
            'slide_id': 'slide_1',
            'title': 'Presentation Title',
            'content_type': 'title_slide',
            'slide_number': 1
        },
        # ... more slides
    ],
    'content_blocks': [                # Content structure for story arc
        {
            'type': 'hook',
            'content': '...',
            'slide_numbers': [2]
        },
        # ... more blocks
    ],
    'metadata': {
        'purpose': 'executive_update',
        'audience': 'C-suite',
        'generated_at': '2024-01-15T10:30:00Z',
        'api_tokens_used': 2450
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

notes = """
Product roadmap Q1 meeting notes:
- Dashboard performance issues (3-5 sec load times)
- Need Redis caching + query optimization
- Timeline: 6 weeks, need budget approval
- Analytics feature requested by top 3 customers
- Custom dashboards with drag-drop
- 3 month dev timeline, 2 engineers
- Mobile app UI outdated vs competitors
- Recommend React Native rebuild, 4 months
"""

result = editor.generate_from_notes(
    notes=notes,
    purpose='executive_update',
    audience='C-suite and product stakeholders'
)

print(f"Created {result['slide_count']}-slide presentation")
print(f"URL: {result['pres_url']}")
print(f"Tokens used: {result['metadata']['api_tokens_used']}")

# Slides generated might include:
# 1. Title: "Q1 Product Roadmap Update"
# 2. Executive Summary
# 3. Performance Challenge
# 4. Caching Solution
# 5. Analytics Opportunity
# 6. Mobile App Recommendation
# 7. Timeline & Resources
# 8. Next Steps
```

**Best Practices:**

```python
# Good: Specific purpose and audience
result = editor.generate_from_notes(
    notes=content,
    purpose='executive_update',
    audience='Board members with 10+ years industry experience'
)

# Bad: Generic purpose and audience
result = editor.generate_from_notes(
    notes=content,
    purpose='presentation',  # Too generic
    audience='people'         # Too vague
)

# Good: Include brand context
brand = editor.load_brand_guidelines('corporate_brand.json')
result = editor.generate_from_notes(
    notes=content,
    purpose='client_pitch',
    audience='Enterprise IT decision makers',
    brand_guidelines=brand
)
```

**Error Handling:**

```python
try:
    result = editor.generate_from_notes(notes, purpose, audience)
except ValueError as e:
    print(f"Invalid input: {e}")
    # Check notes length, purpose validity
except RuntimeError as e:
    print(f"API error: {e}")
    # Check API key, network connection
```

---

### apply_story_arc()

Apply narrative structure to presentation content.

```python
def apply_story_arc(
    presentation_id: str,
    content_blocks: List[Dict[str, Any]],
    audience: str
    # api_key parameter removed - no longer needed!
) -> Dict[str, Any]
```

**Parameters:**

- `presentation_id` (str): Existing presentation ID
- `content_blocks` (list): Content structure (from `generate_from_notes` or manual)
- `audience` (str): Target audience for arc adaptation
- ~~`api_key`~~ **REMOVED** - No longer needed!

**Content Blocks Structure:**

```python
content_blocks = [
    {
        'type': 'hook',              # Story arc element
        'content': 'Opening message',
        'slide_numbers': [1, 2]
    },
    {
        'type': 'context',
        'content': 'Background info',
        'slide_numbers': [3]
    },
    {
        'type': 'challenge',
        'content': 'Problem statement',
        'slide_numbers': [4, 5]
    },
    {
        'type': 'resolution',
        'content': 'Solution approach',
        'slide_numbers': [6, 7]
    },
    {
        'type': 'benefits',
        'content': 'Expected outcomes',
        'slide_numbers': [8]
    },
    {
        'type': 'call_to_action',
        'content': 'Next steps',
        'slide_numbers': [9]
    }
]
```

**Returns:**

```python
{
    'arc_applied': True,
    'arc_score': 85,                  # Narrative strength (0-100)
    'elements_optimized': 6,          # Story elements enhanced
    'slides_modified': [2, 4, 5, 9],  # Slides changed
    'improvements': [                 # Specific changes
        {
            'slide_number': 2,
            'element': 'hook',
            'change': 'Added surprising statistic',
            'before': 'Our Q4 Results',
            'after': 'Our best quarter in 5 years - here\'s how'
        },
        # ... more improvements
    ],
    'metadata': {
        'audience': 'C-suite',
        'arc_type': 'classic',
        'api_tokens_used': 1850
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Option 1: Use content blocks from generate_from_notes
result = editor.generate_from_notes(notes, purpose, audience)
pres_id = result['pres_id']
content_blocks = result['content_blocks']

arc_result = editor.apply_story_arc(
    pres_id,
    content_blocks,
    audience='C-suite executives'
)

print(f"Arc score: {arc_result['arc_score']}/100")
print(f"Modified {len(arc_result['slides_modified'])} slides")

# Option 2: Manual content blocks for existing presentation
content_blocks = [
    {
        'type': 'hook',
        'content': 'Opening slide content',
        'slide_numbers': [1]
    },
    {
        'type': 'challenge',
        'content': 'Problem description',
        'slide_numbers': [2, 3]
    },
    # ... more blocks
]

arc_result = editor.apply_story_arc(
    'existing-pres-id',
    content_blocks,
    audience='Technical team'
)
```

**Arc Types by Audience:**

```python
# Executive audience: Concise, strategic arc
arc_result = editor.apply_story_arc(
    pres_id, content_blocks,
    audience='C-suite'
)
# Hook: 1 slide, data-driven
# Context: Minimal, business impact focused
# Challenge: Quantified in dollars/risk
# Resolution: Strategic level only
# Benefits: Tied to company objectives
# CTA: Decision and resource allocation

# Technical audience: Detailed, implementation-focused arc
arc_result = editor.apply_story_arc(
    pres_id, content_blocks,
    audience='Engineering team'
)
# Hook: Technical intrigue
# Context: Current architecture/constraints
# Challenge: Technical debt, scalability
# Resolution: Implementation details
# Benefits: Technical improvements
# CTA: Collaboration, next phases

# Customer audience: Empathetic, value-focused arc
arc_result = editor.apply_story_arc(
    pres_id, content_blocks,
    audience='Enterprise customers'
)
# Hook: Their pain point
# Context: Validates their experience
# Challenge: Empathizes with problem
# Resolution: How product helps
# Benefits: Use cases and results
# CTA: Easy getting started path
```

---

### add_whimsy()

Add personality and memorable moments to presentation.

```python
def add_whimsy(
    presentation_id: str,
    personality_level: str = 'moderate'
    # api_key parameter removed - no longer needed!
) -> Dict[str, Any]
```

**Parameters:**

- `presentation_id` (str): Existing presentation ID
- `personality_level` (str): Amount of personality to inject
  - `'minimal'` - Subtle improvements, conservative (exec presentations)
  - `'moderate'` - Balanced personality (recommended for most cases)
  - `'generous'` - Bold, creative personality (team rallies, pitches)
- ~~`api_key`~~ **REMOVED** - No longer needed!

**Returns:**

```python
{
    'whimsy_applied': True,
    'personality_level': 'moderate',
    'slides_enhanced': 5,             # Number of slides modified
    'enhancements': [                 # Specific enhancements
        {
            'slide_number': 3,
            'type': 'visual_metaphor',
            'description': 'Technical debt as house of cards',
            'before': 'Our codebase has accumulated technical debt',
            'after': 'Our codebase is like a house of cards - impressive, but one wrong move...'
        },
        {
            'slide_number': 5,
            'type': 'memorable_phrase',
            'description': 'Quotable insight',
            'before': 'We should prioritize correctly',
            'after': 'Speed matters. Direction matters more.'
        },
        {
            'slide_number': 7,
            'type': 'engaging_transition',
            'description': 'Narrative bridge',
            'before': 'Next: Results',
            'after': 'Here\'s where it gets interesting...'
        }
    ],
    'whimsy_techniques': [
        'visual_metaphors',
        'memorable_phrases',
        'engaging_transitions',
        'relatable_analogies'
    ],
    'metadata': {
        'personality_level': 'moderate',
        'slides_processed': 10,
        'api_tokens_used': 980
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# For executive presentation - minimal personality
result = editor.add_whimsy(
    'exec-presentation-id',
    personality_level='minimal'
)
print(f"Enhanced {result['slides_enhanced']} slides conservatively")

# For team meeting - moderate personality (recommended)
result = editor.add_whimsy(
    'team-meeting-id',
    personality_level='moderate'
)
print(f"Added {len(result['enhancements'])} memorable moments")

# For creative pitch - generous personality
result = editor.add_whimsy(
    'innovation-pitch-id',
    personality_level='generous'
)
print(f"Injected bold personality into {result['slides_enhanced']} slides")

# Review enhancements
for enhancement in result['enhancements']:
    print(f"\nSlide {enhancement['slide_number']} ({enhancement['type']}):")
    print(f"  Before: {enhancement['before']}")
    print(f"  After:  {enhancement['after']}")
```

**Personality Levels Compared:**

| Aspect | Minimal | Moderate | Generous |
|--------|---------|----------|----------|
| Metaphors per deck | 0-1 | 2-3 | 4-6 |
| Humor | None/rare | Light, contextual | Well-placed throughout |
| Memorable phrases | 1 | 2-3 | 4-5 |
| Tone | Professional | Engaging | Bold |
| Visual language | Subtle | Relatable | Creative |
| Best for | Executives, formal | Most contexts | Team, innovation |

**What Gets Enhanced:**

```python
# Minimal personality level
{
    'enhancements': [
        {
            'type': 'word_choice',
            'description': 'Stronger, clearer language',
            'before': 'We made improvements',
            'after': 'We doubled performance'
        }
    ]
}

# Moderate personality level
{
    'enhancements': [
        {
            'type': 'visual_metaphor',
            'description': 'Concrete imagery for abstract concept',
            'before': 'Database is slow',
            'after': 'Database is like a filing cabinet that outgrew its room'
        },
        {
            'type': 'relatable_analogy',
            'description': 'Connect to familiar experience',
            'before': 'Distributed consensus is complex',
            'after': 'Like getting friends to pick a restaurant'
        }
    ]
}

# Generous personality level
{
    'enhancements': [
        {
            'type': 'bold_metaphor',
            'description': 'Striking visual language',
            'before': 'Fixing bugs while adding features',
            'after': 'Performing surgery on a rocket mid-flight'
        },
        {
            'type': 'unexpected_transition',
            'description': 'Engaging narrative bridge',
            'before': 'Next slide',
            'after': 'Plot twist:'
        }
    ]
}
```

---

### synthesize_slide_content()

Generate content for a single slide with context awareness.

```python
def synthesize_slide_content(
    slide_purpose: str,
    context: Dict[str, Any],
    style: str = 'professional'
    # api_key parameter removed!
) -> Dict[str, Any]
```

**Parameters:**

- `slide_purpose` (str): Purpose of this specific slide
  - `'title'` - Presentation title slide
  - `'executive_summary'` - High-level overview
  - `'problem_statement'` - Challenge or opportunity
  - `'solution'` - Approach or resolution
  - `'data_visualization'` - Chart or graph slide
  - `'timeline'` - Project schedule
  - `'team'` - Team introduction
  - `'next_steps'` - Action items
  - `'competitive_advantage'` - Differentiation
  - `'customer_testimonial'` - Social proof

- `context` (dict): Context for content generation
  ```python
  {
      'previous_slide': 'What came before (optional)',
      'next_slide': 'What comes after (optional)',
      'key_points': ['Point 1', 'Point 2', 'Point 3'],
      'data': {...},  # Optional: Data for this slide
      'emphasis': 'What to highlight'
  }
  ```

- `style` (str): Content style
  - `'professional'` - Business-appropriate, formal
  - `'conversational'` - Approachable, engaging
  - `'technical'` - Precise, detailed
  - `'inspirational'` - Motivating, bold

- `api_key` (str, optional): Anthropic API key

**Returns:**

```python
{
    'title': 'Slide Title',
    'subtitle': 'Optional subtitle',  # May be None
    'body_points': [                  # Bullet points or content
        'First key point with details',
        'Second key point with context',
        'Third key point with impact'
    ],
    'speaker_notes': 'Talking points...',  # Optional
    'layout_suggestion': 'title_and_body',  # Recommended layout
    'metadata': {
        'purpose': 'problem_statement',
        'style': 'professional',
        'api_tokens_used': 420
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Create presentation and slide
result = editor.create_presentation("Product Update")
pres_id = result['pres_id']
slide = editor.create_slide(pres_id)
slide_id = slide['slide_id']

# Synthesize content for competitive advantage slide
context = {
    'previous_slide': 'Market opportunity shown',
    'next_slide': 'Implementation timeline',
    'key_points': [
        'Only vendor with real-time analytics',
        'Enterprise security certified',
        'Fastest implementation: 2 weeks vs 3 months'
    ],
    'emphasis': 'Speed and security as differentiators'
}

content = editor.synthesize_slide_content(
    slide_purpose='competitive_advantage',
    context=context,
    style='professional'
)

# Add synthesized content to slide
editor.insert_text_box(
    pres_id, slide_id,
    content['title'],
    x=50, y=30, width=620, height=60
)

# Add body points
y_position = 120
for point in content['body_points']:
    editor.insert_text_box(
        pres_id, slide_id,
        f"• {point}",
        x=80, y=y_position, width=580, height=40
    )
    y_position += 60

print(f"Created slide: {content['title']}")
print(f"Body points: {len(content['body_points'])}")
```

**Style Comparison:**

```python
# Professional style
content = editor.synthesize_slide_content(
    slide_purpose='problem_statement',
    context={'key_points': ['Performance issues', 'Customer impact']},
    style='professional'
)
# Result:
# Title: "Performance Challenges"
# Points:
#   - Database query latency: 3-5 seconds in production
#   - Direct impact on user experience and retention
#   - Requires immediate architectural attention

# Conversational style
content = editor.synthesize_slide_content(
    slide_purpose='problem_statement',
    context={'key_points': ['Performance issues', 'Customer impact']},
    style='conversational'
)
# Result:
# Title: "What's Slowing Us Down?"
# Points:
#   - Our database is struggling - queries taking way too long
#   - Users are noticing, and it's affecting their trust
#   - Time to roll up our sleeves and fix the foundation

# Technical style
content = editor.synthesize_slide_content(
    slide_purpose='problem_statement',
    context={'key_points': ['Performance issues', 'Customer impact']},
    style='technical'
)
# Result:
# Title: "Database Performance Bottleneck"
# Points:
#   - Query execution time: P95 3.2s, P99 5.1s (target: <500ms)
#   - Root cause: Unoptimized N+1 queries, missing indices
#   - Proposed solution: Query optimization + Redis caching layer
```

---

### improve_narrative_flow()

Analyze and improve narrative flow of existing presentation.

```python
def improve_narrative_flow(
    presentation_id: str
    # api_key parameter removed!
) -> Dict[str, Any]
```

**Parameters:**

- `presentation_id` (str): Existing presentation ID
- `api_key` (str, optional): Anthropic API key

**Returns:**

```python
{
    'before_score': 62,               # Narrative score before (0-100)
    'after_score': 87,                # Narrative score after (0-100)
    'improvements_made': 5,           # Number of changes
    'suggestions': [                  # Improvement suggestions
        {
            'type': 'missing_hook',
            'description': 'No attention-grabbing opener',
            'suggestion': 'Add surprising statistic or bold statement to slide 2',
            'priority': 'high',
            'implemented': True
        },
        {
            'type': 'weak_transition',
            'description': 'Abrupt jump from problem to solution',
            'suggestion': 'Add transition slide bridging slides 4 and 5',
            'priority': 'medium',
            'implemented': True
        },
        {
            'type': 'missing_cta',
            'description': 'No clear call to action',
            'suggestion': 'Add specific next steps to final slide',
            'priority': 'high',
            'implemented': True
        }
    ],
    'arc_analysis': {
        'hook': {'present': True, 'strength': 8, 'slide': 2},
        'context': {'present': True, 'strength': 7, 'slide': 3},
        'challenge': {'present': True, 'strength': 9, 'slide': 4},
        'resolution': {'present': True, 'strength': 6, 'slide': 5},
        'benefits': {'present': False, 'strength': 0, 'slide': None},
        'call_to_action': {'present': True, 'strength': 5, 'slide': 7}
    },
    'slide_order_changes': [          # Reordering suggestions
        {
            'slide_id': 'slide_4',
            'current_position': 4,
            'suggested_position': 5,
            'reason': 'Better context before challenge'
        }
    ],
    'metadata': {
        'slides_analyzed': 8,
        'api_tokens_used': 1650
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Analyze existing presentation
pres_id = 'existing-presentation-id'

result = editor.improve_narrative_flow(pres_id)

print(f"Narrative Flow Analysis:")
print(f"  Before: {result['before_score']}/100")
print(f"  After:  {result['after_score']}/100")
print(f"  Improvement: +{result['after_score'] - result['before_score']} points")

print(f"\nStory Arc Completeness:")
for element, analysis in result['arc_analysis'].items():
    status = '✓' if analysis['present'] else '✗'
    strength = f"{analysis['strength']}/10" if analysis['present'] else 'missing'
    print(f"  {status} {element.replace('_', ' ').title()}: {strength}")

print(f"\nImprovements Made:")
for suggestion in result['suggestions']:
    if suggestion['implemented']:
        print(f"  ✓ {suggestion['description']}")
        print(f"    → {suggestion['suggestion']}")

print(f"\nRemaining Suggestions:")
for suggestion in result['suggestions']:
    if not suggestion['implemented']:
        priority = suggestion['priority'].upper()
        print(f"  [{priority}] {suggestion['description']}")
        print(f"    → {suggestion['suggestion']}")
```

**What Gets Analyzed:**

1. **Story Arc Completeness**
   - Checks for all 6 story elements
   - Scores strength of each element
   - Identifies missing components

2. **Slide Transitions**
   - Evaluates flow between slides
   - Detects abrupt jumps
   - Suggests bridging content

3. **Content Balance**
   - Checks information density per slide
   - Identifies overstuffed or empty slides
   - Suggests redistribution

4. **Narrative Coherence**
   - Ensures logical progression
   - Validates context before details
   - Checks setup before payoff

**Flow Improvements Example:**

```python
# Before: Weak narrative flow (score: 62/100)
# Slide 1: Title
# Slide 2: "Our Product Features"  ← No hook
# Slide 3: "Implementation Details"  ← Too early
# Slide 4: "Market Opportunity"  ← Should be earlier
# Slide 5: "Thank You"  ← No CTA

result = editor.improve_narrative_flow(pres_id)

# After: Strong narrative flow (score: 87/100)
# Slide 1: Title
# Slide 2: "Market Growing 40% YoY"  ← Added hook
# Slide 3: "Current Market Gap"  ← Reordered for context
# Slide 4: "Our Product Features"  ← Now flows from gap
# Slide 5: "Implementation Roadmap"  ← Logical progression
# Slide 6: "Next Steps: Budget Approval Friday"  ← Clear CTA
```

---

### generate_speaker_notes()

Auto-generate speaker notes for presentation slides.

```python
def generate_speaker_notes(
    presentation_id: str,
    detail_level: str = 'moderate'
    # api_key parameter removed!
) -> Dict[str, Any]
```

**Parameters:**

- `presentation_id` (str): Existing presentation ID
- `detail_level` (str): Amount of detail in notes
  - `'minimal'` - Key points only (30-50 words per slide)
  - `'moderate'` - Full talking points (80-120 words per slide)
  - `'detailed'` - Complete narrative (150-200 words per slide)
- `api_key` (str, optional): Anthropic API key

**Returns:**

```python
{
    'notes_generated': True,
    'slides_processed': 8,
    'detail_level': 'moderate',
    'notes': [                        # Speaker notes per slide
        {
            'slide_number': 1,
            'slide_id': 'slide_abc',
            'title': 'Q1 Product Roadmap',
            'notes': 'Welcome everyone... [80-120 words]',
            'word_count': 95,
            'talking_time_seconds': 45,
            'key_phrases': ['Q1 priorities', 'three major initiatives']
        },
        # ... more slides
    ],
    'total_words': 850,
    'estimated_presentation_time': '12-15 minutes',
    'metadata': {
        'detail_level': 'moderate',
        'api_tokens_used': 2100
    }
}
```

**Example:**

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

pres_id = 'quarterly-results-id'

# Generate moderate detail notes (recommended)
result = editor.generate_speaker_notes(
    pres_id,
    detail_level='moderate'
)

print(f"Generated notes for {result['slides_processed']} slides")
print(f"Total presentation time: {result['estimated_presentation_time']}")

# Review notes for each slide
for note in result['notes']:
    print(f"\n--- Slide {note['slide_number']}: {note['title']} ---")
    print(f"Talking time: {note['talking_time_seconds']}s")
    print(f"\nNotes ({note['word_count']} words):")
    print(note['notes'])
    print(f"\nKey phrases: {', '.join(note['key_phrases'])}")

# Generate minimal notes for quick reference
minimal_result = editor.generate_speaker_notes(
    pres_id,
    detail_level='minimal'
)
# Use for: Experienced presenters, familiar content

# Generate detailed notes for comprehensive prep
detailed_result = editor.generate_speaker_notes(
    pres_id,
    detail_level='detailed'
)
# Use for: Important presentations, unfamiliar content, backup answers
```

**Detail Level Comparison:**

**Minimal Notes (30-50 words):**
```
Slide 3: Performance Challenge

Notes:
Highlight the 3-5 second load times. Emphasize customer impact.
Mention we have a solution ready. Transition to technical details
on next slide. Key stat: 40% of complaints are performance-related.
```

**Moderate Notes (80-120 words):**
```
Slide 3: Performance Challenge

Notes:
Start by acknowledging what our customers are experiencing - dashboard
load times that have crept up to 3-5 seconds. This isn't just a
technical issue; it's affecting user experience and we're seeing it
in the support tickets.

Mention the root causes: unoptimized database queries and the lack of
a caching layer. We've identified the top 10 queries that are the
biggest offenders.

The good news is we have a clear path forward, which I'll show on the
next slide. Pause here for questions about the specific performance
metrics or user impact.

Key point: This is fixable within 6 weeks.
```

**Detailed Notes (150-200 words):**
```
Slide 3: Performance Challenge

Notes:
"Let's talk about what our customers are experiencing right now."

Our enterprise dashboard is taking 3 to 5 seconds to load. For context,
industry standard is under 1 second, and our own internal SLA is 500ms.
We're missing our target by 6-10x, and customers are noticing.

Support data shows that 40% of our recent complaints mention performance.
More concerning, we've seen two enterprise customers delay renewals,
citing "system responsiveness" as a concern.

The root cause is twofold. First, our database queries haven't been
optimized as data volume has grown. We're doing table scans where we
should have indexes. Second, we don't have a caching layer. Every
request hits the database directly.

Good news: Our engineering team has identified the specific problem
queries - the top 10 account for 80% of the slow load times. We also
have a Redis caching architecture designed and ready to implement.

Before I show you the solution, I want to pause for questions. Anyone
want to dive deeper on the performance metrics or the customer impact
data?

[Pause 10-15 seconds for questions]

"Great, let's look at how we fix this..."
```

**Notes Features:**

- **Talking time estimates** - Based on average speaking pace (120 wpm)
- **Key phrases** - Highlighted concepts to emphasize
- **Transition cues** - Bridges to next slide
- **Pause reminders** - When to check for questions
- **Data callouts** - Specific numbers to mention
- **Backup answers** - (detailed level) Anticipated questions

---

## ContentSynthesizer API

Lower-level API for content transformation (used by GoogleSlidesEditor methods).

### Methods

```python
from scripts.content_synthesizer import ContentSynthesizer

synthesizer = ContentSynthesizer(api_key='your-key')

# Transform raw content
result = synthesizer.transform_content(
    raw_content="Meeting notes...",
    target_format='bullet_points',
    style='professional',
    max_length=100
)

# Adapt tone
result = synthesizer.adapt_tone(
    content="Technical description...",
    target_audience='non-technical executives',
    preserve_facts=True
)

# Structure unstructured content
result = synthesizer.structure_content(
    content="Rambling notes...",
    desired_structure='problem_solution',
    key_points=3
)
```

See source code for detailed method signatures.

---

## StoryArcGenerator API

Lower-level API for narrative structure (used by GoogleSlidesEditor methods).

### Methods

```python
from scripts.story_arc_generator import StoryArcGenerator

arc_gen = StoryArcGenerator(api_key='your-key')

# Generate story arc
arc = arc_gen.generate_arc(
    content_summary="Presentation about...",
    audience='executives',
    arc_type='classic'  # or 'hero_journey', 'problem_solution'
)

# Analyze existing presentation
analysis = arc_gen.analyze_presentation(
    slides=slide_data,
    detect_missing=True
)

# Suggest improvements
suggestions = arc_gen.suggest_improvements(
    current_arc=analysis,
    target_audience='technical'
)
```

See source code for detailed method signatures.

---

## WhimsyInjector API

Lower-level API for personality injection (used by GoogleSlidesEditor methods).

### Methods

```python
from scripts.whimsy_injector import WhimsyInjector

whimsy = WhimsyInjector(api_key='your-key')

# Add visual metaphor
result = whimsy.create_metaphor(
    concept="Technical debt",
    context="Software engineering presentation",
    target_audience='product managers'
)

# Generate memorable phrase
phrase = whimsy.create_memorable_phrase(
    message="Quality is important",
    tone='inspirational'
)

# Enhance transition
transition = whimsy.enhance_transition(
    from_slide="Problem statement",
    to_slide="Solution approach",
    engagement_level='moderate'
)
```

See source code for detailed method signatures.

---

## Data Structures

### BrandGuidelines

```python
from scripts.brand_guidelines import BrandGuidelines

brand = BrandGuidelines(
    name="Corporate Brand",
    colors={
        'primary': '#0066cc',
        'secondary': '#00cc66',
        'accent': '#cc6600'
    },
    fonts={
        'heading': 'Arial',
        'body': 'Helvetica'
    },
    voice={
        'tone': 'professional yet approachable',
        'avoid': ['jargon', 'slang'],
        'prefer': ['clear', 'concise']
    }
)

# Load from file
brand = BrandGuidelines.from_json_file('corporate_brand.json')
```

---

## Error Handling

### Common Errors

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

try:
    result = editor.generate_from_notes(notes, purpose, audience)

except ValueError as e:
    # Invalid input
    print(f"Input error: {e}")
    # Check: notes length, purpose validity, audience specificity

except RuntimeError as e:
    # API or processing error
    print(f"Generation error: {e}")
    # Check: API key, network, token limits

except KeyError as e:
    # Missing required parameter
    print(f"Missing parameter: {e}")

except Exception as e:
    # Unexpected error
    print(f"Unexpected error: {e}")
```

### Validation

```python
# Validate before calling
if len(notes) < 50:
    print("Notes too short, add more context")

if purpose not in ['executive_update', 'team_presentation', ...]:
    print("Invalid purpose, use predefined values")

if not audience or len(audience) < 10:
    print("Audience description too vague")
```

---

## Integration Examples

### Example 1: Complete AI-Powered Workflow

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# 1. Generate from notes
result = editor.generate_from_notes(
    notes=meeting_notes,
    purpose='executive_update',
    audience='C-suite'
)

pres_id = result['pres_id']
content_blocks = result['content_blocks']

# 2. Apply story arc
arc_result = editor.apply_story_arc(
    pres_id,
    content_blocks,
    audience='C-suite'
)

print(f"Arc score improved to {arc_result['arc_score']}/100")

# 3. Add moderate personality
whimsy_result = editor.add_whimsy(
    pres_id,
    personality_level='moderate'
)

print(f"Enhanced {whimsy_result['slides_enhanced']} slides")

# 4. Generate speaker notes
notes_result = editor.generate_speaker_notes(
    pres_id,
    detail_level='moderate'
)

print(f"Total presentation time: {notes_result['estimated_presentation_time']}")
print(f"Presentation ready: {result['pres_url']}")
```

### Example 2: Improve Existing Presentation

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

pres_id = 'existing-presentation-id'

# 1. Analyze narrative flow
flow_result = editor.improve_narrative_flow(pres_id)

print(f"Flow improved from {flow_result['before_score']} to {flow_result['after_score']}")

# 2. Add personality if appropriate
if flow_result['after_score'] >= 75:
    whimsy_result = editor.add_whimsy(pres_id, personality_level='minimal')
    print(f"Added {len(whimsy_result['enhancements'])} subtle enhancements")

# 3. Generate notes for better delivery
notes_result = editor.generate_speaker_notes(pres_id, detail_level='detailed')
print(f"Generated detailed notes for {notes_result['slides_processed']} slides")
```

### Example 3: Selective AI Enhancement

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Create presentation manually (Phases 1-4)
result = editor.create_presentation("Product Launch")
pres_id = result['pres_id']

# Add slides with data (charts, tables, etc.)
# ... slide creation code ...

# Use AI only for specific slides
context = {
    'key_points': ['Point 1', 'Point 2', 'Point 3'],
    'emphasis': 'competitive advantage'
}

content = editor.synthesize_slide_content(
    slide_purpose='competitive_advantage',
    context=context,
    style='professional'
)

# Add synthesized content to specific slide
# ... add to presentation ...

print("Hybrid approach: manual creation + AI enhancement")
```

---

## Related Documentation

- [AI Content Generation Guide](AI_CONTENT_GENERATION.md) - Comprehensive guide and best practices
- [Phase 5 Summary](../PHASE5_SUMMARY.md) - Implementation overview
- [Examples](../examples/) - Working code examples
- [Phase 4 API Reference](PHASE4_API_REFERENCE.md) - Data visualization methods
