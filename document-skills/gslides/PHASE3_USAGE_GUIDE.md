# Phase 3 Visual Design System - Usage Guide

Complete guide to using the Phase 3 theme management and visual design system.

## Quick Start

### 1. Apply a Brand to a Presentation

```python
from scripts.gslides_editor import GoogleSlidesEditor

# Initialize editor
editor = GoogleSlidesEditor()

# Create a new presentation
result = editor.create_presentation('My Branded Presentation')
pres_id = result['pres_id']

# Load a brand template
brand = editor.load_brand_guidelines('examples/brand_templates/corporate_brand.json')

# Apply the brand
editor.apply_brand_theme(pres_id, brand)

print(f"Brand applied! View at: {result['pres_url']}")
```

### 2. Validate Brand Compliance

```python
# Validate the presentation against brand guidelines
compliance = editor.validate_brand_compliance(pres_id, brand)

print(f"Compliance Score: {compliance['compliance_score']}%")

if compliance['issues']:
    print("\nIssues found:")
    for issue in compliance['issues']:
        print(f"  - {issue}")
```

### 3. Check Color Contrast (Accessibility)

```python
# Validate text/background contrast for WCAG AA
result = editor.validate_contrast(
    text_color='#333333',
    bg_color='#FFFFFF',
    font_size=18
)

print(f"Contrast Ratio: {result['ratio']:.2f}:1")
print(f"WCAG Level: {result['level']}")
print(f"Passes AA: {result['passes']}")
```

## Available Methods

### Theme Management

#### `apply_theme(pres_id, theme_config)`

Apply a simple theme configuration:

```python
theme = {
    'background_color': '#F9FAFB',
    'primary_color': '#0066CC',
    'secondary_color': '#6B7280',
    'text_color': '#111827'
}

editor.apply_theme(pres_id, theme)
```

#### `set_slide_background(pres_id, slide_id, color)`

Set background color for a specific slide:

```python
editor.set_slide_background(pres_id, slide_id, '#F0F0F0')
```

#### `apply_design_system(pres_id, design_tokens)`

Apply comprehensive design system tokens:

```python
from scripts.visual_composer import DesignTokens

tokens = DesignTokens.default()
editor.apply_design_system(pres_id, tokens)
```

### Brand Guidelines

#### `load_brand_guidelines(filepath)`

Load brand from JSON file:

```python
brand = editor.load_brand_guidelines('examples/brand_templates/startup_brand.json')
print(f"Loaded: {brand.name}")
```

#### `apply_brand_theme(pres_id, brand, slide_ids=None)`

Apply brand to all slides or selected slides:

```python
# Apply to all slides
editor.apply_brand_theme(pres_id, brand)

# Apply to specific slides
editor.apply_brand_theme(pres_id, brand, slide_ids=['slide1', 'slide2'])
```

#### `validate_brand_compliance(pres_id, brand)`

Check presentation against brand guidelines:

```python
compliance = editor.validate_brand_compliance(pres_id, brand)

print(f"Score: {compliance['compliance_score']}%")
print(f"Checks: {compliance['checks']}")
print(f"Issues: {compliance['issues']}")
```

### Visual Design

#### `validate_contrast(text_color, bg_color, font_size, is_bold=False)`

Validate color contrast for accessibility:

```python
result = editor.validate_contrast('#333', '#FFF', 18)

if result['passes']:
    print(f"Accessible! {result['ratio']:.2f}:1")
else:
    print(f"Fails WCAG AA: {result['ratio']:.2f}:1")
```

#### `get_visual_hierarchy(levels=3)`

Get visual hierarchy definitions:

```python
hierarchy = editor.get_visual_hierarchy(4)

for level in hierarchy:
    print(f"Level {level['level']}: {level['font_size']}pt - {level['usage']}")
```

## Using Brand Templates

### Available Templates

Three ready-to-use brand templates are included:

#### 1. Corporate Brand

**File:** `examples/brand_templates/corporate_brand.json`

**Characteristics:**
- Conservative, professional colors (blues, grays)
- Single font family (Roboto)
- Standard spacing
- Professional, authoritative tone

