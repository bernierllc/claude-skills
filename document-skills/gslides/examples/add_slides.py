#!/usr/bin/env python3
"""
Example: Add slides to an existing Google Slides presentation.

This script demonstrates:
- Accepting presentation ID/URL as argument
- Adding slides with different layouts
- Inserting slides at specific positions
- Adding content to new slides

Usage:
    python add_slides.py <presentation_id_or_url>

Example:
    python add_slides.py https://docs.google.com/presentation/d/ABC123/edit
    python add_slides.py ABC123
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Error: Missing presentation ID or URL")
        print()
        print("Usage:")
        print(f"  python {sys.argv[0]} <presentation_id_or_url>")
        print()
        print("Example:")
        print(f"  python {sys.argv[0]} https://docs.google.com/presentation/d/ABC123/edit")
        print(f"  python {sys.argv[0]} ABC123")
        sys.exit(1)

    pres_url_or_id = sys.argv[1]

    print("="*70)
    print("Google Slides API - Add Slides to Existing Presentation")
    print("="*70)
    print()

    # Initialize the editor
    editor = GoogleSlidesEditor()

    # Extract presentation ID
    pres_id = editor.extract_pres_id(pres_url_or_id)

    # Get existing presentation info
    print(f"Loading presentation {pres_id}...")
    try:
        pres = editor.get_presentation(pres_id)
        existing_slides = pres.get('slides', [])
        pres_title = pres.get('title', 'Untitled')

        print(f"✓ Found presentation: {pres_title}")
        print(f"  Current slides: {len(existing_slides)}")
        print()

    except Exception as e:
        print(f"✗ Error loading presentation: {e}")
        sys.exit(1)

    # Add Slide 1: Append to end
    print("Adding Slide 1: New section (appended to end)...")
    slide1_result = editor.create_slide(pres_id)
    slide1_id = slide1_result['slide_id']

    # Add content to slide 1
    editor.insert_text_box(
        pres_id, slide1_id,
        text="New Section",
        x=100, y=150, width=520, height=100
    )

    # Format the title
    pres = editor.get_presentation(pres_id)
    slide1_elements = None
    for slide in pres['slides']:
        if slide['objectId'] == slide1_id:
            slide1_elements = slide.get('pageElements', [])
            break

    if slide1_elements:
        title1_box_id = slide1_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, title1_box_id,
            {
                'fontSize': {'magnitude': 40, 'unit': 'PT'},
                'bold': True,
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.3, 'green': 0.3, 'blue': 0.7}
                    }
                }
            }
        )

    print(f"✓ Added slide at position {slide1_result['index']}")

    # Add Slide 2: Insert at beginning
    print("Adding Slide 2: Table of contents (inserted at beginning)...")
    slide2_result = editor.create_slide(pres_id, index=0)
    slide2_id = slide2_result['slide_id']

    # Add title
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Table of Contents",
        x=60, y=40, width=600, height=60
    )

    # Get the title box and format it
    pres = editor.get_presentation(pres_id)
    slide2_elements = None
    for slide in pres['slides']:
        if slide['objectId'] == slide2_id:
            slide2_elements = slide.get('pageElements', [])
            break

    if slide2_elements:
        title2_box_id = slide2_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, title2_box_id,
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Add content list
    toc_text = """1. Introduction
2. Main Topics
3. New Section
4. Conclusion"""

    editor.insert_text_box(
        pres_id, slide2_id,
        text=toc_text,
        x=100, y=120, width=520, height=240
    )

    # Format TOC
    pres = editor.get_presentation(pres_id)
    for slide in pres['slides']:
        if slide['objectId'] == slide2_id:
            slide2_elements = slide.get('pageElements', [])
            break

    if slide2_elements and len(slide2_elements) >= 2:
        toc_box_id = slide2_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, toc_box_id,
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'}
            }
        )

    print(f"✓ Inserted slide at position {slide2_result['index']}")

    # Add Slide 3: Insert in middle
    print("Adding Slide 3: Additional content (inserted in middle)...")
    middle_index = (len(existing_slides) + 2) // 2  # Rough middle position
    slide3_result = editor.create_slide(pres_id, index=middle_index)
    slide3_id = slide3_result['slide_id']

    # Add title and content
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Key Points",
        x=60, y=40, width=600, height=60
    )

    # Format title
    pres = editor.get_presentation(pres_id)
    slide3_elements = None
    for slide in pres['slides']:
        if slide['objectId'] == slide3_id:
            slide3_elements = slide.get('pageElements', [])
            break

    if slide3_elements:
        title3_box_id = slide3_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, title3_box_id,
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Add content
    key_points = """• Important insight #1
• Important insight #2
• Important insight #3"""

    editor.insert_text_box(
        pres_id, slide3_id,
        text=key_points,
        x=80, y=120, width=560, height=240
    )

    # Format content
    pres = editor.get_presentation(pres_id)
    for slide in pres['slides']:
        if slide['objectId'] == slide3_id:
            slide3_elements = slide.get('pageElements', [])
            break

    if slide3_elements and len(slide3_elements) >= 2:
        content_box_id = slide3_elements[-1]['objectId']
        editor.update_text_style(
            pres_id, content_box_id,
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'}
            }
        )

    print(f"✓ Inserted slide at position {slide3_result['index']}")

    # Get final presentation info
    pres = editor.get_presentation(pres_id)
    final_slides = pres.get('slides', [])

    print()
    print("="*70)
    print("✓ Slides added successfully!")
    print()
    print(f"Presentation: {pres_title}")
    print(f"Original slides: {len(existing_slides)}")
    print(f"Final slides: {len(final_slides)}")
    print(f"Added: 3 new slides")
    print()
    print("New slides:")
    print(f"  • Table of Contents (position 0)")
    print(f"  • Key Points (position {middle_index})")
    print(f"  • New Section (position {len(final_slides) - 1})")
    print()
    print(f"View presentation: https://docs.google.com/presentation/d/{pres_id}/edit")
    print("="*70)


if __name__ == '__main__':
    main()
