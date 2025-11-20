#!/usr/bin/env python3
"""
Demonstrate story arc generation and application.

This example demonstrates:
1. Creating a basic 6-slide presentation (hook, context, challenge, resolution, benefits, CTA)
2. Using apply_story_arc() to optimize narrative flow
3. Showing arc analysis and scoring
4. Displaying suggested improvements

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


def create_basic_presentation(editor):
    """Create a basic presentation without story arc optimization."""

    print("Creating basic 6-slide presentation...\n")

    # Create presentation
    result = editor.create_presentation("Cloud Migration Strategy")
    pres_id = result['pres_id']

    slides = []

    # Slide 1: Hook (but weak)
    slide1 = editor.create_slide(pres_id)
    slides.append(slide1)
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        "Cloud Migration Overview",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        "Our move to cloud infrastructure",
        x=50, y=130, width=620, height=40
    )

    # Slide 2: Context
    slide2 = editor.create_slide(pres_id)
    slides.append(slide2)
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "Current Infrastructure",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "• On-premise data centers\n• Hardware refresh every 5 years\n• Manual scaling processes",
        x=80, y=130, width=560, height=120
    )

    # Slide 3: Challenge (but not urgent enough)
    slide3 = editor.create_slide(pres_id)
    slides.append(slide3)
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Some Issues",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "• Costs are higher\n• Scaling takes time\n• Limited flexibility",
        x=80, y=130, width=560, height=120
    )

    # Slide 4: Resolution
    slide4 = editor.create_slide(pres_id)
    slides.append(slide4)
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "Cloud Solution",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "• Migrate to AWS\n• Auto-scaling enabled\n• Pay-as-you-go pricing",
        x=80, y=130, width=560, height=120
    )

    # Slide 5: Benefits (but not compelling)
    slide5 = editor.create_slide(pres_id)
    slides.append(slide5)
    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "Expected Benefits",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "• Cost savings\n• Better performance\n• More flexibility",
        x=80, y=130, width=560, height=120
    )

    # Slide 6: CTA (but vague)
    slide6 = editor.create_slide(pres_id)
    slides.append(slide6)
    editor.insert_text_box(
        pres_id, slide6['slide_id'],
        "Next Steps",
        x=50, y=50, width=620, height=60
    )
    editor.insert_text_box(
        pres_id, slide6['slide_id'],
        "• Evaluate options\n• Plan migration\n• Execute transition",
        x=80, y=130, width=560, height=120
    )

    print(f"Created presentation: {result['pres_url']}\n")

    return pres_id, result['pres_url'], slides


def main():
    """Demonstrate story arc optimization."""

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n" + "=" * 60)
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("=" * 60)
        print("\nTo use AI story arc generation, you need an Anthropic API key.")
        print("\nSteps:")
        print("1. Get API key from: https://console.anthropic.com/")
        print("2. Set environment variable:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("3. Re-run this script")
        print("\n" + "=" * 60 + "\n")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Story Arc Optimization Example")
    print("=" * 60 + "\n")

    print("This example demonstrates:")
    print("1. Creating a basic presentation with weak narrative flow")
    print("2. Analyzing the story arc")
    print("3. Applying story arc optimization")
    print("4. Showing before/after comparison\n")

    # Initialize editor
    print("Initializing Google Slides Editor...")
    editor = GoogleSlidesEditor()

    # Create basic presentation
    pres_id, pres_url, slides = create_basic_presentation(editor)

    # Prepare content blocks for arc analysis
    content_blocks = [
        {
            'type': 'hook',
            'content': 'Cloud Migration Overview - Our move to cloud infrastructure',
            'slide_numbers': [1]
        },
        {
            'type': 'context',
            'content': 'Current Infrastructure: On-premise data centers, hardware refresh, manual scaling',
            'slide_numbers': [2]
        },
        {
            'type': 'challenge',
            'content': 'Some Issues: Higher costs, slow scaling, limited flexibility',
            'slide_numbers': [3]
        },
        {
            'type': 'resolution',
            'content': 'Cloud Solution: AWS migration, auto-scaling, pay-as-you-go',
            'slide_numbers': [4]
        },
        {
            'type': 'benefits',
            'content': 'Expected Benefits: Cost savings, better performance, more flexibility',
            'slide_numbers': [5]
        },
        {
            'type': 'call_to_action',
            'content': 'Next Steps: Evaluate options, plan migration, execute transition',
            'slide_numbers': [6]
        }
    ]

    print("=" * 60)
    print("BEFORE OPTIMIZATION")
    print("=" * 60 + "\n")

    print("Current Slide Content:")
    print("-" * 60)
    print("1. Hook: 'Cloud Migration Overview' (WEAK - no attention grabber)")
    print("2. Context: Current infrastructure description (OK)")
    print("3. Challenge: 'Some Issues' (WEAK - not urgent or compelling)")
    print("4. Resolution: Cloud solution overview (OK)")
    print("5. Benefits: Generic benefits (WEAK - no specific metrics)")
    print("6. CTA: 'Next Steps' (WEAK - vague, no ownership)\n")

    print("Narrative Issues:")
    print("  ✗ Weak hook - doesn't grab attention")
    print("  ✗ Challenge lacks urgency and specifics")
    print("  ✗ Benefits not quantified")
    print("  ✗ Call to action is vague")
    print("  ✗ No emotional resonance\n")

    try:
        print("=" * 60)
        print("APPLYING STORY ARC OPTIMIZATION")
        print("=" * 60 + "\n")

        print("Analyzing presentation with AI...")
        print("(This may take 8-12 seconds)\n")

        # Apply story arc optimization
        result = editor.apply_story_arc(
            pres_id,
            content_blocks,
            audience='C-suite executives and IT leadership'
        )

        print("OPTIMIZATION COMPLETE!\n")
        print("=" * 60)
        print("RESULTS")
        print("=" * 60 + "\n")

        # Show arc score
        print(f"Narrative Arc Score:")
        print(f"  Before: {result.get('arc_score_before', 'N/A')}/100")
        print(f"  After:  {result['arc_score']}/100")
        print(f"  Improvement: +{result['arc_score'] - result.get('arc_score_before', result['arc_score'])}\n")

        # Show elements optimized
        print(f"Story Elements Optimized: {result['elements_optimized']}")
        print(f"Slides Modified: {len(result['slides_modified'])}\n")

        # Show specific improvements
        if 'improvements' in result and result['improvements']:
            print("SPECIFIC IMPROVEMENTS:")
            print("-" * 60)
            for i, improvement in enumerate(result['improvements'], 1):
                print(f"\n{i}. Slide {improvement['slide_number']}: {improvement['element']}")
                print(f"   Change: {improvement['change']}")
                if 'before' in improvement:
                    print(f"   Before: \"{improvement['before']}\"")
                if 'after' in improvement:
                    print(f"   After:  \"{improvement['after']}\"")
        else:
            print("Improvements applied to overall narrative flow.")

        print("\n" + "-" * 60 + "\n")

        # Show enhanced narrative elements
        print("=" * 60)
        print("AFTER OPTIMIZATION")
        print("=" * 60 + "\n")

        print("Enhanced Slide Content (Examples):")
        print("-" * 60)
        print("1. Hook: '67% of Fortune 500 migrated to cloud in 2023 - Here's why'")
        print("   (STRONG - uses data, creates curiosity)")
        print("\n2. Context: Infrastructure at inflection point (CLEAR)\n")
        print("3. Challenge: '$2.4M annual infrastructure costs with 40% waste'")
        print("   (STRONG - quantified, urgent)")
        print("\n4. Resolution: Cloud solution with proven ROI (CLEAR)\n")
        print("5. Benefits: '30% cost reduction, 5x faster scaling, 99.99% uptime'")
        print("   (STRONG - specific metrics)")
        print("\n6. CTA: 'Board approval needed by March 15 for Q2 migration'")
        print("   (STRONG - specific, time-bound, clear ownership)\n")

        print("Narrative Improvements:")
        print("  ✓ Strong hook with data")
        print("  ✓ Urgent, quantified challenge")
        print("  ✓ Specific, measurable benefits")
        print("  ✓ Clear, time-bound call to action")
        print("  ✓ Compelling narrative flow\n")

        # Show metadata
        if 'metadata' in result:
            metadata = result['metadata']
            print("OPTIMIZATION METADATA:")
            print(f"  - Audience: {metadata.get('audience', 'N/A')}")
            print(f"  - Arc Type: {metadata.get('arc_type', 'classic')}")
            print(f"  - API Tokens: {metadata.get('api_tokens_used', 'N/A')}\n")

        print("=" * 60)
        print("STORY ARC ANALYSIS")
        print("=" * 60 + "\n")

        print("Classic Story Arc Elements:")
        print("  1. HOOK: Grab attention (surprising stat, bold question)")
        print("  2. CONTEXT: Set the scene (why now, what's at stake)")
        print("  3. CHALLENGE: Define problem (concrete, urgent)")
        print("  4. RESOLUTION: Present solution (clear path forward)")
        print("  5. BENEFITS: Show value (measurable outcomes)")
        print("  6. CALL TO ACTION: Next steps (specific, time-bound)\n")

        print("Why Story Arcs Work:")
        print("  • Creates emotional journey for audience")
        print("  • Builds tension and provides resolution")
        print("  • Makes complex information memorable")
        print("  • Drives action with clear next steps")
        print("  • Executive audiences expect this structure\n")

        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60 + "\n")

        print("1. Review the optimized presentation:")
        print(f"   {pres_url}\n")

        print("2. Compare before/after narrative flow:")
        print("   - Notice stronger opening hook")
        print("   - See more specific, urgent challenge")
        print("   - Observe quantified benefits")
        print("   - Check clear call to action\n")

        print("3. Further enhance (optional):")
        print("   - Add data visualizations for metrics")
        print("   - Use editor.add_whimsy() for personality")
        print("   - Use editor.generate_speaker_notes() for talking points\n")

        print("4. Try with your own presentation:")
        print("   - Create a basic presentation")
        print("   - Define content blocks for each slide")
        print("   - Use editor.apply_story_arc() to optimize")
        print("   - Compare the transformation\n")

        print("=" * 60 + "\n")

    except ValueError as e:
        print(f"\nERROR: Invalid input - {e}")
        print("Check your content blocks and audience parameters.\n")
        return 1

    except RuntimeError as e:
        print(f"\nERROR: Story arc optimization failed - {e}")
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
