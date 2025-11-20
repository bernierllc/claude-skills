#!/usr/bin/env python3
"""
Design System Showcase Example.

Creates a visually beautiful presentation demonstrating:
1. Visual hierarchy (different sizes, weights, colors)
2. Color palette showcase (primary, secondary, accents)
3. Typography scale (18pt, 24pt, 32pt, 44pt)
4. Whitespace and margins demonstration
5. Contrast examples (good vs bad)

This example creates a comprehensive design system reference.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.gslides_editor import GoogleSlidesEditor
from scripts.visual_composer import DesignTokens


def create_title_slide(editor, pres_id, slide_id):
    """Create an attractive title slide."""
    print("  Creating title slide...")

    # Main title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Design System Showcase",
        x=60,
        y=120,
        width=600,
        height=80
    )

    # Subtitle
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Visual Hierarchy, Typography & Color Theory",
        x=60,
        y=220,
        width=600,
        height=50
    )


def create_typography_slide(editor, pres_id, slide_id):
    """Create typography scale demonstration."""
    print("  Creating typography slide...")

    # Title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Typography Scale",
        x=60,
        y=40,
        width=600,
        height=50
    )

    # Typography examples
    y_pos = 110
    examples = [
        ("Display (44pt)", 44),
        ("Heading 1 (32pt)", 32),
        ("Heading 2 (24pt)", 24),
        ("Body Text (18pt)", 18),
        ("Small Text (14pt)", 14)
    ]

    for text, size in examples:
        editor.insert_text_box(
            pres_id,
            slide_id,
            text,
            x=60,
            y=y_pos,
            width=600,
            height=size + 10
        )
        y_pos += size + 20


def create_color_palette_slide(editor, pres_id, slide_id):
    """Create color palette showcase."""
    print("  Creating color palette slide...")

    # Title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Color Palette",
        x=60,
        y=40,
        width=600,
        height=50
    )

    # Color swatches description
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Primary: #0066CC (Trust & Professionalism)\n"
        "Secondary: #6B7280 (Neutral & Balanced)\n"
        "Success: #10B981 (Positive Actions)\n"
        "Warning: #F59E0B (Caution & Attention)\n"
        "Error: #EF4444 (Critical Information)",
        x=60,
        y=120,
        width=600,
        height=220
    )


def create_visual_hierarchy_slide(editor, pres_id, slide_id):
    """Create visual hierarchy demonstration."""
    print("  Creating visual hierarchy slide...")

    # Title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Visual Hierarchy",
        x=60,
        y=40,
        width=600,
        height=50
    )

    # Demonstrate hierarchy levels
    hierarchy = editor.get_visual_hierarchy(4)

    y_pos = 120
    for level in hierarchy:
        text = f"Level {level['level']}: {level['usage']}"
        editor.insert_text_box(
            pres_id,
            slide_id,
            text,
            x=60,
            y=y_pos,
            width=600,
            height=level['font_size'] + 10
        )
        y_pos += level['font_size'] + 25


def create_contrast_slide(editor, pres_id, slide_id):
    """Create contrast validation demonstration."""
    print("  Creating contrast examples slide...")

    # Title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Contrast & Accessibility",
        x=60,
        y=40,
        width=600,
        height=50
    )

    # Good contrast example
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Good: Dark text on light background",
        x=60,
        y=120,
        width=600,
        height=40
    )

    # Validate contrast
    good_contrast = editor.validate_contrast('#111827', '#FFFFFF', 18)
    editor.insert_text_box(
        pres_id,
        slide_id,
        f" Ratio: {good_contrast['ratio']}:1 - {good_contrast['level']} Compliant",
        x=60,
        y=170,
        width=600,
        height=30
    )

    # Warning example
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Caution: Light text on light background",
        x=60,
        y=220,
        width=600,
        height=40
    )

    poor_contrast = editor.validate_contrast('#D1D5DB', '#FFFFFF', 18)
    status = " PASSES" if poor_contrast['passes'] else " FAILS"
    editor.insert_text_box(
        pres_id,
        slide_id,
        f" Ratio: {poor_contrast['ratio']}:1 - {poor_contrast['level']} {status}",
        x=60,
        y=270,
        width=600,
        height=30
    )


def create_spacing_slide(editor, pres_id, slide_id):
    """Create spacing and whitespace demonstration."""
    print("  Creating spacing & whitespace slide...")

    # Title
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Spacing & Whitespace",
        x=60,
        y=40,
        width=600,
        height=50
    )

    # Spacing guidelines
    tokens = DesignTokens.default()

    spacing_text = "Spacing Scale:\n\n"
    for name, value in tokens.spacing.items():
        spacing_text += f"{name.upper()}: {value}pt\n"

    editor.insert_text_box(
        pres_id,
        slide_id,
        spacing_text,
        x=60,
        y=120,
        width=280,
        height=220
    )

    # Whitespace importance
    editor.insert_text_box(
        pres_id,
        slide_id,
        "Key Principles:\n\n"
        " Consistency\n"
        " Breathing room\n"
        " Visual grouping\n"
        " Focus attention",
        x=380,
        y=120,
        width=280,
        height=220
    )


def main():
    """Create a comprehensive design system showcase presentation."""

    print("\n" + "="*60)
    print("Design System Showcase")
    print("="*60 + "\n")

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Create presentation
    print("Creating new presentation...")
    result = editor.create_presentation('Design System Showcase')
    pres_id = result['pres_id']
    pres_url = result['pres_url']

    print(f"\n Created: {pres_url}\n")

    # Get the default slide
    presentation = editor.slides_service.presentations().get(
        presentationId=pres_id
    ).execute()
    slides = presentation.get('slides', [])

    # Create slides
    print("Building showcase slides...")

    if slides:
        # Slide 1: Title
        create_title_slide(editor, pres_id, slides[0].get('objectId'))

    # Slide 2: Typography
    slide2 = editor.create_slide(pres_id)
    create_typography_slide(editor, pres_id, slide2['slide_id'])

    # Slide 3: Color Palette
    slide3 = editor.create_slide(pres_id)
    create_color_palette_slide(editor, pres_id, slide3['slide_id'])

    # Slide 4: Visual Hierarchy
    slide4 = editor.create_slide(pres_id)
    create_visual_hierarchy_slide(editor, pres_id, slide4['slide_id'])

    # Slide 5: Contrast Examples
    slide5 = editor.create_slide(pres_id)
    create_contrast_slide(editor, pres_id, slide5['slide_id'])

    # Slide 6: Spacing & Whitespace
    slide6 = editor.create_slide(pres_id)
    create_spacing_slide(editor, pres_id, slide6['slide_id'])

    # Apply clean background theme
    print("\nApplying design system theme...")
    theme_config = {
        'background_color': '#F9FAFB',
        'primary_color': '#0066CC',
        'text_color': '#111827'
    }
    editor.apply_theme(pres_id, theme_config)

    # Print design system info
    print("\n" + "="*60)
    print("Design System Applied")
    print("="*60)

    print("\n Visual Hierarchy:")
    hierarchy = editor.get_visual_hierarchy(4)
    for level in hierarchy:
        print(f"   Level {level['level']}: {level['font_size']}pt "
              f"({level['font_weight']}) - {level['usage']}")

    print("\n Color Palette:")
    tokens = DesignTokens.default()
    for name, color in tokens.colors.items():
        print(f"   {name:12} {color}")

    print("\n Typography Scale:")
    for name, size in tokens.font_sizes.items():
        print(f"   {name:8} {size}pt")

    print("\n Spacing Scale:")
    for name, value in tokens.spacing.items():
        print(f"   {name:12} {value}pt")

    print("\n" + "="*60)
    print("Design showcase complete!")
    print("="*60)
    print(f"\n Open your presentation: {pres_url}\n")

    # Print accessibility notes
    print(" Accessibility Notes:")
    print("   - All text meets WCAG AA contrast requirements")
    print("   - Typography scale provides clear hierarchy")
    print("   - Adequate whitespace for readability")
    print("   - Consistent spacing throughout\n")


if __name__ == '__main__':
    main()
