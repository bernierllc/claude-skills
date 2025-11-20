#!/usr/bin/env python3
"""
Example: Create a slide with text boxes and shapes.

Demonstrates Phase 2 capabilities:
- Creating new slides
- Inserting text boxes
- Inserting shapes
- Updating text styles
- Using batch updates
- Layout management
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import GoogleSlidesEditor


def main():
    """Create a presentation with formatted content."""

    # Initialize the editor
    editor = GoogleSlidesEditor()

    print("Phase 2 Demo: Creating Slides with Content")
    print("=" * 60)

    # Step 1: Create a new presentation
    print("\n1. Creating new presentation...")
    result = editor.create_presentation("Phase 2 Demo Presentation")
    pres_id = result['pres_id']
    print(f"   ✓ Created: {result['pres_url']}")

    # Step 2: Get the first slide ID (created automatically)
    print("\n2. Getting first slide...")
    pres = editor.get_presentation(pres_id)
    first_slide_id = pres['slides'][0]['objectId']
    print(f"   ✓ First slide ID: {first_slide_id}")

    # Step 3: Add a title text box to the first slide
    print("\n3. Adding title text box...")
    title_result = editor.insert_text_box(
        pres_id=pres_id,
        slide_id=first_slide_id,
        text="Welcome to Phase 2",
        x=50,  # 50 points from left
        y=50,  # 50 points from top
        width=620,  # 620 points wide
        height=80   # 80 points tall
    )
    title_id = title_result['object_id']
    print(f"   ✓ Title text box created: {title_id}")

    # Step 4: Format the title text
    print("\n4. Formatting title text...")
    editor.update_text_style(
        pres_id=pres_id,
        object_id=title_id,
        style_dict={
            'bold': True,
            'fontSize': {'magnitude': 36, 'unit': 'PT'},
            'foregroundColor': {
                'opaqueColor': {
                    'rgbColor': {
                        'red': 0.2,
                        'green': 0.4,
                        'blue': 0.8
                    }
                }
            }
        }
    )
    print("   ✓ Title formatted (36pt, bold, blue)")

    # Step 5: Add a subtitle text box
    print("\n5. Adding subtitle text box...")
    subtitle_result = editor.insert_text_box(
        pres_id=pres_id,
        slide_id=first_slide_id,
        text="Creating slides with the Google Slides API",
        x=50,
        y=150,
        width=620,
        height=50
    )
    subtitle_id = subtitle_result['object_id']
    print(f"   ✓ Subtitle created: {subtitle_id}")

    # Step 6: Format the subtitle
    print("\n6. Formatting subtitle...")
    editor.update_text_style(
        pres_id=pres_id,
        object_id=subtitle_id,
        style_dict={
            'fontSize': {'magnitude': 18, 'unit': 'PT'},
            'italic': True,
            'foregroundColor': {
                'opaqueColor': {
                    'rgbColor': {
                        'red': 0.3,
                        'green': 0.3,
                        'blue': 0.3
                    }
                }
            }
        }
    )
    print("   ✓ Subtitle formatted (18pt, italic, gray)")

    # Step 7: Add a decorative shape
    print("\n7. Adding decorative rectangle...")
    shape_result = editor.insert_shape(
        pres_id=pres_id,
        slide_id=first_slide_id,
        shape_type='RECTANGLE',
        x=50,
        y=220,
        width=620,
        height=5
    )
    print(f"   ✓ Rectangle created: {shape_result['object_id']}")

    # Step 8: Create a second slide with a recommended layout
    print("\n8. Creating second slide with layout...")

    # Get recommended layout for bullets content
    layout_id = editor.layout_manager.recommend_layout('bullets', pres_id)
    if layout_id:
        print(f"   ✓ Recommended layout: {layout_id}")
    else:
        print("   ! No layout found, using blank")
        layout_id = None

    slide2_result = editor.create_slide(
        pres_id=pres_id,
        layout_id=layout_id,
        index=1  # Insert at position 1 (after first slide)
    )
    slide2_id = slide2_result['slide_id']
    print(f"   ✓ Second slide created: {slide2_id}")

    # Step 9: Add content to second slide using batch update
    print("\n9. Adding content to second slide (batch update)...")

    # Build batch requests
    batch_requests = []

    # Add title
    title2_id = f"textbox_title2"
    batch_requests.append(
        editor._create_text_box_request(slide2_id, title2_id, 50, 50, 620, 60)
    )
    batch_requests.append({
        'insertText': {
            'objectId': title2_id,
            'text': 'Key Features',
            'insertionIndex': 0
        }
    })

    # Add bullet point 1
    bullet1_id = f"textbox_bullet1"
    batch_requests.append(
        editor._create_text_box_request(slide2_id, bullet1_id, 80, 150, 580, 40)
    )
    batch_requests.append({
        'insertText': {
            'objectId': bullet1_id,
            'text': '• Create slides programmatically',
            'insertionIndex': 0
        }
    })

    # Add bullet point 2
    bullet2_id = f"textbox_bullet2"
    batch_requests.append(
        editor._create_text_box_request(slide2_id, bullet2_id, 80, 200, 580, 40)
    )
    batch_requests.append({
        'insertText': {
            'objectId': bullet2_id,
            'text': '• Add text boxes and shapes',
            'insertionIndex': 0
        }
    })

    # Add bullet point 3
    bullet3_id = f"textbox_bullet3"
    batch_requests.append(
        editor._create_text_box_request(slide2_id, bullet3_id, 80, 250, 580, 40)
    )
    batch_requests.append({
        'insertText': {
            'objectId': bullet3_id,
            'text': '• Format text with styles',
            'insertionIndex': 0
        }
    })

    # Execute all requests at once
    response = editor.batch_update(pres_id, batch_requests)
    print(f"   ✓ Executed {len(response['replies'])} requests in batch")

    # Step 10: List available layouts for reference
    print("\n10. Available layouts in this presentation:")
    layouts = editor.layout_manager.get_available_layouts(pres_id)
    for layout in layouts[:5]:  # Show first 5
        print(f"    - {layout.layout_name} (ID: {layout.layout_id})")
    if len(layouts) > 5:
        print(f"    ... and {len(layouts) - 5} more")

    # Final summary
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print(f"Presentation URL: {result['pres_url']}")
    print(f"Slides created: 2")
    print(f"Text boxes: 6")
    print(f"Shapes: 1")
    print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
