#!/usr/bin/env python3
"""
Example: Text formatting showcase for Google Slides.

This script creates a presentation demonstrating various text formatting options:
- Different font sizes (24pt, 32pt, 44pt)
- Different colors (brand colors and standard colors)
- Bold, italic, underline
- Different font families

This serves as both a formatting reference and a visual style guide.
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    print("="*70)
    print("Google Slides API - Text Formatting Showcase")
    print("="*70)
    print()

    # Initialize the editor
    editor = GoogleSlidesEditor()

    # Create a new presentation
    print("Creating presentation...")
    result = editor.create_presentation(
        title="Text Formatting Showcase"
    )

    pres_id = result['pres_id']
    pres_url = result['pres_url']

    print(f"✓ Created presentation: {result['title']}")
    print(f"  ID: {pres_id}")
    print()

    # Get the default slide
    pres = editor.get_presentation(pres_id)
    slides = pres.get('slides', [])
    first_slide_id = slides[0]['objectId'] if slides else None

    # Slide 1: Font Sizes
    print("Creating Slide 1: Font sizes showcase...")
    if first_slide_id:
        # Title
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="Font Sizes",
            x=60, y=20, width=600, height=50
        )
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            editor.update_text_style(
                pres_id, elements[-1]['objectId'],
                {
                    'fontSize': {'magnitude': 32, 'unit': 'PT'},
                    'bold': True
                }
            )

        # 24pt example
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="24pt - Standard body text",
            x=80, y=90, width=560, height=40
        )
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            editor.update_text_style(
                pres_id, elements[-1]['objectId'],
                {'fontSize': {'magnitude': 24, 'unit': 'PT'}}
            )

        # 32pt example
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="32pt - Section headings",
            x=80, y=150, width=560, height=50
        )
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            editor.update_text_style(
                pres_id, elements[-1]['objectId'],
                {'fontSize': {'magnitude': 32, 'unit': 'PT'}}
            )

        # 44pt example
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="44pt - Main titles",
            x=80, y=220, width=560, height=70
        )
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            editor.update_text_style(
                pres_id, elements[-1]['objectId'],
                {'fontSize': {'magnitude': 44, 'unit': 'PT'}}
            )

        # 18pt example
        editor.insert_text_box(
            pres_id, first_slide_id,
            text="18pt - Small text and captions",
            x=80, y=310, width=560, height=35
        )
        pres = editor.get_presentation(pres_id)
        elements = pres['slides'][0].get('pageElements', [])
        if elements:
            editor.update_text_style(
                pres_id, elements[-1]['objectId'],
                {'fontSize': {'magnitude': 18, 'unit': 'PT'}}
            )

    print("✓ Slide 1 complete")

    # Slide 2: Colors
    print("Creating Slide 2: Color palette...")
    slide2_result = editor.create_slide(pres_id)
    slide2_id = slide2_result['slide_id']

    # Title
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Color Palette",
        x=60, y=20, width=600, height=50
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Brand Blue
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Brand Blue - Primary color",
        x=80, y=90, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
                    }
                }
            }
        )

    # Success Green
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Success Green - Positive indicators",
        x=80, y=145, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.0, 'green': 0.6, 'blue': 0.0}
                    }
                }
            }
        )

    # Warning Orange
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Warning Orange - Caution items",
        x=80, y=200, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.9, 'green': 0.5, 'blue': 0.0}
                    }
                }
            }
        )

    # Error Red
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Error Red - Critical alerts",
        x=80, y=255, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.8, 'green': 0.0, 'blue': 0.0}
                    }
                }
            }
        )

    # Neutral Gray
    editor.insert_text_box(
        pres_id, slide2_id,
        text="Neutral Gray - Secondary text",
        x=80, y=310, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][1].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}
                    }
                }
            }
        )

    print("✓ Slide 2 complete")

    # Slide 3: Text Styles
    print("Creating Slide 3: Text styles (bold, italic, underline)...")
    slide3_result = editor.create_slide(pres_id)
    slide3_id = slide3_result['slide_id']

    # Title
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Text Styles",
        x=60, y=20, width=600, height=50
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Bold example
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Bold text - For emphasis and headings",
        x=80, y=90, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'bold': True
            }
        )

    # Italic example
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Italic text - For quotes and subtle emphasis",
        x=80, y=150, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'italic': True
            }
        )

    # Underline example
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Underlined text - For links and highlights",
        x=80, y=210, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'underline': True
            }
        )

    # Bold + Italic example
    editor.insert_text_box(
        pres_id, slide3_id,
        text="Bold and Italic - For strong emphasis",
        x=80, y=270, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][2].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'bold': True,
                'italic': True
            }
        )

    print("✓ Slide 3 complete")

    # Slide 4: Font Families
    print("Creating Slide 4: Font families...")
    slide4_result = editor.create_slide(pres_id)
    slide4_id = slide4_result['slide_id']

    # Title
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Font Families",
        x=60, y=20, width=600, height=50
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Arial
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Arial - Clean and professional",
        x=80, y=90, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'fontFamily': 'Arial'
            }
        )

    # Roboto
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Roboto - Modern and readable",
        x=80, y=150, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'fontFamily': 'Roboto'
            }
        )

    # Georgia
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Georgia - Classic and elegant",
        x=80, y=210, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 24, 'unit': 'PT'},
                'fontFamily': 'Georgia'
            }
        )

    # Courier New
    editor.insert_text_box(
        pres_id, slide4_id,
        text="Courier New - Monospace for code",
        x=80, y=270, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][3].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 22, 'unit': 'PT'},
                'fontFamily': 'Courier New'
            }
        )

    print("✓ Slide 4 complete")

    # Slide 5: Combined Formatting
    print("Creating Slide 5: Combined formatting showcase...")
    slide5_result = editor.create_slide(pres_id)
    slide5_id = slide5_result['slide_id']

    # Title
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Combined Formatting",
        x=60, y=20, width=600, height=50
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 32, 'unit': 'PT'},
                'bold': True
            }
        )

    # Example 1: Large, bold, blue
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Main Heading",
        x=80, y=90, width=560, height=50
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 36, 'unit': 'PT'},
                'bold': True,
                'fontFamily': 'Arial',
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
                    }
                }
            }
        )

    # Example 2: Medium, italic, gray
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Subtitle or supporting text",
        x=80, y=155, width=560, height=35
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 20, 'unit': 'PT'},
                'italic': True,
                'fontFamily': 'Georgia',
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}
                    }
                }
            }
        )

    # Example 3: Code block style
    editor.insert_text_box(
        pres_id, slide5_id,
        text="def example_code():\n    return 'formatted'",
        x=80, y=210, width=560, height=60
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 18, 'unit': 'PT'},
                'fontFamily': 'Courier New',
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.0, 'green': 0.3, 'blue': 0.0}
                    }
                }
            }
        )

    # Example 4: Warning style
    editor.insert_text_box(
        pres_id, slide5_id,
        text="Important: Review these changes carefully",
        x=80, y=290, width=560, height=40
    )
    pres = editor.get_presentation(pres_id)
    elements = pres['slides'][4].get('pageElements', [])
    if elements:
        editor.update_text_style(
            pres_id, elements[-1]['objectId'],
            {
                'fontSize': {'magnitude': 20, 'unit': 'PT'},
                'bold': True,
                'foregroundColor': {
                    'opaqueColor': {
                        'rgbColor': {'red': 0.9, 'green': 0.5, 'blue': 0.0}
                    }
                }
            }
        )

    print("✓ Slide 5 complete")

    print()
    print("="*70)
    print("✓ Text Formatting Showcase created successfully!")
    print()
    print(f"Title: {result['title']}")
    print(f"Slides: 5")
    print(f"URL: {pres_url}")
    print()
    print("Formatting options demonstrated:")
    print("  ✓ Font sizes: 18pt, 24pt, 32pt, 36pt, 44pt")
    print("  ✓ Colors: Brand blue, success green, warning orange, error red, gray")
    print("  ✓ Styles: Bold, italic, underline, combinations")
    print("  ✓ Fonts: Arial, Roboto, Georgia, Courier New")
    print("  ✓ Combined formatting for different use cases")
    print()
    print("Use this presentation as a visual reference for text formatting!")
    print("="*70)


if __name__ == '__main__':
    main()