**Use for:**
- Corporate presentations
- Annual reports
- Executive briefings
- Board meetings

**Example:**
```python
brand = editor.load_brand_guidelines('examples/brand_templates/corporate_brand.json')
```

#### 2. Startup Brand

**File:** `examples/brand_templates/startup_brand.json`

**Characteristics:**
- Bold, vibrant colors (purples, pinks, cyans)
- Modern font pairing (Montserrat + Open Sans)
- Tighter spacing for energy
- Innovative, forward-thinking tone

**Use for:**
- Pitch decks
- Investor presentations
- Product launches
- Tech conferences

**Example:**
```python
brand = editor.load_brand_guidelines('examples/brand_templates/startup_brand.json')
```

#### 3. Creative Agency Brand

**File:** `examples/brand_templates/creative_brand.json`

**Characteristics:**
- Striking, contrasting colors (orange, blue, yellow)
- Creative font pairing (Poppins + Lato)
- Generous spacing for impact
- Bold, expressive tone

**Use for:**
- Creative portfolios
- Design presentations
- Marketing campaigns
- Agency showcases

**Example:**
```python
brand = editor.load_brand_guidelines('examples/brand_templates/creative_brand.json')
```

## Creating Custom Brands

### Brand JSON Structure

```json
{
  "name": "Your Brand Name",
  "colors": {
    "primary": "#0066CC",
    "secondary": "#6B7280",
    "accents": ["#10B981", "#F59E0B"],
    "neutrals": ["#F9FAFB", "#E5E7EB", "#111827"]
  },
  "typography": {
    "headline": {
      "family": "Roboto",
      "weight": "bold"
    },
    "body": {
      "family": "Open Sans",
      "weight": "regular"
    }
  },
  "spacing": {
    "slide_margin": 60,
    "element_gap": 20,
    "title_margin": 40,
    "content_padding": 30
  },
  "voice_tone": "Professional and engaging"
}
```

### Programmatic Brand Creation

```python
from scripts.theme_manager import BrandGuidelines, ColorScheme, Typography, Spacing

# Define colors
colors = ColorScheme(
    primary='#FF6B35',
    secondary='#004E89',
    accents=['#F7B801', '#1AA7EC'],
    neutrals=['#FFFBF7', '#0A0A0A']
)

# Define typography
typography = Typography(
    headline_family='Poppins',
    headline_weight='bold',
    body_family='Lato',
    body_weight='regular'
)

# Define spacing
spacing = Spacing(
    slide_margin=70,
    element_gap=30,
    title_margin=45,
    content_padding=35
)

# Create brand
brand = BrandGuidelines(
    name='My Custom Brand',
    colors=colors,
    typography=typography,
    spacing=spacing,
    voice_tone='Bold, creative, and expressive'
)

# Apply to presentation
editor.apply_brand_theme(pres_id, brand)
```

## Direct Access to Managers

The editor provides direct access to theme and visual managers:

### Theme Manager

```python
# Access theme manager
theme_mgr = editor.theme_manager

# Set slide background
theme_mgr.set_slide_background(pres_id, slide_id, '#F0F0F0')

# Apply brand theme
theme_mgr.apply_brand_theme(pres_id, brand)

# Validate compliance
theme_mgr.validate_brand_compliance(pres_id, brand)

# Get color palette
palette = theme_mgr.get_brand_color_palette(brand)

# Convert colors
rgb = theme_mgr.hex_to_rgb('#FF5733')
hex_color = theme_mgr.rgb_to_hex(rgb)
```

### Visual Composer

```python
# Access visual composer
composer = editor.visual_composer

# Validate contrast
contrast = composer.validate_contrast('#333', '#FFF', 18)

# Create visual hierarchy
hierarchy = composer.create_visual_hierarchy(4)

# Calculate spacing
spacing = composer.calculate_optimal_spacing(200, 405)

# Validate design system
validation = composer.validate_design_system(elements)

# Get color palette info
palette_info = composer.get_color_palette_info()
```

