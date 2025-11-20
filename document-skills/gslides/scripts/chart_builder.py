#!/usr/bin/env python3
"""
Chart Builder for Google Slides.

Creates and styles charts with Analytics Reporter principles.
Phase 4 component for data visualization and business intelligence.
"""

from typing import Dict, Any, List, Optional, Tuple, Literal
from dataclasses import dataclass
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Chart type definitions
ChartType = Literal[
    'BAR', 'COLUMN', 'LINE', 'AREA',
    'PIE', 'DONUT', 'SCATTER', 'BUBBLE',
    'HISTOGRAM', 'WATERFALL', 'COMBO'
]

DataIntent = Literal[
    'comparison', 'trend', 'composition',
    'distribution', 'relationship'
]


@dataclass
class ChartPosition:
    """Position and size for chart placement."""
    x: int  # Points from left
    y: int  # Points from top
    width: int  # Points
    height: int  # Points

    def to_emu(self) -> Dict[str, Dict[str, int]]:
        """
        Convert points to EMU (English Metric Units) for Google Slides API.

        1 point = 12700 EMU

        Returns:
            Dictionary with transform properties in EMU
        """
        EMU_PER_POINT = 12700

        return {
            'translateX': self.x * EMU_PER_POINT,
            'translateY': self.y * EMU_PER_POINT,
            'scaleX': self.width * EMU_PER_POINT / 914400,  # Normalize scale
            'scaleY': self.height * EMU_PER_POINT / 914400
        }


@dataclass
class ChartData:
    """Structured data for chart creation."""
    labels: List[str]
    datasets: List[Dict[str, Any]]  # Each dataset has 'name' and 'values'
    units: Optional[str] = None
    source: Optional[str] = None
    time_period: Optional[str] = None

    def validate(self) -> bool:
        """
        Validate chart data structure.

        Returns:
            True if data is valid

        Raises:
            ValueError: If data structure is invalid
        """
        if not self.labels:
            raise ValueError("Chart data must have labels")

        if not self.datasets:
            raise ValueError("Chart data must have at least one dataset")

        # Check all datasets have same number of values as labels
        for dataset in self.datasets:
            if 'name' not in dataset:
                raise ValueError("Each dataset must have a 'name'")
            if 'values' not in dataset:
                raise ValueError("Each dataset must have 'values'")
            if len(dataset['values']) != len(self.labels):
                raise ValueError(
                    f"Dataset '{dataset['name']}' has {len(dataset['values'])} values "
                    f"but {len(self.labels)} labels"
                )

        return True


