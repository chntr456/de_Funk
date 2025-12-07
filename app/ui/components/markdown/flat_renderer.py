"""
Flat row-based renderer for markdown notebooks.

This renderer avoids Streamlit's nested column limitations by:
1. Flattening the hierarchical block structure into a list
2. Rendering each block as an independent row with columns
3. Using visibility state to show/hide children when parents collapse
4. Applying indentation via column width, not nested columns

Each row has a consistent column layout:
[indent_spacer | toggle_btn | content | edit_btn | delete_btn]
"""

import streamlit as st
from typing import Dict, Any, List, Optional, Callable

from .blocks import (
    render_markdown_content,
    render_exhibit_block,
    render_collapsible_section,
    render_error_block,
)
from .editors import render_block_editor
from .styles import apply_markdown_styles


# Session state keys
TOGGLE_STATE_KEY = "flat_renderer_toggle_states"
EDIT_STATE_KEY = "flat_renderer_edit_states"


def flatten_blocks(
    blocks: List[Dict[str, Any]],
    parent_id: Optional[str] = None,
    depth: int = 0
) -> List[Dict[str, Any]]:
    """
    Flatten nested block structure into a flat list with hierarchy metadata.

    Args:
        blocks: List of blocks (may have 'children' for nested content)
        parent_id: ID of the parent block (None for root level)
        depth: Current nesting depth

    Returns:
        Flat list of blocks with added metadata:
        - _flat_id: Unique ID for this block
        - _depth: Nesting depth (0 = root)
        - _parent_id: ID of parent block (None for root)
        - _has_children: Whether this block has children
        - _is_header: Whether this is a header block
    """
    flat_list = []

    for block in blocks:
        block_index = block.get('_index', len(flat_list))
        header_level = block.get('_header_level', 0)
        children = block.get('children', [])
        block_type = block.get('type', 'unknown')

        # Generate unique ID
        flat_id = f"block_{block_index}_{depth}"

        # Determine label and icon
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
            icon = "📑" if header_level > 0 else "📝"
        elif block_type == 'exhibit':
            exhibit = block.get('exhibit')
            label = exhibit.title if exhibit and hasattr(exhibit, 'title') and exhibit.title else f"Exhibit {block_index + 1}"
            icon = "📊"
        elif block_type == 'collapsible':
            label = block.get('summary', 'Section')
            icon = "📁"
        elif block_type == 'error':
            label = "Error"
            icon = "⚠️"
        else:
            label = f"Block {block_index + 1}"
            icon = "📄"

        # Create flattened block entry
        flat_block = {
            **block,  # Copy original block data
            '_flat_id': flat_id,
            '_depth': depth,
            '_parent_id': parent_id,
            '_has_children': len(children) > 0,
            '_is_header': header_level > 0,
            '_label': label,
            '_icon': icon,
            '_header_level': header_level,
        }

        flat_list.append(flat_block)

        # Recursively flatten children
        if children:
            child_blocks = flatten_blocks(children, flat_id, depth + 1)
            flat_list.extend(child_blocks)

    return flat_list


def get_toggle_state(block_id: str, default: bool = True) -> bool:
    """Get the toggle state for a block."""
    if TOGGLE_STATE_KEY not in st.session_state:
        st.session_state[TOGGLE_STATE_KEY] = {}
    return st.session_state[TOGGLE_STATE_KEY].get(block_id, default)


def set_toggle_state(block_id: str, is_open: bool):
    """Set the toggle state for a block."""
    if TOGGLE_STATE_KEY not in st.session_state:
        st.session_state[TOGGLE_STATE_KEY] = {}
    st.session_state[TOGGLE_STATE_KEY][block_id] = is_open


def get_edit_state(block_id: str) -> bool:
    """Get the edit state for a block."""
    if EDIT_STATE_KEY not in st.session_state:
        st.session_state[EDIT_STATE_KEY] = {}
    return st.session_state[EDIT_STATE_KEY].get(block_id, False)


def set_edit_state(block_id: str, is_editing: bool):
    """Set the edit state for a block."""
    if EDIT_STATE_KEY not in st.session_state:
        st.session_state[EDIT_STATE_KEY] = {}
    st.session_state[EDIT_STATE_KEY][block_id] = is_editing


