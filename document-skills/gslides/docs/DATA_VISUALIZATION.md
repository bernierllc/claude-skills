# Data Visualization Guide

Comprehensive guide to creating effective charts, tables, and visual data representations in Google Slides.

## Table of Contents

- [Chart Type Selection](#chart-type-selection)
- [Data Storytelling Principles](#data-storytelling-principles)
- [Chart Best Practices](#chart-best-practices)
- [Table Formatting](#table-formatting)
- [Image Placement](#image-placement)
- [Analytics Reporter Principles](#analytics-reporter-principles)
- [Examples](#examples)

## Chart Type Selection

### When to Use Each Chart Type

#### Bar Chart
**Best for:** Comparing values across categories

**Use when:**
- Comparing different items or categories
- Showing rankings or relative sizes
- Data has distinct categories

**Example use cases:**
- Sales by product
- Performance by department
- Regional comparisons

```python
bar_data = {
    'categories': ['Product A', 'Product B', 'Product C'],
    'series': [
        {'name': 'Q1', 'values': [100, 150, 120]},
        {'name': 'Q2', 'values': [120, 180, 140]}
    ]
}

editor.create_chart(
    pres_id, slide_id, 'BAR_CHART', bar_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300}
)
```

#### Line Chart
**Best for:** Showing trends over time

**Use when:**
- Displaying time-series data
- Showing growth or decline trends
- Comparing multiple trends

**Example use cases:**
- Revenue over months
- Stock prices
- User growth metrics

```python
line_data = {
    'categories': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    'series': [
        {'name': 'Revenue', 'values': [45000, 48000, 52000, 55000, 58000, 62000]},
        {'name': 'Target', 'values': [50000, 50000, 50000, 55000, 55000, 55000]}
    ]
}

editor.create_chart(
    pres_id, slide_id, 'LINE_CHART', line_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
    style={'title': 'Revenue vs Target'}
)
```

#### Pie Chart
**Best for:** Showing parts of a whole

**Use when:**
- Displaying proportions or percentages
- Data adds up to 100%
- You have 5-7 categories maximum

**Example use cases:**
- Market share distribution
- Budget allocation
- Survey results

```python
pie_data = {
    'categories': ['Our Company', 'Competitor A', 'Competitor B', 'Others'],
    'series': [
        {'name': 'Market Share', 'values': [28, 25, 18, 29]}
    ]
}

editor.create_chart(
    pres_id, slide_id, 'PIE_CHART', pie_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
    style={'show_data_labels': True}
)
```

#### Scatter Plot
**Best for:** Showing correlations and distributions

**Use when:**
- Examining relationships between variables
- Identifying patterns or outliers
- Showing distribution of data points

**Example use cases:**
- Marketing spend vs sales
- Age vs income correlation
- Performance metrics comparison

```python
scatter_data = {
    'categories': [str(i) for i in range(1, 11)],
    'series': [
        {'name': 'Data Points', 'values': [10, 15, 13, 18, 20, 22, 25, 28, 26, 30]}
    ]
}

editor.create_chart(
    pres_id, slide_id, 'SCATTER_CHART', scatter_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300}
)
```

#### Column Chart
**Best for:** Comparing values vertically

**Use when:**
- Similar to bar charts but vertical orientation
- Time-series with fewer data points
- Emphasizing magnitude differences

**Example use cases:**
- Quarterly sales
- Monthly performance
- Year-over-year comparison

```python
column_data = {
    'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
    'series': [
        {'name': 'Sales', 'values': [550, 620, 705, 735]}
    ]
}

editor.create_chart(
    pres_id, slide_id, 'COLUMN_CHART', column_data,
    position={'x': 110, 'y': 150, 'width': 500, 'height': 300},
    style={'show_data_labels': True}
)
```

## Data Storytelling Principles

### 1. Start with the Message
Before creating any visualization, ask:
- What story am I trying to tell?
- What decision should this data support?
- What's the key takeaway?

### 2. Choose the Right Chart
- Match the chart type to your data and message
- Don't force data into inappropriate chart types
- Consider your audience's familiarity with chart types

### 3. Reduce Cognitive Load
- Limit the number of series in one chart (3-5 maximum)
- Use consistent colors across related charts
- Remove unnecessary gridlines and decorations
- Highlight the most important data

### 4. Provide Context
- Always include a descriptive title
- Add units and scales
- Include trend lines or targets when relevant
- Annotate significant data points

### 5. Tell a Progressive Story
- Order slides to build understanding
- Start with overview, then drill into details
- Use consistent formatting across slides
- Guide the audience through insights

## Chart Best Practices

### Color Usage

#### Brand Colors
Use your brand's primary and secondary colors consistently:

```python
# Load brand guidelines
brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')

# Use brand colors in charts
style = {
    'colors': [brand.colors.primary, brand.colors.secondary, brand.colors.accent],
    'title': 'Branded Chart'
}

editor.create_chart(pres_id, slide_id, 'BAR_CHART', data, position, style)
```

#### Color Principles
- Use high contrast for important distinctions
- Avoid red/green combinations (colorblind accessibility)
- Limit to 5-6 distinct colors
- Use shades of one color for related data
- Reserve bright colors for emphasis

### Data Labels

**Use data labels when:**
- Exact values are important
- Chart has few data points (< 10)
- Comparing specific numbers

**Avoid data labels when:**
- Chart is crowded
- Trends are more important than exact values
- Multiple overlapping series

```python
style = {
    'show_data_labels': True,  # Show exact values
    'show_legend': True         # Show series names
}
```

### Titles and Legends

**Effective titles:**
- Descriptive and specific
- Include time period
- Highlight the insight

```python
style = {
    'title': 'Revenue Growth Exceeded Target by 15% in Q4 2024'
}
```

**Legend placement:**
- Right side for most charts
- Bottom for very wide charts
- Hide if only one series and title explains it

### Chart Positioning

Standard positioning guidelines:

```python
# Centered chart on slide
position = {
    'x': 110,      # Centered horizontally (720px slide width)
    'y': 150,      # Below title area
    'width': 500,  # Standard chart width
    'height': 300  # Standard chart height
}

# Leave margins:
# - Top: 60pt minimum for title
# - Left/Right: 110pt from edges
# - Bottom: 60pt for footnotes
```

## Table Formatting

### Header Row Styling

Always style header rows to distinguish them:

```python
style = {
    'header_style': {
        'bg_color': '#0066cc',      # Brand primary color
        'text_color': '#ffffff',     # White text
        'bold': True                 # Bold font
    }
}

editor.create_table(pres_id, slide_id, data, position, style)
```

### Zebra Striping

Improves readability for tables with many rows:

```python
style = {
    'header_style': {
        'bg_color': '#0066cc',
        'text_color': '#ffffff',
        'bold': True
    },
    'zebra_striping': True  # Alternating row colors
}
```

### Number Formatting

Format numbers consistently:

```python
table_data = [
    ['Product', 'Revenue', 'Growth'],
    ['Widget A', '$52,000', '+15%'],     # Currency with commas
    ['Widget B', '$48,000', '+12%'],     # Consistent decimal places
    ['Widget C', '$61,000', '+18%']      # Percentage with sign
]
```

### Cell Merging

For headers and totals:

```python
# Create table first
result = editor.create_table(pres_id, slide_id, data, position)

# Then merge cells
editor.table_manager.merge_cells(
    pres_id, result['table_id'],
    start_row=0, start_col=0,
    row_span=1, col_span=2  # Merge 2 columns in header
)
```

### Table Best Practices

1. **Keep it simple**
   - Limit to 7-8 columns maximum
   - Limit to 10-12 rows on one slide
   - Break large tables into multiple slides

2. **Align content**
   - Left-align text
   - Right-align numbers
   - Center-align headers

3. **Highlight totals**
   - Use bold or color for total rows
   - Consider a separator line

4. **Use consistent formatting**
   - Same number of decimal places
   - Consistent units (K, M, B)
   - Consistent date formats

## Image Placement

### Image Sources

Support for multiple image sources:

```python
# URL
editor.insert_image(
    pres_id, slide_id,
    'https://example.com/logo.png',
    position={'x': 100, 'y': 150, 'width': 200, 'height': 150}
)

# Local file (uploads to Drive)
editor.insert_image(
    pres_id, slide_id,
    '/path/to/image.png',
    position={'x': 100, 'y': 150, 'width': 200, 'height': 150}
)

# Drive file
editor.insert_image(
    pres_id, slide_id,
    'drive://FILE_ID_HERE',
    position={'x': 100, 'y': 150, 'width': 200, 'height': 150}
)
```

### Image Positioning Guidelines

1. **Logo placement**
   - Top-left corner: 20-30pt margin
   - Top-right corner: aligned with right edge
   - Size: 80-120pt wide maximum

2. **Hero images**
   - Full-width or near full-width
   - Position: y=80-100
   - Leave space for headline

3. **Supporting images**
   - 1/3 to 1/2 slide width
   - Align with text or charts
   - Maintain aspect ratio

### Accessibility

Always add alt text for accessibility:

```python
editor.insert_image(
    pres_id, slide_id,
    image_url,
    position=position,
    description='Company logo featuring blue and green design'
)
```

## Analytics Reporter Principles

When creating data-driven presentations, follow these principles:

### 1. Executive Summary First
Start with high-level insights, then provide details:
- Slide 1: Key metrics and trends
- Slide 2-4: Supporting data and charts
- Slide 5: Detailed breakdowns

### 2. Context Before Data
Always provide context:
- Time periods
- Comparison baselines
- Industry benchmarks
- Historical trends

### 3. Insights Over Data
Highlight the "so what":
- What changed?
- Why did it change?
- What should we do about it?

### 4. Visual Hierarchy
Guide attention with:
- Size (larger = more important)
- Color (highlighted = noteworthy)
- Position (top/left = priority)
- Whitespace (grouped = related)

### 5. Progressive Disclosure
Build understanding incrementally:
- Overview → Details → Recommendations
- Trends → Drivers → Actions
- Problem → Analysis → Solution

## Examples

### Complete Business Report

See `/Users/mattbernier/projects/agents-environment-config/.claude/skills/document-skills/gslides/examples/business_report.py` for a comprehensive example including:
- Title slide with branding
- Executive summary
- Multiple chart types
- Data tables
- Team section with images
- Next steps

### Chart Gallery

See `/Users/mattbernier/projects/agents-environment-config/.claude/skills/document-skills/gslides/examples/create_charts.py` for examples of all chart types:
- Bar chart
- Line chart
- Pie chart
- Scatter plot
- Column chart

### Table Examples

See `/Users/mattbernier/projects/agents-environment-config/.claude/skills/document-skills/gslides/examples/create_tables.py` for table formatting examples:
- Simple data table
- Comparison table with zebra striping
- Summary table with totals

## Quick Reference

### Standard Chart Position
```python
position = {'x': 110, 'y': 150, 'width': 500, 'height': 300}
```

### Standard Table Position
```python
position = {'x': 50, 'y': 100, 'width': 620, 'height': 200}
```

### Chart with Title Position
```python
# Title
editor.insert_text_box(pres_id, slide_id, title, x=50, y=50, width=620, height=40)

# Chart below title
editor.create_chart(pres_id, slide_id, chart_type, data,
                   position={'x': 110, 'y': 100, 'width': 500, 'height': 280})
```

### Color Palette
```python
colors = {
    'primary': '#0066cc',    # Blue
    'secondary': '#00cc66',  # Green
    'accent': '#cc6600',     # Orange
    'warning': '#cc0066',    # Pink
    'info': '#6600cc'        # Purple
}
```

## Related Documentation

- [Phase 4 API Reference](PHASE4_API_REFERENCE.md) - Complete API documentation
- [Layout Guide](LAYOUT_GUIDE.md) - Positioning and spacing
- [Brand Guidelines](BRAND_GUIDELINES.md) - Brand compliance
- [Examples Directory](../examples/) - Working code examples
