#!/usr/bin/env python3
"""
Example: Creating Charts in Google Slides

Demonstrates creating 5 different chart types with sample data:
- Bar chart (sales comparison)
- Line chart (revenue trend)
- Pie chart (market share)
- Scatter plot (correlation)
- Column chart (quarterly performance)

Usage:
    python examples/create_charts.py
"""

import sys
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.gslides_editor import GoogleSlidesEditor


def load_json_data(filename):
    """Load JSON data from examples/data directory."""
    data_dir = Path(__file__).parent / 'data'
    filepath = data_dir / filename
    with open(filepath, 'r') as f:
        return json.load(f)


def main():
    print("Creating Charts Example")
    print("=" * 60)

    # Initialize editor
    editor = GoogleSlidesEditor()

    # Create presentation
    print("\n1. Creating new presentation...")
    result = editor.create_presentation("Chart Visualization Examples")
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
        "Chart Visualization Examples",
        x=50, y=150, width=620, height=100
    )

    # Chart 1: Bar Chart - Sales Comparison
    print("\n3. Creating Bar Chart (Sales Comparison)...")
    slide1 = editor.create_slide(pres_id)
    sales_data = load_json_data('sales_data.json')

    bar_chart_data = {
        'categories': sales_data['quarters'],
        'series': [
            {'name': region, 'values': values}
            for region, values in sales_data['regions'].items()
        ]
    }

    editor.create_chart(
        pres_id, slide1['slide_id'],
        'BAR_CHART',
        bar_chart_data,
        position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
        style={
            'title': 'Sales by Region (2024)',
            'colors': ['#0066cc', '#00cc66', '#cc6600', '#cc0066'],
            'show_legend': True,
            'show_data_labels': False
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide1['slide_id'],
        "Bar Chart: Sales by Region",
        x=50, y=50, width=620, height=40
    )

    # Chart 2: Line Chart - Revenue Trend
    print("\n4. Creating Line Chart (Revenue Trend)...")
    slide2 = editor.create_slide(pres_id)
    revenue_data = load_json_data('revenue_trend.json')

    line_chart_data = {
        'categories': revenue_data['months'],
        'series': [
            {'name': 'Revenue', 'values': revenue_data['revenue']},
            {'name': 'Target', 'values': revenue_data['target']},
            {'name': 'Expenses', 'values': revenue_data['expenses']}
        ]
    }

    editor.create_chart(
        pres_id, slide2['slide_id'],
        'LINE_CHART',
        line_chart_data,
        position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
        style={
            'title': 'Revenue Trend (2024)',
            'colors': ['#0066cc', '#00cc66', '#cc6600'],
            'show_legend': True,
            'show_data_labels': False
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide2['slide_id'],
        "Line Chart: Revenue Trend Over Time",
        x=50, y=50, width=620, height=40
    )

    # Chart 3: Pie Chart - Market Share
    print("\n5. Creating Pie Chart (Market Share)...")
    slide3 = editor.create_slide(pres_id)
    market_data = load_json_data('market_share.json')

    pie_chart_data = {
        'categories': market_data['companies'],
        'series': [
            {'name': 'Market Share %', 'values': market_data['market_share']}
        ]
    }

    editor.create_chart(
        pres_id, slide3['slide_id'],
        'PIE_CHART',
        pie_chart_data,
        position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
        style={
            'title': 'Market Share Distribution (2024)',
            'colors': ['#0066cc', '#00cc66', '#cc6600', '#cc0066', '#6600cc'],
            'show_legend': True,
            'show_data_labels': True
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide3['slide_id'],
        "Pie Chart: Market Share Distribution",
        x=50, y=50, width=620, height=40
    )

    # Chart 4: Scatter Plot - Correlation
    print("\n6. Creating Scatter Plot (Correlation)...")
    slide4 = editor.create_slide(pres_id)

    # Generate correlation data
    scatter_data = {
        'categories': [str(i) for i in range(1, 11)],
        'series': [
            {
                'name': 'Marketing Spend vs Sales',
                'values': [10, 15, 13, 18, 20, 22, 25, 28, 26, 30]
            }
        ]
    }

    editor.create_chart(
        pres_id, slide4['slide_id'],
        'SCATTER_CHART',
        scatter_data,
        position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
        style={
            'title': 'Marketing Spend vs Sales Correlation',
            'colors': ['#0066cc'],
            'show_legend': False,
            'show_data_labels': False
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide4['slide_id'],
        "Scatter Plot: Marketing ROI Analysis",
        x=50, y=50, width=620, height=40
    )

    # Chart 5: Column Chart - Quarterly Performance
    print("\n7. Creating Column Chart (Quarterly Performance)...")
    slide5 = editor.create_slide(pres_id)

    column_chart_data = {
        'categories': sales_data['quarters'],
        'series': [
            {'name': 'Total Sales', 'values': sales_data['total']}
        ]
    }

    editor.create_chart(
        pres_id, slide5['slide_id'],
        'COLUMN_CHART',
        column_chart_data,
        position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
        style={
            'title': 'Quarterly Performance (2024)',
            'colors': ['#0066cc'],
            'show_legend': False,
            'show_data_labels': True
        }
    )

    # Add slide title
    editor.insert_text_box(
        pres_id, slide5['slide_id'],
        "Column Chart: Total Quarterly Sales",
        x=50, y=50, width=620, height=40
    )

    print("\n" + "=" * 60)
    print("Charts Created Successfully!")
    print(f"\nPresentation URL: {pres_url}")
    print("\nCreated 5 chart types:")
    print("  1. Bar Chart - Sales by Region")
    print("  2. Line Chart - Revenue Trend")
    print("  3. Pie Chart - Market Share")
    print("  4. Scatter Plot - Marketing ROI")
    print("  5. Column Chart - Quarterly Performance")
    print("\nOpen the URL in your browser to view the charts.")
    print("=" * 60)


if __name__ == '__main__':
    main()