def compute_visibility(flat_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compute which blocks are visible based on parent toggle states.

    A block is visible if all its ancestors are open.

    Args:
        flat_blocks: Flattened list of blocks with hierarchy metadata

    Returns:
        List of visible blocks only
    """
    # Build a map of block IDs to their open state
    open_states = {}
    for block in flat_blocks:
        block_id = block['_flat_id']
        if block['_has_children'] or block['_is_header']:
            open_states[block_id] = get_toggle_state(block_id, default=True)
        else:
            open_states[block_id] = True  # Non-toggle blocks are always "open"

    # Determine visibility for each block
    visible_blocks = []
    for block in flat_blocks:
        parent_id = block['_parent_id']

        # Check if all ancestors are open
        is_visible = True
        current_parent = parent_id

        # Walk up the parent chain
        parent_map = {b['_flat_id']: b for b in flat_blocks}
        while current_parent is not None:
            if not open_states.get(current_parent, True):
                is_visible = False
                break
            parent_block = parent_map.get(current_parent)
            if parent_block:
                current_parent = parent_block['_parent_id']
            else:
                break

        if is_visible:
            visible_blocks.append(block)

    return visible_blocks


def expand_all_flat(flat_blocks: List[Dict[str, Any]]):
    """Expand all toggle blocks."""
    for block in flat_blocks:
        if block['_has_children'] or block['_is_header']:
            set_toggle_state(block['_flat_id'], True)


def collapse_all_flat(flat_blocks: List[Dict[str, Any]]):
    """Collapse all toggle blocks."""
    for block in flat_blocks:
        if block['_has_children'] or block['_is_header']:
            set_toggle_state(block['_flat_id'], False)


def render_flat_row(
    block: Dict[str, Any],
    notebook_session,
    connection,
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None
):
    """
    Render a single block as a flat row with columns.

    Column layout: [indent | toggle | content | edit | delete]
    """
    depth = block['_depth']
    block_id = block['_flat_id']
    block_index = block.get('_index', 0)
    block_type = block.get('type', 'unknown')
    has_children = block['_has_children']
    is_header = block['_is_header']
    label = block['_label']
    icon = block['_icon']

    is_editing = get_edit_state(block_id)
    is_open = get_toggle_state(block_id, default=True)

    # Calculate column widths based on depth
    # Indent: 2% per depth level (max 10%)
    indent_width = min(depth * 0.02, 0.10)
    toggle_width = 0.04 if (has_children or is_header) else 0.0
    edit_width = 0.04 if editable else 0.0
    delete_width = 0.04 if editable else 0.0
    content_width = 1.0 - indent_width - toggle_width - edit_width - delete_width

    # Build column spec (filter out zero-width columns)
    col_spec = []
    col_names = []

    if indent_width > 0:
        col_spec.append(indent_width)
        col_names.append('indent')

    if toggle_width > 0:
        col_spec.append(toggle_width)
        col_names.append('toggle')

    col_spec.append(content_width)
    col_names.append('content')

    if edit_width > 0:
        col_spec.append(edit_width)
        col_names.append('edit')

    if delete_width > 0:
        col_spec.append(delete_width)
        col_names.append('delete')

    # Create columns
    cols = st.columns(col_spec)
    col_map = {name: cols[i] for i, name in enumerate(col_names)}

    # Render indent spacer
    if 'indent' in col_map:
        with col_map['indent']:
            st.empty()

    # Render toggle button
    if 'toggle' in col_map:
        with col_map['toggle']:
            toggle_icon = "▼" if is_open else "▶"
            if st.button(toggle_icon, key=f"toggle_{block_id}", help="Expand/Collapse"):
                set_toggle_state(block_id, not is_open)
                st.rerun()

    # Render content
    with col_map['content']:
        if is_editing:
            # Render editor
            _render_inline_editor(block, block_id, block_index, on_block_edit)
        else:
            # Render header label or content
            if is_header:
                st.markdown(f"**{icon} {label}**")
                # Also render body content if exists
                _render_block_body(block, notebook_session, connection)
            else:
                _render_block_content(block, notebook_session, connection)

    # Render edit button
    if 'edit' in col_map:
        with col_map['edit']:
            if is_editing:
                if st.button("✕", key=f"cancel_{block_id}", help="Cancel"):
                    set_edit_state(block_id, False)
                    st.rerun()
            else:
                if st.button("✏️", key=f"edit_{block_id}", help="Edit"):
                    set_edit_state(block_id, True)
                    st.rerun()

    # Render delete button
    if 'delete' in col_map:
        with col_map['delete']:
            if not is_editing:
                if st.button("🗑️", key=f"delete_{block_id}", help="Delete"):
                    if on_block_delete:
                        on_block_delete(block_index)
                    st.rerun()


def _render_block_body(block: Dict[str, Any], notebook_session, connection):
    """Render the body content of a header block (content after the header line)."""
    if block.get('type') != 'markdown':
        return

    content = block.get('content', '')
    lines = content.strip().split('\n')

    # Skip the header line, render the rest
    if lines and lines[0].startswith('#'):
        body_lines = lines[1:]
    else:
        body_lines = lines

    body_content = '\n'.join(body_lines).strip()
    if body_content:
        render_markdown_content(body_content)


def _render_block_content(block: Dict[str, Any], notebook_session, connection):
    """Render block content based on type."""
    block_type = block.get('type', 'unknown')

    if block_type == 'markdown':
        content = block.get('content', '')
        render_markdown_content(content)
    elif block_type == 'exhibit':
        render_exhibit_block(block, notebook_session, connection)
    elif block_type == 'collapsible':
        block_index = block.get('_index', 0)
        render_collapsible_section(block, notebook_session, connection, block_index)
    elif block_type == 'error':
        block_index = block.get('_index', 0)
        render_error_block(block, block_index)
    else:
        st.warning(f"Unknown block type: {block_type}")


def _render_inline_editor(
    block: Dict[str, Any],
    block_id: str,
    block_index: int,
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """Render inline editor for a block."""
    block_type = block.get('type', 'markdown')

    # Get content to edit
    if block_type == 'markdown':
        original_content = block.get('content', '')
    else:
        original_content = str(block)

    content_key = f"edit_content_{block_id}"
    if content_key not in st.session_state:
        st.session_state[content_key] = original_content

    # Text area for editing
    edited_content = st.text_area(
        "Edit content",
        value=st.session_state[content_key],
        height=150,
        key=f"textarea_{block_id}",
        label_visibility="collapsed"
    )
    st.session_state[content_key] = edited_content

    # Save/Cancel buttons (inline, no columns)
    save_clicked = st.button("💾 Save", key=f"save_{block_id}", type="primary")
    cancel_clicked = st.button("Cancel", key=f"cancel_edit_{block_id}")

    if save_clicked:
        if on_edit:
            on_edit(block_index, edited_content)
        set_edit_state(block_id, False)
        if content_key in st.session_state:
            del st.session_state[content_key]
        st.success("Saved!")
        st.rerun()

    if cancel_clicked:
        set_edit_state(block_id, False)
        if content_key in st.session_state:
            del st.session_state[content_key]
        st.rerun()


def render_flat_notebook(
    notebook_config,
    notebook_session,
    connection,
    notebook_id: str = "default",
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_insert: Optional[Callable[[int, str, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None
):
    """
    Render a notebook using flat row-based rendering.

    This avoids Streamlit's nested column limitations by rendering each block
    as an independent row with a single level of columns.

    Args:
        notebook_config: NotebookConfig with markdown content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        notebook_id: Unique ID for this notebook
        editable: Whether blocks can be edited
        on_block_edit: Callback when a block is edited
        on_block_insert: Callback when a block is inserted
        on_block_delete: Callback when a block is deleted
    """
    from .parser import build_header_tree

    if not hasattr(notebook_config, '_content_blocks') or not notebook_config._content_blocks:
        st.error("This notebook has no markdown content blocks")
        return

    # Apply styles
    apply_markdown_styles()

    # Build nested tree then flatten
    try:
        nested_blocks = build_header_tree(notebook_config._content_blocks)
        flat_blocks = flatten_blocks(nested_blocks)
    except Exception as e:
        st.error(f"Error building notebook structure: {str(e)}")
        import traceback
        st.code(traceback.format_exc()[:1000])
        return

    # Toolbar with expand/collapse buttons
    toolbar_cols = st.columns([0.88, 0.06, 0.06])
    with toolbar_cols[1]:
        if st.button("⊞", key=f"exp_flat_{notebook_id}", help="Expand all"):
            expand_all_flat(flat_blocks)
            st.rerun()
    with toolbar_cols[2]:
        if st.button("⊟", key=f"col_flat_{notebook_id}", help="Collapse all"):
            collapse_all_flat(flat_blocks)
            st.rerun()

    # Compute visible blocks
    visible_blocks = compute_visibility(flat_blocks)

    # Render each visible block as a flat row
    for block in visible_blocks:
        render_flat_row(
            block,
            notebook_session,
            connection,
            editable=editable,
            on_block_edit=on_block_edit,
            on_block_delete=on_block_delete
        )
