"""
Google Slides Editor Scripts Package.

Provides core functionality for working with Google Slides API.
"""

from .auth_manager import AuthManager
from .gslides_editor import GoogleSlidesEditor, PresentationAnalysis
from .layout_manager import LayoutManager, LayoutInfo

__all__ = [
    'AuthManager',
    'GoogleSlidesEditor',
    'PresentationAnalysis',
    'LayoutManager',
    'LayoutInfo',
]
