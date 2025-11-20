# Phase 4 API Reference: Data Visualization

Complete API documentation for charts, tables, and images in Google Slides.

## Table of Contents

- [ChartBuilder API](#chartbuilder-api)
- [TableManager API](#tablemanager-api)
- [ImageManager API](#imagemanager-api)
- [GoogleSlidesEditor Integration](#googleslideseditor-integration)
- [Code Examples](#code-examples)
- [Troubleshooting](#troubleshooting)

## ChartBuilder API

The `ChartBuilder` class handles chart creation and data visualization.

### Initialization

```python
from scripts.chart_builder import ChartBuilder

chart_builder = ChartBuilder(slides_service)
```

### create_chart()

Create a chart on a slide.

```python
def create_chart(
    pres_id: str,
    slide_id: str,
    chart_type: str,
    data: Dict[str, Any],
    position: Dict[str, float],
    style: Optional[Dict[str, Any]] = None
) -> Dict[str, str]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `slide_id` (str): Slide object ID
- `chart_type` (str): One of:
  - `'BAR_CHART'` - Horizontal bars
  - `'LINE_CHART'` - Line graph
  - `'PIE_CHART'` - Pie/donut chart
  - `'SCATTER_CHART'` - Scatter plot
  - `'COLUMN_CHART'` - Vertical columns
- `data` (dict): Chart data structure:
  ```python
  {
      'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
      'series': [
          {'name': 'Sales', 'values': [100, 150, 200, 180]},
          {'name': 'Revenue', 'values': [120, 180, 240, 220]}
      ]
  }
  ```
- `position` (dict): Position and size:
  ```python
  {
      'x': 110,       # X position in points
      'y': 150,       # Y position in points
      'width': 500,   # Width in points
      'height': 300   # Height in points
  }
  ```
- `style` (dict, optional): Style configuration:
  ```python
  {
      'title': 'Chart Title',
      'colors': ['#0066cc', '#00cc66', '#cc6600'],
      'show_legend': True,
      'show_data_labels': False
  }
  ```

**Returns:**
- `dict`: `{'chart_id': 'chart_abc123'}`

**Example:**

```python
data = {
    'categories': ['Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2024'],
    'series': [
        {'name': 'North', 'values': [150, 175, 200, 180]},
        {'name': 'South', 'values': [120, 140, 165, 190]}
    ]
}

position = {
    'x': 110,
    'y': 150,
    'width': 500,
    'height': 300
}

style = {
    'title': 'Regional Sales Performance',
    'colors': ['#0066cc', '#00cc66'],
    'show_legend': True
}

result = chart_builder.create_chart(
    pres_id, slide_id,
    'BAR_CHART',
    data, position, style
)
print(f"Created chart: {result['chart_id']}")
```

### update_chart_data()

Update existing chart with new data.

```python
def update_chart_data(
    pres_id: str,
    chart_id: str,
    new_data: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `chart_id` (str): Chart object ID
- `new_data` (dict): New chart data (same format as create_chart)

**Returns:**
- `dict`: Update response

**Example:**

```python
new_data = {
    'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
    'series': [
        {'name': 'Updated Sales', 'values': [180, 200, 220, 250]}
    ]
}

result = chart_builder.update_chart_data(pres_id, chart_id, new_data)
```

### get_chart_types()

Get list of supported chart types.

```python
def get_chart_types() -> List[str]
```

**Returns:**
- `list`: List of chart type constants

**Example:**

```python
types = chart_builder.get_chart_types()
print(types)
# ['BAR_CHART', 'LINE_CHART', 'PIE_CHART', 'SCATTER_CHART', 'COLUMN_CHART']
```

## TableManager API

The `TableManager` class handles table creation and formatting.

### Initialization

```python
from scripts.table_manager import TableManager

table_manager = TableManager(slides_service)
```

### create_table()

Create a table on a slide.

```python
def create_table(
    pres_id: str,
    slide_id: str,
    data: List[List[str]],
    position: Dict[str, float],
    style: Optional[Dict[str, Any]] = None
) -> Dict[str, str]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `slide_id` (str): Slide object ID
- `data` (list): Table data as list of rows:
  ```python
  [
      ['Header 1', 'Header 2', 'Header 3'],
      ['Row 1 Col 1', 'Row 1 Col 2', 'Row 1 Col 3'],
      ['Row 2 Col 1', 'Row 2 Col 2', 'Row 2 Col 3']
  ]
  ```
- `position` (dict): Position and size:
  ```python
  {
      'x': 50,
      'y': 100,
      'width': 620,
      'height': 200
  }
  ```
- `style` (dict, optional): Style configuration:
  ```python
  {
      'header_style': {
          'bg_color': '#0066cc',
          'text_color': '#ffffff',
          'bold': True
      },
      'zebra_striping': True,
      'border_color': '#cccccc',
      'cell_padding': 5
  }
  ```

**Returns:**
- `dict`: `{'table_id': 'table_abc123'}`

**Example:**

```python
data = [
    ['Product', 'Q1', 'Q2', 'Q3', 'Q4'],
    ['Widget A', '100', '120', '140', '160'],
    ['Widget B', '150', '180', '200', '220'],
    ['Widget C', '120', '140', '160', '180']
]

position = {
    'x': 50,
    'y': 100,
    'width': 620,
    'height': 180
}

style = {
    'header_style': {
        'bg_color': '#0066cc',
        'text_color': '#ffffff',
        'bold': True
    },
    'zebra_striping': True
}

result = table_manager.create_table(pres_id, slide_id, data, position, style)
print(f"Created table: {result['table_id']}")
```

### merge_cells()

Merge table cells.

```python
def merge_cells(
    pres_id: str,
    table_id: str,
    start_row: int,
    start_col: int,
    row_span: int,
    col_span: int
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `table_id` (str): Table object ID
- `start_row` (int): Starting row index (0-based)
- `start_col` (int): Starting column index (0-based)
- `row_span` (int): Number of rows to merge
- `col_span` (int): Number of columns to merge

**Returns:**
- `dict`: Merge response

**Example:**

```python
# Merge header cells (first row, columns 0-1)
table_manager.merge_cells(
    pres_id, table_id,
    start_row=0, start_col=0,
    row_span=1, col_span=2
)
```

### format_cell()

Format a specific cell.

```python
def format_cell(
    pres_id: str,
    table_id: str,
    row: int,
    col: int,
    format_type: str,
    **kwargs
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `table_id` (str): Table object ID
- `row` (int): Row index (0-based)
- `col` (int): Column index (0-based)
- `format_type` (str): Format type ('number', 'currency', 'percentage', 'date')
- `**kwargs`: Additional formatting options

**Returns:**
- `dict`: Format response

**Example:**

```python
# Format cell as currency
table_manager.format_cell(
    pres_id, table_id,
    row=1, col=2,
    format_type='currency',
    font_size=12
)
```

## ImageManager API

The `ImageManager` class handles image insertion and management.

### Initialization

```python
from scripts.image_manager import ImageManager

image_manager = ImageManager(slides_service, drive_service)
```

### insert_image()

Insert an image on a slide.

```python
def insert_image(
    pres_id: str,
    slide_id: str,
    image_source: str,
    position: Dict[str, float],
    **kwargs
) -> Dict[str, str]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `slide_id` (str): Slide object ID
- `image_source` (str): Image source:
  - URL: `'https://example.com/image.png'`
  - Local file: `'/path/to/image.png'`
  - Drive ID: `'drive://FILE_ID'`
- `position` (dict): Position and size:
  ```python
  {
      'x': 100,
      'y': 150,
      'width': 300,
      'height': 200
  }
  ```
- `**kwargs`: Additional options:
  - `maintain_aspect_ratio` (bool): Default True
  - `description` (str): Alt text for accessibility

**Returns:**
- `dict`: `{'image_id': 'image_abc123'}`

**Example:**

```python
position = {
    'x': 100,
    'y': 150,
    'width': 300,
    'height': 200
}

# From URL
result = image_manager.insert_image(
    pres_id, slide_id,
    'https://example.com/logo.png',
    position,
    description='Company logo'
)

# From local file
result = image_manager.insert_image(
    pres_id, slide_id,
    '/Users/you/images/photo.jpg',
    position
)

# From Google Drive
result = image_manager.insert_image(
    pres_id, slide_id,
    'drive://1abc123xyz',
    position
)
```

### replace_image()

Replace an existing image.

```python
def replace_image(
    pres_id: str,
    image_id: str,
    new_image_source: str
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `image_id` (str): Existing image object ID
- `new_image_source` (str): New image source

**Returns:**
- `dict`: Replace response

**Example:**

```python
image_manager.replace_image(
    pres_id,
    'image_abc123',
    'https://example.com/new-logo.png'
)
```

### crop_image()

Crop an image.

```python
def crop_image(
    pres_id: str,
    image_id: str,
    left: float,
    top: float,
    right: float,
    bottom: float
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `image_id` (str): Image object ID
- `left` (float): Left crop ratio (0.0 to 1.0)
- `top` (float): Top crop ratio (0.0 to 1.0)
- `right` (float): Right crop ratio (0.0 to 1.0)
- `bottom` (float): Bottom crop ratio (0.0 to 1.0)

**Returns:**
- `dict`: Crop response

**Example:**

```python
# Crop 10% from each side
image_manager.crop_image(
    pres_id, image_id,
    left=0.1, top=0.1, right=0.1, bottom=0.1
)
```

### set_image_transparency()

Set image transparency.

```python
def set_image_transparency(
    pres_id: str,
    image_id: str,
    transparency: float
) -> Dict[str, Any]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `image_id` (str): Image object ID
- `transparency` (float): Transparency value (0.0 = opaque, 1.0 = fully transparent)

**Returns:**
- `dict`: Transparency response

**Example:**

```python
# Set 50% transparency
image_manager.set_image_transparency(pres_id, image_id, 0.5)
```

### insert_placeholder_image()

Insert a placeholder image (useful for templates).

```python
def insert_placeholder_image(
    pres_id: str,
    slide_id: str,
    position: Dict[str, float],
    placeholder_type: str = 'gradient'
) -> Dict[str, str]
```

**Parameters:**
- `pres_id` (str): Presentation ID
- `slide_id` (str): Slide object ID
- `position` (dict): Position and size
- `placeholder_type` (str): Type ('gradient', 'solid', 'pattern')

**Returns:**
- `dict`: `{'shape_id': 'shape_abc123'}`

**Example:**

```python
position = {'x': 100, 'y': 150, 'width': 200, 'height': 150}
image_manager.insert_placeholder_image(
    pres_id, slide_id, position, 'gradient'
)
```

## GoogleSlidesEditor Integration

The Phase 4 methods are integrated into the main `GoogleSlidesEditor` class.

### Accessing Phase 4 Components

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Access chart builder
editor.chart_builder.create_chart(...)

# Access table manager
editor.table_manager.create_table(...)

# Access image manager
editor.image_manager.insert_image(...)
```

### Convenience Methods

The editor also provides convenience methods:

```python
# Create chart (calls chart_builder.create_chart)
editor.create_chart(pres_id, slide_id, chart_type, data, position, style)

# Create table (calls table_manager.create_table)
editor.create_table(pres_id, slide_id, data, position, style)

# Insert image (calls image_manager.insert_image)
editor.insert_image(pres_id, slide_id, image_source, position, **kwargs)
```

## Code Examples

### Example 1: Complete Slide with Chart and Table

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation("Data Report")
pres_id = result['pres_id']

# Create slide
slide = editor.create_slide(pres_id)
slide_id = slide['slide_id']

# Add title
editor.insert_text_box(
    pres_id, slide_id,
    "Sales Performance Report",
    x=50, y=30, width=620, height=50
)

# Add chart
chart_data = {
    'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
    'series': [
        {'name': 'Sales', 'values': [100, 150, 200, 180]}
    ]
}

editor.create_chart(
    pres_id, slide_id,
    'COLUMN_CHART',
    chart_data,
    position={'x': 50, 'y': 100, 'width': 280, 'height': 220},
    style={'title': 'Quarterly Sales', 'show_data_labels': True}
)

# Add table
table_data = [
    ['Quarter', 'Sales', 'Target', 'Variance'],
    ['Q1', '100', '120', '-20'],
    ['Q2', '150', '140', '+10'],
    ['Q3', '200', '180', '+20'],
    ['Q4', '180', '200', '-20']
]

editor.create_table(
    pres_id, slide_id,
    table_data,
    position={'x': 380, 'y': 100, 'width': 290, 'height': 180},
    style={
        'header_style': {
            'bg_color': '#0066cc',
            'text_color': '#ffffff',
            'bold': True
        }
    }
)

print(f"Created report: {result['pres_url']}")
```

### Example 2: Dashboard with Multiple Charts

```python
from scripts.gslides_editor import GoogleSlidesEditor
import json

editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation("Executive Dashboard")
pres_id = result['pres_id']

# Create dashboard slide
slide = editor.create_slide(pres_id)
slide_id = slide['slide_id']

# Title
editor.insert_text_box(
    pres_id, slide_id,
    "Executive Dashboard - Q4 2024",
    x=50, y=20, width=620, height=40
)

# Chart 1: Revenue trend (top-left)
revenue_data = {
    'categories': ['Oct', 'Nov', 'Dec'],
    'series': [{'name': 'Revenue', 'values': [75000, 78000, 82000]}]
}

editor.create_chart(
    pres_id, slide_id, 'LINE_CHART', revenue_data,
    position={'x': 50, 'y': 80, 'width': 300, 'height': 140},
    style={'title': 'Revenue Trend'}
)

# Chart 2: Market share (top-right)
market_data = {
    'categories': ['Us', 'Comp A', 'Comp B', 'Others'],
    'series': [{'name': 'Share %', 'values': [28, 25, 18, 29]}]
}

editor.create_chart(
    pres_id, slide_id, 'PIE_CHART', market_data,
    position={'x': 370, 'y': 80, 'width': 300, 'height': 140},
    style={'title': 'Market Share', 'show_data_labels': True}
)

# Chart 3: Regional sales (bottom)
regional_data = {
    'categories': ['North', 'South', 'East', 'West'],
    'series': [{'name': 'Q4 Sales', 'values': [180, 190, 220, 145]}]
}

editor.create_chart(
    pres_id, slide_id, 'BAR_CHART', regional_data,
    position={'x': 110, 'y': 240, 'width': 500, 'height': 140},
    style={'title': 'Regional Performance'}
)

print(f"Created dashboard: {result['pres_url']}")
```

### Example 3: Data-Driven Report from JSON

```python
from scripts.gslides_editor import GoogleSlidesEditor
import json
from pathlib import Path

editor = GoogleSlidesEditor()

# Load data from JSON
data_dir = Path('examples/data')
with open(data_dir / 'sales_data.json') as f:
    sales_data = json.load(f)

# Create presentation
result = editor.create_presentation("Automated Sales Report")
pres_id = result['pres_id']

# Create slide
slide = editor.create_slide(pres_id)
slide_id = slide['slide_id']

# Build chart from JSON data
chart_data = {
    'categories': sales_data['quarters'],
    'series': [
        {'name': region, 'values': values}
        for region, values in sales_data['regions'].items()
    ]
}

editor.create_chart(
    pres_id, slide_id, 'BAR_CHART', chart_data,
    position={'x': 110, 'y': 100, 'width': 500, 'height': 280},
    style={
        'title': 'Sales by Region (2024)',
        'colors': ['#0066cc', '#00cc66', '#cc6600', '#cc0066'],
        'show_legend': True
    }
)

print(f"Created automated report: {result['pres_url']}")
```

## Common Patterns

### Pattern 1: Chart with Title Above

```python
# Add title
editor.insert_text_box(
    pres_id, slide_id,
    "Chart Title",
    x=50, y=50, width=620, height=40
)

# Add chart below (y=100 to leave room for title)
editor.create_chart(
    pres_id, slide_id, chart_type, data,
    position={'x': 110, 'y': 100, 'width': 500, 'height': 280}
)
```

### Pattern 2: Side-by-Side Chart and Table

```python
# Chart on left half
editor.create_chart(
    pres_id, slide_id, chart_type, data,
    position={'x': 50, 'y': 100, 'width': 300, 'height': 250}
)

# Table on right half
editor.create_table(
    pres_id, slide_id, table_data,
    position={'x': 370, 'y': 100, 'width': 300, 'height': 250}
)
```

### Pattern 3: Full-Width Table

```python
editor.create_table(
    pres_id, slide_id, data,
    position={'x': 50, 'y': 100, 'width': 620, 'height': 280}
)
```

### Pattern 4: Image with Caption

```python
# Image
editor.insert_image(
    pres_id, slide_id, image_url,
    position={'x': 200, 'y': 100, 'width': 320, 'height': 240}
)

# Caption below
editor.insert_text_box(
    pres_id, slide_id,
    "Figure 1: Company headquarters",
    x=200, y=350, width=320, height=30
)
```

## Troubleshooting

### Chart Not Displaying

**Problem:** Chart appears blank or doesn't render

**Solutions:**
1. Verify data structure matches expected format
2. Check that categories and series values have same length
3. Ensure values are numeric (not strings)

```python
# Correct data format
data = {
    'categories': ['A', 'B', 'C'],
    'series': [
        {'name': 'Series 1', 'values': [10, 20, 30]}  # Numbers, not strings
    ]
}
```

### Table Formatting Issues

**Problem:** Table cells not styled correctly

**Solutions:**
1. Apply styles after table creation completes
2. Use batch operations for large tables
3. Check color format (hex with #)

```python
# Correct hex color format
style = {
    'header_style': {
        'bg_color': '#0066cc',  # Include # prefix
        'text_color': '#ffffff'
    }
}
```

### Image Upload Failures

**Problem:** Local image file won't upload

**Solutions:**
1. Verify file path is absolute, not relative
2. Check file exists and is readable
3. Ensure file is a valid image format
4. Check Drive API is enabled

```python
from pathlib import Path

# Use absolute path
image_path = Path('/Users/you/images/logo.png').resolve()
editor.insert_image(pres_id, slide_id, str(image_path), position)
```

### Position/Size Issues

**Problem:** Elements overlap or appear outside slide

**Solutions:**
1. Use standard positioning guidelines
2. Remember: slide is 720x405 points
3. Leave margins (50-110pt from edges)
4. Check coordinates are positive

```python
# Standard safe positions
SLIDE_WIDTH = 720
SLIDE_HEIGHT = 405
MARGIN = 50

position = {
    'x': MARGIN,
    'y': 100,
    'width': SLIDE_WIDTH - (2 * MARGIN),  # Full width minus margins
    'height': 200
}
```

### Performance with Large Tables

**Problem:** Slow table creation with many cells

**Solutions:**
1. Break large tables into multiple slides
2. Use batch operations (handled automatically)
3. Limit to 10-12 rows per table
4. Consider using charts instead

```python
# For large datasets, create multiple tables
rows_per_table = 10
for i in range(0, len(data), rows_per_table):
    chunk = data[i:i+rows_per_table+1]  # +1 for header
    slide = editor.create_slide(pres_id)
    editor.create_table(pres_id, slide['slide_id'], chunk, position)
```

## Related Documentation

- [Data Visualization Guide](DATA_VISUALIZATION.md) - Best practices and principles
- [Layout Guide](LAYOUT_GUIDE.md) - Positioning and spacing
- [Examples](../examples/) - Working code examples
- [Phase 3 API Reference](PHASE3_API_REFERENCE.md) - Theme and design system
