#!/usr/bin/env python3
"""
Generate a presentation from meeting notes using AI.

This example demonstrates:
1. Taking 250 words of raw meeting notes
2. Using generate_from_notes() to create a 5-slide deck
3. Applying brand theme (uses startup_brand.json)
4. Showing the before/after transformation

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


def main():
    """Generate presentation from meeting notes."""

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n" + "=" * 60)
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("=" * 60)
        print("\nTo use AI content generation, you need an Anthropic API key.")
        print("\nSteps:")
        print("1. Get API key from: https://console.anthropic.com/")
        print("2. Set environment variable:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("3. Re-run this script")
        print("\n" + "=" * 60 + "\n")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("AI-Powered Presentation Generation Example")
    print("=" * 60 + "\n")

    # Meeting notes (250 words of rough content)
    meeting_notes = """
    Product roadmap meeting - January 15, 2024

    PERFORMANCE ISSUES:
    Dashboard performance problems reported by enterprise customers.
    Load times currently 3-5 seconds, should be under 1 second for good UX.
    Root cause analysis shows database queries not optimized, no caching layer.

    SOLUTION PROPOSED:
    Implement Redis caching infrastructure ($500/month operational cost).
    Optimize top 10 slowest queries (represent 80% of performance issues).
    Timeline: 6 weeks for full implementation with 2 engineers dedicated.
    Expected improvement: Load times under 500ms after optimization.

    NEW FEATURE REQUESTS:
    Analytics feature requested by three top customers:
    - Acme Corporation
    - TechStart Inc
    - BigCo Enterprises

    They want custom dashboards with drag-and-drop widget capabilities.
    Competitive advantage: None of our competitors offer this level of customization.
    Market research shows 40% of enterprise customers would pay premium for this.

    DEVELOPMENT ESTIMATE:
    3 months development timeline with 2 senior engineers.
    Requires new microservice architecture for widget system.
    Investment: $180K in development costs.

    MOBILE APP FEEDBACK:
    Mobile app UI feels dated compared to competitors (user feedback).
    Team discussed two options:
    1. Incremental UI updates (faster but limited impact)
    2. Complete React Native rebuild (4-month timeline, better long-term)

    Team strongly recommends option 2 for future maintainability and performance.

    DECISION NEEDED:
    Need executive approval for Redis infrastructure budget and resource allocation
    for the three initiatives: performance, analytics, mobile rebuild.
    """

    print("MEETING NOTES (250 words):")
    print("-" * 60)
    print(meeting_notes.strip())
    print("-" * 60 + "\n")

    # Initialize editor
    print("Initializing Google Slides Editor...")
    editor = GoogleSlidesEditor()

    print("Generating presentation from notes using AI...")
    print("(This may take 10-20 seconds)\n")

    try:
        # Generate presentation from notes
        result = editor.generate_from_notes(
            notes=meeting_notes,
            purpose='executive_update',
            audience='C-suite executives and product stakeholders'
        )

        print("\n" + "=" * 60)
        print("GENERATION SUCCESSFUL!")
        print("=" * 60 + "\n")

        print(f"Presentation ID: {result['pres_id']}")
        print(f"Presentation URL: {result['pres_url']}")
        print(f"Slides Generated: {result['slide_count']}\n")

        # Show slide structure
        print("SLIDE STRUCTURE:")
        print("-" * 60)
        for i, slide in enumerate(result['slides'], 1):
            print(f"\n{i}. {slide['title']}")
            print(f"   Type: {slide['content_type']}")
            if 'preview' in slide:
                print(f"   Preview: {slide['preview'][:80]}...")

        print("\n" + "-" * 60 + "\n")

        # Apply brand theme if available
        brand_file = Path(__file__).parent.parent / 'brand_templates' / 'startup_brand.json'

        if brand_file.exists():
            print("Applying startup brand theme...")
            brand = editor.load_brand_guidelines(str(brand_file))
            editor.apply_brand_theme(result['pres_id'], brand)
            print("Brand theme applied!\n")
        else:
            print("Startup brand template not found, skipping brand application.")
            print(f"Expected at: {brand_file}\n")

        # Show transformation summary
        print("=" * 60)
        print("TRANSFORMATION SUMMARY")
        print("=" * 60 + "\n")

        print("BEFORE (Meeting Notes):")
        print("  - 250 words of rough, unstructured notes")
        print("  - Mixed topics and priorities")
        print("  - Technical jargon and details")
        print("  - No clear narrative flow\n")

        print("AFTER (AI-Generated Presentation):")
        print(f"  - {result['slide_count']} professionally structured slides")
        print("  - Clear narrative arc (Hook → Challenge → Resolution → Action)")
        print("  - Executive-appropriate language")
        print("  - Organized by priority and impact")
        print("  - Ready for board presentation\n")

        # Show metadata if available
        if 'metadata' in result:
            metadata = result['metadata']
            print("GENERATION METADATA:")
            print(f"  - Purpose: {metadata.get('purpose', 'N/A')}")
            print(f"  - Audience: {metadata.get('audience', 'N/A')}")
            print(f"  - Generated: {metadata.get('generated_at', 'N/A')}")
            print(f"  - API Tokens: {metadata.get('api_tokens_used', 'N/A')}\n")

        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60 + "\n")
        print("1. Open the presentation in your browser:")
        print(f"   {result['pres_url']}\n")
        print("2. Review the generated content:")
        print("   - Check accuracy of facts and numbers")
        print("   - Verify tone matches your brand")
        print("   - Add specific data points and examples\n")
        print("3. Refine and personalize:")
        print("   - Add charts/graphs using Phase 4 methods")
        print("   - Insert company logos and images")
        print("   - Adjust wording for your specific context\n")
        print("4. Enhance with AI (optional):")
        print("   - Use editor.apply_story_arc() to optimize flow")
        print("   - Use editor.add_whimsy() for personality")
        print("   - Use editor.generate_speaker_notes() for talking points\n")

        print("=" * 60 + "\n")

    except ValueError as e:
        print(f"\nERROR: Invalid input - {e}")
        print("Check your notes, purpose, and audience parameters.\n")
        return 1

    except RuntimeError as e:
        print(f"\nERROR: Generation failed - {e}")
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
