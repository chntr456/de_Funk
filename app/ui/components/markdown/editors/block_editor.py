"""
Block editor components.

Provides editing UI for different block types including:
- Markdown blocks
- Exhibit blocks (YAML editing)
- Collapsible sections
"""

import streamlit as st
import markdown
from typing import Dict, Any, Optional, Callable

from ..blocks.text import render_markdown_content
from ..utils import exhibit_to_yaml, collapsible_to_editable


def render_block_type_badge(block_type: str):
    """Render a small badge showing the block type."""
    type_labels = {
        'markdown': '📝 Markdown',
        'exhibit': '📊 Exhibit',
        'collapsible': '📁 Collapsible',
        'error': '⚠️ Error'
    }
    label = type_labels.get(block_type, block_type)
    st.caption(label)


def render_block_editor(
    block_index: int,
    block: Dict[str, Any],
    on_edit: Optional[Callable[[int, str], None]] = None,
    block_type: str = 'markdown'
):
    """
    Render inline editor for a content block.

    Supports editing all block types:
    - markdown: Plain text editor with preview
    - exhibit: YAML editor for exhibit configuration
    - collapsible: Summary + content editor

    Args:
        block_index: Index of the block being edited
        block: Block data containing content
        on_edit: Callback when content is saved
        block_type: Type of block being edited
    """
    edit_key = f"block_edit_mode_{block_index}"
    content_key = f"block_content_{block_index}"

    # Get content based on block type
    if block_type == 'markdown':
        original_content = block.get('content', '')
    elif block_type == 'exhibit':
        # Convert exhibit to YAML for editing
        original_content = exhibit_to_yaml(block.get('exhibit'))
    elif block_type == 'collapsible':
        # Get summary and inner content
        original_content = collapsible_to_editable(block)
    else:
        original_content = block.get('content', '')

    # Store original content for comparison
    if content_key not in st.session_state:
        st.session_state[content_key] = original_content

    # Editor header
    type_labels = {
        'markdown': '📝 Editing Markdown Block',
        'exhibit': '📊 Editing Exhibit (YAML)',
        'collapsible': '📁 Editing Collapsible Section',
        'error': '⚠️ Editing Error Block'
    }
    st.markdown(f"**{type_labels.get(block_type, 'Editing Block')}**")

    # Editor height based on content type
    height = 300 if block_type == 'exhibit' else 200

    edited_content = st.text_area(
        "Content",
        value=st.session_state[content_key],
        height=height,
        key=f"editor_textarea_{block_index}",
        label_visibility="collapsed"
    )

    # Update stored content
    st.session_state[content_key] = edited_content

    # Help text based on block type
    if block_type == 'exhibit':
        st.caption("Edit the exhibit YAML configuration. Properties: type, title, source, x, y, color, etc.")
    elif block_type == 'collapsible':
        st.caption("First line is the summary (clickable header). Rest is the inner content.")

    # Action buttons (inline to avoid nested columns)
    button_container = st.container()
    with button_container:
        save_clicked = st.button("💾 Save", key=f"save_block_{block_index}", type="primary")
        cancel_clicked = st.button("Cancel", key=f"cancel_block_{block_index}")

    if save_clicked:
        # Call the on_edit callback if provided
        if on_edit:
            on_edit(block_index, edited_content)

        # Exit edit mode
        st.session_state[edit_key] = False
        # Clear stored content so it reloads next time
        if content_key in st.session_state:
            del st.session_state[content_key]
        st.success("Block saved!")
        st.rerun()

    if cancel_clicked:
        # Reset content and exit edit mode
        if content_key in st.session_state:
            del st.session_state[content_key]
        st.session_state[edit_key] = False
        st.rerun()


def render_editable_block(
    block_index: int,
    block: Dict[str, Any],
    notebook_session,
    connection,
    on_edit: Optional[Callable[[int, str], None]] = None,
    on_delete: Optional[Callable[[int], None]] = None
):
    """Render a block with edit/delete controls on the right."""
    block_type = block['type']
    edit_key = f"block_edit_mode_{block_index}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    is_editing = st.session_state[edit_key]

    col_content, col_edit, col_delete = st.columns([0.90, 0.05, 0.05])

    with col_edit:
        if is_editing:
            if st.button("✕", key=f"cancel_edit_{block_index}", help="Cancel"):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            if st.button("✏️", key=f"start_edit_{block_index}", help="Edit"):
                st.session_state[edit_key] = True
                st.rerun()

    with col_delete:
        if not is_editing:
            if st.button("🗑️", key=f"delete_block_{block_index}", help="Delete"):
                if on_delete:
                    on_delete(block_index)
                st.rerun()

    with col_content:
        if is_editing:
            render_block_editor(block_index, block, on_edit, block_type)
        else:
            if block_type == 'markdown':
                render_markdown_content(block.get('content', ''))
            elif block_type == 'exhibit':
                from ..blocks.exhibit import render_exhibit_block
                render_exhibit_block(block, notebook_session, connection)


def render_editable_block_wrapper(
    block_index: int,
    block: Dict[str, Any],
    notebook_session,
    connection,
    on_edit: Optional[Callable[[int, str], None]] = None,
    on_delete: Optional[Callable[[int], None]] = None
):
    """
    Wrap a content block with editing controls.

    Provides inline editing capability for all block types.

    Args:
        block_index: Index of this block
        block: Content block data
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        on_edit: Callback when block is edited
        on_delete: Callback when block is deleted
    """
    block_type = block['type']

    # Generate unique key for this block's edit state
    edit_key = f"block_edit_mode_{block_index}"

    # Initialize edit state
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    is_editing = st.session_state[edit_key]

    # Editable block types
    editable_types = ['markdown', 'exhibit', 'collapsible', 'error']

    # Create container for the block with edit controls
    col_content, col_edit, col_delete = st.columns([0.90, 0.05, 0.05])

    with col_edit:
        # Edit button (for all editable block types)
        if block_type in editable_types:
            if is_editing:
                if st.button("✕", key=f"cancel_edit_{block_index}", help="Cancel editing"):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                if st.button("✏️", key=f"start_edit_{block_index}", help="Edit this block"):
                    st.session_state[edit_key] = True
                    st.rerun()

    with col_delete:
        # Delete button
        if not is_editing:
            if st.button("🗑️", key=f"delete_block_{block_index}", help="Delete this block"):
                if on_delete:
                    on_delete(block_index)
                st.rerun()

    with col_content:
        if is_editing:
            render_block_editor(block_index, block, on_edit, block_type)
        else:
            # Render based on block type
            if block_type == 'markdown':
                render_markdown_content(block.get('content', ''))
            elif block_type == 'exhibit':
                from ..blocks.exhibit import render_exhibit_block
                render_exhibit_block(block, notebook_session, connection)
            elif block_type == 'collapsible':
                from ..blocks.collapsible import render_collapsible_section
                render_collapsible_section(block, notebook_session, connection, block_index)
            elif block_type == 'error':
                from ..blocks.error import render_error_block
                render_error_block(block, block_index)
