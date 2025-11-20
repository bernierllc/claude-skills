# Phase 4 Quick Start Guide

Get started with data visualization in Google Slides in 5 minutes.

## Installation

Phase 4 requires no additional dependencies beyond the base Google Slides skill:

```bash
cd /Users/mattbernier/projects/agents-environment-config/.claude/skills/document-skills/gslides
pip install -r requirements.txt
```

## Authentication

If you haven't already set up authentication:

```bash
python examples/test_auth.py
```

Follow the OAuth flow to authenticate with Google.

## Your First Chart

Create a simple bar chart in 3 steps:

### Step 1: Create the Script

```python
#!/usr/bin/env python3
from scripts.gslides_editor import GoogleSlidesEditor

# Initialize
editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation("My First Chart")
pres_id = result['pres_id']

# Create slide
slide = editor.create_slide(pres_id)

# Add chart
data = {
    'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
    'series': [
        {'name': 'Sales', 'values': [100, 150, 200, 180]}
    ]
}

editor.create_chart(
    pres_id, slide['slide_id'],
    'BAR_CHART',
    data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
    style={'title': 'Quarterly Sales', 'show_legend': True}
)

print(f"Created: {result['pres_url']}")
```

### Step 2: Run It

```bash
python your_script.py
```

### Step 3: View It

Open the URL printed in your browser to see your chart!

## Try the Examples

### Chart Gallery

See all 5 chart types:

```bash
python examples/create_charts.py
```

Creates:
- Bar chart (sales comparison)
- Line chart (revenue trend)
- Pie chart (market share)
- Scatter plot (correlation)
- Column chart (quarterly performance)

### Table Examples

See professional table formatting:

```bash
python examples/create_tables.py
```

Creates:
- Simple data table with styled header
- Comparison table with zebra striping
- Summary table with totals

### Business Report

See a complete 8-slide business report:

```bash
python examples/business_report.py
```

Includes:
- Title slide
- Executive summary
- Multiple charts
- Data table
- Team section with images
- Next steps

## Common Use Cases

### Use Case 1: Sales Report

```python
import json
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Load your data
with open('my_sales_data.json') as f:
    data = json.load(f)

# Create presentation
result = editor.create_presentation("Sales Report")
pres_id = result['pres_id']
slide = editor.create_slide(pres_id)

# Add chart
chart_data = {
    'categories': data['months'],
    'series': [{'name': 'Sales', 'values': data['sales']}]
}

editor.create_chart(
    pres_id, slide['slide_id'],
    'LINE_CHART', chart_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300}
)

print(f"Report: {result['pres_url']}")
```

### Use Case 2: Data Table

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Your data
table_data = [
    ['Product', 'Q1', 'Q2', 'Q3', 'Q4'],
    ['Widget A', '100', '120', '140', '160'],
    ['Widget B', '150', '180', '200', '220']
]

# Create presentation
result = editor.create_presentation("Product Data")
pres_id = result['pres_id']
slide = editor.create_slide(pres_id)

# Add table
editor.create_table(
    pres_id, slide['slide_id'],
    table_data,
    position={'x': 50, 'y': 100, 'width': 620, 'height': 150},
    style={
        'header_style': {
            'bg_color': '#0066cc',
            'text_color': '#ffffff',
            'bold': True
        }
    }
)

print(f"Table: {result['pres_url']}")
```

### Use Case 3: Dashboard

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

result = editor.create_presentation("Dashboard")
pres_id = result['pres_id']
slide = editor.create_slide(pres_id)

# Revenue chart (top-left)
revenue_data = {
    'categories': ['Jan', 'Feb', 'Mar'],
    'series': [{'name': 'Revenue', 'values': [50, 60, 70]}]
}
editor.create_chart(
    pres_id, slide['slide_id'], 'LINE_CHART', revenue_data,
    position={'x': 50, 'y': 80, 'width': 300, 'height': 140}
)

# Market share (top-right)
market_data = {
    'categories': ['Us', 'Them', 'Others'],
    'series': [{'name': 'Share', 'values': [40, 35, 25]}]
}
editor.create_chart(
    pres_id, slide['slide_id'], 'PIE_CHART', market_data,
    position={'x': 370, 'y': 80, 'width': 300, 'height': 140}
)

print(f"Dashboard: {result['pres_url']}")
```

## Chart Types Reference

### Bar Chart
**When to use:** Comparing categories
```python
editor.create_chart(pres_id, slide_id, 'BAR_CHART', data, position)
```

### Line Chart
**When to use:** Trends over time
```python
editor.create_chart(pres_id, slide_id, 'LINE_CHART', data, position)
```

