#!/usr/bin/env python3
"""
Example: Create a new Google Slides presentation with content.

This script demonstrates how to create new Google Slides presentations
and add basic content using Phase 2 features:
- Creating presentations
- Adding slides
- Adding text boxes
- Applying basic formatting
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    print("="*60)
    print("Google Slides API - Create Presentation Example")
    print("="*60)
    print()

    # Initialize the editor
    editor = GoogleSlidesEditor()

    # Create a presentation with content
    print("Creating a presentation with content...")
    result = editor.create_presentation(
        title="My First Presentation"
    )

    pres_id = result['pres_id']
    pres_url = result['pres_url']

    print(f"\n✓ Created presentation:")
    print(f"  Title: {result['title']}")
    print(f"  ID: {pres_id}")
    print()

    # Get the default first slide
    pres = editor.get_presentation(pres_id)
    slides = pres.get('slides', [])
    first_slide_id = slides[0]['objectId'] if slides else None

    if first_slide_id:
        # Add a title to the first slide
        print("Adding title to first slide...")
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="Welcome to Google Slides",
            x=100, y=150, width=520, height=100
        )

        # Format the title
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            title_box_id = elements[-1]['objectId']
            editor.update_text_style(
                pres_id, title_box_id,
                {
                    'fontSize': {'magnitude': 40, 'unit': 'PT'},
                    'bold': True,
                    'foregroundColor': {
                        'opaqueColor': {
                            'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
                        }
                    }
                }
            )
        print("✓ Title added and formatted")

    # Add a second slide
    print("\nAdding a second slide...")
    slide2_result = editor.create_slide(pres_id)
    slide2_id = slide2_result['slide_id']

    # Add content to second slide
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Getting Started",
        x=60, y=40, width=600, height=60
    )

    # Format the heading
    pres = editor.get_presentation(pres_id)
    slide2_elements = None
    for slide in pres['slides']:
        if slide['objectId'] == slide2_id:
            slide2_elements = slide.get('pageElements', [])
            break

    if slide2_elements:
        heading_box_id = slide2_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, heading_box_id,
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Add body text
    editor.insert_text_box(
        pres_id, slide2_id,
        text="This is a simple example of creating presentations with the Google Slides API.",
        x=80, y=120, width=560, height=100
    )

    # Format the body text
    pres = editor.get_presentation(pres_id)
    for slide in pres['slides']:
        if slide['objectId'] == slide2_id:
            slide2_elements = slide.get('pageElements', [])
            break

    if slide2_elements and len(slide2_elements) >= 2:
        body_box_id = slide2_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, body_box_id,
            {'fontSize': {'magnitude': 24, 'unit': 'PT'}}
        )

    print("✓ Second slide added with content")

    print("\n" + "="*60)
    print("✓ Done! Your presentation is ready.")
    print()
    print(f"Title: {result['title']}")
    print(f"Slides: 2")
    print(f"URL: {pres_url}")
    print()
    print("Features used:")
    print("  ✓ Created presentation")
    print("  ✓ Added formatted title")
    print("  ✓ Added second slide")
    print("  ✓ Applied text formatting (size, color, bold)")
    print()
    print("For more advanced examples, see:")
    print("  - create_deck.py: Comprehensive multi-slide deck")
    print("  - format_text.py: Text formatting showcase")
    print("  - add_slides.py: Adding slides to existing presentations")
    print("="*60)


if __name__ == '__main__':
    main()
