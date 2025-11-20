#!/usr/bin/env python3
"""
Visual Composer for Google Slides.

Implements design system principles including visual hierarchy, contrast validation,
color theory, and typography best practices. Phase 3 component for UI Designer agent.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class DesignTokens:
    """Design system tokens for consistent visual composition."""
    # Typography scale (in points)
    font_sizes: Dict[str, int]

    # Spacing scale (in points)
    spacing: Dict[str, int]

    # Color palette
    colors: Dict[str, str]

    @classmethod
    def default(cls) -> 'DesignTokens':
        """Create default design tokens."""
        return cls(
            font_sizes={
                'display': 44,      # Large display text
                'h1': 32,           # Main headings
                'h2': 24,           # Sub headings
                'body': 18,         # Body text
                'small': 14         # Small text, captions
            },
            spacing={
                'xs': 10,
                'sm': 20,
                'md': 30,
                'lg': 40,
                'xl': 60
            },
            colors={
                'primary': '#0066cc',
                'secondary': '#6b7280',
                'success': '#10b981',
                'warning': '#f59e0b',
                'error': '#ef4444',
                'text_dark': '#111827',
                'text_light': '#6b7280',
                'bg_light': '#f9fafb',
                'bg_white': '#ffffff'
            }
        )


class VisualComposer:
    """
    Composes visual designs following design system principles.

    Implements:
    - Visual hierarchy (size, weight, color contrast)
    - Color theory and accessibility
    - Typography best practices
    - Spacing and layout rules
    - Contrast validation (WCAG AA compliance)
    """

    # WCAG 2.1 AA contrast requirements
    MIN_CONTRAST_NORMAL = 4.5   # For normal text
    MIN_CONTRAST_LARGE = 3.0    # For large text (18pt+ or 14pt+ bold)

    def __init__(self, design_tokens: Optional[DesignTokens] = None):
        """
        Initialize VisualComposer.

        Args:
            design_tokens: Optional custom design tokens.
                          If None, uses default tokens.
        """
        self.tokens = design_tokens or DesignTokens.default()

    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """
        Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., '#FF5733')

        Returns:
            Tuple of (r, g, b) values (0-255)
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """
        Convert RGB values to hex color.

        Args:
            r, g, b: RGB values (0-255)

        Returns:
            Hex color string
        """
        return f"#{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def calculate_luminance(r: int, g: int, b: int) -> float:
        """
        Calculate relative luminance of a color.

        Uses WCAG formula for luminance calculation.

        Args:
            r, g, b: RGB values (0-255)

        Returns:
            Relative luminance (0.0-1.0)
        """
        # Convert to 0-1 range
        r, g, b = r / 255.0, g / 255.0, b / 255.0

        # Apply gamma correction
        def gamma_correct(val):
            if val <= 0.03928:
                return val / 12.92
            else:
                return math.pow((val + 0.055) / 1.055, 2.4)

        r = gamma_correct(r)
        g = gamma_correct(g)
        b = gamma_correct(b)

        # Calculate luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def calculate_contrast_ratio(
        self,
        color1: str,
        color2: str
    ) -> float:
        """
        Calculate contrast ratio between two colors.

        Uses WCAG formula: (L1 + 0.05) / (L2 + 0.05)
        where L1 is the lighter color's luminance.

        Args:
            color1: First hex color
            color2: Second hex color

        Returns:
            Contrast ratio (1.0 to 21.0)

        Example:
            >>> composer = VisualComposer()
            >>> ratio = composer.calculate_contrast_ratio('#000000', '#FFFFFF')
            >>> print(f"Contrast: {ratio:.2f}:1")  # Should be 21.0:1
        """
        r1, g1, b1 = self.hex_to_rgb(color1)
        r2, g2, b2 = self.hex_to_rgb(color2)

        lum1 = self.calculate_luminance(r1, g1, b1)
        lum2 = self.calculate_luminance(r2, g2, b2)

        # Ensure L1 is the lighter color
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)

        return (lighter + 0.05) / (darker + 0.05)

    def validate_contrast(
        self,
        text_color: str,
        bg_color: str,
        font_size: int,
        is_bold: bool = False
    ) -> Dict[str, Any]:
        """
        Validate color contrast meets WCAG AA standards.

        Args:
            text_color: Text hex color
            bg_color: Background hex color
            font_size: Font size in points
            is_bold: Whether text is bold

        Returns:
            Dictionary with validation results:
            - 'passes': bool - Whether contrast is sufficient
            - 'ratio': float - Actual contrast ratio
            - 'required': float - Required contrast ratio
            - 'level': str - 'AAA', 'AA', or 'FAIL'

        Example:
            >>> result = composer.validate_contrast('#333333', '#FFFFFF', 16)
            >>> if result['passes']:
            ...     print(f"Passes with ratio {result['ratio']:.2f}:1")
        """
        ratio = self.calculate_contrast_ratio(text_color, bg_color)

        # Determine if text is "large"
        is_large_text = font_size >= 18 or (font_size >= 14 and is_bold)

        # Determine required contrast
        required = self.MIN_CONTRAST_LARGE if is_large_text else self.MIN_CONTRAST_NORMAL

        # Determine compliance level
        if ratio >= 7.0:
            level = 'AAA'
        elif ratio >= required:
            level = 'AA'
        else:
            level = 'FAIL'

        return {
            'passes': ratio >= required,
            'ratio': round(ratio, 2),
            'required': required,
            'level': level,
            'is_large_text': is_large_text
        }

    def suggest_accessible_color(
        self,
        base_color: str,
        bg_color: str,
        target_ratio: float = MIN_CONTRAST_NORMAL
    ) -> Optional[str]:
        """
        Suggest an accessible color variation that meets contrast requirements.

        Args:
            base_color: Starting hex color
            bg_color: Background hex color
            target_ratio: Target contrast ratio (default: 4.5)

        Returns:
            Hex color string that meets contrast ratio, or None if not possible

        Example:
            >>> suggested = composer.suggest_accessible_color('#8899AA', '#FFFFFF')
            >>> print(f"Use {suggested} instead for better contrast")
        """
        r, g, b = self.hex_to_rgb(base_color)
        bg_r, bg_g, bg_b = self.hex_to_rgb(bg_color)
        bg_lum = self.calculate_luminance(bg_r, bg_g, bg_b)

        # Try darkening or lightening the color
        for adjustment in range(-200, 201, 10):
            new_r = max(0, min(255, r + adjustment))
            new_g = max(0, min(255, g + adjustment))
            new_b = max(0, min(255, b + adjustment))

            new_lum = self.calculate_luminance(new_r, new_g, new_b)

            lighter = max(new_lum, bg_lum)
            darker = min(new_lum, bg_lum)
            ratio = (lighter + 0.05) / (darker + 0.05)

            if ratio >= target_ratio:
                return self.rgb_to_hex(new_r, new_g, new_b)

        return None

    def create_visual_hierarchy(
        self,
        levels: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Create a visual hierarchy definition with multiple levels.

        Args:
            levels: Number of hierarchy levels (default: 3)

        Returns:
            List of dictionaries defining each hierarchy level with:
            - 'level': Level number (1 = most important)
            - 'font_size': Font size in points
            - 'font_weight': 'bold' or 'normal'
            - 'color': Hex color
            - 'usage': Description of when to use this level

        Example:
            >>> hierarchy = composer.create_visual_hierarchy(3)
            >>> for level in hierarchy:
            ...     print(f"Level {level['level']}: {level['font_size']}pt")
        """
        hierarchy = []

        if levels >= 1:
            hierarchy.append({
                'level': 1,
                'font_size': self.tokens.font_sizes['h1'],
                'font_weight': 'bold',
                'color': self.tokens.colors['text_dark'],
                'usage': 'Main headings, slide titles'
            })

        if levels >= 2:
            hierarchy.append({
                'level': 2,
                'font_size': self.tokens.font_sizes['h2'],
                'font_weight': 'bold',
                'color': self.tokens.colors['text_dark'],
                'usage': 'Section headings, subtitles'
            })

        if levels >= 3:
            hierarchy.append({
                'level': 3,
                'font_size': self.tokens.font_sizes['body'],
                'font_weight': 'normal',
                'color': self.tokens.colors['text_light'],
                'usage': 'Body text, content'
            })

        if levels >= 4:
            hierarchy.append({
                'level': 4,
                'font_size': self.tokens.font_sizes['small'],
                'font_weight': 'normal',
                'color': self.tokens.colors['text_light'],
                'usage': 'Captions, footnotes, metadata'
            })

        return hierarchy

    def calculate_optimal_spacing(
        self,
        content_height: float,
        slide_height: float = 405.0
    ) -> Dict[str, float]:
        """
        Calculate optimal spacing for content on a slide.

        Uses the rule of thirds and golden ratio principles.

        Args:
            content_height: Height of content in points
            slide_height: Total slide height in points (default: 405)

        Returns:
            Dictionary with spacing recommendations:
            - 'top_margin': Top margin in points
            - 'bottom_margin': Bottom margin in points
            - 'side_margin': Side margins in points

        Example:
            >>> spacing = composer.calculate_optimal_spacing(200)
            >>> print(f"Top margin: {spacing['top_margin']}pt")
        """
        # Use rule of thirds for vertical positioning
        available_space = slide_height - content_height

        # Golden ratio for top/bottom split
        golden_ratio = 1.618
        total_parts = golden_ratio + 1

        top_margin = available_space * (golden_ratio / total_parts)
        bottom_margin = available_space * (1 / total_parts)

        # Standard side margins (typically 10% of width)
        side_margin = self.tokens.spacing['xl']

        return {
            'top_margin': round(top_margin),
            'bottom_margin': round(bottom_margin),
            'side_margin': side_margin
        }

    def validate_design_system(
        self,
        element_styles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a collection of elements against design system rules.

        Args:
            element_styles: List of element style dictionaries with:
                - 'font_size': Font size in points
                - 'color': Hex color
                - 'bg_color': Background hex color

        Returns:
            Dictionary with validation results:
            - 'valid': bool - Overall validity
            - 'issues': List of validation issues
            - 'warnings': List of warnings

        Example:
            >>> elements = [
            ...     {'font_size': 18, 'color': '#333', 'bg_color': '#FFF'},
            ...     {'font_size': 14, 'color': '#999', 'bg_color': '#FFF'}
            ... ]
            >>> result = composer.validate_design_system(elements)
        """
        issues = []
        warnings = []

        for idx, element in enumerate(element_styles):
            # Validate contrast
            if 'color' in element and 'bg_color' in element:
                font_size = element.get('font_size', 18)
                is_bold = element.get('is_bold', False)

                contrast = self.validate_contrast(
                    element['color'],
                    element['bg_color'],
                    font_size,
                    is_bold
                )

                if not contrast['passes']:
                    issues.append(
                        f"Element {idx + 1}: Insufficient contrast "
                        f"({contrast['ratio']:.2f}:1, requires {contrast['required']}:1)"
                    )

            # Validate font sizes against tokens
            if 'font_size' in element:
                font_size = element['font_size']
                valid_sizes = set(self.tokens.font_sizes.values())

                if font_size not in valid_sizes:
                    warnings.append(
                        f"Element {idx + 1}: Font size {font_size}pt not in design system. "
                        f"Use: {', '.join(map(str, sorted(valid_sizes)))}pt"
                    )

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'total_elements': len(element_styles)
        }

    def get_color_palette_info(self) -> Dict[str, Any]:
        """
        Get information about the current color palette.

        Returns:
            Dictionary with palette information and usage guidelines
        """
        return {
            'primary': {
                'color': self.tokens.colors['primary'],
                'usage': 'Main brand color, primary CTAs, key elements'
            },
            'secondary': {
                'color': self.tokens.colors['secondary'],
                'usage': 'Secondary elements, supporting content'
            },
            'success': {
                'color': self.tokens.colors['success'],
                'usage': 'Success states, positive feedback'
            },
            'warning': {
                'color': self.tokens.colors['warning'],
                'usage': 'Warning states, caution indicators'
            },
            'error': {
                'color': self.tokens.colors['error'],
                'usage': 'Error states, critical information'
            },
            'text': {
                'dark': self.tokens.colors['text_dark'],
                'light': self.tokens.colors['text_light'],
                'usage': 'Dark for headings, light for body text'
            },
            'background': {
                'light': self.tokens.colors['bg_light'],
                'white': self.tokens.colors['bg_white'],
                'usage': 'Slide backgrounds, content areas'
            }
        }

    def calculate_element_positions(
        self,
        slide_width: float,
        slide_height: float,
        elements: List[Dict[str, Any]]
    ) -> List[Dict[str, float]]:
        """
        Calculate optimal positioning for elements on a slide.

        Uses rule of thirds and visual balance principles.

        Args:
            slide_width: Slide width in points (default: 720)
            slide_height: Slide height in points (default: 405)
            elements: List of elements with 'width' and 'height' properties

        Returns:
            List of position dictionaries with 'x', 'y' coordinates

        Example:
            >>> elements = [
            ...     {'width': 300, 'height': 100, 'type': 'title'},
            ...     {'width': 500, 'height': 200, 'type': 'content'}
            ... ]
            >>> positions = composer.calculate_element_positions(720, 405, elements)
            >>> print(f"Title at: ({positions[0]['x']}, {positions[0]['y']})")
        """
        positions = []
        margin = self.tokens.spacing['xl']  # Default margin from edges

        # Rule of thirds points
        third_x = slide_width / 3
        third_y = slide_height / 3

        current_y = margin

        for idx, element in enumerate(elements):
            width = element.get('width', 0)
            height = element.get('height', 0)
            element_type = element.get('type', 'content')

            # Calculate X position (centered by default, or use rule of thirds)
            if element_type == 'title':
                # Center titles
                x = (slide_width - width) / 2
            elif element_type == 'image' and idx % 2 == 0:
                # Alternate images left/right using rule of thirds
                x = third_x - (width / 2)
            elif element_type == 'image':
                x = (third_x * 2) - (width / 2)
            else:
                # Center other content
                x = (slide_width - width) / 2

            # Ensure within margins
            x = max(margin, min(x, slide_width - width - margin))

            positions.append({
                'x': round(x),
                'y': round(current_y)
            })

            # Update Y position for next element
            current_y += height + self.tokens.spacing['md']

        return positions

    def apply_visual_hierarchy(
        self,
        elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply visual hierarchy to elements (size, weight, color).

        Automatically assigns appropriate styling based on element type
        and importance.

        Args:
            elements: List of elements with 'type' and 'content' properties

        Returns:
            List of elements with applied hierarchy styling

        Example:
            >>> elements = [
            ...     {'type': 'title', 'content': 'Main Title'},
            ...     {'type': 'subtitle', 'content': 'Subtitle'},
            ...     {'type': 'body', 'content': 'Body text'}
            ... ]
            >>> styled = composer.apply_visual_hierarchy(elements)
            >>> print(styled[0]['font_size'])  # Title size
            32
        """
        hierarchy = self.create_visual_hierarchy(4)

        styled_elements = []
        for element in elements:
            element_type = element.get('type', 'body')

            # Map element types to hierarchy levels
            if element_type in ['title', 'heading']:
                level = 0  # H1
            elif element_type in ['subtitle', 'subheading']:
                level = 1  # H2
            elif element_type in ['body', 'content']:
                level = 2  # Body
            elif element_type in ['caption', 'footnote']:
                level = 3  # Small
            else:
                level = 2  # Default to body

            # Apply hierarchy styling
            style = hierarchy[min(level, len(hierarchy) - 1)]

            styled_element = element.copy()
            styled_element.update({
                'font_size': style['font_size'],
                'font_weight': style['font_weight'],
                'color': style['color']
            })

            styled_elements.append(styled_element)

        return styled_elements

    def ensure_whitespace(
        self,
        elements: List[Dict[str, Any]],
        min_margin: float = 60.0
    ) -> Dict[str, Any]:
        """
        Ensure adequate whitespace and margins.

        Validates and adjusts element positions to maintain minimum margins
        and spacing between elements.

        Args:
            elements: List of elements with 'x', 'y', 'width', 'height'
            min_margin: Minimum margin from slide edges in points

        Returns:
            Dictionary with validation results and suggested adjustments

        Example:
            >>> elements = [
            ...     {'x': 10, 'y': 10, 'width': 700, 'height': 100}
            ... ]
            >>> result = composer.ensure_whitespace(elements, min_margin=60)
            >>> if result['adjustments_needed']:
            ...     print("Whitespace violations found")
        """
        issues = []
        adjustments = []

        slide_width = 720.0  # Default Google Slides width
        slide_height = 405.0  # Default Google Slides height

        for idx, element in enumerate(elements):
            x = element.get('x', 0)
            y = element.get('y', 0)
            width = element.get('width', 0)
            height = element.get('height', 0)

            # Check left margin
            if x < min_margin:
                issues.append(f"Element {idx + 1}: Left margin too small ({x}pt < {min_margin}pt)")
                adjustments.append({
                    'element_index': idx,
                    'property': 'x',
                    'current': x,
                    'suggested': min_margin
                })

            # Check top margin
            if y < min_margin:
                issues.append(f"Element {idx + 1}: Top margin too small ({y}pt < {min_margin}pt)")
                adjustments.append({
                    'element_index': idx,
                    'property': 'y',
                    'current': y,
                    'suggested': min_margin
                })

            # Check right margin
            right_edge = x + width
            if right_edge > slide_width - min_margin:
                issues.append(
                    f"Element {idx + 1}: Right margin too small "
                    f"({slide_width - right_edge}pt < {min_margin}pt)"
                )

            # Check bottom margin
            bottom_edge = y + height
            if bottom_edge > slide_height - min_margin:
                issues.append(
                    f"Element {idx + 1}: Bottom margin too small "
                    f"({slide_height - bottom_edge}pt < {min_margin}pt)"
                )

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'adjustments_needed': len(adjustments) > 0,
            'adjustments': adjustments,
            'min_margin': min_margin
        }

    def apply_design_tokens(
        self,
        element: Dict[str, Any],
        design_system: Optional[DesignTokens] = None
    ) -> Dict[str, Any]:
        """
        Apply design system tokens to an element.

        Maps element properties to design token values for consistency.

        Args:
            element: Element to style
            design_system: Optional custom design tokens (uses default if None)

        Returns:
            Element with applied design tokens

        Example:
            >>> element = {'type': 'heading', 'content': 'Title'}
            >>> styled = composer.apply_design_tokens(element)
            >>> print(styled['font_size'])
            32
        """
        tokens = design_system or self.tokens
        styled_element = element.copy()

        element_type = element.get('type', 'body')

        # Apply font size from tokens
        if element_type in ['title', 'heading']:
            styled_element['font_size'] = tokens.font_sizes['h1']
            styled_element['font_weight'] = 'bold'
        elif element_type in ['subtitle', 'subheading']:
            styled_element['font_size'] = tokens.font_sizes['h2']
            styled_element['font_weight'] = 'bold'
        elif element_type in ['display', 'hero']:
            styled_element['font_size'] = tokens.font_sizes['display']
            styled_element['font_weight'] = 'bold'
        elif element_type in ['caption', 'footnote']:
            styled_element['font_size'] = tokens.font_sizes['small']
            styled_element['font_weight'] = 'normal'
        else:
            styled_element['font_size'] = tokens.font_sizes['body']
            styled_element['font_weight'] = 'normal'

        # Apply color from tokens
        if 'color' not in styled_element:
            if element_type in ['title', 'heading']:
                styled_element['color'] = tokens.colors['text_dark']
            else:
                styled_element['color'] = tokens.colors['text_light']

        # Apply spacing
        styled_element['margin_bottom'] = tokens.spacing['md']

        return styled_element

    def balance_layout(
        self,
        elements: List[Dict[str, Any]],
        slide_dimensions: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Validate visual balance of layout.

        Analyzes distribution of visual weight across the slide using
        the rule of thirds and center of gravity.

        Args:
            elements: List of elements with position and size
            slide_dimensions: Dictionary with 'width' and 'height'

        Returns:
            Dictionary with balance analysis:
                - 'balanced': bool - Whether layout is balanced
                - 'center_of_gravity': Dict with 'x', 'y'
                - 'recommendations': List of suggestions

        Example:
            >>> elements = [
            ...     {'x': 100, 'y': 100, 'width': 200, 'height': 100},
            ...     {'x': 400, 'y': 200, 'width': 200, 'height': 100}
            ... ]
            >>> balance = composer.balance_layout(elements, {'width': 720, 'height': 405})
            >>> if not balance['balanced']:
            ...     print(balance['recommendations'])
        """
        slide_width = slide_dimensions.get('width', 720)
        slide_height = slide_dimensions.get('height', 405)

        # Calculate center of gravity (weighted average of positions)
        total_weight = 0
        weighted_x = 0
        weighted_y = 0

        for element in elements:
            x = element.get('x', 0)
            y = element.get('y', 0)
            width = element.get('width', 0)
            height = element.get('height', 0)

            # Weight is based on area
            weight = width * height
            center_x = x + (width / 2)
            center_y = y + (height / 2)

            weighted_x += center_x * weight
            weighted_y += center_y * weight
            total_weight += weight

        if total_weight > 0:
            cog_x = weighted_x / total_weight
            cog_y = weighted_y / total_weight
        else:
            cog_x = slide_width / 2
            cog_y = slide_height / 2

        # Check if center of gravity is near slide center
        slide_center_x = slide_width / 2
        slide_center_y = slide_height / 2

        x_deviation = abs(cog_x - slide_center_x)
        y_deviation = abs(cog_y - slide_center_y)

        # Allow 20% deviation from center
        max_x_deviation = slide_width * 0.2
        max_y_deviation = slide_height * 0.2

        balanced = (x_deviation <= max_x_deviation and y_deviation <= max_y_deviation)

        recommendations = []
        if x_deviation > max_x_deviation:
            direction = 'left' if cog_x > slide_center_x else 'right'
            recommendations.append(
                f"Layout is weighted too far {direction}. "
                f"Consider adding elements or adjusting positions."
            )

        if y_deviation > max_y_deviation:
            direction = 'bottom' if cog_y > slide_center_y else 'top'
            recommendations.append(
                f"Layout is weighted too far toward the {direction}. "
                f"Consider redistributing elements."
            )

        return {
            'balanced': balanced,
            'center_of_gravity': {
                'x': round(cog_x),
                'y': round(cog_y)
            },
            'slide_center': {
                'x': slide_center_x,
                'y': slide_center_y
            },
            'deviation': {
                'x': round(x_deviation),
                'y': round(y_deviation)
            },
            'recommendations': recommendations
        }
