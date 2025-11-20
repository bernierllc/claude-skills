# Phase 5: Intelligent Content Generation - Quick Start Guide

## 🎉 No Setup Required!

**Phase 5 now works through Claude skill invocation - no API key needed!**

### ~~1. Install Dependencies~~ (NO LONGER NEEDED!)
```bash
# pip install anthropic>=0.39.0  # Not required anymore!
```

### ~~2. Set API Key~~ (NO LONGER NEEDED!)
```bash
# export ANTHROPIC_API_KEY="not-required"  # Phase 5 works through Claude!
```

**How It Works:**
- Simply invoke the gslides skill through Claude Code
- Claude generates AI content directly
- No external API calls or costs
- Real-time content generation

## Basic Usage

### Content Synthesizer - Transform Notes to Slides

```python
from scripts.content_synthesizer import ContentSynthesizer

# Initialize - no API key needed!
synthesizer = ContentSynthesizer()

# Transform meeting notes into presentation
notes = """
Team meeting notes from Q4 planning:
- Revenue targets up 20% next quarter
- Need to hire 3 engineers
- Launch new product feature by March
- Customer satisfaction at all-time high
"""

structure = synthesizer.synthesize_from_notes(
    raw_notes=notes,
    presentation_purpose="report",
    target_audience="senior leadership",
    slide_count=6
)

# Review generated slides
print(f"Presentation: {structure.title}")
print(f"Total slides: {structure.total_slides}\n")

for i, slide in enumerate(structure.slides, 1):
    print(f"Slide {i}: {slide.title}")
    for bullet in slide.body:
        print(f"  • {bullet}")
    if slide.speaker_notes:
        print(f"  Notes: {slide.speaker_notes[:100]}...")
    print()
```

### Story Arc Generator - Create Compelling Narratives

```python
from scripts.story_arc_generator import StoryArcGenerator

# Initialize
generator = StoryArcGenerator()

# Create story arc
arc = generator.generate_story_arc(
    topic="Cloud Migration Strategy",
    key_messages=[
        "Cloud reduces costs by 40%",
        "Migration can complete in 6 months",
        "Minimal business disruption"
    ],
    audience="C-level executives",
    slide_count=12,
    presentation_goal="Get approval for cloud migration"
)

# Review arc structure
print(f"Title: {arc.title}")
print(f"Story: {arc.narrative_summary}\n")

print(f"Hook ({len(arc.hook)} slides):")
for slide in arc.hook:
    print(f"  - {slide.title}")

print(f"\nContext ({len(arc.context)} slides):")
for slide in arc.context:
    print(f"  - {slide.title}")

print(f"\nConflict ({len(arc.conflict)} slides):")
for slide in arc.conflict:
    print(f"  - {slide.title}")

print(f"\nResolution ({len(arc.resolution)} slides):")
for slide in arc.resolution:
    print(f"  - {slide.title}")

print(f"\nCall to Action ({len(arc.call_to_action)} slides):")
for slide in arc.call_to_action:
    print(f"  - {slide.title}")
```

### Whimsy Injector - Add Personality and Memorable Elements

```python
from scripts.whimsy_injector import WhimsyInjector

# Initialize with personality level
injector = WhimsyInjector(personality_level='moderate')

# 1. Suggest visual metaphors
metaphors = injector.suggest_visual_metaphors(
    slide_content="Our multi-layered security approach protects data at every level",
    concept_to_illustrate="layered security"
)

for metaphor in metaphors:
    print(f"Metaphor: {metaphor.metaphor}")
    print(f"Visual: {metaphor.visual_description}")
    print(f"Why it works: {metaphor.explanation}\n")

# 2. Add memorable quotes
quotes = injector.add_memorable_quotes(
    topic="Innovation and Risk-Taking",
    context="Encouraging team to experiment",
    message_to_reinforce="Failure is part of learning"
)

for quote in quotes:
    print(f"Quote: \"{quote.quote}\"")
    if quote.attribution:
        print(f"- {quote.attribution}")
    print(f"Use when: {quote.context}\n")

# 3. Create engaging transitions
transition = injector.create_engaging_transitions(
    from_slide={'title': 'The Challenge We Face'},
    to_slide={'title': 'Our Innovative Solution'}
)

print(f"Transition: {transition.transition_text}")
print(f"Why it works: {transition.rationale}")

# 4. Inject personality into dry content
original = "Revenue increased 15% in Q4 compared to Q3."

injection = injector.inject_personality(
    content=original,
    context_type='business'
)

print(f"\nOriginal: {injection.original_content}")
print(f"Enhanced: {injection.enhanced_content}")
print(f"Changes made: {', '.join(injection.changes_made)}")
```