## Example Workflows

### Workflow 1: Create Branded Presentation from Scratch

```python
from scripts.gslides_editor import GoogleSlidesEditor

def create_branded_presentation(title, brand_file):
    """Create a fully branded presentation."""
    editor = GoogleSlidesEditor()

    # Create presentation
    result = editor.create_presentation(title)
    pres_id = result['pres_id']

    # Load and apply brand
    brand = editor.load_brand_guidelines(brand_file)
    editor.apply_brand_theme(pres_id, brand)

    # Add slides
    slide2 = editor.create_slide(pres_id)
    slide3 = editor.create_slide(pres_id)

    # Validate
    compliance = editor.validate_brand_compliance(pres_id, brand)

    return {
        'pres_url': result['pres_url'],
        'pres_id': pres_id,
        'compliance': compliance['compliance_score']
    }

# Usage
result = create_branded_presentation(
    'Q4 Business Review',
    'examples/brand_templates/corporate_brand.json'
)

print(f"Created: {result['pres_url']}")
print(f"Compliance: {result['compliance']}%")
```

### Workflow 2: Apply Brand to Existing Presentation

```python
def rebrand_presentation(pres_id, new_brand_file):
    """Apply new brand to existing presentation."""
    editor = GoogleSlidesEditor()

    # Load new brand
    brand = editor.load_brand_guidelines(new_brand_file)

    # Apply to presentation
    result = editor.apply_brand_theme(pres_id, brand)

    # Validate compliance
    compliance = editor.validate_brand_compliance(pres_id, brand)

    return {
        'slides_updated': result['slides_updated'],
        'compliance_score': compliance['compliance_score'],
        'issues': compliance['issues']
    }

# Usage
result = rebrand_presentation(
    'your_presentation_id',
    'examples/brand_templates/startup_brand.json'
)

print(f"Updated {result['slides_updated']} slides")
print(f"Compliance: {result['compliance_score']}%")
```

### Workflow 3: Batch Process Multiple Presentations

```python
def batch_apply_brand(presentation_ids, brand_file):
    """Apply brand to multiple presentations."""
    editor = GoogleSlidesEditor()
    brand = editor.load_brand_guidelines(brand_file)

    results = []
    for pres_id in presentation_ids:
        # Apply brand
        theme_result = editor.apply_brand_theme(pres_id, brand)

        # Validate
        compliance = editor.validate_brand_compliance(pres_id, brand)

        results.append({
            'pres_id': pres_id,
            'slides_updated': theme_result['slides_updated'],
            'compliance': compliance['compliance_score']
        })

    return results

# Usage
pres_ids = ['id1', 'id2', 'id3']
results = batch_apply_brand(pres_ids, 'examples/brand_templates/corporate_brand.json')

for r in results:
    print(f"{r['pres_id']}: {r['slides_updated']} slides, {r['compliance']}% compliant")
```

### Workflow 4: Validate and Fix Contrast Issues

```python
def check_and_fix_contrast(elements):
    """Validate and suggest fixes for contrast issues."""
    editor = GoogleSlidesEditor()
    composer = editor.visual_composer

    issues = []
    fixes = []

    for element in elements:
        # Validate contrast
        result = composer.validate_contrast(
            element['text_color'],
            element['bg_color'],
            element['font_size']
        )

        if not result['passes']:
            issues.append({
                'element': element['name'],
                'ratio': result['ratio'],
                'required': result['required']
            })

            # Suggest accessible color
            fixed_color = composer.suggest_accessible_color(
                element['text_color'],
                element['bg_color']
            )

            if fixed_color:
                fixes.append({
                    'element': element['name'],
                    'original': element['text_color'],
                    'suggested': fixed_color
                })

    return {
        'issues': issues,
        'fixes': fixes
    }

# Usage
elements = [
    {'name': 'Title', 'text_color': '#D1D5DB', 'bg_color': '#FFFFFF', 'font_size': 32},
    {'name': 'Body', 'text_color': '#6B7280', 'bg_color': '#FFFFFF', 'font_size': 18}
]

result = check_and_fix_contrast(elements)

print(f"Found {len(result['issues'])} contrast issues")
for fix in result['fixes']:
    print(f"  {fix['element']}: {fix['original']} → {fix['suggested']}")
```

