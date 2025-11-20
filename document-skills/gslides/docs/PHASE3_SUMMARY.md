# Phase 3: Visual Design System - Summary

Phase 3 adds comprehensive theme management, visual design rules, and brand guidelines integration to the Google Slides Editor.

## What's New in Phase 3

### Core Modules

1. **`scripts/theme_manager.py`** - Theme and brand management
   - `ThemeManager` class for applying themes
   - `BrandGuidelines` for complete brand definitions
   - Color scheme, typography, and spacing management
   - Brand compliance validation

2. **`scripts/visual_composer.py`** - Design system implementation
   - `VisualComposer` class for design principles
   - Visual hierarchy creation
   - WCAG AA contrast validation
   - Color theory and accessibility tools
   - Layout balancing and spacing calculations

3. **Enhanced `scripts/gslides_editor.py`** - New Phase 3 methods
   - `apply_theme()` - Apply theme configuration
   - `set_slide_background()` - Set individual slide backgrounds
   - `apply_design_system()` - Apply design tokens
   - `load_brand_guidelines()` - Load brand from JSON
   - `apply_brand_theme()` - Apply complete brand
   - `validate_brand_compliance()` - Check brand compliance
   - `validate_contrast()` - WCAG contrast validation
   - `get_visual_hierarchy()` - Get hierarchy definitions

### Brand Templates

Three ready-to-use brand templates in `examples/brand_templates/`:

1. **`corporate_brand.json`** - Conservative corporate brand
   - Professional blues and grays
   - Roboto typography
   - Standard spacing
   - Authoritative tone

2. **`startup_brand.json`** - Modern startup brand
   - Vibrant purples and pinks
   - Montserrat + Open Sans
   - Tighter spacing
   - Innovative tone

3. **`creative_brand.json`** - Bold creative agency
   - Striking orange and blue
   - Poppins + Lato
   - Generous spacing
   - Expressive tone

### Example Scripts

1. **`examples/apply_brand.py`** - Brand application demo
   - Loads brand guidelines from JSON
   - Creates 3-slide presentation
   - Applies brand theme throughout
   - Validates compliance
   - Generates compliance report

2. **`examples/design_showcase.py`** - Design system demo
   - Creates 6-slide showcase
   - Visual hierarchy examples
   - Typography scale demonstration
   - Color palette showcase
   - Contrast validation examples
   - Spacing and whitespace guide

### Documentation

1. **`docs/DESIGN_PRINCIPLES.md`** - Visual design guide
   - Visual hierarchy principles
   - Color theory for presentations
   - Typography best practices
   - Spacing and layout rules
   - Contrast and accessibility
   - Examples and anti-patterns

2. **`docs/BRAND_INTEGRATION.md`** - Brand integration guide
   - Defining brand guidelines
   - Applying brands to presentations
   - Brand compliance validation
   - Creating brand templates
   - Customizing for different brands
   - Complete code examples

## Quick Start

### 1. Run Brand Application Example

```bash
cd examples
python3 apply_brand.py
```

This will:
- Load corporate brand guidelines
- Create a branded presentation
- Apply brand theme
- Validate compliance
- Print compliance report

### 2. Run Design Showcase Example

```bash
python3 design_showcase.py
```

This will:
- Create a design system showcase
- Demonstrate visual hierarchy
- Show typography scale
- Display color palette
- Validate contrast
- Demonstrate spacing rules

### 3. Use in Your Code

```python
from scripts.gslides_editor import GoogleSlidesEditor

# Initialize
editor = GoogleSlidesEditor()

# Load brand
brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')

# Create presentation
result = editor.create_presentation('My Presentation')
pres_id = result['pres_id']

# Apply brand
editor.apply_brand_theme(pres_id, brand)

# Validate compliance
compliance = editor.validate_brand_compliance(pres_id, brand)
print(f"Compliance: {compliance['compliance_score']}%")
```

## Key Features

### Theme Management

- **Color Schemes**: Primary, secondary, accent, and neutral colors
- **Typography**: Headline and body font definitions
- **Spacing Rules**: Consistent margins and padding
- **Brand Application**: Apply complete brand to presentations
- **Compliance Validation**: Automated brand compliance checking

### Visual Design System

- **Visual Hierarchy**: 4-level hierarchy with size, weight, color
- **Contrast Validation**: WCAG 2.1 AA compliance checking
- **Color Theory**: Color palette management and validation
- **Typography Scale**: Modular scale (14pt to 44pt)
- **Spacing System**: 5-level spacing scale (10pt to 60pt)
- **Layout Balancing**: Rule of thirds and golden ratio

### Brand Guidelines

Complete brand definition includes:

```json
{
  "name": "Brand Name",
  "colors": {
    "primary": "#0066CC",
    "secondary": "#6B7280",
    "accents": ["#10B981"],
    "neutrals": ["#F9FAFB", "#111827"]
  },
  "typography": {
    "headline": {"family": "Roboto", "weight": "bold"},
    "body": {"family": "Open Sans", "weight": "regular"}
  },
  "spacing": {
    "slide_margin": 60,
    "element_gap": 20
  },
  "voice_tone": "Professional and engaging"
}
```

## Integration Points

### With Layout Manager (Phase 2)

```python
# Combine layout with brand theme
layout = editor.layout_manager.get_layout_by_name(pres_id, 'TITLE_AND_BODY')
editor.apply_brand_theme(pres_id, brand)
```

### With Visual Composer

