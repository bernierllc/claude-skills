# Brand Integration Guide

Complete guide to defining, applying, and validating brand guidelines in Google Slides presentations.

## Table of Contents

- [Overview](#overview)
- [Defining Brand Guidelines](#defining-brand-guidelines)
- [Applying Brand to Presentations](#applying-brand-to-presentations)
- [Brand Compliance Validation](#brand-compliance-validation)
- [Creating Brand Templates](#creating-brand-templates)
- [Customizing for Different Brands](#customizing-for-different-brands)
- [Examples and Code](#examples-and-code)

## Overview

The brand integration system allows you to:

- Define comprehensive brand guidelines in JSON
- Apply brand theme to presentations automatically
- Validate presentations against brand standards
- Create reusable brand templates
- Maintain consistency across all presentations

## Defining Brand Guidelines

Brand guidelines are defined in JSON format with the following structure:

### Complete Brand Definition

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
  "logo_url": "https://example.com/logo.png",
  "voice_tone": "Professional, clear, and trustworthy"
}
```

### Color Scheme

Define your brand's color palette:

```json
"colors": {
  "primary": "#0066CC",      // Main brand color
  "secondary": "#6B7280",    // Supporting color
  "accents": [               // Accent colors (2-4 recommended)
    "#10B981",
    "#F59E0B"
  ],
  "neutrals": [              // Backgrounds and text (3-5 shades)
    "#F9FAFB",               // Lightest
    "#E5E7EB",
    "#111827"                // Darkest
  ]
}
```

**Guidelines:**
- Use hex color codes
- Primary color: Your main brand color (40% usage)
- Secondary color: Complementary color (30% usage)
- Accents: 2-4 colors for highlights (20% usage)
- Neutrals: 3-5 shades for backgrounds and text (10% usage)

### Typography

Define headline and body text fonts:

```json
"typography": {
  "headline": {
    "family": "Montserrat",
    "weight": "bold"
  },
  "body": {
    "family": "Open Sans",
    "weight": "regular"
  }
}
```

**Available fonts in Google Slides:**
- Roboto, Open Sans, Lato
- Montserrat, Poppins, Raleway
- Playfair Display, Merriweather
- And many more via Google Fonts

**Best practices:**
- Use maximum 2 font families
- Pair serif with sans-serif (or two sans-serif)
- Ensure good readability
- Test across devices

### Spacing Rules

Define consistent spacing throughout:

```json
"spacing": {
  "slide_margin": 60,      // Distance from slide edges
  "element_gap": 20,       // Space between elements
  "title_margin": 40,      // Top margin for titles
  "content_padding": 30    // Padding around content blocks
}
```

All values are in points (1 inch = 72 points).

### Voice and Tone

Optional field describing communication style:

```json
"voice_tone": "Professional, authoritative, and trustworthy. Focus on expertise and reliability."
```

This guides content creation and ensures consistent messaging.

## Applying Brand to Presentations

### Basic Brand Application

```python
from scripts.gslides_editor import GoogleSlidesEditor

# Initialize editor
editor = GoogleSlidesEditor()

# Load brand guidelines
brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')

# Create or get presentation
result = editor.create_presentation('Branded Presentation')
pres_id = result['pres_id']

# Apply brand theme to all slides
theme_result = editor.apply_brand_theme(pres_id, brand)

print(f"Applied brand '{brand.name}' to {theme_result['slides_updated']} slides")
```

### Selective Brand Application

Apply brand to specific slides only:

```python
# Get presentation slides
presentation = editor.get_presentation(pres_id)
slides = presentation.get('slides', [])

# Apply to first and last slides only
slide_ids = [
    slides[0].get('objectId'),
    slides[-1].get('objectId')
]

# Apply brand theme to selected slides
editor.apply_brand_theme(pres_id, brand, slide_ids=slide_ids)
```

### Custom Theme Configuration

Apply a simplified theme without full brand guidelines:

```python
# Define custom theme
theme_config = {
    'background_color': '#F5F5F5',
    'primary_color': '#0066CC',
    'secondary_color': '#6B7280',
    'text_color': '#111827',
    'accent_colors': ['#10B981', '#F59E0B']
}

# Apply theme
editor.apply_theme(pres_id, theme_config)
```

## Brand Compliance Validation

### Validate Presentation

Check if a presentation follows brand guidelines:

```python
# Load brand guidelines
brand = editor.load_brand_guidelines('corporate_brand.json')

# Validate presentation
compliance = editor.validate_brand_compliance(pres_id, brand)

# Print results
print(f"Compliance Score: {compliance['compliance_score']}%")
print(f"Brand: {compliance['brand_name']}")
print(f"Total Slides: {compliance['total_slides']}")

# Check for issues
if compliance['issues']:
    print("\nCompliance Issues:")
    for issue in compliance['issues']:
        print(f"  - {issue}")
else:
    print("\nNo compliance issues found!")
```

### Validation Checks

The validator checks:

1. **Color Compliance**
   - All colors match brand palette
   - No unauthorized colors used
   - Proper color usage patterns

2. **Typography Compliance**
   - Fonts match brand specifications
   - Proper font weights used
   - Consistent font sizing

3. **Spacing Compliance**
   - Margins follow brand rules
   - Consistent element spacing
   - Proper content padding

### Compliance Scoring

- **100%**: Perfect compliance
- **75-99%**: Good, minor issues
- **50-74%**: Fair, multiple issues
- **< 50%**: Poor, major violations

## Creating Brand Templates

### Template Structure

Create a reusable brand template:

```bash
examples/brand_templates/
├── corporate_brand.json
├── startup_brand.json
└── creative_brand.json
```

### Example: Corporate Brand

```json
{
  "name": "Acme Corporation",
  "colors": {
    "primary": "#003B5C",
    "secondary": "#6B7280",
    "accents": ["#0066CC", "#10B981"],
    "neutrals": ["#F9FAFB", "#E5E7EB", "#D1D5DB", "#111827"]
  },
  "typography": {
    "headline": {
      "family": "Roboto",
      "weight": "bold"
    },
    "body": {
      "family": "Roboto",
      "weight": "regular"
    }
  },
  "spacing": {
    "slide_margin": 60,
    "element_gap": 20,
    "title_margin": 40,
    "content_padding": 30
  },
  "voice_tone": "Professional, authoritative, and trustworthy."
}
```

**Characteristics:**
- Conservative, professional colors (blues, grays)
- Single font family for consistency
- Standard spacing for formal look
- Authoritative voice and tone

### Example: Startup Brand

```json
{
  "name": "TechStart Innovation",
  "colors": {
    "primary": "#8B5CF6",
    "secondary": "#EC4899",
    "accents": ["#06B6D4", "#F59E0B", "#10B981"],
    "neutrals": ["#FAFAFA", "#F3F4F6", "#374151", "#1F2937"]
  },
  "typography": {
    "headline": {
      "family": "Montserrat",
      "weight": "bold"
    },
    "body": {
      "family": "Open Sans",
      "weight": "regular"
    }
  },
  "spacing": {
    "slide_margin": 50,
    "element_gap": 25,
    "title_margin": 35,
    "content_padding": 25
  },
  "voice_tone": "Innovative, energetic, and forward-thinking."
}
```

**Characteristics:**
- Bold, vibrant colors (purples, pinks, cyans)
- Modern font pairing
- Slightly tighter spacing for energy
- Innovative, disruptive voice

### Example: Creative Agency

```json
{
  "name": "Bold Creative Agency",
  "colors": {
    "primary": "#FF6B35",
    "secondary": "#004E89",
    "accents": ["#F7B801", "#1AA7EC", "#E63946"],
    "neutrals": ["#FFFBF7", "#F0F0F0", "#2C2C2C", "#0A0A0A"]
  },
  "typography": {
    "headline": {
      "family": "Poppins",
      "weight": "bold"
    },
    "body": {
      "family": "Lato",
      "weight": "regular"
    }
  },
  "spacing": {
    "slide_margin": 70,
    "element_gap": 30,
    "title_margin": 45,
    "content_padding": 35
  },
  "voice_tone": "Bold, creative, and expressive."
}
```

**Characteristics:**
- Striking, contrasting colors (orange, blue, yellow)
- Creative font pairing
- Generous spacing for impact
- Bold, expressive voice

## Customizing for Different Brands

### Brand Identity Matrix

Choose characteristics based on brand personality:

| Aspect | Corporate | Startup | Creative |
|--------|-----------|---------|----------|
| **Colors** | Blues, Grays | Purples, Pinks | Orange, Yellow |
| **Fonts** | Single family | Modern pairing | Creative pairing |
| **Spacing** | Standard (60pt) | Tight (50pt) | Generous (70pt) |
| **Tone** | Professional | Innovative | Bold |

### Color Selection Guide

**Professional/Corporate:**
- Blues: Trust, stability
- Grays: Neutrality, sophistication
- Dark greens: Growth, reliability

**Innovative/Tech:**
- Purples: Creativity, innovation
- Cyans: Modern, digital
- Bright accents: Energy, forward-thinking

**Creative/Bold:**
- Warm colors: Energy, passion
- High contrast: Impact, boldness
- Unique combinations: Distinctive, memorable

### Font Pairing Guide

**Conservative:**
- Roboto + Roboto (same family)
- Open Sans + Open Sans

**Modern:**
- Montserrat + Open Sans
- Poppins + Lato
- Raleway + Roboto

**Creative:**
- Playfair Display + Lato
- Merriweather + Open Sans
- Poppins + Lato

## Examples and Code

### Complete Workflow Example

```python
#!/usr/bin/env python3
"""Complete brand integration workflow."""

from scripts.gslides_editor import GoogleSlidesEditor

def main():
    # Initialize
    editor = GoogleSlidesEditor()

    # Load brand
    brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')
    print(f"Loaded brand: {brand.name}")

    # Create presentation
    result = editor.create_presentation('Q4 Business Review')
    pres_id = result['pres_id']

    # Add content slides
    slide2 = editor.create_slide(pres_id)
    slide3 = editor.create_slide(pres_id)

    # Apply brand theme
    theme_result = editor.apply_brand_theme(pres_id, brand)
    print(f"Applied to {theme_result['slides_updated']} slides")

    # Validate compliance
    compliance = editor.validate_brand_compliance(pres_id, brand)
    print(f"Compliance: {compliance['compliance_score']}%")

    # View color palette
    palette = editor.theme_manager.get_brand_color_palette(brand)
    print("\nBrand Colors:")
    for color in palette:
        print(f"  {color['name']}: {color['hex']}")

    print(f"\nPresentation URL: {result['pres_url']}")

if __name__ == '__main__':
    main()
```

### Programmatic Brand Creation

```python
from scripts.theme_manager import BrandGuidelines, ColorScheme, Typography, Spacing

# Create brand programmatically
colors = ColorScheme(
    primary='#0066CC',
    secondary='#6B7280',
    accents=['#10B981', '#F59E0B'],
    neutrals=['#F9FAFB', '#111827']
)

typography = Typography(
    headline_family='Roboto',
    headline_weight='bold',
    body_family='Open Sans',
    body_weight='regular'
)

spacing = Spacing(
    slide_margin=60,
    element_gap=20,
    title_margin=40,
    content_padding=30
)

brand = BrandGuidelines(
    name='My Custom Brand',
    colors=colors,
    typography=typography,
    spacing=spacing,
    voice_tone='Professional and engaging'
)

# Apply to presentation
editor.apply_brand_theme(pres_id, brand)
```

### Batch Processing

Apply brand to multiple presentations:

```python
def apply_brand_to_presentations(brand_file, presentation_ids):
    """Apply brand to multiple presentations."""
    editor = GoogleSlidesEditor()
    brand = editor.load_brand_guidelines(brand_file)

    results = []
    for pres_id in presentation_ids:
        result = editor.apply_brand_theme(pres_id, brand)
        compliance = editor.validate_brand_compliance(pres_id, brand)

        results.append({
            'pres_id': pres_id,
            'slides_updated': result['slides_updated'],
            'compliance_score': compliance['compliance_score']
        })

    return results

# Usage
pres_ids = ['pres_id_1', 'pres_id_2', 'pres_id_3']
results = apply_brand_to_presentations('corporate_brand.json', pres_ids)

for r in results:
    print(f"Presentation {r['pres_id']}: "
          f"{r['slides_updated']} slides, "
          f"{r['compliance_score']}% compliant")
```

## Best Practices

### Brand Definition

1. **Start Simple**
   - Begin with colors and typography
   - Add spacing rules
   - Refine based on usage

2. **Test Thoroughly**
   - Create sample presentations
   - Test all color combinations
   - Verify font availability

3. **Document Rationale**
   - Explain color choices
   - Document font pairings
   - Note spacing decisions

### Brand Application

1. **Apply Early**
   - Set up brand theme first
   - Create content with brand in mind
   - Validate frequently

2. **Stay Consistent**
   - Use brand colors exclusively
   - Follow spacing rules
   - Maintain typography standards

3. **Validate Regularly**
   - Check compliance after major changes
   - Review before finalizing
   - Fix issues immediately

### Common Pitfalls

**Avoid:**
- Too many brand colors (> 5)
- Mixing multiple brands
- Inconsistent application
- Ignoring compliance issues
- Overriding brand guidelines

**Do:**
- Keep palette focused
- Apply brand consistently
- Validate frequently
- Fix violations promptly
- Document exceptions

## Troubleshooting

### Brand Not Applying

**Issue:** Theme doesn't apply to slides

**Solutions:**
1. Verify brand JSON is valid
2. Check file path is correct
3. Ensure slides exist
4. Review error messages

### Low Compliance Score

**Issue:** Presentation fails validation

**Solutions:**
1. Review compliance issues
2. Check color usage
3. Verify font consistency
4. Fix spacing violations

### Colors Look Different

**Issue:** Applied colors don't match brand

**Solutions:**
1. Verify hex color codes
2. Check color conversion
3. Test in Google Slides directly
4. Validate RGB values

## Additional Resources

- [Design Principles](DESIGN_PRINCIPLES.md) - Visual design guidelines
- [Phase 2 Reference](PHASE2_REFERENCE.md) - Slide creation and editing
- Example scripts in `examples/`
- Brand templates in `examples/brand_templates/`

## Summary

Brand integration enables:

1. **Consistency** - Uniform look across presentations
2. **Efficiency** - Quick brand application
3. **Compliance** - Automated validation
4. **Flexibility** - Multiple brand support
5. **Quality** - Professional results

Start with a simple brand template, apply it to a presentation, validate compliance, and iterate based on results.
