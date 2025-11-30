"""
Markdown renderer component for notebook UI.

REFACTORED: This file is now a thin re-export layer.
The implementation has been split into the markdown/ submodule:

    app/ui/components/markdown/
    ├── __init__.py          # Public API exports
    ├── renderer.py          # Main orchestrator
    ├── parser.py            # Markdown parsing logic
    ├── styles.py            # CSS and styling constants
    ├── utils.py             # Utility functions
    ├── toggle_container.py  # Toggle container re-export
    ├── blocks/              # Block type renderers
    │   ├── text.py          # Markdown text blocks
    │   ├── exhibit.py       # Data exhibits
    │   ├── collapsible.py   # Collapsible sections
    │   ├── error.py         # Error blocks
    │   └── header.py        # Notebook headers
    └── editors/             # Editing components
        ├── section_editor.py
        ├── inline_editor.py
        ├── block_editor.py
        └── insert_button.py

All exports from this file are re-exported for backwards compatibility.
New code should import directly from app.ui.components.markdown.
"""

# Re-export everything from the new markdown module
from .markdown import (
    # Main entry point
    render_markdown_notebook,

    # Block renderers
    render_markdown_block,
    render_markdown_content,
    render_exhibit_block,
    render_collapsible_section,
    render_error_block,
    render_notebook_header,
    render_filters_header,

    # Editors
    render_section_editor,
    render_inline_editor,
    render_block_editor,
    render_editable_block,
    render_editable_block_wrapper,
    render_insert_block_button,

    # Styles
    apply_markdown_styles,
    get_block_icon,
    get_block_badge_color,

    # Parser
    get_header_level,
    split_markdown_by_headers,
    build_header_tree,
    extract_header_text,
    gather_section_content,
    count_section_exhibits,

    # Utils
    exhibit_to_syntax,
    exhibit_to_yaml,
    collapsible_to_editable,
    get_default_block_content,

    # Toggle container
    ToggleContainer,
    apply_toggle_styles,
    expand_all,
    collapse_all,
)

# Legacy private function aliases for any internal usage
_render_markdown_content = render_markdown_content
_get_header_level = get_header_level
_split_markdown_by_headers = split_markdown_by_headers
_build_header_tree = build_header_tree
_gather_section_content = gather_section_content
_count_section_exhibits = count_section_exhibits
_exhibit_to_syntax = exhibit_to_syntax
_exhibit_to_yaml = exhibit_to_yaml
_collapsible_to_editable = collapsible_to_editable
_render_insert_block_button = render_insert_block_button
_render_section_editor = render_section_editor
_render_inline_editor = render_inline_editor
_render_editable_block = render_editable_block
_render_block_editor = render_block_editor
_render_block_type_badge = lambda block_type: None  # Deprecated
_get_default_block_content = get_default_block_content

__all__ = [
    'render_markdown_notebook',
    'render_markdown_block',
    'render_markdown_content',
    'render_exhibit_block',
    'render_collapsible_section',
    'render_error_block',
    'render_notebook_header',
    'render_filters_header',
    'apply_markdown_styles',
    'ToggleContainer',
    'apply_toggle_styles',
    'expand_all',
    'collapse_all',
]
