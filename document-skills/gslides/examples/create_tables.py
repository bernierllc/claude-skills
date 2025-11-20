#!/usr/bin/env python3
"""
Example: Creating Tables in Google Slides

Demonstrates creating 3 different table types:
- Simple data table (styled header)
- Comparison table (alternating rows)
- Summary table (merged cells, totals)

Usage:
    python examples/create_tables.py
"""

import sys
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def main():
    print("Creating Tables Example")
    print("=" * 60)

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Create presentation
    print("\n1. Creating new presentation...")
    result = editor.create_presentation("Table Formatting Examples")
    pres_id = result['pres_id']
    pres_url = result['pres_url']
    print(f"   Created: {result['title']}")
    print(f"   URL: {pres_url}")

    # Get the first slide (title slide)
    analysis = editor.analyze_presentation(pres_id)
    title_slide_id = analysis.slides[0]['object_id']

    # Add title to first slide
    print("\n2. Adding title...")
    editor.insert_text_box(
        pres_id, title_slide_id,
        "Table Formatting Examples",
        x=50, y=150, width=620, height=100
    )

    # Table 1: Simple Data Table with Styled Header
    print("\n3. Creating Simple Data Table...")
    slide1 = editor.create_slide(pres_id)

    simple_table_data = [
        ['Product', 'Price', 'Units Sold', 'Revenue'],
        ['Widget A', '$29.99', '450', '$13,495'],
        ['Widget B', '$39.99', '320', '$12,797'],
        ['Widget C', '$49.99', '280', '$13,997'],
        ['Widget D', '$19.99', '600', '$11,994']
    ]

    editor.create_table(
        pres_id, slide1['slide_id'],
        simple_table_data,
        position={'x': 50, 'y': 120, 'width': 620, 'height': 200},
        style={
            'header_style': {
                'bg_color': '#0066cc',
                'text_color': '#ffffff',
                'bold': True
            },
            'border_color': '#cccccc',
            'cell_padding': 5
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        "Simple Data Table",
        x=50, y=50, width=620, height=40
    )

    # Table 2: Comparison Table with Zebra Striping
    print("\n4. Creating Comparison Table...")
    slide2 = editor.create_slide(pres_id)

    comparison_table_data = [
        ['Feature', 'Basic Plan', 'Pro Plan', 'Enterprise'],
        ['Users', '1-5', '6-50', 'Unlimited'],
        ['Storage', '10 GB', '100 GB', '1 TB'],
        ['Support', 'Email', 'Email + Chat', '24/7 Phone'],
        ['Price', '$9/mo', '$29/mo', 'Custom'],
        ['API Access', 'No', 'Yes', 'Yes'],
        ['Analytics', 'Basic', 'Advanced', 'Custom']
    ]

    editor.create_table(
        pres_id, slide2['slide_id'],
        comparison_table_data,
        position={'x': 50, 'y': 120, 'width': 620, 'height': 240},
        style={
            'header_style': {
                'bg_color': '#00cc66',
                'text_color': '#ffffff',
                'bold': True
            },
            'zebra_striping': True,
            'border_color': '#cccccc'
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "Comparison Table with Zebra Striping",
        x=50, y=50, width=620, height=40
    )

    # Table 3: Summary Table with Totals
    print("\n5. Creating Summary Table...")
    slide3 = editor.create_slide(pres_id)

    summary_table_data = [
        ['Quarter', 'North', 'South', 'East', 'West', 'Total'],
        ['Q1 2024', '150', '120', '180', '100', '550'],
        ['Q2 2024', '175', '140', '190', '115', '620'],
        ['Q3 2024', '200', '165', '210', '130', '705'],
        ['Q4 2024', '180', '190', '220', '145', '735'],
        ['TOTAL', '705', '615', '800', '490', '2,610']
    ]

    table_result = editor.create_table(
        pres_id, slide3['slide_id'],
        summary_table_data,
        position={'x': 50, 'y': 120, 'width': 620, 'height': 200},
        style={
            'header_style': {
                'bg_color': '#cc6600',
                'text_color': '#ffffff',
                'bold': True
            },
            'border_color': '#cccccc'
        }
    )

    # Style the total row (last row)
    # This would require additional API calls to style specific rows
    # For demonstration, we've included the data with TOTAL row

    # Add slide title
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Summary Table with Totals",
        x=50, y=50, width=620, height=40
    )

    # Add description
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Regional sales summary with quarterly totals",
        x=50, y=340, width=620, height=30
    )

    print("\n" + "=" * 60)
    print("Tables Created Successfully!")
    print(f"\nPresentation URL: {pres_url}")
    print("\nCreated 3 table types:")
    print("  1. Simple Data Table - Product sales with styled header")
    print("  2. Comparison Table - Plan features with zebra striping")
    print("  3. Summary Table - Regional totals with TOTAL row")
    print("\nOpen the URL in your browser to view the tables.")
    print("=" * 60)


if __name__ == '__main__':
    main()
