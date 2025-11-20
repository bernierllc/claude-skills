#!/usr/bin/env python3
"""
Brand Guidelines schema for Google Slides presentations.

Defines structured brand identity including colors, typography, logo, spacing,
and voice guidelines for consistent, branded presentations.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class ColorPalette:
    """Brand color palette definition."""
    primary: str  # Hex color code (e.g., '#3b82f6')
    secondary: str  # Hex color code
    accents: List[str] = field(default_factory=list)  # List of accent colors
    neutrals: List[str] = field(default_factory=list)  # Backgrounds and text colors
    forbidden: List[str] = field(default_factory=list)  # Colors to avoid

    def validate(self) -> bool:
        """
        Validate all colors are in valid hex format.

        Returns:
            True if all colors are valid hex codes.

        Raises:
            ValueError: If any color is invalid.
        """
        import re
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')

        colors_to_check = [self.primary, self.secondary] + self.accents + self.neutrals + self.forbidden

        for color in colors_to_check:
            if not hex_pattern.match(color):
                raise ValueError(f"Invalid hex color code: {color}. Must be format #RRGGBB")

        return True


@dataclass
class FontConfig:
    """Font configuration for a specific text role."""
    family: str  # Font family name (e.g., 'Montserrat', 'Open Sans')
    weight: str  # Font weight (e.g., 'regular', 'bold', 'semibold')
    size: Optional[int] = None  # Default size in points (optional)

    def validate(self) -> bool:
        """
        Validate font configuration.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If weight is invalid or size is out of range.
        """
        valid_weights = ['thin', 'light', 'regular', 'medium', 'semibold', 'bold', 'black']

        if self.weight.lower() not in valid_weights:
            raise ValueError(
                f"Invalid font weight: {self.weight}. "
                f"Valid weights: {', '.join(valid_weights)}"
            )

        if self.size is not None and (self.size < 8 or self.size > 96):
            raise ValueError(f"Font size must be between 8 and 96 points, got {self.size}")

        return True


@dataclass
class Typography:
    """Typography configuration for brand."""
    headline: FontConfig
    subhead: Optional[FontConfig] = None
    body: Optional[FontConfig] = None
    caption: Optional[FontConfig] = None

    def validate(self) -> bool:
        """
        Validate all font configurations.

        Returns:
            True if all configurations are valid.
        """
        self.headline.validate()
        if self.subhead:
            self.subhead.validate()
        if self.body:
            self.body.validate()
        if self.caption:
            self.caption.validate()

        return True


@dataclass
class LogoConfig:
    """Logo configuration for brand."""
    url: Optional[str] = None  # URL or path to logo image
    placement: str = 'bottom-right'  # Logo placement (e.g., 'bottom-right', 'top-left')
    min_size: int = 40  # Minimum size in points
    max_size: int = 100  # Maximum size in points

    def validate(self) -> bool:
        """
        Validate logo configuration.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If placement is invalid or sizes are out of range.
        """
        valid_placements = [
            'top-left', 'top-center', 'top-right',
            'bottom-left', 'bottom-center', 'bottom-right'
        ]

        if self.placement not in valid_placements:
            raise ValueError(
                f"Invalid logo placement: {self.placement}. "
                f"Valid placements: {', '.join(valid_placements)}"
            )

        if self.min_size <= 0 or self.max_size <= 0:
            raise ValueError("Logo sizes must be positive")

        if self.min_size > self.max_size:
            raise ValueError(f"min_size ({self.min_size}) cannot exceed max_size ({self.max_size})")

        return True


@dataclass
class SpacingConfig:
    """Spacing configuration for brand."""
    slide_margin: int = 60  # Minimum margin from slide edges in points
    element_gap: int = 20  # Minimum gap between elements in points
    title_spacing: int = 40  # Space between title and content in points
    section_spacing: int = 30  # Space between sections in points

    def validate(self) -> bool:
        """
        Validate spacing configuration.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If any spacing value is negative.
        """
        if any([
            self.slide_margin < 0,
            self.element_gap < 0,
            self.title_spacing < 0,
            self.section_spacing < 0
        ]):
            raise ValueError("All spacing values must be non-negative")

        return True


@dataclass
class VoiceConfig:
    """Brand voice and personality configuration."""
    tone: str = 'professional'  # Tone (e.g., 'professional', 'casual', 'friendly')
    personality: List[str] = field(default_factory=list)  # Personality traits
    language_style: str = 'formal'  # Language style (e.g., 'formal', 'conversational')

    def validate(self) -> bool:
        """
        Validate voice configuration.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If tone or language_style is invalid.
        """
        valid_tones = ['professional', 'casual', 'friendly', 'authoritative', 'playful']
        valid_styles = ['formal', 'conversational', 'technical', 'simple']

        if self.tone not in valid_tones:
            raise ValueError(
                f"Invalid tone: {self.tone}. "
                f"Valid tones: {', '.join(valid_tones)}"
            )

        if self.language_style not in valid_styles:
            raise ValueError(
                f"Invalid language style: {self.language_style}. "
                f"Valid styles: {', '.join(valid_styles)}"
            )

        return True


@dataclass
class RequiredElements:
    """Required elements for brand compliance."""
    footer_text: Optional[str] = None  # Footer text to include on all slides
    slide_numbers: bool = True  # Whether to include slide numbers
    logo: bool = True  # Whether to include logo
    date: bool = False  # Whether to include date
    custom_elements: List[str] = field(default_factory=list)  # Custom required elements


@dataclass
class BrandGuidelines:
    """
    Complete brand guidelines for presentations.

    Defines all visual identity elements including colors, typography, logo,
    spacing, voice, and required elements for consistent branded presentations.

    Attributes:
        name: Brand or organization name
        colors: Color palette configuration
        typography: Typography configuration
        logo: Logo configuration (optional)
        spacing: Spacing configuration
        voice: Brand voice configuration (optional)
        required_elements: Required elements configuration (optional)

    Example:
        >>> # Create brand guidelines
        >>> brand = BrandGuidelines(
        ...     name='Acme Corp',
        ...     colors=ColorPalette(
        ...         primary='#3b82f6',
        ...         secondary='#6b7280',
        ...         accents=['#10b981', '#f59e0b'],
        ...         neutrals=['#f9fafb', '#111827']
        ...     ),
        ...     typography=Typography(
        ...         headline=FontConfig(family='Montserrat', weight='bold', size=44),
        ...         body=FontConfig(family='Open Sans', weight='regular', size=18)
        ...     )
        ... )
        >>> brand.validate()
        True
    """

    name: str
    colors: ColorPalette
    typography: Typography
    logo: Optional[LogoConfig] = None
    spacing: SpacingConfig = field(default_factory=SpacingConfig)
    voice: Optional[VoiceConfig] = None
    required_elements: Optional[RequiredElements] = None

    def validate(self) -> bool:
        """
        Validate all brand guideline components.

        Returns:
            True if all components are valid.

        Raises:
            ValueError: If any component is invalid.

        Example:
            >>> brand = BrandGuidelines(...)
            >>> try:
            ...     brand.validate()
            ...     print("Brand guidelines are valid")
            ... except ValueError as e:
            ...     print(f"Validation error: {e}")
        """
        # Validate name
        if not self.name or not self.name.strip():
            raise ValueError("Brand name cannot be empty")

        # Validate colors
        self.colors.validate()

        # Validate typography
        self.typography.validate()

        # Validate logo if present
        if self.logo:
            self.logo.validate()

        # Validate spacing
        self.spacing.validate()

        # Validate voice if present
        if self.voice:
            self.voice.validate()

        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert brand guidelines to dictionary.

        Returns:
            Dictionary representation of brand guidelines.

        Example:
            >>> brand = BrandGuidelines(...)
            >>> data = brand.to_dict()
            >>> print(data['name'])
            'Acme Corp'
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrandGuidelines':
        """
        Create brand guidelines from dictionary.

        Args:
            data: Dictionary with brand guideline data.

        Returns:
            BrandGuidelines instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If validation fails.

        Example:
            >>> data = {
            ...     'name': 'Acme Corp',
            ...     'colors': {
            ...         'primary': '#3b82f6',
            ...         'secondary': '#6b7280',
            ...         'accents': ['#10b981'],
            ...         'neutrals': ['#f9fafb']
            ...     },
            ...     'typography': {
            ...         'headline': {'family': 'Montserrat', 'weight': 'bold'}
            ...     }
            ... }
            >>> brand = BrandGuidelines.from_dict(data)
            >>> brand.validate()
        """
        # Parse colors
        color_data = data.get('colors', {})
        colors = ColorPalette(
            primary=color_data.get('primary', '#000000'),
            secondary=color_data.get('secondary', '#666666'),
            accents=color_data.get('accents', []),
            neutrals=color_data.get('neutrals', []),
            forbidden=color_data.get('forbidden', [])
        )

        # Parse typography
        typo_data = data.get('typography', {})

        headline_data = typo_data.get('headline', {})
        headline = FontConfig(
            family=headline_data.get('family', 'Arial'),
            weight=headline_data.get('weight', 'bold'),
            size=headline_data.get('size')
        )

        subhead = None
        if 'subhead' in typo_data:
            subhead_data = typo_data['subhead']
            subhead = FontConfig(
                family=subhead_data.get('family', headline.family),
                weight=subhead_data.get('weight', 'semibold'),
                size=subhead_data.get('size')
            )

        body = None
        if 'body' in typo_data:
            body_data = typo_data['body']
            body = FontConfig(
                family=body_data.get('family', 'Arial'),
                weight=body_data.get('weight', 'regular'),
                size=body_data.get('size')
            )

        caption = None
        if 'caption' in typo_data:
            caption_data = typo_data['caption']
            caption = FontConfig(
                family=caption_data.get('family', body.family if body else 'Arial'),
                weight=caption_data.get('weight', 'regular'),
                size=caption_data.get('size')
            )

        typography = Typography(
            headline=headline,
            subhead=subhead,
            body=body,
            caption=caption
        )

        # Parse logo
        logo = None
        if 'logo' in data:
            logo_data = data['logo']
            logo = LogoConfig(
                url=logo_data.get('url'),
                placement=logo_data.get('placement', 'bottom-right'),
                min_size=logo_data.get('min_size', 40),
                max_size=logo_data.get('max_size', 100)
            )

        # Parse spacing
        spacing_data = data.get('spacing', {})
        spacing = SpacingConfig(
            slide_margin=spacing_data.get('slide_margin', 60),
            element_gap=spacing_data.get('element_gap', 20),
            title_spacing=spacing_data.get('title_spacing', 40),
            section_spacing=spacing_data.get('section_spacing', 30)
        )

        # Parse voice
        voice = None
        if 'voice' in data:
            voice_data = data['voice']
            voice = VoiceConfig(
                tone=voice_data.get('tone', 'professional'),
                personality=voice_data.get('personality', []),
                language_style=voice_data.get('language_style', 'formal')
            )

        # Parse required elements
        required_elements = None
        if 'required_elements' in data:
            req_data = data['required_elements']
            required_elements = RequiredElements(
                footer_text=req_data.get('footer_text'),
                slide_numbers=req_data.get('slide_numbers', True),
                logo=req_data.get('logo', True),
                date=req_data.get('date', False),
                custom_elements=req_data.get('custom_elements', [])
            )

        # Create brand guidelines
        brand = cls(
            name=data.get('name', 'Unnamed Brand'),
            colors=colors,
            typography=typography,
            logo=logo,
            spacing=spacing,
            voice=voice,
            required_elements=required_elements
        )

        # Validate
        brand.validate()

        return brand

    @classmethod
    def from_json_file(cls, file_path: str) -> 'BrandGuidelines':
        """
        Load brand guidelines from JSON file.

        Args:
            file_path: Path to JSON file containing brand guidelines.

        Returns:
            BrandGuidelines instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            json.JSONDecodeError: If file contains invalid JSON.
            ValueError: If validation fails.

        Example:
            >>> brand = BrandGuidelines.from_json_file('brand.json')
            >>> print(f"Loaded brand: {brand.name}")
        """
        with open(file_path, 'r') as f:
            data = json.load(f)

        return cls.from_dict(data)

    def to_json_file(self, file_path: str):
        """
        Save brand guidelines to JSON file.

        Args:
            file_path: Path where to save the JSON file.

        Example:
            >>> brand = BrandGuidelines(...)
            >>> brand.to_json_file('brand.json')
        """
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
