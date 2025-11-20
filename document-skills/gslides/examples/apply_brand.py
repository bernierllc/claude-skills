#!/usr/bin/env python3
"""
Brand Guidelines Application Example.

Demonstrates how to:
1. Load brand guidelines from JSON
2. Create a presentation following brand guidelines
3. Apply brand theme throughout
4. Validate brand compliance
5. Generate compliance report

This example creates a 3-slide presentation showcasing brand application.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.gslides_editor import GoogleSlidesEditor
from scripts.theme_manager import BrandGuidelines


def main():
    """Create and brand a presentation following corporate guidelines."""

    print("\n" + "="*60)
    print("Brand Guidelines Application Example")
    print("="*60 + "\n")

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Load brand guidelines
    brand_file = os.path.join(
        os.path.dirname(__file__),
        'brand_templates',
        'corporate_brand.json'
    )

    print(f"Loading brand guidelines from: {brand_file}")
    brand = editor.load_brand_guidelines(brand_file)

    print(f"\n Brand: {brand.name}")
    print(f"  Primary Color: {brand.colors.primary}")
    print(f"  Secondary Color: {brand.colors.secondary}")
    print(f"  Headline Font: {brand.typography.headline_family}")
    print(f"  Body Font: {brand.typography.body_family}")
    print(f"  Voice/Tone: {brand.voice_tone}\n")

    # Create presentation
    print("Creating new presentation...")
    result = editor.create_presentation('Brand Guidelines Demo')
    pres_id = result['pres_id']
    pres_url = result['pres_url']

    print(f"\n Created: {pres_url}\n")

    # Get the default slide
    presentation = editor.slides_service.presentations().get(
        presentationId=pres_id
    ).execute()
    slides = presentation.get('slides', [])

    if slides:
        slide1_id = slides[0].get('objectId')

        # Add title to first slide
        print("Creating title slide with brand colors...")
        editor.insert_text_box(
            pres_id,
            slide1_id,
            brand.name,
            x=60,
            y=150,
            width=600,
            height=100
        )

    # Create second slide for content
    print("Creating content slide...")
    slide2 = editor.create_slide(pres_id)
    slide2_id = slide2['slide_id']

    # Add content with brand typography
    editor.insert_text_box(
        pres_id,
        slide2_id,
        "Our Brand Guidelines",
        x=60,
        y=60,
        width=600,
        height=60
    )

    editor.insert_text_box(
        pres_id,
        slide2_id,
        f"Primary Color: {brand.colors.primary}\n"
        f"Secondary Color: {brand.colors.secondary}\n"
        f"Typography: {brand.typography.headline_family}/{brand.typography.body_family}\n"
        f"Spacing: {brand.spacing.slide_margin}pt margins",
        x=60,
        y=160,
        width=600,
        height=200
    )

    # Create third slide for brand voice
    print("Creating closing slide...")
    slide3 = editor.create_slide(pres_id)
    slide3_id = slide3['slide_id']

    editor.insert_text_box(
        pres_id,
        slide3_id,
        "Our Voice & Tone",
        x=60,
        y=60,
        width=600,
        height=60
    )

    editor.insert_text_box(
        pres_id,
        slide3_id,
        brand.voice_tone or "Professional and engaging",
        x=60,
        y=160,
        width=600,
        height=180
    )

    # Apply brand theme to all slides
    print("\nApplying brand theme to presentation...")
    theme_result = editor.apply_brand_theme(pres_id, brand)

    print(f" Applied to {theme_result['slides_updated']} slides")
    print(f" Brand: {theme_result['brand_name']}")

    # Validate brand compliance
    print("\nValidating brand compliance...")
    compliance = editor.validate_brand_compliance(pres_id, brand)

    print(f"\n Compliance Score: {compliance['compliance_score']}%")
    print(f" Total Slides: {compliance['total_slides']}")

    if compliance['issues']:
        print("\n Compliance Issues:")
        for issue in compliance['issues']:
            print(f"   - {issue}")
    else:
        print(" No compliance issues found")

    # Print color palette
    print("\n Brand Color Palette:")
    palette = editor.theme_manager.get_brand_color_palette(brand)
    for color in palette:
        print(f"   {color['name']:12} {color['hex']:8} RGB({color['rgb']['red']:.2f}, "
              f"{color['rgb']['green']:.2f}, {color['rgb']['blue']:.2f})")

    print("\n" + "="*60)
    print("Brand application complete!")
    print("="*60)
    print(f"\n Open your presentation: {pres_url}\n")


if __name__ == '__main__':
    main()
