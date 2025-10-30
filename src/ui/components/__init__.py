"""
UI components for the notebook application.

This package contains modular components for:
- Theme styling
- Sidebar navigation
- Filters
- Exhibit rendering
- YAML editor
- Notebook view
"""

from .theme import apply_professional_theme
from .sidebar import SidebarNavigator, close_tab
from .filters import render_filters_section
from .yaml_editor import render_yaml_editor
from .notebook_view import render_notebook_exhibits

__all__ = [
    'apply_professional_theme',
    'SidebarNavigator',
    'close_tab',
    'render_filters_section',
    'render_yaml_editor',
    'render_notebook_exhibits',
]
