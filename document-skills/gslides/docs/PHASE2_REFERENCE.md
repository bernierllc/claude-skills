# Phase 2 API Reference

Quick reference for Google Slides creation and editing capabilities.

## Table of Contents

- [Coordinate System](#coordinate-system)
- [Slide Operations](#slide-operations)
- [Element Operations](#element-operations)
- [Text Styling](#text-styling)
- [Layout Management](#layout-management)
- [Batch Operations](#batch-operations)

---

## Coordinate System

Google Slides uses **points** as the unit of measurement:
- **1 inch = 72 points**
- **Default slide size**: 720 x 405 points (10" x 5.625")
- **Origin (0, 0)**: Top-left corner of the slide
- **X-axis**: Increases from left to right
- **Y-axis**: Increases from top to bottom

### Common Measurements

```python
# Coordinate constants
POINTS_PER_INCH = 72
DEFAULT_SLIDE_WIDTH = 720   # 10 inches
DEFAULT_SLIDE_HEIGHT = 405  # 5.625 inches

# Common positions (in points)
TOP_LEFT = (0, 0)
CENTER = (360, 202.5)
BOTTOM_RIGHT = (720, 405)

# Margins (suggested)
MARGIN = 50  # 0.69 inches from edge
```

---

## Slide Operations

### Create Slide

```python
result = editor.create_slide(
    pres_id='1abc...',
    layout_id='layout123',  # Optional
    index=1                 # Optional, 0-based index
)

slide_id = result['slide_id']
```

**Parameters:**
- `pres_id`: Presentation ID (required)
- `layout_id`: Layout to apply (optional, uses blank if None)
- `index`: Position to insert slide (optional, appends if None)

**Returns:** `{'slide_id': str, 'index': int}`

---

### Delete Slide

```python
editor.delete_slide(
    pres_id='1abc...',
    slide_id='slide123'
)
```

**Note:** Cannot delete the last remaining slide in a presentation.

---

### Duplicate Slide

```python
result = editor.duplicate_slide(
    pres_id='1abc...',
    slide_id='slide123'
)

new_slide_id = result['new_slide_id']
```

The duplicated slide is inserted immediately after the original.

---

### Get Slide Details

```python
slide = editor.get_slide(
    pres_id='1abc...',
    slide_id='slide123'
)

print(f"Elements: {len(slide.get('pageElements', []))}")
```

---

## Element Operations

### Insert Text Box

```python
result = editor.insert_text_box(
    pres_id='1abc...',
    slide_id='slide123',
    text='Hello World',
    x=50,      # Points from left
    y=100,     # Points from top
    width=300, # Width in points
    height=80  # Height in points
)

object_id = result['object_id']
```

**Common Text Box Sizes:**
- **Title**: width=620, height=80
- **Body**: width=620, height=300
- **Caption**: width=400, height=40

---

### Insert Shape

```python
result = editor.insert_shape(
    pres_id='1abc...',
    slide_id='slide123',
    shape_type='RECTANGLE',
    x=100,
    y=150,
    width=200,
    height=100
)

object_id = result['object_id']
```

**Common Shape Types:**
- `TEXT_BOX` - Text box
- `RECTANGLE` - Rectangle
- `ROUND_RECTANGLE` - Rounded rectangle
- `ELLIPSE` - Circle/Ellipse
- `CLOUD` - Cloud callout
- `RIGHT_ARROW` - Right arrow
- `STAR_5` - 5-point star
- `TRIANGLE` - Triangle
- `HEXAGON` - Hexagon

See [Google Slides API docs](https://developers.google.com/slides/api/reference/rest/v1/presentations.pages#shapetype) for complete list.

---

## Text Styling

### Update Text Style

```python
editor.update_text_style(
    pres_id='1abc...',
    object_id='textbox123',
    style_dict={
        'bold': True,
        'italic': False,
        'fontSize': {'magnitude': 18, 'unit': 'PT'},
        'fontFamily': 'Arial',
        'foregroundColor': {
            'opaqueColor': {
                'rgbColor': {
                    'red': 1.0,
                    'green': 0.0,
                    'blue': 0.0
                }
            }
        }
    }
)
```

### Style Properties

| Property | Type | Example |
|----------|------|---------|
| `bold` | Boolean | `True` |
| `italic` | Boolean | `True` |
| `underline` | Boolean | `True` |
| `strikethrough` | Boolean | `True` |
| `fontSize` | Object | `{'magnitude': 14, 'unit': 'PT'}` |
| `fontFamily` | String | `'Arial'`, `'Times New Roman'` |
| `foregroundColor` | Object | See color format below |

### Color Format

```python
# RGB Color (values 0.0 to 1.0)
color = {
    'opaqueColor': {
        'rgbColor': {
            'red': 1.0,    # Red component
            'green': 0.5,  # Green component
            'blue': 0.0    # Blue component
        }
    }
}

# Common Colors
BLACK = {'red': 0.0, 'green': 0.0, 'blue': 0.0}
WHITE = {'red': 1.0, 'green': 1.0, 'blue': 1.0}
RED = {'red': 1.0, 'green': 0.0, 'blue': 0.0}
GREEN = {'red': 0.0, 'green': 1.0, 'blue': 0.0}
BLUE = {'red': 0.0, 'green': 0.0, 'blue': 1.0}
```

---

## Layout Management

### Get Available Layouts

```python
layouts = editor.layout_manager.get_available_layouts('1abc...')

for layout in layouts:
    print(f"{layout.layout_name}: {layout.layout_id}")
```

**Returns:** List of `LayoutInfo` objects with:
- `layout_id`: Layout object ID
- `layout_name`: Display name
- `master_id`: Parent master ID
- `element_count`: Number of placeholder elements

---

### Recommend Layout

```python
layout_id = editor.layout_manager.recommend_layout(
    content_type='bullets',
    pres_id='1abc...'
)
```

**Content Types:**
- `'title'` - Title slide
- `'section'` - Section header
- `'bullets'` - Title and bullet points
- `'two_column'` - Two column layout
- `'blank'` - Blank slide
- `'title_only'` - Title only

**Returns:** Layout ID or `None` if no match found

---

### Apply Layout

```python
editor.layout_manager.apply_layout(
    pres_id='1abc...',
    slide_id='slide123',
    layout_id='layout456'
)
```

**Warning:** Applying a layout replaces the slide's placeholder structure.

---

### Get Layout Placeholders

```python
placeholders = editor.layout_manager.get_layout_placeholders(
    pres_id='1abc...',
    layout_id='layout456'
)

for ph in placeholders:
    print(f"{ph['type']}: {ph['object_id']}")
```

---

## Batch Operations

### Batch Update

Execute multiple operations atomically:

```python
requests = [
    # Create text box
    editor._create_text_box_request(
        slide_id='slide123',
        text_box_id='textbox1',
        x=50, y=50, width=300, height=80
    ),
    # Insert text
    {
        'insertText': {
            'objectId': 'textbox1',
            'text': 'Hello',
            'insertionIndex': 0
        }
    },
    # Style text
    {
        'updateTextStyle': {
            'objectId': 'textbox1',
            'style': {
                'bold': True,
                'fontSize': {'magnitude': 24, 'unit': 'PT'}
            },
            'fields': 'bold,fontSize'
        }
    }
]

response = editor.batch_update('1abc...', requests)
print(f"Executed {len(response['replies'])} requests")
```

**Benefits:**
- **Atomic**: All requests succeed or all fail
- **Efficient**: Single API call
- **Consistent**: No partial updates

---

## Helper Methods

### Create Text Box Request

```python
request = editor._create_text_box_request(
    slide_id='slide123',
    text_box_id='unique_id',
    x=50, y=100,
    width=300, height=80
)
```

### Create Shape Request

```python
request = editor._create_shape_request(
    slide_id='slide123',
    shape_id='unique_id',
    shape_type='RECTANGLE',
    x=100, y=150,
    width=200, height=100
)
```

---

## Complete Example

```python
from scripts import GoogleSlidesEditor

# Initialize editor
editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation("My Presentation")
pres_id = result['pres_id']

# Get first slide
pres = editor.get_presentation(pres_id)
slide_id = pres['slides'][0]['objectId']

# Add title
title_result = editor.insert_text_box(
    pres_id=pres_id,
    slide_id=slide_id,
    text="Welcome",
    x=50, y=50,
    width=620, height=80
)

# Format title
editor.update_text_style(
    pres_id=pres_id,
    object_id=title_result['object_id'],
    style_dict={
        'bold': True,
        'fontSize': {'magnitude': 36, 'unit': 'PT'},
        'foregroundColor': {
            'opaqueColor': {
                'rgbColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8}
            }
        }
    }
)

print(f"Created: {result['pres_url']}")
```

---

## Best Practices

1. **Use batch updates** for multiple operations on the same slide
2. **Generate unique IDs** for new elements (use uuid)
3. **Validate coordinates** to ensure elements fit within slide bounds
4. **Test layouts** before applying to understand placeholder behavior
5. **Use constants** for common sizes and positions
6. **Handle errors** gracefully with try/except blocks
7. **Check permissions** before attempting write operations

---

## Error Handling

```python
from googleapiclient.errors import HttpError

try:
    result = editor.create_slide(pres_id, layout_id='invalid')
except HttpError as error:
    if error.resp.status == 400:
        print("Invalid request")
    elif error.resp.status == 404:
        print("Presentation not found")
    elif error.resp.status == 403:
        print("Permission denied")
    else:
        raise
except RuntimeError as error:
    print(f"Operation failed: {error}")
```

---

## Resources

- [Google Slides API Reference](https://developers.google.com/slides/api/reference/rest)
- [Shape Types](https://developers.google.com/slides/api/reference/rest/v1/presentations.pages#shapetype)
- [Text Style Properties](https://developers.google.com/slides/api/reference/rest/v1/presentations.pages#textstyle)
- [Request Types](https://developers.google.com/slides/api/reference/rest/v1/presentations/request)