### Pie Chart
**When to use:** Parts of a whole (percentages)
```python
editor.create_chart(pres_id, slide_id, 'PIE_CHART', data, position)
```

### Scatter Plot
**When to use:** Correlations and distributions
```python
editor.create_chart(pres_id, slide_id, 'SCATTER_CHART', data, position)
```

### Column Chart
**When to use:** Vertical bar comparisons
```python
editor.create_chart(pres_id, slide_id, 'COLUMN_CHART', data, position)
```

## Standard Positions

### Centered Chart
```python
position = {'x': 110, 'y': 150, 'width': 500, 'height': 300}
```

### Full-Width Table
```python
position = {'x': 50, 'y': 100, 'width': 620, 'height': 200}
```

### Side-by-Side (Chart + Table)
```python
# Left side
chart_pos = {'x': 50, 'y': 100, 'width': 300, 'height': 250}

# Right side
table_pos = {'x': 370, 'y': 100, 'width': 300, 'height': 250}
```

## Styling Tips

### Use Brand Colors
```python
style = {
    'colors': ['#0066cc', '#00cc66', '#cc6600'],
    'title': 'My Chart',
    'show_legend': True
}
```

### Professional Table
```python
style = {
    'header_style': {
        'bg_color': '#0066cc',
        'text_color': '#ffffff',
        'bold': True
    },
    'zebra_striping': True
}
```

### Chart with Labels
```python
style = {
    'title': 'Sales Performance',
    'show_data_labels': True,
    'show_legend': True
}
```

## Data Format

### Chart Data
```python
{
    'categories': ['Label 1', 'Label 2', 'Label 3'],
    'series': [
        {'name': 'Series 1', 'values': [10, 20, 30]},
        {'name': 'Series 2', 'values': [15, 25, 35]}
    ]
}
```

### Table Data
```python
[
    ['Header 1', 'Header 2', 'Header 3'],
    ['Row 1 Data 1', 'Row 1 Data 2', 'Row 1 Data 3'],
    ['Row 2 Data 1', 'Row 2 Data 2', 'Row 2 Data 3']
]
```

## Working with JSON Data

### Load from File
```python
import json
from pathlib import Path

data_file = Path('examples/data/sales_data.json')
with open(data_file) as f:
    sales_data = json.load(f)

# Use in chart
chart_data = {
    'categories': sales_data['quarters'],
    'series': [
        {'name': region, 'values': values}
        for region, values in sales_data['regions'].items()
    ]
}
```

### Sample JSON Files
- `examples/data/sales_data.json` - Regional sales by quarter
- `examples/data/revenue_trend.json` - Monthly revenue data
- `examples/data/market_share.json` - Market share analysis

## Next Steps

### Learn More
- Read [DATA_VISUALIZATION.md](docs/DATA_VISUALIZATION.md) for best practices
- Review [PHASE4_API_REFERENCE.md](docs/PHASE4_API_REFERENCE.md) for complete API
- See [PHASE4_SUMMARY.md](PHASE4_SUMMARY.md) for implementation details

### Advanced Features
- Merge table cells
- Apply brand guidelines
- Create custom color schemes
- Build multi-slide reports
- Automate from databases

### Explore Examples
All examples are in `/examples`:
- `create_charts.py` - Chart gallery
- `create_tables.py` - Table formatting
- `business_report.py` - Complete report

## Troubleshooting

### Import Error
```bash
# Make sure you're in the right directory
cd /Users/mattbernier/projects/agents-environment-config/.claude/skills/document-skills/gslides

# Run with proper path
python examples/your_script.py
```

### Authentication Error
```bash
# Re-authenticate
rm auth/token.json
python examples/test_auth.py
```

### Chart Not Showing
- Check data format matches examples
- Verify categories and values have same length
- Ensure values are numbers, not strings

## Support

Need help?
- Check documentation in `/docs`
- Review examples in `/examples`
- See API reference for method details

## Quick Reference Card

```python
# Import
from scripts.gslides_editor import GoogleSlidesEditor
editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation("Title")
pres_id = result['pres_id']

# Create slide
slide = editor.create_slide(pres_id)
slide_id = slide['slide_id']

# Add chart
data = {'categories': [...], 'series': [...]}
editor.create_chart(pres_id, slide_id, 'BAR_CHART', data, position)

# Add table
table_data = [[...], [...]]
editor.create_table(pres_id, slide_id, table_data, position)

# Add image
editor.insert_image(pres_id, slide_id, 'url', position)

# Get URL
print(result['pres_url'])
```

---

**Ready to create data-driven presentations!**

Run `python examples/business_report.py` to see what's possible.
