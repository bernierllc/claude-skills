#!/usr/bin/env python3
"""
Add whimsy and personality to existing presentations.

This example demonstrates:
1. Loading an existing bland technical presentation
2. Using add_whimsy() with different personality levels
3. Showing visual metaphor suggestions
4. Adding memorable quotes
5. Creating engaging transitions

Requirements:
- ANTHROPIC_API_KEY environment variable set
- Google OAuth credentials configured
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.gslides_editor import GoogleSlidesEditor
except ImportError:
    print("Error: Unable to import GoogleSlidesEditor")
    print("Make sure you're running from the correct directory")
    sys.exit(1)


def create_bland_technical_presentation(editor):
    """Create a bland, technical presentation that needs personality."""

    print("Creating bland technical presentation...\n")

    # Create presentation
    result = editor.create_presentation("Database Optimization Project")
    pres_id = result['pres_id']

    # Slide 1: Title
    slide1 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        "Database Optimization Project",
        x=50, y=150, width=620, height=80
    )

    # Slide 2: Problem (dry)
    slide2 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "Current State",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "• Database queries are slow\n• Users experiencing delays\n• Performance degraded over time",
        x=80, y=130, width=560, height=120
    )

    # Slide 3: Technical details (jargon-heavy)
    slide3 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Technical Analysis",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "• N+1 query patterns detected\n• Missing database indices\n• Suboptimal query execution plans\n• Connection pool exhaustion",
        x=80, y=130, width=560, height=150
    )

    # Slide 4: Solution (boring)
    slide4 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "Proposed Solution",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "• Implement query optimization\n• Add database indices\n• Configure connection pooling\n• Deploy caching layer",
        x=80, y=130, width=560, height=150
    )

    # Slide 5: Benefits (generic)
    slide5 = editor.create_slide(pres_id)
    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "Expected Results",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "• Faster query performance\n• Improved user experience\n• Better system reliability",
        x=80, y=130, width=560, height=120
    )

    print(f"Created presentation: {result['pres_url']}\n")

    return pres_id, result['pres_url']


def main():
    """Demonstrate personality injection at different levels."""

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n" + "=" * 60)
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("=" * 60)
        print("\nTo use AI personality injection, you need an Anthropic API key.")
        print("\nSteps:")
        print("1. Get API key from: https://console.anthropic.com/")
        print("2. Set environment variable:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("3. Re-run this script")
        print("\n" + "=" * 60 + "\n")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Personality Injection Example")
    print("=" * 60 + "\n")

    print("This example demonstrates:")
    print("1. Creating a bland, technical presentation")
    print("2. Applying three levels of personality:")
    print("   - Minimal (conservative)")
    print("   - Moderate (balanced, recommended)")
    print("   - Generous (bold)")
    print("3. Showing specific enhancements for each level\n")

    # Initialize editor
    print("Initializing Google Slides Editor...")
    editor = GoogleSlidesEditor()

    # Create bland presentation
    pres_id, pres_url = create_bland_technical_presentation(editor)

    print("=" * 60)
    print("BEFORE PERSONALITY INJECTION")
    print("=" * 60 + "\n")

    print("Current Presentation State:")
    print("-" * 60)
    print("Slide 1: 'Database Optimization Project'")
    print("  - Generic title, no hook")
    print("\nSlide 2: 'Current State'")
    print("  - Dry problem statement")
    print("  - '• Database queries are slow'")
    print("\nSlide 3: 'Technical Analysis'")
    print("  - Heavy jargon, not relatable")
    print("  - '• N+1 query patterns detected'")
    print("\nSlide 4: 'Proposed Solution'")
    print("  - Boring list of tasks")
    print("  - '• Implement query optimization'")
    print("\nSlide 5: 'Expected Results'")
    print("  - Generic benefits")
    print("  - '• Faster query performance'\n")

    print("Issues with Current Presentation:")
    print("  ✗ No attention-grabbing elements")
    print("  ✗ Heavy technical jargon")
    print("  ✗ Dry, forgettable language")
    print("  ✗ No visual imagery or metaphors")
    print("  ✗ Transitions are abrupt")
    print("  ✗ Nothing memorable or quotable\n")

    try:
        # Demo 1: Minimal Personality
        print("=" * 60)
        print("PERSONALITY LEVEL: MINIMAL (Conservative)")
        print("=" * 60 + "\n")

        print("Use when: Executive presentations, board meetings, formal settings")
        print("Applying minimal personality...")
        print("(This may take 3-5 seconds)\n")

        result_minimal = editor.add_whimsy(
            pres_id,
            personality_level='minimal'
        )

        print("MINIMAL ENHANCEMENTS:")
        print("-" * 60)
        print(f"Slides enhanced: {result_minimal['slides_enhanced']}")
        print(f"Personality level: {result_minimal['personality_level']}\n")

        print("Example Enhancements:")
        if 'enhancements' in result_minimal:
            for enhancement in result_minimal['enhancements'][:2]:
                print(f"\nSlide {enhancement['slide_number']}: {enhancement['type']}")
                print(f"  Before: {enhancement.get('before', 'N/A')}")
                print(f"  After:  {enhancement.get('after', 'N/A')}")
        else:
            print("  • Subtle word choice improvements")
            print("  • 'Database queries are slow' → 'Database response time needs attention'")
            print("  • One memorable phrase: 'Fast data drives fast decisions'\n")

        print("\nCharacteristics:")
        print("  • Professional tone maintained")
        print("  • Minimal changes, maximum impact")
        print("  • Appropriate for risk-averse audiences")
        print("  • 1-2 enhancements total\n")

        # Demo 2: Moderate Personality
        print("=" * 60)
        print("PERSONALITY LEVEL: MODERATE (Balanced) - RECOMMENDED")
        print("=" * 60 + "\n")

        print("Use when: Team meetings, client presentations, most business contexts")
        print("Applying moderate personality...")
        print("(This may take 5-8 seconds)\n")

        result_moderate = editor.add_whimsy(
            pres_id,
            personality_level='moderate'
        )

        print("MODERATE ENHANCEMENTS:")
        print("-" * 60)
        print(f"Slides enhanced: {result_moderate['slides_enhanced']}")
        print(f"Personality level: {result_moderate['personality_level']}\n")

        print("Example Enhancements:")
        print("\n1. Visual Metaphor (Slide 2):")
        print("   Before: 'Database queries are slow'")
        print("   After:  'Our database is like a filing cabinet that outgrew its room'")
        print("   Why it works: Concrete imagery makes abstract concept relatable")

        print("\n2. Memorable Phrase (Slide 4):")
        print("   Before: 'Proposed Solution'")
        print("   After:  'The Fix: Speed Without Compromise'")
        print("   Why it works: Quotable, action-oriented")

        print("\n3. Engaging Transition (Slide 3 → 4):")
        print("   Before: 'Next slide'")
        print("   After:  'Here's where it gets interesting...'")
        print("   Why it works: Builds curiosity, maintains engagement")

        print("\n4. Relatable Analogy (Slide 3):")
        print("   Before: 'N+1 query patterns detected'")
        print("   After:  'Like making 100 trips to the store instead of one big trip'")
        print("   Why it works: Technical concept → everyday experience\n")

        print("Characteristics:")
        print("  • 2-3 memorable moments")
        print("  • Relatable analogies")
        print("  • Light, contextual humor")
        print("  • Engaging transitions")
        print("  • Maintains professionalism\n")

        # Demo 3: Generous Personality
        print("=" * 60)
        print("PERSONALITY LEVEL: GENEROUS (Bold)")
        print("=" * 60 + "\n")

        print("Use when: Team rallies, creative pitches, innovation discussions")
        print("Applying generous personality...")
        print("(This may take 6-10 seconds)\n")

        result_generous = editor.add_whimsy(
            pres_id,
            personality_level='generous'
        )

        print("GENEROUS ENHANCEMENTS:")
        print("-" * 60)
        print(f"Slides enhanced: {result_generous['slides_enhanced']}")
        print(f"Personality level: {result_generous['personality_level']}\n")

        print("Example Enhancements:")
        print("\n1. Bold Metaphor (Slide 2):")
        print("   Before: 'Database queries are slow'")
        print("   After:  'We're performing surgery on a rocket mid-flight'")
        print("   Why it works: Dramatic, memorable, conveys urgency")

        print("\n2. Memorable Quote (Slide 1):")
        print("   Before: 'Database Optimization Project'")
        print("   After:  'Database Optimization: Because Every Millisecond Matters'")
        print("   Why it works: Bold, quotable, stakes are clear")

        print("\n3. Unexpected Transition (Slide 3 → 4):")
        print("   Before: 'Next: Solution'")
        print("   After:  'Plot twist: The fix is simpler than you think'")
        print("   Why it works: Surprising, engaging, builds interest")

        print("\n4. Creative Visual Language (Slide 5):")
        print("   Before: 'Faster query performance'")
        print("   After:  'From tortoise to cheetah: 10x performance boost'")
        print("   Why it works: Vivid imagery, quantified improvement")

        print("\n5. Human Moment (Slide 4):")
        print("   Before: 'Configure connection pooling'")
        print("   After:  'One weekend sprint. One architect. Game-changing results.'")
        print("   Why it works: Personal, achievable, inspiring\n")

        print("Characteristics:")
        print("  • Strong personality throughout")
        print("  • Creative metaphors")
        print("  • Well-placed humor")
        print("  • Unexpected elements")
        print("  • 4-6 memorable moments\n")

        # Comparison Summary
        print("=" * 60)
        print("PERSONALITY LEVELS COMPARED")
        print("=" * 60 + "\n")

        print("Same Content, Different Personality:\n")

        print("MINIMAL (Conservative):")
        print("  'Database response time needs attention'")
        print("  - Professional, measured")
        print("  - Safe for any audience")
        print("  - 1-2 subtle improvements\n")

        print("MODERATE (Balanced) - RECOMMENDED:")
        print("  'Our database is like a filing cabinet that outgrew its room'")
        print("  - Relatable, engaging")
        print("  - Appropriate for most contexts")
        print("  - 2-3 memorable moments\n")

        print("GENEROUS (Bold):")
        print("  'We're performing surgery on a rocket mid-flight'")
        print("  - Dramatic, memorable")
        print("  - Best for creative contexts")
        print("  - 4-6 bold enhancements\n")

        # Show metadata
        if 'metadata' in result_generous:
            metadata = result_generous['metadata']
            print("ENHANCEMENT METADATA:")
            print(f"  - Personality Level: {metadata.get('personality_level', 'N/A')}")
            print(f"  - Slides Processed: {metadata.get('slides_processed', 'N/A')}")
            print(f"  - API Tokens: {metadata.get('api_tokens_used', 'N/A')}\n")

        print("=" * 60)
        print("WHIMSY TECHNIQUES EXPLAINED")
        print("=" * 60 + "\n")

        print("1. VISUAL METAPHORS:")
        print("   Transform abstract → concrete imagery")
        print("   Example: 'Technical debt' → 'House of cards'\n")

        print("2. RELATABLE ANALOGIES:")
        print("   Connect unfamiliar → familiar experiences")
        print("   Example: 'Distributed consensus' → 'Friends picking a restaurant'\n")

        print("3. MEMORABLE PHRASES:")
        print("   Create quotable moments")
        print("   Example: 'Speed matters. Direction matters more.'\n")

        print("4. ENGAGING TRANSITIONS:")
        print("   Connect slides with narrative flow")
        print("   Example: 'Here's where it gets interesting...'\n")

        print("5. HUMAN MOMENTS:")
        print("   Add personality without losing professionalism")
        print("   Example: 'Can we do this in 6 weeks? Challenging. Worth it? Absolutely.'\n")

        print("=" * 60)
        print("WHAT TO AVOID")
        print("=" * 60 + "\n")

        print("Never inject whimsy that:")
        print("  ✗ Undermines the message")
        print("  ✗ Seems forced or unnatural")
        print("  ✗ Uses corporate buzzwords sarcastically")
        print("  ✗ Distracts from data or facts")
        print("  ✗ Doesn't match company culture")
        print("  ✗ Includes memes in executive presentations")
        print("  ✗ Makes jokes about sensitive topics\n")

        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60 + "\n")

        print("1. Review the enhanced presentation:")
        print(f"   {pres_url}\n")

        print("2. Compare personality levels:")
        print("   - Notice subtlety of minimal level")
        print("   - See balance in moderate level")
        print("   - Observe boldness of generous level\n")

        print("3. Choose appropriate level for context:")
        print("   - Executive meeting? → Minimal")
        print("   - Team presentation? → Moderate")
        print("   - Creative pitch? → Generous\n")

        print("4. Try with your own presentation:")
        print("   - Create or load existing presentation")
        print("   - Choose personality level")
        print("   - Use editor.add_whimsy(pres_id, level)")
        print("   - Review and refine enhancements\n")

        print("5. Combine with other AI features:")
        print("   - Generate from notes first")
        print("   - Apply story arc optimization")
        print("   - Add personality last")
        print("   - Generate speaker notes for delivery\n")

        print("=" * 60 + "\n")

    except ValueError as e:
        print(f"\nERROR: Invalid input - {e}")
        print("Check your personality level parameter.\n")
        return 1

    except RuntimeError as e:
        print(f"\nERROR: Personality injection failed - {e}")
        print("\nPossible causes:")
        print("- API key invalid or expired")
        print("- Network connection issues")
        print("- API rate limit reached")
        print("\nPlease check your API key and try again.\n")
        return 1

    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        print("Please report this issue with the full error message.\n")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
