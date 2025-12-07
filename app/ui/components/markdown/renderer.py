"""
Main markdown notebook renderer.

This is the orchestrator that coordinates rendering of markdown notebooks
using the modular block renderers, editors, and parser utilities.
"""

import streamlit as st
from typing import Dict, Any, List, Optional, Callable

from app.notebook.schema import NotebookConfig

from .toggle_container import ToggleContainer, apply_toggle_styles, expand_all, collapse_all
from .styles import apply_markdown_styles, get_block_icon
from .parser import build_header_tree, gather_section_content, count_section_exhibits
from .blocks import (
    render_markdown_block,
    render_markdown_content,
    render_exhibit_block,
    render_collapsible_section,
    render_error_block,
    render_notebook_header,
    render_filters_header,
)
from .editors import (
    render_section_editor,
    render_inline_editor,
    render_editable_block,
    render_insert_block_button,
)


def render_markdown_notebook(
    notebook_config: NotebookConfig,
    notebook_session,
    connection,
    notebook_id: str = "default",
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_insert: Optional[Callable[[int, str, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None,
    on_header_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render a markdown-based notebook.

    Args:
        notebook_config: NotebookConfig with markdown content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        notebook_id: Unique ID for this notebook (used for collapse/expand all)
        editable: Whether blocks can be edited inline
        on_block_edit: Callback when a block is edited (block_index, new_content)
        on_block_insert: Callback when a block is inserted (after_index, block_type, content)
        on_block_delete: Callback when a block is deleted (block_index)
        on_header_edit: Callback when a header is renamed (block_index, new_header)
    """
    if not hasattr(notebook_config, '_content_blocks') or not notebook_config._content_blocks:
        st.error("This notebook has no markdown content blocks")
        return

    # Apply toggle container styles
    apply_toggle_styles()

    # Toolbar with expand/collapse buttons on the right
    cols = st.columns([0.88, 0.06, 0.06])
    with cols[1]:
        if st.button("⊞", key=f"exp_{notebook_id}", help="Expand all sections"):
            expand_all(notebook_id)
            st.rerun()
    with cols[2]:
        if st.button("⊟", key=f"col_{notebook_id}", help="Collapse all sections"):
            collapse_all(notebook_id)
            st.rerun()

    # Build nested tree structure from header hierarchy
    try:
        nested_blocks = build_header_tree(notebook_config._content_blocks)
    except Exception as e:
        st.error(f"Error building notebook structure: {str(e)}")
        import traceback
        st.code(traceback.format_exc()[:1000])
        return

    # Insert block button at start if editable
    if editable:
        render_insert_block_button(-1, on_block_insert)

    # Render blocks with nested toggle containers based on header hierarchy
    try:
        _render_nested_toggles(
            blocks=nested_blocks,
            notebook_session=notebook_session,
            connection=connection,
            context=notebook_id,
            editable=editable,
            on_block_edit=on_block_edit,
            on_block_insert=on_block_insert,
            on_block_delete=on_block_delete
        )
    except Exception as e:
        st.error(f"Error rendering notebook content: {str(e)}")
        import traceback
        st.code(traceback.format_exc()[:1000])


def _render_nested_toggles(
    blocks: List[Dict[str, Any]],
    notebook_session,
    connection,
    context: str = "default",
    depth: int = 0,
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_insert: Optional[Callable[[int, str, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None
):
    """
    Render blocks with nested toggle containers based on header hierarchy.

    Args:
        blocks: List of blocks (may have 'children' for nested content)
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        context: Context for collapse/expand all functionality
        depth: Current nesting depth
        editable: Whether blocks can be edited
        on_block_edit: Callback when block content is edited
        on_block_insert: Callback when block is inserted
        on_block_delete: Callback when block is deleted
    """
    for block in blocks:
        block_type = block['type']
        block_index = block.get('_index', 0)
        children = block.get('children', [])
        header_level = block.get('_header_level', 0)

        # Determine toggle label and icon
        if block_type == 'markdown':
            content = block.get('content', '')
            lines = content.strip().split('\n')
            first_line = lines[0] if lines else 'Text'
            if first_line.startswith('#'):
                label = first_line.lstrip('#').strip()
            else:
                label = first_line[:40] + '...' if len(first_line) > 40 else first_line
                if not label:
                    label = 'Text Block'
            toggle_icon = "📝" if header_level == 0 else "📑"

        elif block_type == 'exhibit':
            exhibit = block.get('exhibit')
            label = exhibit.title if exhibit and exhibit.title else f"Exhibit {block_index + 1}"
            toggle_icon = "📊"

        elif block_type == 'collapsible':
            label = block.get('summary', 'Section')
            toggle_icon = "📁"

        elif block_type == 'error':
            label = "Error"
            toggle_icon = "⚠️"

        else:
            label = f"Block {block_index + 1}"
            toggle_icon = "📄"

        # Apply depth-based indentation using columns (only at depth 1 and when NOT editable)
        # Streamlit only allows one level of nested columns, and render_editable_block uses columns
        # So we can only indent when not in edit mode
        if depth == 1 and not editable:
            indent_ratio = 0.03  # 3% indent for nested content
            _, content_col = st.columns([indent_ratio, 1 - indent_ratio])
            block_container = content_col
        else:
            block_container = st.container()

        with block_container:
            # Header blocks with children get a toggle container
            if header_level > 0 and children:
                # Render header with nested content in toggle
                with ToggleContainer(
                    f"{toggle_icon} {label}",
                    expanded=True,
                    container_id=f"section_{block_index}",
                    style="section",
                    context=context
                ) as tc:
                    if tc.is_open:
                        # Render any non-header content from this block
                        if block_type == 'markdown':
                            content = block.get('content', '')
                            # Skip the header line, render the rest
                            lines = content.strip().split('\n')
                            body_lines = lines[1:] if lines and lines[0].startswith('#') else lines
                            body_content = '\n'.join(body_lines).strip()
                            if body_content:
                                if editable:
                                    render_editable_block(
                                        block_index,
                                        {'type': 'markdown', 'content': body_content},
                                        notebook_session,
                                        connection,
                                        on_block_edit,
                                        on_block_delete
                                    )
                                else:
                                    render_markdown_content(body_content)

                        # Render children
                        _render_nested_toggles(
                            blocks=children,
                            notebook_session=notebook_session,
                            connection=connection,
                            context=context,
                            depth=depth + 1,
                            editable=editable,
                            on_block_edit=on_block_edit,
                            on_block_insert=on_block_insert,
                            on_block_delete=on_block_delete
                        )

                        # Insert button after section if editable
                        if editable:
                            render_insert_block_button(block_index, on_block_insert)

            elif block_type == 'exhibit':
                # Render exhibit directly (it handles its own collapsibility)
                if editable:
                    render_editable_block(
                        block_index, block, notebook_session, connection,
                        on_block_edit, on_block_delete
                    )
                else:
                    render_exhibit_block(block, notebook_session, connection)

                if editable:
                    render_insert_block_button(block_index, on_block_insert)

            elif block_type == 'collapsible':
                render_collapsible_section(block, notebook_session, connection, block_index)
                if editable:
                    render_insert_block_button(block_index, on_block_insert)

            elif block_type == 'error':
                render_error_block(block, block_index)
                if editable:
                    render_insert_block_button(block_index, on_block_insert)

            elif block_type == 'markdown':
                # Non-header markdown or header without children
                if header_level > 0:
                    # Header without children - render as toggle
                    with ToggleContainer(
                        f"{toggle_icon} {label}",
                        expanded=True,
                        container_id=f"header_{block_index}",
                        style="section",
                        context=context
                    ) as tc:
                        if tc.is_open:
                            content = block.get('content', '')
                            lines = content.strip().split('\n')
                            body_lines = lines[1:] if lines and lines[0].startswith('#') else lines
                            body_content = '\n'.join(body_lines).strip()
                            if body_content:
                                if editable:
                                    render_editable_block(
                                        block_index,
                                        {'type': 'markdown', 'content': body_content},
                                        notebook_session, connection,
                                        on_block_edit, on_block_delete
                                    )
                                else:
                                    render_markdown_content(body_content)
                else:
                    # Regular markdown content
                    if editable:
                        render_editable_block(
                            block_index, block, notebook_session, connection,
                            on_block_edit, on_block_delete
                        )
                    else:
                        render_markdown_block(
                            block.get('content', ''),
                            in_collapsible=False,
                            block_index=block_index
                        )

                if editable:
                    render_insert_block_button(block_index, on_block_insert)

            else:
                # Unknown block type - render as error
                st.warning(f"Unknown block type: {block_type}")
                if editable:
                    render_insert_block_button(block_index, on_block_insert)