## Common Workflows

### Workflow 1: Notes → Presentation

```python
from scripts.content_synthesizer import ContentSynthesizer

synthesizer = ContentSynthesizer()

# Your raw notes
notes = "Your meeting notes, transcript, or outline here..."

# Generate presentation structure
structure = synthesizer.synthesize_from_notes(
    raw_notes=notes,
    presentation_purpose="pitch",  # or "training", "report", "strategy"
    target_audience="investors",
    slide_count=10,
    key_messages=["Market is huge", "Product is unique", "Team is strong"]
)

# Use structure to create actual slides
# (Integration with GoogleSlidesEditor in Phase 6)
```

### Workflow 2: Analyze and Improve Existing Presentation

```python
from scripts.story_arc_generator import StoryArcGenerator

generator = StoryArcGenerator()

# Your current slides
current_slides = [
    {'title': 'Introduction', 'content': ['...']},
    {'title': 'Product Features', 'content': ['...']},
    {'title': 'Pricing', 'content': ['...']}
]

# Get improvement suggestions
analysis = generator.suggest_arc_improvements(
    current_slides,
    presentation_goal="Close sales deals"
)

print(f"Current arc quality: {analysis.current_arc_quality}/100")

print("\nWhat's working:")
for strength in analysis.strengths:
    print(f"✓ {strength}")

print("\nWhat needs improvement:")
for improvement in analysis.improvements:
    print(f"→ {improvement}")

print("\nMissing from narrative:")
for missing in analysis.missing_elements:
    print(f"✗ {missing}")
```

### Workflow 3: Add Personality to Bland Content

```python
from scripts.whimsy_injector import WhimsyInjector

injector = WhimsyInjector(personality_level='moderate')

bland_bullets = [
    "Sales increased by 15%",
    "Customer retention improved",
    "Operating costs decreased"
]

enhanced_bullets = []
for bullet in bland_bullets:
    injection = injector.inject_personality(
        content=bullet,
        brand_voice={'tone': 'energetic', 'style': 'results-focused'},
        context_type='business'
    )
    enhanced_bullets.append(injection.enhanced_content)

print("Before vs After:")
for original, enhanced in zip(bland_bullets, enhanced_bullets):
    print(f"• {original}")
    print(f"→ {enhanced}\n")
```

### Workflow 4: Complete AI-Powered Presentation Creation

```python
from scripts.content_synthesizer import ContentSynthesizer
from scripts.story_arc_generator import StoryArcGenerator
from scripts.whimsy_injector import WhimsyInjector

# Initialize all components
synthesizer = ContentSynthesizer()
generator = StoryArcGenerator()
injector = WhimsyInjector(personality_level='moderate')

# Step 1: Generate content from notes
raw_notes = "Product launch notes..."
structure = synthesizer.synthesize_from_notes(
    raw_notes=raw_notes,
    presentation_purpose="announcement",
    target_audience="customers and press"
)

# Step 2: Organize into compelling story arc
content_blocks = [
    {'title': slide.title, 'content': slide.body}
    for slide in structure.slides
]
arc = generator.map_content_to_arc(content_blocks)

# Step 3: Enhance with personality
for narrative_slide in arc.get_all_slides():
    # Enhance title
    enhanced = injector.inject_personality(
        narrative_slide.title,
        context_type='creative'
    )
    narrative_slide.title = enhanced.enhanced_content

    # Get visual metaphor for key slides
    if narrative_slide.arc_stage in ['conflict', 'resolution']:
        metaphors = injector.suggest_visual_metaphors(
            slide_content=' '.join(narrative_slide.content)
        )
        if metaphors:
            print(f"\nSlide: {narrative_slide.title}")
            print(f"Visual suggestion: {metaphors[0].metaphor}")

# Step 4: Create slides with GoogleSlidesEditor
# (Integration in Phase 6)
```