```python
# Validate contrast for elements
contrast = editor.validate_contrast('#333333', '#FFFFFF', 18)

# Get visual hierarchy
hierarchy = editor.get_visual_hierarchy(3)

# Apply to text elements
for level in hierarchy:
    print(f"Level {level['level']}: {level['font_size']}pt")
```

### With Theme Manager

```python
# Set individual slide background
editor.set_slide_background(pres_id, slide_id, '#F9FAFB')

# Get color palette
palette = editor.theme_manager.get_brand_color_palette(brand)
```

## Accessibility Features

### WCAG 2.1 Compliance

- **Contrast Validation**: Automatic WCAG AA checking
- **Minimum Ratios**: 4.5:1 for normal text, 3.0:1 for large text
- **Color-Blind Safe**: Validation and suggestions
- **Accessible Colors**: Tools to suggest compliant alternatives

### Contrast Validation Example

```python
# Validate text/background contrast
result = editor.validate_contrast(
    text_color='#333333',
    bg_color='#FFFFFF',
    font_size=18,
    is_bold=False
)

print(f"Passes: {result['passes']}")
print(f"Ratio: {result['ratio']:.2f}:1")
print(f"Level: {result['level']}")  # AA or AAA
```

## Design Principles

### Visual Hierarchy

1. **Level 1**: 32-44pt, Bold - Titles
2. **Level 2**: 24-32pt, Bold - Subtitles
3. **Level 3**: 18-24pt, Regular - Body text
4. **Level 4**: 14-18pt, Regular - Captions

### Color Usage

- **Primary**: 40% usage - Main brand color
- **Secondary**: 30% usage - Supporting color
- **Accents**: 20% usage - Highlights
- **Neutrals**: 10% usage - Backgrounds/text

### Spacing Scale

- **XS**: 10pt - Tight spacing
- **SM**: 20pt - Default spacing
- **MD**: 30pt - Section spacing
- **LG**: 40pt - Major sections
- **XL**: 60pt - Slide margins

## API Reference

### Theme Manager Methods

```python
# Set slide background
theme_manager.set_slide_background(pres_id, slide_id, '#FFFFFF')

# Apply brand theme
theme_manager.apply_brand_theme(pres_id, brand, slide_ids=None)

# Validate compliance
theme_manager.validate_brand_compliance(pres_id, brand)

# Get color palette
theme_manager.get_brand_color_palette(brand)

# Convert colors
rgb = theme_manager.hex_to_rgb('#FF5733')
hex_color = theme_manager.rgb_to_hex(rgb)
```

### Visual Composer Methods

```python
# Validate contrast
visual_composer.validate_contrast(text_color, bg_color, font_size, is_bold)

# Create hierarchy
visual_composer.create_visual_hierarchy(levels=3)

# Calculate spacing
visual_composer.calculate_optimal_spacing(content_height, slide_height)

# Validate design system
visual_composer.validate_design_system(element_styles)

# Get color palette info
visual_composer.get_color_palette_info()
```

### Editor Phase 3 Methods

```python
# Apply theme
editor.apply_theme(pres_id, theme_config)

# Set background
editor.set_slide_background(pres_id, slide_id, color)

# Apply design system
editor.apply_design_system(pres_id, design_tokens)

# Load brand
brand = editor.load_brand_guidelines(filepath)

# Apply brand
editor.apply_brand_theme(pres_id, brand, slide_ids=None)

# Validate brand
editor.validate_brand_compliance(pres_id, brand)

# Validate contrast
editor.validate_contrast(text_color, bg_color, font_size, is_bold)

# Get hierarchy
editor.get_visual_hierarchy(levels=3)
```

## Next Steps

1. **Read Documentation**
   - [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) - Visual design guide
   - [BRAND_INTEGRATION.md](BRAND_INTEGRATION.md) - Brand integration guide

2. **Run Examples**
   - `apply_brand.py` - See brand application
   - `design_showcase.py` - See design system

3. **Create Your Brand**
   - Copy a template from `brand_templates/`
   - Customize colors, fonts, spacing
   - Save as your brand JSON

4. **Apply to Presentations**
   - Load your brand
   - Apply to existing presentations
   - Validate compliance
   - Iterate and refine

## Common Use Cases

### Corporate Presentations

```python
brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')
editor.apply_brand_theme(pres_id, brand)
```

### Startup Pitch Decks

```python
brand = editor.load_brand_guidelines('brand_templates/startup_brand.json')
editor.apply_brand_theme(pres_id, brand)
```

### Creative Portfolios

```python
brand = editor.load_brand_guidelines('brand_templates/creative_brand.json')
editor.apply_brand_theme(pres_id, brand)
```

### Custom Brands

```python
from scripts.theme_manager import BrandGuidelines

brand = BrandGuidelines.from_dict({
    'name': 'My Brand',
    'colors': {...},
    'typography': {...},
    'spacing': {...}
})
editor.apply_brand_theme(pres_id, brand)
```

## Troubleshooting

### Brand Not Applying

1. Verify JSON is valid
2. Check file path
3. Ensure slides exist
4. Review error messages

### Low Compliance Score

1. Check color usage
2. Verify fonts
3. Fix spacing
4. Review issues list

### Contrast Issues

1. Use contrast validator
2. Adjust colors
3. Test with WCAG tools
4. Use suggested colors

## Summary

Phase 3 provides:

- **Theme Management**: Complete brand control
- **Visual Design**: Professional design principles
- **Accessibility**: WCAG compliance tools
- **Brand Templates**: Ready-to-use examples
- **Validation**: Automated compliance checking
- **Documentation**: Comprehensive guides

The system integrates seamlessly with Phase 1 (reading) and Phase 2 (editing) to provide a complete Google Slides automation solution.