class ChartBuilder:
    """
    Creates and styles charts for Google Slides presentations.

    Implements Analytics Reporter principles:
    - Chart type selection based on data story
    - Brand color application
    - Direct data labeling
    - Context inclusion (units, time periods, sources)
    - Simplicity and clarity
    """

    # Chart type selection based on data intent
    CHART_TYPE_SELECTION: Dict[DataIntent, List[ChartType]] = {
        'comparison': ['BAR', 'COLUMN'],
        'trend': ['LINE', 'AREA'],
        'composition': ['PIE', 'DONUT'],
        'distribution': ['HISTOGRAM', 'SCATTER'],
        'relationship': ['SCATTER', 'BUBBLE']
    }

    # Maximum recommended colors for charts (Analytics Reporter principle)
    MAX_CHART_COLORS = 5

    def __init__(self, slides_service):
        """
        Initialize ChartBuilder.

        Args:
            slides_service: Google Slides API service object
        """
        self.slides_service = slides_service

    def recommend_chart_type(
        self,
        data_intent: DataIntent,
        num_data_points: Optional[int] = None
    ) -> ChartType:
        """
        Recommend chart type based on data story intent.

        Analytics Reporter Principle: Match visualization to data story.

        Args:
            data_intent: The story you want to tell with the data
            num_data_points: Number of data points (affects some recommendations)

        Returns:
            Recommended chart type

        Example:
            >>> chart_type = builder.recommend_chart_type('trend', num_data_points=12)
            >>> # Returns 'LINE' for showing trend over 12 time periods
        """
        recommended_types = self.CHART_TYPE_SELECTION.get(data_intent, ['COLUMN'])

        # Use first recommendation by default
        chart_type = recommended_types[0]

        # Refinement based on data points
        if num_data_points:
            if data_intent == 'comparison':
                # Use horizontal bars for many categories
                if num_data_points > 8:
                    chart_type = 'BAR'
                else:
                    chart_type = 'COLUMN'

            elif data_intent == 'composition':
                # Avoid pie charts with too many slices
                if num_data_points > 7:
                    logger.warning(
                        f"Pie/Donut charts with {num_data_points} slices are hard to read. "
                        "Consider using BAR chart instead."
                    )

        return chart_type

    def apply_brand_colors(
        self,
        chart_spec: Dict[str, Any],
        brand_colors: List[str]
    ) -> Dict[str, Any]:
        """
        Apply brand colors to chart specification.

        Analytics Reporter Principle: Use brand colors, limit to 3-5 colors.

        Args:
            chart_spec: Chart specification to modify
            brand_colors: List of hex color strings from brand guidelines

        Returns:
            Modified chart specification with brand colors applied

        Example:
            >>> colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
            >>> chart_spec = builder.apply_brand_colors(chart_spec, colors)
        """
        # Limit colors to MAX_CHART_COLORS
        colors_to_use = brand_colors[:self.MAX_CHART_COLORS]

        if len(brand_colors) > self.MAX_CHART_COLORS:
            logger.warning(
                f"Using only first {self.MAX_CHART_COLORS} brand colors "
                f"for chart (Analytics Reporter best practice)"
            )

        # Convert hex colors to RGB for API
        rgb_colors = []
        for hex_color in colors_to_use:
            rgb = self._hex_to_rgb(hex_color)
            rgb_colors.append({
                'rgbColor': rgb
            })

        # Apply to chart spec
        if 'basicChart' in chart_spec:
            chart_spec['basicChart']['series'] = chart_spec['basicChart'].get('series', [])
            for idx, series in enumerate(chart_spec['basicChart']['series']):
                color_idx = idx % len(rgb_colors)
                series['color'] = rgb_colors[color_idx]

        return chart_spec

    def add_data_labels(self, chart_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add direct data labels to chart.

        Analytics Reporter Principle: Direct labeling preferred over legends.

        Args:
            chart_spec: Chart specification to modify

        Returns:
            Modified chart specification with data labels enabled
        """
        if 'basicChart' in chart_spec:
            chart_spec['basicChart']['dataLabelOptions'] = {
                'displayOption': 'DATA_VALUE'
            }

        return chart_spec

    def style_chart(
        self,
        chart_spec: Dict[str, Any],
        style_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply comprehensive styling to chart.

        Args:
            chart_spec: Chart specification to modify
            style_config: Style configuration dictionary
                {
                    'title': str,
                    'subtitle': str,
                    'show_legend': bool,
                    'legend_position': 'BOTTOM' | 'TOP' | 'RIGHT' | 'LEFT',
                    'axis_titles': {'x': str, 'y': str},
                    'grid_lines': bool
                }

        Returns:
            Modified chart specification with styling applied

        Example:
            >>> style = {
            ...     'title': 'Q4 Revenue by Region',
            ...     'subtitle': 'In millions USD',
            ...     'show_legend': True,
            ...     'legend_position': 'BOTTOM',
            ...     'axis_titles': {'x': 'Region', 'y': 'Revenue ($M)'}
            ... }
            >>> chart_spec = builder.style_chart(chart_spec, style)
        """
        if 'basicChart' not in chart_spec:
            return chart_spec

        basic_chart = chart_spec['basicChart']

        # Title and subtitle
        if 'title' in style_config:
            basic_chart['chartTitle'] = {
                'title': style_config['title']
            }

        # Legend
        if 'show_legend' in style_config:
            if style_config['show_legend']:
                position = style_config.get('legend_position', 'BOTTOM')
                basic_chart['legendPosition'] = position
            else:
                basic_chart['legendPosition'] = 'NONE'

        # Axis titles
        if 'axis_titles' in style_config:
            axis_titles = style_config['axis_titles']

            if 'x' in axis_titles:
                basic_chart['axis'] = basic_chart.get('axis', [])
                basic_chart['axis'].append({
                    'position': 'BOTTOM_AXIS',
                    'title': axis_titles['x']
                })

            if 'y' in axis_titles:
                basic_chart['axis'] = basic_chart.get('axis', [])
                basic_chart['axis'].append({
                    'position': 'LEFT_AXIS',
                    'title': axis_titles['y']
                })

        return chart_spec

    def create_chart(
        self,
        pres_id: str,
        slide_id: str,
        chart_type: ChartType,
        data: ChartData,
        position: ChartPosition,
        style_config: Optional[Dict[str, Any]] = None,
        brand_colors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a chart with data on a slide.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            chart_type: Type of chart to create
            data: ChartData object with labels, datasets, and context
            position: ChartPosition object for placement
            style_config: Optional styling configuration
            brand_colors: Optional brand color palette

        Returns:
            Response from the batchUpdate API call

        Raises:
            ValueError: If data validation fails

        Example:
            >>> data = ChartData(
            ...     labels=['Q1', 'Q2', 'Q3', 'Q4'],
            ...     datasets=[{
            ...         'name': 'Revenue',
            ...         'values': [120, 145, 160, 180]
            ...     }],
            ...     units='millions USD',
            ...     time_period='2024',
            ...     source='Finance Department'
            ... )
            >>> position = ChartPosition(x=100, y=150, width=500, height=300)
            >>> result = builder.create_chart(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     chart_type='COLUMN',
            ...     data=data,
            ...     position=position
            ... )
        """
        # Validate data
        data.validate()

        # Create chart specification
        chart_spec = self._build_chart_spec(chart_type, data)

        # Apply brand colors if provided
        if brand_colors:
            chart_spec = self.apply_brand_colors(chart_spec, brand_colors)

        # Apply data labels (Analytics Reporter principle)
        chart_spec = self.add_data_labels(chart_spec)

        # Apply styling if provided
        if style_config:
            chart_spec = self.style_chart(chart_spec, style_config)

        # Create element ID for chart
        chart_id = f'chart_{slide_id}_{len(data.labels)}'

        # Convert position to EMU
        transform = position.to_emu()

        # Build request
        request = {
            'createChart': {
                'objectId': chart_id,
                'chartSpec': chart_spec,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': position.width * 12700, 'unit': 'EMU'},
                        'height': {'magnitude': position.height * 12700, 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': transform['translateX'],
                        'translateY': transform['translateY'],
                        'unit': 'EMU'
                    }
                }
            }
        }

        # Execute request
        response = self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(
            f"Created {chart_type} chart on slide {slide_id} "
            f"with {len(data.datasets)} dataset(s)"
        )

        return response

    def create_embedded_chart(
        self,
        pres_id: str,
        slide_id: str,
        spreadsheet_id: str,
        chart_id: int,
        position: ChartPosition,
        link_mode: Literal['LINKED', 'NOT_LINKED_IMAGE'] = 'LINKED'
    ) -> Dict[str, Any]:
        """
        Create a chart linked to Google Sheets data.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            spreadsheet_id: Source Google Sheets spreadsheet ID
            chart_id: Chart ID from the spreadsheet
            position: ChartPosition object for placement
            link_mode: 'LINKED' (updates with sheet) or 'NOT_LINKED_IMAGE' (static)

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> position = ChartPosition(x=100, y=150, width=500, height=300)
            >>> result = builder.create_embedded_chart(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     spreadsheet_id='sheet456...',
            ...     chart_id=789,
            ...     position=position,
            ...     link_mode='LINKED'
            ... )
        """
        # Create element ID
        element_id = f'embedded_chart_{chart_id}'

        # Build request
        request = {
            'createSheetsChart': {
                'objectId': element_id,
                'spreadsheetId': spreadsheet_id,
                'chartId': chart_id,
                'linkingMode': link_mode,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': position.width * 12700, 'unit': 'EMU'},
                        'height': {'magnitude': position.height * 12700, 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': position.x * 12700,
                        'translateY': position.y * 12700,
                        'unit': 'EMU'
                    }
                }
            }
        }

        # Execute request
        response = self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(
            f"Created embedded chart from Sheets (ID: {spreadsheet_id}) "
            f"on slide {slide_id}"
        )

        return response

    def _build_chart_spec(
        self,
        chart_type: ChartType,
        data: ChartData
    ) -> Dict[str, Any]:
        """
        Build chart specification from data.

        Args:
            chart_type: Type of chart
            data: ChartData object

        Returns:
            Chart specification dictionary
        """
        # Map chart types to API types
        type_mapping = {
            'BAR': 'BAR',
            'COLUMN': 'COLUMN',
            'LINE': 'LINE',
            'AREA': 'AREA',
            'PIE': 'PIE',
            'DONUT': 'PIE',  # Donut is a pie with hole
            'SCATTER': 'SCATTER',
            'BUBBLE': 'BUBBLE',
            'HISTOGRAM': 'HISTOGRAM',
            'WATERFALL': 'WATERFALL',
            'COMBO': 'COMBO'
        }

        api_type = type_mapping.get(chart_type, 'COLUMN')

        # Build series data
        series = []
        for dataset in data.datasets:
            series_data = {
                'series': {
                    'sourceRange': {
                        'sources': [
                            {'rowIndex': idx, 'value': value}
                            for idx, value in enumerate(dataset['values'])
                        ]
                    }
                },
                'targetAxis': 'LEFT_AXIS'
            }
            series.append(series_data)

        # Build domains (categories/labels)
        domains = [{
            'domain': {
                'sourceRange': {
                    'sources': [
                        {'rowIndex': idx, 'value': label}
                        for idx, label in enumerate(data.labels)
                    ]
                }
            }
        }]

        # Build basic chart spec
        chart_spec = {
            'basicChart': {
                'chartType': api_type,
                'series': series,
                'domains': domains,
                'headerCount': 1
            }
        }

        # Add donut hole for donut charts
        if chart_type == 'DONUT':
            chart_spec['basicChart']['pieChartSpec'] = {
                'pieHole': 0.5
            }

        return chart_spec

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Dict[str, float]:
        """
        Convert hex color to RGB values (0.0 to 1.0).

        Args:
            hex_color: Hex color string (e.g., '#FF5733' or 'FF5733')

        Returns:
            Dictionary with 'red', 'green', 'blue' keys (values 0.0-1.0)
        """
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB (0-255)
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Convert to 0.0-1.0 range
        return {
            'red': r / 255.0,
            'green': g / 255.0,
            'blue': b / 255.0
        }
