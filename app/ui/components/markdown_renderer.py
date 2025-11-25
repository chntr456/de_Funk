"""
Markdown renderer component for notebook UI.

Renders markdown content with embedded exhibits and collapsible sections.
Uses ToggleContainer instead of st.expander to avoid nesting issues.
Supports collapse/expand all functionality.
"""

import streamlit as st
import markdown
from typing import Dict, Any, List, Optional, Callable, Union
from app.notebook.schema import NotebookConfig
from .toggle_container import (
    ToggleContainer,
    apply_toggle_styles,
    expand_all,
    collapse_all
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

    # Toolbar with expand/collapse buttons
    cols = st.columns([0.06, 0.06, 0.88])
    with cols[0]:
        if st.button("⊞", key=f"exp_{notebook_id}", help="Expand all sections"):
            expand_all(notebook_id)
            st.rerun()
    with cols[1]:
        if st.button("⊟", key=f"col_{notebook_id}", help="Collapse all sections"):
            collapse_all(notebook_id)
            st.rerun()

    # Build nested tree structure from header hierarchy
    nested_blocks = _build_header_tree(notebook_config._content_blocks)

    # Insert block button at start if editable
    if editable:
        _render_insert_block_button(-1, on_block_insert)

    # Render blocks with nested toggle containers based on header hierarchy
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


def _render_block_in_toggle(
    block_index: int,
    block: Dict[str, Any],
    notebook_session,
    connection,
    context: str = "default"
):
    """
    Render a block inside a toggle container for view mode.
    """
    block_type = block['type']

    # Determine label from content
    if block_type == 'markdown':
        content = block.get('content', '')
        lines = content.strip().split('\n')
        first_line = lines[0] if lines else 'Content'
        if first_line.startswith('#'):
            label = first_line.lstrip('#').strip()
            toggle_icon = "📑"
        else:
            label = first_line[:50] + '...' if len(first_line) > 50 else first_line
            if not label:
                label = 'Text'
            toggle_icon = "📝"

    elif block_type == 'exhibit':
        exhibit = block.get('exhibit')
        label = exhibit.title if exhibit and exhibit.title else f"Exhibit {block_index + 1}"
        toggle_icon = "📊"

    elif block_type == 'collapsible':
        label = block.get('summary', 'Section')
        toggle_icon = "📁"

    else:
        label = f"Block {block_index + 1}"
        toggle_icon = "📄"

    # Render in toggle container
    with ToggleContainer(
        f"{toggle_icon} {label}",
        expanded=True,
        container_id=f"block_{block_index}",
        style="section",
        context=context
    ) as tc:
        if tc.is_open:
            if block_type == 'markdown':
                _render_markdown_content(block['content'])
            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection, in_collapsible=True)
            elif block_type == 'collapsible':
                inner_blocks = block.get('content', [])
                for inner_block in inner_blocks:
                    if inner_block['type'] == 'markdown':
                        _render_markdown_content(inner_block.get('content', ''))
                    elif inner_block['type'] == 'exhibit':
                        render_exhibit_block(inner_block, notebook_session, connection, in_collapsible=True)
            elif block_type == 'error':
                render_error_block(block, block_index=block_index)


