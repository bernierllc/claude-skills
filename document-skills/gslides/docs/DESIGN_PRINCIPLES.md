# Design Principles for Google Slides

This document outlines the design principles, best practices, and visual guidelines for creating professional, accessible, and visually appealing Google Slides presentations.

## Table of Contents

- [Visual Hierarchy](#visual-hierarchy)
- [Color Theory](#color-theory)
- [Typography](#typography)
- [Spacing and Layout](#spacing-and-layout)
- [Contrast and Accessibility](#contrast-and-accessibility)
- [Brand Consistency](#brand-consistency)
- [Examples and Anti-Patterns](#examples-and-anti-patterns)

## Visual Hierarchy

Visual hierarchy guides the viewer's attention through content in order of importance.

### Principles

1. **Size and Scale**
   - Larger elements naturally draw more attention
   - Use size to establish importance
   - Maintain consistent ratios (e.g., 1.5x, 2x scaling)

2. **Weight and Emphasis**
   - Bold text for headings and important information
   - Regular weight for body text
   - Use sparingly to maintain impact

3. **Color for Priority**
   - Darker colors for primary content
   - Lighter colors for secondary information
   - Brand colors for key elements

### Recommended Hierarchy Levels

```
Level 1 (Titles):       32-44pt, Bold, Dark Color
Level 2 (Subtitles):    24-32pt, Bold, Dark Color
Level 3 (Body):         18-24pt, Regular, Medium Color
Level 4 (Captions):     14-18pt, Regular, Light Color
```

### Implementation

```python
from scripts.gslides_editor import GoogleSlidesEditor

editor = GoogleSlidesEditor()

# Get visual hierarchy definitions
hierarchy = editor.get_visual_hierarchy(4)

for level in hierarchy:
    print(f"Level {level['level']}: {level['font_size']}pt - {level['usage']}")
```

## Color Theory

Effective color use enhances communication and maintains brand identity.

### Color Palette Structure

1. **Primary Color** (40% usage)
   - Main brand color
   - Used for primary CTAs and key elements
   - Should be distinctive and memorable

2. **Secondary Color** (30% usage)
   - Supporting brand color
   - Complements primary color
   - Used for secondary elements

3. **Accent Colors** (20% usage)
   - Highlight important information
   - Create visual interest
   - Typically 2-3 colors max

4. **Neutral Colors** (10% usage)
   - Backgrounds and text
   - Provide balance
   - Usually grays or off-whites

### Color Psychology

- **Blue**: Trust, professionalism, stability
- **Green**: Growth, success, harmony
- **Red**: Energy, urgency, passion
- **Yellow**: Optimism, attention, warmth
- **Purple**: Creativity, luxury, innovation
- **Gray**: Neutrality, professionalism, balance

### Best Practices

- Use color consistently throughout
- Limit palette to 3-5 colors
- Consider cultural color meanings
- Test colors for accessibility
- Use color to group related information

## Typography

Typography affects readability and professional appearance.

### Font Selection

1. **Headlines**: Sans-serif, bold, 32-44pt
   - Examples: Roboto, Montserrat, Poppins
   - High impact, clear hierarchy

2. **Body Text**: Sans-serif, regular, 18-24pt
   - Examples: Open Sans, Lato, Roboto
   - Optimized for readability

3. **Captions**: Sans-serif, regular, 14-18pt
   - Same family as body text
   - Slightly smaller for hierarchy

### Typography Scale

Based on a modular scale (1.5 ratio):

```
Display:   44pt  (Headlines, hero text)
H1:        32pt  (Main headings)
H2:        24pt  (Subheadings)
Body:      18pt  (Content, paragraphs)
Small:     14pt  (Captions, footnotes)
```

### Best Practices

- Maximum 2 font families per presentation
- Maintain consistent line spacing (1.2-1.5x)
- Avoid all caps except for emphasis
- Use proper punctuation and grammar
- Left-align body text for readability

### Anti-Patterns

- Don't use Comic Sans or decorative fonts
- Avoid mixing too many font weights
- Don't use font sizes below 14pt
- Avoid centered paragraphs for body text
- Don't use color as the only differentiator

## Spacing and Layout

Proper spacing creates visual breathing room and improves comprehension.

### Spacing Scale

```python
XS:  10pt  # Tight spacing, related items
SM:  20pt  # Default element spacing
MD:  30pt  # Section spacing
LG:  40pt  # Major section separation
XL:  60pt  # Slide margins
```

### Layout Principles

1. **Rule of Thirds**
   - Divide slide into 3x3 grid
   - Place key elements at intersections
   - Creates balanced, dynamic compositions

2. **Golden Ratio** (1.618:1)
   - Use for proportions and spacing
   - Natural, aesthetically pleasing layouts
   - Applies to element sizes and positions

3. **Whitespace**
   - Empty space is not wasted space
   - Provides visual rest
   - Emphasizes content
   - Minimum 60pt margins recommended

### Margin Recommendations

```
Slide Margins:     60pt (all sides)
Title Margin:      40pt (from top)
Content Padding:   30pt (between sections)
Element Gap:       20pt (between items)
```

### Implementation

```python
# Calculate optimal spacing
spacing = editor.visual_composer.calculate_optimal_spacing(
    content_height=200,
    slide_height=405
)

print(f"Top margin: {spacing['top_margin']}pt")
print(f"Side margin: {spacing['side_margin']}pt")
```

## Contrast and Accessibility

WCAG 2.1 Level AA compliance ensures accessibility for all users.

### Contrast Requirements

- **Normal Text** (< 18pt): Minimum 4.5:1 ratio
- **Large Text** (≥ 18pt or ≥14pt bold): Minimum 3.0:1 ratio
- **Level AAA**: 7.0:1 ratio (enhanced)

### Validation

```python
# Validate contrast
result = editor.validate_contrast(
    text_color='#333333',
    bg_color='#FFFFFF',
    font_size=18,
    is_bold=False
)

if result['passes']:
    print(f"Accessible! Ratio: {result['ratio']:.2f}:1")
    print(f"Level: {result['level']}")
else:
    print(f"Insufficient contrast: {result['ratio']:.2f}:1")
```

### Color-Blind Considerations

- Don't rely on color alone to convey information
- Use patterns, icons, or text labels
- Test with color-blindness simulators
- Common safe combinations:
  - Blue + Orange
  - Blue + Yellow
  - Dark Gray + Light Gray

### Best Practices

- Dark text on light backgrounds
- High contrast for important information
- Test with grayscale preview
- Provide sufficient color differentiation
- Use tools to validate contrast ratios

## Brand Consistency

Maintain brand identity across all presentations.

### Brand Guidelines Components

1. **Color Scheme**
   - Primary, secondary, accent colors
   - Defined hex values
   - Usage guidelines

2. **Typography**
   - Headline and body fonts
   - Font weights and sizes
   - Font pairing rules

3. **Spacing Rules**
   - Margins and padding
   - Element gaps
   - Layout grids

4. **Voice and Tone**
   - Writing style guidelines
   - Brand personality
   - Communication principles

### Loading Brand Guidelines

```python
# Load brand from JSON
brand = editor.load_brand_guidelines('corporate_brand.json')

# Apply to presentation
editor.apply_brand_theme(pres_id, brand)

# Validate compliance
compliance = editor.validate_brand_compliance(pres_id, brand)
print(f"Compliance: {compliance['compliance_score']}%")
```

## Examples and Anti-Patterns

### Good Examples

1. **Clear Hierarchy**
   ```
   Title:    44pt, Bold, #111827
   Subtitle: 24pt, Bold, #6B7280
   Body:     18pt, Regular, #6B7280
   ```

2. **Accessible Contrast**
   ```
   Dark on Light: #111827 on #FFFFFF (15.8:1) ✓
   Brand Color:   #0066CC on #FFFFFF (8.6:1) ✓
   ```

3. **Consistent Spacing**
   ```
   Margins:  60pt all sides
   Headings: 40pt top margin
   Sections: 30pt padding
   ```

### Anti-Patterns to Avoid

1. **Poor Hierarchy**
   - Similar sizes for all text
   - Inconsistent weights
   - No clear visual order

2. **Insufficient Contrast**
   - Light gray on white (< 4.5:1)
   - Colored text on colored backgrounds
   - Relying only on color

3. **Cramped Layout**
   - No margins or whitespace
   - Text too close to edges
   - Overcrowded slides

4. **Typography Mistakes**
   - Too many fonts (> 2 families)
   - Text below 14pt
   - All caps paragraphs
   - Poor alignment

5. **Color Overuse**
   - Rainbow color schemes
   - Too many accent colors
   - Inconsistent color usage

## Tools and Resources

### Built-in Validation

```python
# Visual hierarchy
hierarchy = editor.get_visual_hierarchy(3)

# Contrast validation
contrast = editor.validate_contrast('#333', '#FFF', 18)

# Design system validation
validation = editor.visual_composer.validate_design_system(elements)
```

### External Resources

- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Google Fonts](https://fonts.google.com/)
- [Adobe Color](https://color.adobe.com/)

## Summary Checklist

- [ ] Clear visual hierarchy established
- [ ] Color palette limited to 3-5 colors
- [ ] Typography uses max 2 font families
- [ ] All text meets WCAG AA contrast (4.5:1 minimum)
- [ ] Adequate whitespace and margins (60pt minimum)
- [ ] Consistent spacing throughout
- [ ] Brand guidelines followed
- [ ] Content is accessible to all users
- [ ] Layout uses rule of thirds
- [ ] No anti-patterns present

## Next Steps

- See [BRAND_INTEGRATION.md](BRAND_INTEGRATION.md) for brand application
- Review example scripts in `examples/`
- Test designs with accessibility tools
- Validate against brand guidelines
