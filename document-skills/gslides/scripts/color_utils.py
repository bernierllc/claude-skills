#!/usr/bin/env python3
"""
Color utility functions for Google Slides.

Provides color conversion, validation, contrast calculation, and palette generation
utilities for creating accessible and visually appealing presentations.
"""

import re
import colorsys
from typing import Dict, List, Tuple, Optional


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert hex color to RGB tuple with values 0.0-1.0.

    Args:
        hex_color: Hex color code (e.g., '#3b82f6' or '3b82f6')

    Returns:
        Tuple of (red, green, blue) with values from 0.0 to 1.0

    Raises:
        ValueError: If hex_color is not a valid hex color code

    Example:
        >>> hex_to_rgb('#3b82f6')
        (0.23137254901960785, 0.5098039215686274, 0.9647058823529412)
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')

    # Validate format
    if not re.match(r'^[0-9A-Fa-f]{6}$', hex_color):
        raise ValueError(f"Invalid hex color: #{hex_color}. Must be format #RRGGBB")

    # Convert to RGB (0-255)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Normalize to 0.0-1.0
    return (r / 255.0, g / 255.0, b / 255.0)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """
    Convert RGB values (0.0-1.0) to hex color code.

    Args:
        r: Red component (0.0-1.0)
        g: Green component (0.0-1.0)
        b: Blue component (0.0-1.0)

    Returns:
        Hex color code (e.g., '#3b82f6')

    Raises:
        ValueError: If any RGB value is out of range

    Example:
        >>> rgb_to_hex(0.23, 0.51, 0.96)
        '#3a82f5'
    """
    # Validate range
    if not (0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0):
        raise ValueError(f"RGB values must be between 0.0 and 1.0, got ({r}, {g}, {b})")

    # Convert to 0-255 range
    r_int = int(round(r * 255))
    g_int = int(round(g * 255))
    b_int = int(round(b * 255))

    # Format as hex
    return f"#{r_int:02x}{g_int:02x}{b_int:02x}"


def hex_to_gslides_color(hex_color: str) -> Dict[str, float]:
    """
    Convert hex color to Google Slides API color format.

    Args:
        hex_color: Hex color code (e.g., '#3b82f6')

    Returns:
        Dictionary with 'red', 'green', 'blue' keys and 0.0-1.0 values

    Example:
        >>> hex_to_gslides_color('#3b82f6')
        {'red': 0.23137254901960785, 'green': 0.5098039215686274, 'blue': 0.9647058823529412}
    """
    r, g, b = hex_to_rgb(hex_color)
    return {
        'red': r,
        'green': g,
        'blue': b
    }


def gslides_color_to_hex(color: Dict[str, float]) -> str:
    """
    Convert Google Slides API color format to hex.

    Args:
        color: Dictionary with 'red', 'green', 'blue' keys (0.0-1.0)

    Returns:
        Hex color code (e.g., '#3b82f6')

    Example:
        >>> gslides_color_to_hex({'red': 0.23, 'green': 0.51, 'blue': 0.96})
        '#3a82f5'
    """
    r = color.get('red', 0.0)
    g = color.get('green', 0.0)
    b = color.get('blue', 0.0)
    return rgb_to_hex(r, g, b)