def _render_block_with_toggle(
    block_index: int,
    block: Dict[str, Any],
    notebook_session,
    connection,
    context: str = "default",
    editable: bool = False,
    on_header_edit: Optional[Callable[[int, str], None]] = None,
    on_block_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render a content block wrapped in a toggle container.

    Args:
        block_index: Index of this block
        block: Content block dictionary
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        context: Context for collapse/expand all functionality
        editable: Whether headers can be edited
        on_header_edit: Callback when header is edited
        on_block_edit: Callback when block content is edited
    """
    block_type = block['type']

    # Determine toggle label and header level
    header_level = 0
    if block_type == 'markdown':
        content = block.get('content', '')
        lines = content.strip().split('\n')
        first_line = lines[0] if lines else 'Text'
        if first_line.startswith('#'):
            label = first_line.lstrip('#').strip()
            header_level = len(first_line) - len(first_line.lstrip('#'))
        else:
            label = first_line[:40] + '...' if len(first_line) > 40 else first_line
            if not label:
                label = 'Text Block'
        toggle_icon = "📝"

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

    # Create header edit callback for this block
    def handle_label_change(new_label: str):
        if on_header_edit and header_level > 0:
            on_header_edit(block_index, new_label)

    # Render with toggle container
    with ToggleContainer(
        f"{toggle_icon} {label}",
        expanded=True,
        container_id=f"block_{block_index}",
        style="section",
        context=context,
        editable=editable and header_level > 0,  # Only headers are editable
        on_label_change=handle_label_change if editable else None
    ) as tc:
        if tc.is_open:
            if block_type == 'markdown':
                _render_markdown_content(block['content'])

            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection, in_collapsible=True)

            elif block_type == 'collapsible':
                inner_blocks = block.get('content', [])
                for inner_idx, inner_block in enumerate(inner_blocks):
                    inner_type = inner_block['type']
                    if inner_type == 'markdown':
                        _render_markdown_content(inner_block.get('content', ''))
                    elif inner_type == 'exhibit':
                        render_exhibit_block(inner_block, notebook_session, connection, in_collapsible=True)
                    elif inner_type == 'error':
                        render_error_block(inner_block, block_index=f"{block_index}_{inner_idx}")

            elif block_type == 'error':
                render_error_block(block, block_index=block_index)


def _render_markdown_content(content: str):
    """
    Render markdown content directly (without additional toggle wrapper).

    Args:
        content: Markdown content string
    """
    md = markdown.Markdown(
        extensions=[
            'extra',
            'codehilite',
            'nl2br',
            'sane_lists',
            'toc',
        ]
    )
    html = md.convert(content)
    st.markdown(html, unsafe_allow_html=True)


def _get_header_level(content: str) -> int:
    """
    Get the header level from markdown content.

    Args:
        content: Markdown content string

    Returns:
        Header level (1-6) or 0 if no header
    """
    lines = content.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            # Count the number of # symbols
            level = 0
            for char in stripped:
                if char == '#':
                    level += 1
                else:
                    break
            return min(level, 6)
    return 0


def _split_markdown_by_headers(content: str) -> List[Dict[str, Any]]:
    """
    Split markdown content into separate blocks at each header.

    For example:
        "# Title\ncontent\n## Sub\nmore"
    Becomes:
        [
            {'type': 'markdown', 'content': '# Title\ncontent'},
            {'type': 'markdown', 'content': '## Sub\nmore'}
        ]
    """
    import re

    if not content or not content.strip():
        return []

    # Pattern to match headers at start of line
    header_pattern = re.compile(r'^(#{1,6})\s+', re.MULTILINE)

    blocks = []
    lines = content.split('\n')
    current_block_lines = []

    for line in lines:
        # Check if this line starts with a header
        if header_pattern.match(line):
            # Save previous block if any
            if current_block_lines:
                block_content = '\n'.join(current_block_lines).strip()
                if block_content:
                    blocks.append({
                        'type': 'markdown',
                        'content': block_content
                    })
            # Start new block with this header
            current_block_lines = [line]
        else:
            current_block_lines.append(line)

    # Don't forget the last block
    if current_block_lines:
        block_content = '\n'.join(current_block_lines).strip()
        if block_content:
            blocks.append({
                'type': 'markdown',
                'content': block_content
            })

    return blocks


def _build_header_tree(content_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a tree structure from content blocks based on header levels.

    First splits markdown blocks by headers, then builds nested structure:
    - H1 creates top-level sections
    - H2 nests under H1
    - H3 nests under H2
    - etc.

    Args:
        content_blocks: Flat list of content blocks

    Returns:
        List of blocks with 'children' for nested content
    """
    if not content_blocks:
        return []

    # First, split markdown blocks by headers
    split_blocks = []
    for block in content_blocks:
        if block['type'] == 'markdown':
            # Split this markdown block by headers
            sub_blocks = _split_markdown_by_headers(block.get('content', ''))
            split_blocks.extend(sub_blocks)
        else:
            # Keep non-markdown blocks as-is
            split_blocks.append(block)

    # Add header level and index info to each block
    blocks_with_levels = []
    for i, block in enumerate(split_blocks):
        block_copy = block.copy()
        block_copy['_index'] = i

        if block['type'] == 'markdown':
            level = _get_header_level(block.get('content', ''))
            block_copy['_header_level'] = level
        else:
            block_copy['_header_level'] = 0  # Non-markdown blocks have no header

        blocks_with_levels.append(block_copy)

    # Build tree structure
    root = {'children': [], '_header_level': 0}
    stack = [root]  # Stack of parent nodes

    for block in blocks_with_levels:
        level = block['_header_level']

        if level == 0:
            # Non-header content goes under current parent
            stack[-1]['children'].append(block)
        else:
            # Pop stack until we find a parent with lower level
            while len(stack) > 1 and stack[-1].get('_header_level', 0) >= level:
                stack.pop()

            # Create new section for this header
            block['children'] = []
            stack[-1]['children'].append(block)
            stack.append(block)

    return root['children']


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

    Each header creates a collapsible toggle that contains:
    - The header's body content (text after the header line)
    - Any child blocks (nested headers or content)
    """
    for idx, block in enumerate(blocks):
        block_type = block['type']
        block_index = block.get('_index', 0)
        children = block.get('children', [])
        header_level = block.get('_header_level', 0)

        # Get label for toggle
        if block_type == 'markdown':
            content = block.get('content', '')
            lines = content.strip().split('\n')
            first_line = lines[0] if lines else ''

            if first_line.startswith('#'):
                # This is a header - use header text as toggle label
                label = first_line.lstrip('#').strip()
                body_lines = lines[1:] if len(lines) > 1 else []
                body_content = '\n'.join(body_lines).strip()
            else:
                # Non-header markdown - render directly (no toggle)
                _render_markdown_content(content)
                continue

        elif block_type == 'exhibit':
            # Exhibits render directly (no toggle)
            render_exhibit_block(block, notebook_session, connection)
            continue
        else:
            # Other block types - skip
            continue

        # Create toggle for header sections
        icon = "📑" if header_level == 1 else "📁" if header_level == 2 else "📄"

        # Edit state for this section
        edit_key = f"edit_section_{block_index}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        is_editing = st.session_state[edit_key]

        # Gather full section content (this section + all nested children)
        full_section_content = _gather_section_content(block)

        # Only use columns at top level to avoid nesting error
        if editable and depth == 0 and not is_editing:
            col_toggle, col_edit, col_delete = st.columns([0.90, 0.05, 0.05])
            with col_edit:
                if st.button("✏️", key=f"edit_sec_{block_index}", help="Edit section"):
                    st.session_state[edit_key] = True
                    st.rerun()
            with col_delete:
                if st.button("🗑️", key=f"del_sec_{block_index}", help="Delete section"):
                    if on_block_delete:
                        on_block_delete(block_index)
                    st.rerun()
            container = col_toggle
        else:
            container = st.container()

        with container:
            if is_editing:
                # Show editor for the whole section including children
                _render_section_editor(block_index, full_section_content, first_line, on_block_edit, children)
            else:
                with ToggleContainer(
                    f"{icon} {label}",
                    expanded=(depth == 0),  # Top level expanded by default
                    container_id=f"section_{block_index}",
                    style="section" if depth == 0 else "default",
                    context=context
                ) as tc:
                    if tc.is_open:
                        # For nested sections, show edit/delete buttons inside the toggle
                        if editable and depth > 0:
                            btn_col1, btn_col2, btn_col3 = st.columns([0.88, 0.06, 0.06])
                            with btn_col2:
                                if st.button("✏️", key=f"edit_sec_{block_index}", help="Edit"):
                                    st.session_state[edit_key] = True
                                    st.rerun()
                            with btn_col3:
                                if st.button("🗑️", key=f"del_sec_{block_index}", help="Delete"):
                                    if on_block_delete:
                                        on_block_delete(block_index)
                                    st.rerun()

                        # Render body content (text after header)
                        if body_content:
                            _render_markdown_content(body_content)

                        # Render children recursively (nested sections)
                        if children:
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

        # Add insert button after each top-level section
        if editable and depth == 0:
            _render_insert_block_button(block_index, on_block_insert)


def _gather_section_content(block: Dict[str, Any]) -> str:
    """
    Gather the full content of a section including all nested children.

    This creates a single markdown string that includes the header,
    body content, and all nested subsections.
    """
    content = block.get('content', '')
    children = block.get('children', [])

    if not children:
        return content

    # Build full content by appending children
    parts = [content]
    for child in children:
        if child.get('type') == 'markdown':
            child_content = _gather_section_content(child)
            if child_content:
                parts.append(child_content)

    return '\n\n'.join(parts)


def _render_section_editor(
    block_index: int,
    content: str,
    header_line: str,
    on_edit: Optional[Callable[[int, str], None]] = None,
    children: Optional[List[Dict[str, Any]]] = None
):
    """
    Render an editor for a section (header + body + nested content).

    When a section has children (nested headers), the editor shows the full
    grouped content so the user sees everything together.

    Args:
        block_index: Index of the block
        content: Full content including header and nested sections
        header_line: The header line (e.g., "# Title")
        on_edit: Callback when content is saved
        children: List of child blocks (for info display)
    """
    edit_key = f"edit_section_{block_index}"
    content_key = f"section_content_{block_index}"

    # Store content in session state
    if content_key not in st.session_state:
        st.session_state[content_key] = content

    # Show header info
    has_children = children and len(children) > 0
    if has_children:
        st.markdown(f"**Edit Section** *(includes {len(children)} subsection(s))*")
        st.caption("Tip: Edit all content including nested headers here. They will be grouped together.")
    else:
        st.markdown("**Edit Section**")

    # Calculate height based on content
    line_count = content.count('\n') + 1
    height = min(max(150, line_count * 20), 400)

    edited_content = st.text_area(
        "Content",
        value=st.session_state[content_key],
        height=height,
        key=f"section_editor_{block_index}",
        label_visibility="collapsed"
    )
    st.session_state[content_key] = edited_content

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save", key=f"save_section_{block_index}", use_container_width=True):
            if on_edit:
                on_edit(block_index, edited_content)
            st.session_state[edit_key] = False
            if content_key in st.session_state:
                del st.session_state[content_key]
            st.rerun()

    with col2:
        if st.button("Cancel", key=f"cancel_section_{block_index}", use_container_width=True):
            st.session_state[edit_key] = False
            if content_key in st.session_state:
                del st.session_state[content_key]
            st.rerun()


def _render_inline_editor(
    block_index: int,
    content: str,
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render an inline editor for non-header markdown content.

    Args:
        block_index: Index of the block
        content: Markdown content
        on_edit: Callback when content is saved
    """
    edit_key = f"inline_edit_{block_index}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    col_content, col_edit = st.columns([0.95, 0.05])

    with col_edit:
        if st.session_state[edit_key]:
            if st.button("✕", key=f"cancel_inline_{block_index}", help="Cancel"):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            if st.button("✏️", key=f"edit_inline_{block_index}", help="Edit"):
                st.session_state[edit_key] = True
                st.rerun()

    with col_content:
        if st.session_state[edit_key]:
            edited = st.text_area(
                "Edit",
                value=content,
                height=150,
                key=f"inline_editor_{block_index}",
                label_visibility="collapsed"
            )
            if st.button("💾 Save", key=f"save_inline_{block_index}"):
                if on_edit:
                    on_edit(block_index, edited)
                st.session_state[edit_key] = False
                st.rerun()
        else:
            _render_markdown_content(content)


def _render_editable_block(
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
            _render_block_editor(block_index, block, on_edit, block_type)
        else:
            if block_type == 'markdown':
                _render_markdown_content(block.get('content', ''))
            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection)


def _render_nested_blocks(
    blocks: List[Dict[str, Any]],
    notebook_session,
    connection,
    context: str = "default",
    depth: int = 0,
    editable: bool = False,
    on_header_edit: Optional[Callable[[int, str], None]] = None,
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
        editable: Whether headers/blocks can be edited
        on_header_edit: Callback when header is edited
        on_block_edit: Callback when block content is edited
        on_block_insert: Callback when block is inserted
        on_block_delete: Callback when block is deleted
    """
    for block in blocks:
        block_type = block['type']
        block_index = block.get('_index', 0)
        children = block.get('children', [])
        header_level = block.get('_header_level', 0)

        # Determine toggle label
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

        # Create header edit callback for this block
        def make_handler(idx, lvl):
            def handler(new_label: str):
                if on_header_edit and lvl > 0:
                    on_header_edit(idx, new_label)
            return handler

        # If this block has children (is a header section), render with toggle
        if children or header_level > 0:
            style = "section" if depth == 0 else "default"

            with ToggleContainer(
                f"{toggle_icon} {label}",
                expanded=(depth == 0),
                container_id=f"nested_{block_index}_{depth}",
                style=style,
                context=context,
                editable=editable and header_level > 0,
                on_label_change=make_handler(block_index, header_level) if editable else None
            ) as tc:
                if tc.is_open:
                    # Render this block's content (if it has body text beyond header)
                    if block_type == 'markdown':
                        content = block.get('content', '')
                        lines = content.strip().split('\n')
                        body_lines = [l for l in lines[1:] if l.strip()] if len(lines) > 1 else []
                        if body_lines:
                            _render_markdown_content('\n'.join(body_lines))

                    elif block_type == 'exhibit':
                        render_exhibit_block(block, notebook_session, connection, in_collapsible=True)

                    # Render children recursively
                    if children:
                        _render_nested_blocks(
                            children,
                            notebook_session,
                            connection,
                            context=context,
                            depth=depth + 1,
                            editable=editable,
                            on_header_edit=on_header_edit,
                            on_block_edit=on_block_edit,
                            on_block_insert=on_block_insert,
                            on_block_delete=on_block_delete
                        )

                    # Show edit/delete buttons if editable
                    if editable:
                        _render_block_edit_buttons(
                            block_index, block, on_block_edit, on_block_delete
                        )

        else:
            # Render without toggle (simple content like non-header text)
            if editable:
                # Show with edit controls
                col1, col2 = st.columns([0.95, 0.05])
                with col1:
                    if block_type == 'markdown':
                        _render_markdown_content(block.get('content', ''))
                    elif block_type == 'exhibit':
                        render_exhibit_block(block, notebook_session, connection, in_collapsible=True)
                    elif block_type == 'error':
                        render_error_block(block, block_index=block_index)
                with col2:
                    _render_block_edit_buttons(
                        block_index, block, on_block_edit, on_block_delete, compact=True
                    )
            else:
                if block_type == 'markdown':
                    _render_markdown_content(block.get('content', ''))
                elif block_type == 'exhibit':
                    render_exhibit_block(block, notebook_session, connection, in_collapsible=True)
                elif block_type == 'error':
                    render_error_block(block, block_index=block_index)


def _render_block_edit_buttons(
    block_index: int,
    block: Dict[str, Any],
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None,
    compact: bool = False
):
    """Render edit/delete buttons for a block."""
    edit_key = f"edit_mode_block_{block_index}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    is_editing = st.session_state[edit_key]

    if is_editing:
        # Show editor
        block_type = block['type']
        if block_type == 'markdown':
            content = block.get('content', '')
            new_content = st.text_area(
                "Edit content",
                value=content,
                key=f"editor_{block_index}",
                height=200,
                label_visibility="collapsed"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save", key=f"save_{block_index}"):
                    if on_block_edit:
                        on_block_edit(block_index, new_content)
                    st.session_state[edit_key] = False
                    st.rerun()
            with col2:
                if st.button("Cancel", key=f"cancel_{block_index}"):
                    st.session_state[edit_key] = False
                    st.rerun()
    else:
        # Show edit/delete buttons
        if compact:
            if st.button("✏️", key=f"edit_btn_{block_index}", help="Edit"):
                st.session_state[edit_key] = True
                st.rerun()
        else:
            col1, col2 = st.columns([0.5, 0.5])
            with col1:
                if st.button("✏️ Edit", key=f"edit_btn_{block_index}"):
                    st.session_state[edit_key] = True
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_btn_{block_index}", help="Delete"):
                    if on_block_delete:
                        on_block_delete(block_index)
                    st.rerun()


def render_exhibit_block(block: Dict[str, Any], notebook_session, connection, in_collapsible: bool = False):
    """
    Render a single exhibit block.

    Supports collapsible exhibits via exhibit.collapsible flag.
    Auto-wraps exhibits with selectors in a collapsible section.

    Args:
        block: Content block with exhibit data
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        in_collapsible: True if already rendering inside a collapsible section
    """
    exhibit = block['exhibit']
    exhibit_id = block['id']

    # Import exhibit renderers
    from .exhibits import (
        render_metric_cards,
        render_line_chart,
        render_bar_chart,
        render_data_table,
    )
    from .exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart
    from .exhibits.forecast_chart import render_forecast_chart, render_forecast_metrics_table

    # Check if exhibit has selectors
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector
    has_selectors = has_measure_selector or has_dimension_selector

    # Check if exhibit should be rendered in collapsible section
    # NOTE: Don't auto-wrap exhibits with selectors - they'll create their own individual expanders
    is_collapsible = getattr(exhibit, 'collapsible', False) and not has_selectors
    collapsible_title = getattr(exhibit, 'collapsible_title', None) or exhibit.title
    collapsible_expanded = getattr(exhibit, 'collapsible_expanded', True)

    # Render function to execute the actual exhibit rendering
    def _render_exhibit_content():
        try:
            with st.spinner(f"Loading {exhibit.title or 'exhibit'}..."):
                # Get data for exhibit
                df = notebook_session.get_exhibit_data(exhibit_id)

                # Debug: Check what type we got from get_exhibit_data
                st.caption(f"DEBUG: df type = {type(df).__name__}, has .data = {hasattr(df, 'data')}")

                pdf = connection.to_pandas(df)

                # Debug: Check what type we got after conversion
                st.caption(f"DEBUG: pdf type = {type(pdf).__name__}, shape = {pdf.shape if hasattr(pdf, 'shape') else 'N/A'}")

                # Debug: Check column dtypes
                if hasattr(pdf, 'dtypes'):
                    problematic = [col for col in pdf.columns if pdf[col].dtype == 'object']
                    if problematic:
                        st.caption(f"DEBUG: Object columns = {problematic}")

            # Render based on type
            from app.notebook.schema import ExhibitType
            if exhibit.type == ExhibitType.METRIC_CARDS:
                render_metric_cards(exhibit, pdf)
            elif exhibit.type == ExhibitType.LINE_CHART:
                render_line_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.BAR_CHART:
                render_bar_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.DATA_TABLE:
                render_data_table(exhibit, pdf)
            elif exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
                render_weighted_aggregate_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.FORECAST_CHART:
                render_forecast_chart(exhibit, pdf, in_collapsible=in_collapsible)
            elif exhibit.type == ExhibitType.FORECAST_METRICS_TABLE:
                render_forecast_metrics_table(exhibit, pdf)
            else:
                st.warning(f"Exhibit type not yet implemented: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering exhibit: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    # Wrap in ToggleContainer if collapsible
    if is_collapsible:
        with ToggleContainer(
            collapsible_title,
            expanded=collapsible_expanded,
            container_id=f"exhibit_{exhibit_id}",
            style="card"
        ) as tc:
            if tc.is_open:
                _render_exhibit_content()
    else:
        _render_exhibit_content()


def render_collapsible_section(block: Dict[str, Any], notebook_session, connection, block_index: int = 0):
    """
    Render a collapsible section using ToggleContainer.

    Uses ToggleContainer instead of st.expander to avoid nesting issues.

    Args:
        block: Content block with summary and inner content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        block_index: Index of this block for unique keys
    """
    summary = block['summary']
    inner_blocks = block['content']

    # Use ToggleContainer for collapsible sections (no nesting issues)
    with ToggleContainer(
        summary,
        expanded=False,
        container_id=f"collapsible_{block_index}",
        style="default"
    ) as tc:
        if tc.is_open:
            # Render inner content blocks
            for inner_idx, inner_block in enumerate(inner_blocks):
                inner_type = inner_block['type']

                if inner_type == 'markdown':
                    # No need for in_collapsible flag with ToggleContainer
                    render_markdown_block(
                        inner_block['content'],
                        in_collapsible=True,
                        block_index=f"{block_index}_{inner_idx}"
                    )

                elif inner_type == 'exhibit':
                    render_exhibit_block(inner_block, notebook_session, connection, in_collapsible=True)

                elif inner_type == 'error':
                    render_error_block(inner_block, block_index=f"{block_index}_{inner_idx}")


def render_markdown_block(content: str, in_collapsible: bool = False, block_index: Any = 0):
    """
    Render a markdown content block.

    Text paragraphs are wrapped in a ToggleContainer (not expander) to enable
    a clean view of just exhibits and headers (unless already inside a
    collapsible section).

    Uses ToggleContainer instead of st.expander to avoid nesting issues.

    Supports:
    - Standard markdown (headers, bold, italic, lists, etc.)
    - HTML tags (for collapsible sections)
    - Code blocks
    - Tables
    - Links and images

    Args:
        content: Markdown content string
        in_collapsible: True if already rendering inside a collapsible section
        block_index: Index of this block for unique keys
    """
    # Check if this content is substantial text (more than just a header)
    lines = content.strip().split('\n')
    non_empty_lines = [l for l in lines if l.strip()]

    # Detect if this is a header-only block (just 1-2 lines starting with #)
    is_header_only = (
        len(non_empty_lines) <= 2 and
        any(line.strip().startswith('#') for line in non_empty_lines)
    )

    # Configure markdown extensions
    md = markdown.Markdown(
        extensions=[
            'extra',          # Tables, fenced code, etc.
            'codehilite',     # Syntax highlighting
            'nl2br',          # Newline to <br>
            'sane_lists',     # Better list handling
            'toc',            # Table of contents
        ]
    )

    # Convert markdown to HTML
    html = md.convert(content)

    # If it's just a header, render directly
    if is_header_only:
        st.markdown(html, unsafe_allow_html=True)
    elif in_collapsible:
        # Already inside a collapsible section - render directly
        st.markdown(html, unsafe_allow_html=True)
    else:
        # Wrap text paragraphs in ToggleContainer for clean view
        with ToggleContainer(
            "Details",
            expanded=False,
            container_id=f"md_details_{block_index}",
            icon_open="📄",
            icon_closed="📄",
            style="minimal"
        ) as tc:
            if tc.is_open:
                st.markdown(html, unsafe_allow_html=True)


def render_notebook_header(notebook_config: NotebookConfig):
    """
    Render notebook header with metadata.

    Args:
        notebook_config: NotebookConfig with metadata
    """
    metadata = notebook_config.notebook

    # Title
    st.title(metadata.title)

    # Description
    if metadata.description:
        st.markdown(metadata.description)

    # Metadata row
    cols = st.columns([1, 1, 1, 1])

    with cols[0]:
        if metadata.author:
            st.caption(f"👤 {metadata.author}")

    with cols[1]:
        if metadata.created:
            st.caption(f"📅 Created: {metadata.created}")

    with cols[2]:
        if metadata.updated:
            st.caption(f"🔄 Updated: {metadata.updated}")

    with cols[3]:
        if metadata.tags:
            st.caption(f"🏷️ {', '.join(metadata.tags)}")

    st.divider()


def render_filters_header(notebook_config: NotebookConfig):
    """
    Render filters section header (if filters are defined).

    Args:
        notebook_config: NotebookConfig with variables
    """
    if notebook_config.variables:
        st.subheader("🔍 Active Filters")

        # Show filter summary
        filter_summary = []
        for var_id, variable in notebook_config.variables.items():
            filter_summary.append(f"• **{variable.display_name}** ({var_id})")

        st.markdown("\n".join(filter_summary))
        st.caption("Configure filters in the sidebar")
        st.divider()


def apply_markdown_styles():
    """
    Apply custom CSS styles for markdown rendering.

    Enhances the default Streamlit markdown styling with:
    - Improved code blocks
    - Enhanced tables
    - Better spacing
    """
    st.markdown("""
    <style>
    /* Code blocks */
    .codehilite {
        background-color: #f6f8fa;
        border-radius: 6px;
        padding: 16px;
        overflow: auto;
    }

    /* Tables */
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1rem 0;
    }

    th {
        background-color: rgba(28, 131, 225, 0.1);
        font-weight: 600;
        padding: 12px;
        text-align: left;
        border-bottom: 2px solid #1c83e1;
    }

    td {
        padding: 8px 12px;
        border-bottom: 1px solid #e1e4e8;
    }

    /* Blockquotes */
    blockquote {
        border-left: 4px solid #1c83e1;
        padding-left: 1rem;
        margin-left: 0;
        color: #586069;
    }

    /* Headers spacing */
    h1, h2, h3, h4, h5, h6 {
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Lists */
    ul, ol {
        padding-left: 2rem;
        margin: 0.5rem 0;
    }

    li {
        margin: 0.25rem 0;
    }

    /* Links */
    a {
        color: #1c83e1;
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    /* Horizontal rules */
    hr {
        border: none;
        border-top: 1px solid #e1e4e8;
        margin: 1.5rem 0;
    }

    /* Inline code */
    code {
        background-color: rgba(175, 184, 193, 0.2);
        padding: 0.2em 0.4em;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 85%;
    }

    /* Paragraphs */
    p {
        margin: 0.75rem 0;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)


def render_error_block(block: Dict[str, Any], block_index: Any = 0):
    """
    Render an error block with YAML content display.

    Args:
        block: Error block with message and content
        block_index: Index of this block for unique keys
    """
    st.error(f"Error: {block['message']}")

    # Use ToggleContainer to show exhibit YAML
    with ToggleContainer(
        "Show exhibit YAML",
        expanded=False,
        container_id=f"error_yaml_{block_index}",
        style="minimal"
    ) as tc:
        if tc.is_open:
            st.code(block['content'], language='yaml')


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
            # Edit mode for any block type
            _render_block_editor(block_index, block, on_edit, block_type)
        else:
            # View mode - show block type badge
            _render_block_type_badge(block_type)

            if block_type == 'markdown':
                render_markdown_block(block['content'], block_index=block_index)
            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection)
            elif block_type == 'collapsible':
                render_collapsible_section(block, notebook_session, connection, block_index=block_index)
            elif block_type == 'error':
                render_error_block(block, block_index=block_index)


def _render_block_type_badge(block_type: str):
    """Render a small badge showing the block type."""
    type_labels = {
        'markdown': '📝 Markdown',
        'exhibit': '📊 Exhibit',
        'collapsible': '📁 Collapsible',
        'error': '⚠️ Error'
    }
    label = type_labels.get(block_type, block_type)
    st.caption(label)


def _render_block_editor(
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
        original_content = _exhibit_to_yaml(block.get('exhibit'))
    elif block_type == 'collapsible':
        # Get summary and inner content
        original_content = _collapsible_to_editable(block)
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

    # Action buttons
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6])

    with col1:
        if st.button("💾 Save", key=f"save_block_{block_index}", type="primary"):
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

    with col2:
        if st.button("Cancel", key=f"cancel_block_{block_index}"):
            # Reset content and exit edit mode
            if content_key in st.session_state:
                del st.session_state[content_key]
            st.session_state[edit_key] = False
            st.rerun()

    # Show preview based on block type
    with ToggleContainer(
        "Preview",
        expanded=True,
        container_id=f"preview_{block_index}",
        style="minimal"
    ) as tc:
        if tc.is_open:
            if block_type == 'markdown':
                md = markdown.Markdown(
                    extensions=['extra', 'codehilite', 'nl2br', 'sane_lists', 'toc']
                )
                html = md.convert(edited_content)
                st.markdown(html, unsafe_allow_html=True)
            elif block_type == 'exhibit':
                st.code(edited_content, language='yaml')
                st.caption("Exhibit will be rendered after save")
            elif block_type == 'collapsible':
                lines = edited_content.split('\n', 1)
                summary = lines[0] if lines else "Details"
                content = lines[1] if len(lines) > 1 else ""
                st.markdown(f"**Summary:** {summary}")
                st.markdown("**Content:**")
                st.markdown(content)


def _exhibit_to_yaml(exhibit) -> str:
    """Convert an Exhibit object to YAML string for editing."""
    if not exhibit:
        return "type: line_chart\ntitle: New Chart\nsource: model.table\nx: dimension\ny: measure"

    lines = []
    lines.append(f"type: {exhibit.type.value}")

    if exhibit.title:
        lines.append(f"title: {exhibit.title}")
    if exhibit.description:
        lines.append(f"description: {exhibit.description}")
    if exhibit.source:
        lines.append(f"source: {exhibit.source}")

    # Axis configuration
    if exhibit.x_axis:
        if exhibit.x_axis.dimension:
            lines.append(f"x: {exhibit.x_axis.dimension}")
        elif exhibit.x_axis.measure:
            lines.append(f"x: {exhibit.x_axis.measure}")

    if exhibit.y_axis:
        if exhibit.y_axis.measure:
            lines.append(f"y: {exhibit.y_axis.measure}")
        elif exhibit.y_axis.measures:
            lines.append(f"y: [{', '.join(exhibit.y_axis.measures)}]")

    if exhibit.color_by:
        lines.append(f"color: {exhibit.color_by}")

    if exhibit.collapsible:
        lines.append(f"collapsible: true")
        if exhibit.collapsible_title:
            lines.append(f"collapsible_title: {exhibit.collapsible_title}")

    return '\n'.join(lines)


def _collapsible_to_editable(block: Dict[str, Any]) -> str:
    """Convert a collapsible block to editable format."""
    summary = block.get('summary', 'Details')
    inner_blocks = block.get('content', [])

    # Build inner content from blocks
    inner_parts = []
    for inner_block in inner_blocks:
        inner_type = inner_block['type']
        if inner_type == 'markdown':
            inner_parts.append(inner_block.get('content', ''))
        elif inner_type == 'exhibit':
            inner_parts.append(f"$exhibits${{\n{_exhibit_to_yaml(inner_block.get('exhibit'))}\n}}")

    inner_content = '\n\n'.join(inner_parts)
    return f"{summary}\n{inner_content}"


def _render_insert_block_button(
    after_index: int,
    on_insert: Optional[Callable[[int, str, str], None]] = None
):
    """
    Render a simple "+" button to add a new section.

    Args:
        after_index: Index after which to insert (-1 for start)
        on_insert: Callback when block is inserted (after_index, block_type, content)
    """
    # Centered insert button
    col1, col2, col3 = st.columns([0.45, 0.1, 0.45])

    with col2:
        if st.button("➕", key=f"add_block_{after_index}", help="Add new section"):
            # Add a new section with default content
            content = "## New Section\n\nAdd your content here."
            if on_insert:
                on_insert(after_index, 'markdown', content)
            st.rerun()


def _get_default_block_content(block_type: str) -> str:
    """Get default content for a new block."""
    if block_type == 'markdown':
        return "## New Section\n\nAdd your content here."
    elif block_type == 'exhibit':
        return """type: line_chart
title: New Chart
source: model.table
x: date
y: value
color: category"""
    elif block_type == 'collapsible':
        return "Click to expand\nAdd your collapsible content here."
    return ""
