#!/usr/bin/env python3
"""
Example: Creating a Complete Business Report

Creates a comprehensive 8-slide business report with:
- Title slide with company branding
- Executive summary with bullet points
- Revenue chart (line chart)
- Sales by region (bar chart)
- Market share (pie chart)
- Data table (quarterly results)
- Team section (placeholder images)
- Closing slide (next steps)

Usage:
    python examples/business_report.py
"""

import sys
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor
from scripts.brand_guidelines import BrandGuidelines


def load_json_data(filename):
    """Load JSON data from examples/data directory."""
    data_dir = Path(__file__).parent / 'data'
    filepath = data_dir / filename
    with open(filepath, 'r') as f:
        return json.load(f)


def main():
    print("Creating Business Report")
    print("=" * 60)

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Create presentation
    print("\n1. Creating new presentation...")
    result = editor.create_presentation("Q4 2024 Business Report")
    pres_id = result['pres_id']
    pres_url = result['pres_url']
    print(f"   Created: {result['title']}")
    print(f"   URL: {pres_url}")

    # Load brand guidelines (if available)
    brand_path = Path(__file__).parent.parent / 'brand_templates' / 'corporate_brand.json'
    if brand_path.exists():
        print("\n2. Applying brand guidelines...")
        brand = editor.load_brand_guidelines(str(brand_path))
        editor.apply_brand_theme(pres_id, brand)
        primary_color = brand.colors.primary
        secondary_color = brand.colors.secondary
    else:
        print("\n2. Using default colors...")
        primary_color = '#0066cc'
        secondary_color = '#00cc66'

    # Get slides
    analysis = editor.analyze_presentation(pres_id)

    # ==================================================================
    # Slide 1: Title Slide
    # ==================================================================
    print("\n3. Creating title slide...")
    title_slide_id = analysis.slides[0]['object_id']

    # Company name
    editor.insert_text_box(
        pres_id, title_slide_id,
        "ACME Corporation",
        x=50, y=100, width=620, height=60
    )

    # Report title
    editor.insert_text_box(
        pres_id, title_slide_id,
        "Q4 2024 Business Report",
        x=50, y=170, width=620, height=80
    )

    # Date and presenter
    editor.insert_text_box(
        pres_id, title_slide_id,
        "Presented by: Executive Team\nDate: January 15, 2025",
        x=50, y=280, width=620, height=60
    )

    # ==================================================================
    # Slide 2: Executive Summary
    # ==================================================================
    print("\n4. Creating executive summary...")
    slide2 = editor.create_slide(pres_id)

    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "Executive Summary",
        x=50, y=30, width=620, height=50
    )

    summary_points = """Key Highlights:

• Revenue exceeded target by 15% in Q4 2024
• Strong growth in East and South regions
• Market share increased from 22% to 28%
• Successfully launched 4 new products
• Customer satisfaction rating: 94%
• Net profit margin improved to 18%

Strategic Priorities for 2025:
• Expand into new markets
• Invest in R&D and innovation
• Strengthen customer relationships"""

    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        summary_points,
        x=60, y=90, width=600, height=300
    )

    # ==================================================================
    # Slide 3: Revenue Chart
    # ==================================================================
    print("\n5. Creating revenue chart...")
    slide3 = editor.create_slide(pres_id)
    revenue_data = load_json_data('revenue_trend.json')

    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Revenue Trend Analysis",
        x=50, y=30, width=620, height=50
    )

    line_chart_data = {
        'categories': revenue_data['months'],
        'series': [
            {'name': 'Revenue', 'values': revenue_data['revenue']},
            {'name': 'Target', 'values': revenue_data['target']},
            {'name': 'Expenses', 'values': revenue_data['expenses']}
        ]
    }

    editor.create_chart(
        pres_id, slide3['slide_id'],
        'LINE_CHART',
        line_chart_data,
        position={'x': 110, 'y': 100, 'width': 500, 'height': 280},
        style={
            'title': '2024 Financial Performance',
            'colors': [primary_color, secondary_color, '#cc6600'],
            'show_legend': True
        }
    )

    # ==================================================================
    # Slide 4: Sales by Region
    # ==================================================================
    print("\n6. Creating sales by region chart...")
    slide4 = editor.create_slide(pres_id)
    sales_data = load_json_data('sales_data.json')

    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "Sales Performance by Region",
        x=50, y=30, width=620, height=50
    )

    bar_chart_data = {
        'categories': sales_data['quarters'],
        'series': [
            {'name': region, 'values': values}
            for region, values in sales_data['regions'].items()
        ]
    }

    editor.create_chart(
        pres_id, slide4['slide_id'],
        'BAR_CHART',
        bar_chart_data,
        position={'x': 110, 'y': 100, 'width': 500, 'height': 280},
        style={
            'title': 'Regional Sales Comparison',
            'colors': [primary_color, secondary_color, '#cc6600', '#cc0066'],
            'show_legend': True
        }
    )

    # ==================================================================
    # Slide 5: Market Share
    # ==================================================================
    print("\n7. Creating market share chart...")
    slide5 = editor.create_slide(pres_id)
    market_data = load_json_data('market_share.json')

    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "Market Share Analysis",
        x=50, y=30, width=620, height=50
    )

    pie_chart_data = {
        'categories': market_data['companies'],
        'series': [
            {'name': 'Market Share %', 'values': market_data['market_share']}
        ]
    }

    editor.create_chart(
        pres_id, slide5['slide_id'],
        'PIE_CHART',
        pie_chart_data,
        position={'x': 110, 'y': 100, 'width': 500, 'height': 280},
        style={
            'title': 'Market Position (2024)',
            'colors': [primary_color, '#00cc66', '#cc6600', '#cc0066', '#6600cc'],
            'show_legend': True,
            'show_data_labels': True
        }
    )

    # ==================================================================
    # Slide 6: Data Table - Quarterly Results
    # ==================================================================
    print("\n8. Creating quarterly results table...")
    slide6 = editor.create_slide(pres_id)

    editor.insert_text_box(
        pres_id, slide6['slide_id'],
        "Quarterly Results Summary",
        x=50, y=30, width=620, height=50
    )

    table_data = [
        ['Quarter', 'Revenue', 'Expenses', 'Profit', 'Margin'],
        ['Q1 2024', '$52,000', '$38,000', '$14,000', '27%'],
        ['Q2 2024', '$62,000', '$43,000', '$19,000', '31%'],
        ['Q3 2024', '$72,000', '$48,000', '$24,000', '33%'],
        ['Q4 2024', '$82,000', '$51,000', '$31,000', '38%'],
        ['TOTAL', '$268,000', '$180,000', '$88,000', '33%']
    ]

    editor.create_table(
        pres_id, slide6['slide_id'],
        table_data,
        position={'x': 60, 'y': 100, 'width': 600, 'height': 240},
        style={
            'header_style': {
                'bg_color': primary_color,
                'text_color': '#ffffff',
                'bold': True
            },
            'zebra_striping': True,
            'border_color': '#cccccc'
        }
    )

    # ==================================================================
    # Slide 7: Team Section
    # ==================================================================
    print("\n9. Creating team section...")
    slide7 = editor.create_slide(pres_id)

    editor.insert_text_box(
        pres_id, slide7['slide_id'],
        "Our Leadership Team",
        x=50, y=30, width=620, height=50
    )

    # Create placeholder images for team members
    team_positions = [
        {'x': 80, 'y': 120, 'name': 'CEO'},
        {'x': 260, 'y': 120, 'name': 'CTO'},
        {'x': 440, 'y': 120, 'name': 'CFO'},
        {'x': 80, 'y': 240, 'name': 'COO'},
        {'x': 260, 'y': 240, 'name': 'VP Sales'},
        {'x': 440, 'y': 240, 'name': 'VP Marketing'}
    ]

    for pos in team_positions:
        # Create placeholder image
        editor.image_manager.insert_placeholder_image(
            pres_id, slide7['slide_id'],
            position={'x': pos['x'], 'y': pos['y'], 'width': 120, 'height': 90},
            placeholder_type='gradient'
        )

        # Add name label
        editor.insert_text_box(
            pres_id, slide7['slide_id'],
            pos['name'],
            x=pos['x'], y=pos['y'] + 95, width=120, height=20
        )

    # ==================================================================
    # Slide 8: Closing - Next Steps
    # ==================================================================
    print("\n10. Creating closing slide...")
    slide8 = editor.create_slide(pres_id)

    editor.insert_text_box(
        pres_id, slide8['slide_id'],
        "Next Steps & Action Items",
        x=50, y=30, width=620, height=50
    )

    next_steps = """Q1 2025 Priorities:

1. Product Innovation
   • Launch new product line in February
   • Expand feature set based on customer feedback

2. Market Expansion
   • Enter 3 new geographic markets
   • Establish partnerships in target regions

3. Operational Excellence
   • Implement new CRM system
   • Streamline supply chain processes

4. Team Development
   • Hire 15 new team members
   • Invest in training and development programs"""

    editor.insert_text_box(
        pres_id, slide8['slide_id'],
        next_steps,
        x=60, y=90, width=600, height=280
    )

    # Add contact information
    editor.insert_text_box(
        pres_id, slide8['slide_id'],
        "Questions? Contact: executive@acmecorp.com",
        x=50, y=370, width=620, height=30
    )

    print("\n" + "=" * 60)
    print("Business Report Created Successfully!")
    print(f"\nPresentation URL: {pres_url}")
    print("\nReport includes 8 slides:")
    print("  1. Title Slide - Company branding")
    print("  2. Executive Summary - Key highlights")
    print("  3. Revenue Chart - Financial performance")
    print("  4. Sales Chart - Regional breakdown")
    print("  5. Market Share - Competitive position")
    print("  6. Data Table - Quarterly results")
    print("  7. Team Section - Leadership profiles")
    print("  8. Next Steps - Action items")
    print("\nOpen the URL in your browser to view the complete report.")
    print("=" * 60)


if __name__ == '__main__':
    main()