def calculate_relative_luminance(r: float, g: float, b: float) -> float:
    """
    Calculate relative luminance for contrast calculations (WCAG formula).

    Args:
        r: Red component (0.0-1.0)
        g: Green component (0.0-1.0)
        b: Blue component (0.0-1.0)

    Returns:
        Relative luminance value (0.0-1.0)

    Example:
        >>> calculate_relative_luminance(1.0, 1.0, 1.0)  # White
        1.0
        >>> calculate_relative_luminance(0.0, 0.0, 0.0)  # Black
        0.0
    """
    # Apply gamma correction (WCAG formula)
    def adjust(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    r_adj = adjust(r)
    g_adj = adjust(g)
    b_adj = adjust(b)

    # Calculate luminance (WCAG formula)
    return 0.2126 * r_adj + 0.7152 * g_adj + 0.0722 * b_adj


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two hex colors.

    WCAG 2.1 requirements:
    - AA (normal text): 4.5:1
    - AA (large text 18pt+): 3:1
    - AAA (normal text): 7:1
    - AAA (large text): 4.5:1

    Args:
        color1: First hex color (e.g., '#3b82f6')
        color2: Second hex color (e.g., '#ffffff')

    Returns:
        Contrast ratio (1.0-21.0, higher is better)

    Example:
        >>> ratio = calculate_contrast_ratio('#000000', '#ffffff')
        >>> print(f"Contrast ratio: {ratio:.2f}:1")
        Contrast ratio: 21.00:1
    """
    # Convert to RGB
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)

    # Calculate luminance
    l1 = calculate_relative_luminance(r1, g1, b1)
    l2 = calculate_relative_luminance(r2, g2, b2)

    # Calculate contrast ratio
    lighter = max(l1, l2)
    darker = min(l1, l2)

    return (lighter + 0.05) / (darker + 0.05)


def validate_contrast(foreground: str, background: str, level: str = 'AA') -> bool:
    """
    Validate if color contrast meets WCAG standards.

    Args:
        foreground: Foreground hex color (text color)
        background: Background hex color
        level: WCAG level ('AA' or 'AAA')

    Returns:
        True if contrast meets the standard

    Raises:
        ValueError: If level is not 'AA' or 'AAA'

    Example:
        >>> validate_contrast('#000000', '#ffffff', 'AA')
        True
        >>> validate_contrast('#777777', '#888888', 'AA')
        False
    """
    if level not in ['AA', 'AAA']:
        raise ValueError(f"Invalid WCAG level: {level}. Must be 'AA' or 'AAA'")

    ratio = calculate_contrast_ratio(foreground, background)

    # WCAG AA requires 4.5:1 for normal text, 3:1 for large text
    # We use the stricter requirement (normal text)
    if level == 'AA':
        return ratio >= 4.5
    else:  # AAA
        return ratio >= 7.0


def adjust_brightness(hex_color: str, factor: float) -> str:
    """
    Adjust brightness of a color.

    Args:
        hex_color: Hex color code
        factor: Brightness factor (< 1.0 darker, > 1.0 lighter)

    Returns:
        Adjusted hex color code

    Example:
        >>> adjust_brightness('#3b82f6', 1.2)  # Make lighter
        '#4798ff'
        >>> adjust_brightness('#3b82f6', 0.8)  # Make darker
        '#2f68c5'
    """
    r, g, b = hex_to_rgb(hex_color)

    # Adjust brightness
    r = max(0.0, min(1.0, r * factor))
    g = max(0.0, min(1.0, g * factor))
    b = max(0.0, min(1.0, b * factor))

    return rgb_to_hex(r, g, b)


def adjust_saturation(hex_color: str, factor: float) -> str:
    """
    Adjust saturation of a color.

    Args:
        hex_color: Hex color code
        factor: Saturation factor (< 1.0 less saturated, > 1.0 more saturated)

    Returns:
        Adjusted hex color code

    Example:
        >>> adjust_saturation('#3b82f6', 0.5)  # Less saturated
        '#6d93f6'
        >>> adjust_saturation('#3b82f6', 1.5)  # More saturated
        '#0962ff'
    """
    r, g, b = hex_to_rgb(hex_color)

    # Convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Adjust saturation
    s = max(0.0, min(1.0, s * factor))

    # Convert back to RGB
    r, g, b = colorsys.hsv_to_rgb(h, s, v)

    return rgb_to_hex(r, g, b)


def generate_palette_from_primary(primary: str, include_neutrals: bool = True) -> Dict[str, str]:
    """
    Generate a complete color palette from a primary color.

    Creates a harmonious palette with complementary and accent colors.

    Args:
        primary: Primary hex color
        include_neutrals: Whether to include neutral colors

    Returns:
        Dictionary with 'primary', 'secondary', 'accents', and optionally 'neutrals'

    Example:
        >>> palette = generate_palette_from_primary('#3b82f6')
        >>> print(palette['primary'])
        '#3b82f6'
        >>> print(len(palette['accents']))
        2
    """
    r, g, b = hex_to_rgb(primary)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    palette = {
        'primary': primary,
        'secondary': None,
        'accents': []
    }

    # Generate secondary (complementary color - opposite on color wheel)
    h_secondary = (h + 0.5) % 1.0
    r_sec, g_sec, b_sec = colorsys.hsv_to_rgb(h_secondary, s * 0.6, v * 0.8)
    palette['secondary'] = rgb_to_hex(r_sec, g_sec, b_sec)

    # Generate accents (triadic colors)
    h_accent1 = (h + 0.33) % 1.0
    h_accent2 = (h + 0.67) % 1.0

    r_a1, g_a1, b_a1 = colorsys.hsv_to_rgb(h_accent1, s * 0.8, v * 0.9)
    r_a2, g_a2, b_a2 = colorsys.hsv_to_rgb(h_accent2, s * 0.8, v * 0.9)

    palette['accents'] = [
        rgb_to_hex(r_a1, g_a1, b_a1),
        rgb_to_hex(r_a2, g_a2, b_a2)
    ]

    # Generate neutrals if requested
    if include_neutrals:
        palette['neutrals'] = [
            '#f9fafb',  # Very light gray (backgrounds)
            '#e5e7eb',  # Light gray
            '#9ca3af',  # Medium gray
            '#6b7280',  # Dark gray
            '#374151',  # Darker gray
            '#111827'   # Near black (text)
        ]

    return palette


def get_accessible_text_color(background: str) -> str:
    """
    Get an accessible text color (black or white) for a given background.

    Automatically chooses black or white text based on WCAG contrast requirements.

    Args:
        background: Background hex color

    Returns:
        '#000000' or '#ffffff' depending on which provides better contrast

    Example:
        >>> get_accessible_text_color('#3b82f6')  # Blue background
        '#ffffff'  # Returns white
        >>> get_accessible_text_color('#f9fafb')  # Light gray background
        '#000000'  # Returns black
    """
    # Calculate contrast with black and white
    black_contrast = calculate_contrast_ratio('#000000', background)
    white_contrast = calculate_contrast_ratio('#ffffff', background)

    # Return the one with better contrast
    return '#000000' if black_contrast > white_contrast else '#ffffff'


def suggest_font_pairing(font_family: str) -> Dict[str, str]:
    """
    Suggest font pairings based on a primary font.

    Returns recommended complementary fonts for different text roles.

    Args:
        font_family: Primary font family name

    Returns:
        Dictionary with 'headline', 'body', and 'caption' font suggestions

    Example:
        >>> pairing = suggest_font_pairing('Montserrat')
        >>> print(pairing['body'])
        'Open Sans'
    """
    # Common pairings based on design best practices
    pairings = {
        'montserrat': {'headline': 'Montserrat', 'body': 'Open Sans', 'caption': 'Open Sans'},
        'roboto': {'headline': 'Roboto', 'body': 'Roboto', 'caption': 'Roboto'},
        'playfair display': {'headline': 'Playfair Display', 'body': 'Source Sans Pro', 'caption': 'Source Sans Pro'},
        'lato': {'headline': 'Lato', 'body': 'Lato', 'caption': 'Lato'},
        'raleway': {'headline': 'Raleway', 'body': 'Open Sans', 'caption': 'Open Sans'},
        'oswald': {'headline': 'Oswald', 'body': 'Open Sans', 'caption': 'Open Sans'},
        'merriweather': {'headline': 'Merriweather', 'body': 'Open Sans', 'caption': 'Open Sans'},
        'ubuntu': {'headline': 'Ubuntu', 'body': 'Ubuntu', 'caption': 'Ubuntu'},
        'nunito': {'headline': 'Nunito', 'body': 'Nunito', 'caption': 'Nunito'},
        'poppins': {'headline': 'Poppins', 'body': 'Poppins', 'caption': 'Poppins'},
    }

    font_lower = font_family.lower()

    # Return pairing if found, otherwise return sensible defaults
    if font_lower in pairings:
        return pairings[font_lower]
    else:
        return {
            'headline': font_family,
            'body': 'Open Sans',  # Safe default
            'caption': 'Open Sans'
        }
