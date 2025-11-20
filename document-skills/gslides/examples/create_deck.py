#!/usr/bin/env python3
"""
Example: Create a comprehensive presentation deck with multiple slide layouts.

This script demonstrates Phase 2 capabilities:
- Creating presentations with multiple slides
- Using different layouts (title, section divider, bullet points, two-column)
- Adding formatted text boxes
- Applying text formatting (size, color, bold)

Standard slide dimensions: 720 x 405 points (10" x 5.625")
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    print("="*70)
    print("Google Slides API - Create Comprehensive Deck Example")
    print("="*70)
    print()

    # Initialize the editor
    editor = GoogleSlidesEditor()

    # Create a new presentation
    print("Creating presentation...")
    result = editor.create_presentation(
        title="Q4 Business Review - Example Deck"
    )

    pres_id = result['pres_id']
    pres_url = result['pres_url']

    print(f"✓ Created presentation: {result['title']}")
    print(f"  ID: {pres_id}")
    print(f"  URL: {pres_url}")
    print()

    # Get the default slide (created with presentation)
    pres = editor.get_presentation(pres_id)
    slides = pres.get('slides', [])
    first_slide_id = slides[0]['objectId'] if slides else None

    # Slide 1: Title Slide (use the default first slide)
    print("Creating Slide 1: Title slide...")
    if first_slide_id:
        # Add title
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="Q4 Business Review",
            x=60, y=120, width=600, height=80
        )
        # Get the text box ID from the last created element
        pres = editor.get_presentation(pres_id)
        slides = pres.get('slides', [])
        elements = slides[0].get('pageElements', [])
        title_box_id = elements[-1]['objectId'] if elements else None

        if title_box_id:
            # Format title: 44pt, bold, blue
            editor.update_text_style(
                pres_id, title_box_id,
                {
                    'fontSize': {'magnitude': 44, 'unit': 'PT'},
                    'bold': True,
                    'foregroundColor': {
                        'opaqueColor': {
                            'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
                        }
                    }
                }
            )

        # Add subtitle
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="Presented by: Example Company",
            x=60, y=220, width=600, height=50
        )
        # Format subtitle: 24pt, italic
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        subtitle_box_id = elements[-1]['objectId'] if elements else None

        if subtitle_box_id:
            editor.update_text_style(
                pres_id, subtitle_box_id,
                {
                    'fontSize': {'magnitude': 24, 'unit': 'PT'},
                    'italic': True,
                    'foregroundColor': {
                        'opaqueColor': {
                            'rgbColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}
                        }
                    }
                }
            )

    print("✓ Slide 1 complete")

    # Slide 2: Section Divider
    print("Creating Slide 2: Section divider...")
    slide2_result = editor.create_slide(pres_id)
    slide2_id = slide2_result['slide_id']

    # Add section title
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Key Metrics",
        x=100, y=150, width=520, height=100
    )

    # Get the text box ID and format it
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    section_box_id = elements[-1]['objectId'] if elements else None

    if section_box_id:
        editor.update_text_style(
            pres_id, section_box_id,
            {
                'fontSize': {'magnitude': 48, 'unit': 'PT'},
                'bold': True,
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.1, 'green': 0.1, 'blue': 0.1}
                    }
                }
            }
        )

    print("✓ Slide 2 complete")

    # Slide 3: Bullet Points
    print("Creating Slide 3: Bullet points...")
    slide3_result = editor.create_slide(pres_id)
    slide3_id = slide3_result['slide_id']

    # Add title
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Q4 Highlights",
        x=60, y=40, width=600, height=60
    )

    # Format title
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    title3_box_id = elements[-1]['objectId'] if elements else None

    if title3_box_id:
        editor.update_text_style(
            pres_id, title3_box_id,
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Add bullet points
    bullet_text = """• Revenue up 25% YoY
• Customer satisfaction: 92%
• 3 new product launches
• Team grew to 150+ employees"""

    editor.insert_text_box(
        pres_id, slide3_id,
        text=bullet_text,
        x=80, y=120, width=560, height=240
    )

    # Format bullet points
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    bullet_box_id = elements[-1]['objectId'] if elements else None

    if bullet_box_id:
        editor.update_text_style(
            pres_id, bullet_box_id,
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'}
            }
        )

    print("✓ Slide 3 complete")

    # Slide 4: Two-Column Layout
    print("Creating Slide 4: Two-column layout...")
    slide4_result = editor.create_slide(pres_id)
    slide4_id = slide4_result['slide_id']

    # Add title
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Strengths & Opportunities",
        x=60, y=40, width=600, height=60
    )

    # Format title
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    title4_box_id = elements[-1]['objectId'] if elements else None

    if title4_box_id:
        editor.update_text_style(
            pres_id, title4_box_id,
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Left column - Strengths
    strengths_text = """Strengths:
• Strong product-market fit
• Talented team
• Growing customer base"""

    editor.insert_text_box(
        pres_id, slide4_id,
        text=strengths_text,
        x=60, y=120, width=280, height=240
    )

    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    strengths_box_id = elements[-1]['objectId'] if elements else None

    if strengths_box_id:
        editor.update_text_style(
            pres_id, strengths_box_id,
            {
                'fontSize': {'magnitude': 20, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.0, 'green': 0.6, 'blue': 0.0}
                    }
                }
            }
        )

    # Right column - Opportunities
    opportunities_text = """Opportunities:
• International expansion
• Enterprise segment
• New product categories"""

    editor.insert_text_box(
        pres_id, slide4_id,
        text=opportunities_text,
        x=380, y=120, width=280, height=240
    )

    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    opportunities_box_id = elements[-1]['objectId'] if elements else None

    if opportunities_box_id:
        editor.update_text_style(
            pres_id, opportunities_box_id,
            {
                'fontSize': {'magnitude': 20, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.8, 'green': 0.5, 'blue': 0.0}
                    }
                }
            }
        )

    print("✓ Slide 4 complete")

    # Slide 5: Closing Slide
    print("Creating Slide 5: Closing slide...")
    slide5_result = editor.create_slide(pres_id)
    slide5_id = slide5_result['slide_id']

    # Add closing message
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Thank You!",
        x=150, y=120, width=420, height=100
    )

    # Format closing
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    closing_box_id = elements[-1]['objectId'] if elements else None

    if closing_box_id:
        editor.update_text_style(
            pres_id, closing_box_id,
            {
                'fontSize': {'magnitude': 48, 'unit': 'PT'},
                'bold': True,
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
                    }
                }
            }
        )

    # Add call to action
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Questions? Contact us at team@example.com",
        x=150, y=240, width=420, height=60
    )

    # Format call to action
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    cta_box_id = elements[-1]['objectId'] if elements else None

    if cta_box_id:
        editor.update_text_style(
            pres_id, cta_box_id,
            {
                'fontSize': {'magnitude': 18, 'unit': 'PT'}
            }
        )

    print("✓ Slide 5 complete")

    print()
    print("="*70)
    print("✓ Presentation created successfully!")
    print()
    print(f"Title: {result['title']}")
    print(f"Slides: 5")
    print(f"URL: {pres_url}")
    print()
    print("Features demonstrated:")
    print("  ✓ Title slide with formatted title and subtitle")
    print("  ✓ Section divider with large heading")
    print("  ✓ Bullet points slide")
    print("  ✓ Two-column layout")
    print("  ✓ Closing slide with call-to-action")
    print("  ✓ Various text formatting (size, color, bold, italic)")
    print("="*70)


if __name__ == '__main__':
    main()