## Running Example Scripts

### Apply Brand Example

Demonstrates brand loading and application:

```bash
cd examples
python3 apply_brand.py
```

**What it does:**
1. Loads corporate brand guidelines
2. Creates 3-slide presentation
3. Applies brand theme throughout
4. Validates compliance
5. Prints compliance report
6. Shows brand color palette

### Design Showcase Example

Demonstrates design system principles:

```bash
cd examples
python3 design_showcase.py
```

**What it does:**
1. Creates 6-slide design showcase
2. Demonstrates visual hierarchy
3. Shows typography scale
4. Displays color palette
5. Validates contrast examples
6. Shows spacing and whitespace
7. Applies clean design theme

## Best Practices

### Brand Application

1. **Load brand first**
   ```python
   brand = editor.load_brand_guidelines('brand.json')
   editor.apply_brand_theme(pres_id, brand)
   ```

2. **Validate frequently**
   ```python
   compliance = editor.validate_brand_compliance(pres_id, brand)
   if compliance['compliance_score'] < 80:
       print("Fix issues before proceeding")
   ```

3. **Use brand colors**
   ```python
   palette = editor.theme_manager.get_brand_color_palette(brand)
   # Use colors from palette only
   ```

### Accessibility

1. **Always validate contrast**
   ```python
   result = editor.validate_contrast(text_color, bg_color, font_size)
   if not result['passes']:
       # Use suggested accessible color
   ```

2. **Use visual hierarchy**
   ```python
   hierarchy = editor.get_visual_hierarchy(3)
   # Apply appropriate sizes and weights
   ```

3. **Maintain adequate spacing**
   ```python
   # Use minimum 60pt margins
   # Maintain 20pt element gaps
   ```

### Design System

1. **Follow typography scale**
   ```python
   # Use defined sizes: 44pt, 32pt, 24pt, 18pt, 14pt
   ```

2. **Limit color palette**
   ```python
   # Use 3-5 colors maximum
   # Primary, secondary, accents, neutrals
   ```

3. **Consistent spacing**
   ```python
   # Use spacing scale: 10pt, 20pt, 30pt, 40pt, 60pt
   ```

## Troubleshooting

### Brand Not Applying

**Problem:** Theme doesn't apply to slides

**Solutions:**
1. Verify brand JSON is valid
2. Check file path is correct
3. Ensure presentation exists
4. Review error messages

### Low Compliance Score

**Problem:** Presentation fails validation

**Solutions:**
1. Review compliance issues
2. Fix color usage
3. Correct font inconsistencies
4. Adjust spacing violations

### Contrast Failures

**Problem:** Text fails WCAG AA

**Solutions:**
1. Use contrast validator
2. Increase color difference
3. Use darker text or lighter background
4. Test with accessibility tools

## Additional Resources

### Documentation

- [DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md) - Visual design guide
- [BRAND_INTEGRATION.md](docs/BRAND_INTEGRATION.md) - Brand integration guide
- [PHASE3_SUMMARY.md](docs/PHASE3_SUMMARY.md) - Phase 3 overview

### Code

- `scripts/theme_manager.py` - Theme and brand management
- `scripts/visual_composer.py` - Design system implementation
- `scripts/gslides_editor.py` - Main editor with Phase 3 methods

### Examples

- `examples/apply_brand.py` - Brand application demo
- `examples/design_showcase.py` - Design system showcase
- `examples/brand_templates/` - Ready-to-use brand files

## Summary

Phase 3 provides comprehensive theme and brand management:

- **Load** brand guidelines from JSON
- **Apply** brands to presentations
- **Validate** brand compliance
- **Check** accessibility (WCAG AA)
- **Use** design system principles
- **Create** professional, accessible presentations

The system integrates seamlessly with Phase 1 (reading) and Phase 2 (editing) for complete presentation automation.
