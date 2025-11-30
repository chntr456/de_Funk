"""
Markdown rendering module for notebook UI.

This module provides a modular architecture for rendering markdown notebooks,
split into logical components:

- renderer.py: Main orchestrator
- parser.py: Markdown parsing utilities
- styles.py: CSS styles and constants
- blocks/: Individual block type renderers
- editors/: Editing components

Usage:
    from app.ui.components.markdown import render_markdown_notebook

    render_markdown_notebook(
        notebook_config=config,
        notebook_session=session,
        connection=connection,
        notebook_id="my_notebook",
        editable=True,
        on_block_edit=handle_edit
    )
"""

# Main renderer
from .renderer import render_markdown_notebook

# Block renderers
from .blocks import (
    render_markdown_block,
    render_markdown_content,
    render_exhibit_block,
    render_collapsible_section,
    render_error_block,
    render_notebook_header,
    render_filters_header,
)

# Editor components
from .editors import (
    render_section_editor,
    render_inline_editor,
    render_block_editor,
    render_editable_block,
    render_editable_block_wrapper,
    render_insert_block_button,
)

# Styles
from .styles import apply_markdown_styles, get_block_icon, get_block_badge_color

# Parser utilities
from .parser import (
    get_header_level,
    split_markdown_by_headers,
    build_header_tree,
    extract_header_text,
    gather_section_content,
    count_section_exhibits,
)

# Utility functions
from .utils import (
    exhibit_to_syntax,
    exhibit_to_yaml,
    collapsible_to_editable,
    get_default_block_content,
)

# Toggle container (re-exported from parent)
from .toggle_container import (
    ToggleContainer,
    apply_toggle_styles,
    expand_all,
    collapse_all,
)

__all__ = [
    # Main entry point
    'render_markdown_notebook',

    # Block renderers
    'render_markdown_block',
    'render_markdown_content',
    'render_exhibit_block',
    'render_collapsible_section',
    'render_error_block',
    'render_notebook_header',
    'render_filters_header',

    # Editors
    'render_section_editor',
    'render_inline_editor',
    'render_block_editor',
    'render_editable_block',
    'render_editable_block_wrapper',
    'render_insert_block_button',

    # Styles
    'apply_markdown_styles',
    'get_block_icon',
    'get_block_badge_color',

    # Parser
    'get_header_level',
    'split_markdown_by_headers',
    'build_header_tree',
    'extract_header_text',
    'gather_section_content',
    'count_section_exhibits',

    # Utils
    'exhibit_to_syntax',
    'exhibit_to_yaml',
    'collapsible_to_editable',
    'get_default_block_content',

    # Toggle container
    'ToggleContainer',
    'apply_toggle_styles',
    'expand_all',
    'collapse_all',
]