## Personality Levels

### Minimal
```python
injector = WhimsyInjector(personality_level='minimal')
# Subtle, professional
# Original: "Revenue increased 15%"
# Enhanced: "Revenue grew 15% year-over-year"
```

### Moderate (Default)
```python
injector = WhimsyInjector(personality_level='moderate')
# Balanced, engaging
# Original: "Revenue increased 15%"
# Enhanced: "Revenue surged 15%, exceeding our ambitious targets"
```

### High
```python
injector = WhimsyInjector(personality_level='high')
# Bold, memorable
# Original: "Revenue increased 15%"
# Enhanced: "Revenue skyrocketed 15%, crushing every forecast we dared to dream"
```

## Context Types

### Formal
```python
# Board meetings, compliance, legal
injector.inject_personality(content, context_type='formal')
```

### Business (Default)
```python
# Standard business presentations
injector.inject_personality(content, context_type='business')
```

### Creative
```python
# Marketing, design, innovation
injector.inject_personality(content, context_type='creative')
```

### Educational
```python
# Training, teaching
injector.inject_personality(content, context_type='educational')
```

### Inspirational
```python
# Keynotes, motivation
injector.inject_personality(content, context_type='inspirational')
```

## Best Practices

### Content Synthesizer
1. **Provide rich context**: More details = better content
2. **Set constraints**: Slide count and duration help focus generation
3. **Include key messages**: Ensures critical points aren't missed
4. **Review and refine**: AI is a starting point, not final output

### Story Arc Generator
1. **Define clear goal**: What should presentation achieve?
2. **Know your audience**: Arc adapts based on who's listening
3. **Don't skip stages**: Complete arc is more compelling
4. **Use analysis first**: Understand current state before generating

### Whimsy Injector
1. **Match level to context**: Formal = minimal, Creative = high
2. **Validate appropriateness**: Test risky elements
3. **Respect brand voice**: Provide guidelines for consistency
4. **Understand rationale**: Don't blindly accept suggestions

## Error Handling

```python
from anthropic import APIError

try:
    structure = synthesizer.synthesize_from_notes(notes)
except ValueError as e:
    print(f"Configuration error: {e}")
    # Missing API key or invalid parameters
except APIError as e:
    print(f"API error: {e}")
    # Rate limit, network issue, or API problem
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Cost Considerations

### Phase 5 is FREE!

**No external API costs** - Phase 5 works through Claude skill invocation:

- ✅ **Zero token costs** to track
- ✅ **Unlimited generation** (within Claude usage)
- ✅ **No budget management** needed
- ✅ **No optimization required** for costs

Simply use the features through Claude Code - all AI generation is free!

## Next Steps

1. Try the examples above
2. Review generated content
3. Experiment with different personality levels
4. Combine all three components for complete workflow
5. Wait for Phase 6 integration with GoogleSlidesEditor

## Support

For questions:
- Review `PHASE5_SUMMARY.md` for detailed documentation
- Check individual module docstrings
- See example usage in this guide

---

**Quick Reference**:
- `ContentSynthesizer()` - Generate content from notes
- `StoryArcGenerator()` - Create narrative structure
- `WhimsyInjector()` - Add personality and memorability
