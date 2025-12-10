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
        block_type = block.get('type', 'unknown')

        # Get children - check both 'children' (from header tree) and 'content' (for collapsible blocks)
        children = block.get('children', [])
        if not children and block_type == 'collapsible':
            # Collapsible blocks have inner blocks in 'content', not 'children'
            inner_content = block.get('content', [])
            if isinstance(inner_content, list):
                children = inner_content

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
    on_block_insert: Optional[Callable[[int, str, str], None]] = None,
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

    # Collapsible blocks can't be edited directly - their inner content is editable separately
    # This prevents issues with reconstructing the <details> HTML during save
    is_collapsible = block_type == 'collapsible'
    block_editable = editable and not is_collapsible

    # Calculate column widths based on depth
    # Indent: 2% per depth level (max 10%)
    indent_width = min(depth * 0.02, 0.10)
    toggle_width = 0.04 if (has_children or is_header) else 0.0
    edit_width = 0.04 if block_editable else 0.0
    delete_width = 0.04 if block_editable else 0.0
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
                        # Set session state for backend to find content to delete
                        if block_type == 'markdown':
                            st.session_state['_content_to_delete'] = block.get('content', '')
                        else:
                            st.session_state['_content_to_delete'] = str(block)
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


def _format_content_for_display(content: str) -> str:
    """
    Format markdown content for pretty display in the editor.

    Handles:
    - Embedded YAML/JSON blocks ($exhibit$, $filter$) with proper indentation
    - Consistent line spacing
    - Markdown structure formatting

    This is display-only formatting - doesn't affect saved content.
    """
    import re
    import logging

    logger = logging.getLogger(__name__)

    # Safeguard: ensure content is a string
    if not isinstance(content, str):
        logger.warning(f"_format_content_for_display received non-string: {type(content)}")
        if isinstance(content, list):
            # Try to convert list to string representation
            import yaml
            return yaml.dump(content, default_flow_style=False)
        return str(content)

    def find_matching_brace(text: str, start: int) -> int:
        """Find the matching closing brace, handling nested braces."""
        depth = 0
        i = start
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def format_yaml_block(yaml_content: str) -> str:
        """Format YAML-like content with consistent indentation and visual structure."""
        lines = yaml_content.strip().split('\n')
        formatted_lines = []

        # Major section keys that should have blank line before them
        section_keys = {
            'columns', 'rows', 'spanners', 'filters', 'metrics',
            'measure_selector', 'dimension_selector', 'conditional',
            'source_note', 'footnotes', 'theme', 'calculated_columns'
        }

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue

            # Calculate original indentation level
            original_indent = len(line) - len(line.lstrip())

            # Determine indent string (4 spaces per level for better readability)
            if original_indent == 0:
                # Top-level key
                indent = '  '

                # Add blank line before major sections for visual separation
                if ':' in stripped:
                    key = stripped.split(':')[0].strip()
                    if key in section_keys and formatted_lines and formatted_lines[-1].strip():
                        formatted_lines.append('')
            else:
                # Nested content - use 4 spaces per level for better visibility
                level = original_indent // 2
                indent = '  ' + ('    ' * level)

            # Format list items with extra indent
            if stripped.startswith('-'):
                # List items get additional visual indent
                if original_indent > 0:
                    level = original_indent // 2
                    indent = '  ' + ('    ' * level)
                else:
                    indent = '      '  # 6 spaces for top-level list items

            formatted_lines.append(f"{indent}{stripped}")

        return '\n'.join(formatted_lines)

    def format_blocks(text: str) -> str:
        """Find and format all $exhibit$ and $filter$ blocks."""
        result = []
        i = 0
        pattern = re.compile(r'\$(exhibit|filter|exhibits|filters)\$\{')

        while i < len(text):
            match = pattern.search(text, i)
            if not match:
                result.append(text[i:])
                break

            # Add text before the match
            result.append(text[i:match.start()])

            # Find the matching closing brace
            brace_start = match.end() - 1
            brace_end = find_matching_brace(text, brace_start)

            if brace_end == -1:
                result.append(text[match.start():match.end()])
                i = match.end()
                continue

            # Extract and format the block content
            block_content = text[brace_start + 1:brace_end]
            prefix = f"${match.group(1)}$"

            # Format the YAML/JSON content
            formatted_content = format_yaml_block(block_content)
            result.append(f"{prefix}{{\n{formatted_content}\n}}")

            i = brace_end + 1

        return ''.join(result)

    formatted = format_blocks(content)

    # Normalize multiple blank lines to max 2
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    # Ensure blank line before headers
    formatted = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', formatted)

    return formatted


def _exhibit_to_dict(exhibit) -> dict:
    """Convert an Exhibit object to a dictionary for YAML serialization.

    Uses the original raw data for true 1:1 round-trip serialization.
    If raw data is not available, corrupted, or uses internal format keys,
    falls back to rebuilding from exhibit attributes using the shorthand format.
    """
    import logging
    logger = logging.getLogger(__name__)

    if exhibit is None:
        return {}

    exhibit_id = getattr(exhibit, 'id', 'unknown')
    exhibit_type = getattr(exhibit, 'type', 'unknown')

    # Debug: Log what we're working with
    has_raw_data = hasattr(exhibit, '_raw_data')
    raw_data_value = getattr(exhibit, '_raw_data', None)
    logger.debug(f"_exhibit_to_dict({exhibit_id}): has_raw_data={has_raw_data}, _raw_data type={type(raw_data_value)}")

    # Internal format keys that should NOT be at root level
    # These indicate corrupted _raw_data that needs to be rebuilt
    internal_format_keys = {'dimension', 'measure', 'label', 'measures', 'x_axis', 'y_axis', 'color_by', 'size_by'}

    # Use raw data for 1:1 serialization - but only if it uses shorthand format
    if has_raw_data and raw_data_value and isinstance(raw_data_value, dict):
        # Check for internal format keys at root level (indicates corruption)
        root_keys = set(raw_data_value.keys())
        invalid_keys = root_keys & internal_format_keys
        if invalid_keys:
            logger.warning(f"_exhibit_to_dict({exhibit_id}): _raw_data has internal format keys {invalid_keys}, rebuilding")
        else:
            logger.debug(f"_exhibit_to_dict({exhibit_id}): Using _raw_data with keys: {list(raw_data_value.keys())}")
            return raw_data_value.copy()

    # Fallback: Build dict from exhibit attributes using shorthand format
    # This handles old cached exhibits that don't have _raw_data
    logger.warning(f"_exhibit_to_dict({exhibit_id}): No _raw_data, rebuilding from attributes")

    result = {}

    # Type is required
    if hasattr(exhibit, 'type') and exhibit.type:
        result['type'] = exhibit.type.value if hasattr(exhibit.type, 'value') else str(exhibit.type)

    # Common fields
    if hasattr(exhibit, 'title') and exhibit.title:
        result['title'] = exhibit.title
    if hasattr(exhibit, 'source') and exhibit.source:
        result['source'] = exhibit.source

    # Chart fields - use shorthand format (x, y, color) not internal (dimension, measure)
    if hasattr(exhibit, 'x_axis') and exhibit.x_axis:
        if exhibit.x_axis.dimension:
            result['x'] = exhibit.x_axis.dimension
    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if exhibit.y_axis.measure:
            result['y'] = exhibit.y_axis.measure
        elif exhibit.y_axis.measures:
            result['y'] = exhibit.y_axis.measures
    if hasattr(exhibit, 'color_by') and exhibit.color_by:
        result['color'] = exhibit.color_by

    # Height
    if hasattr(exhibit, 'options') and exhibit.options and 'height' in exhibit.options:
        result['height'] = exhibit.options['height']

    # Metric cards
    if hasattr(exhibit, 'metrics') and exhibit.metrics:
        result['metrics'] = [
            {'measure': m.measure, 'label': m.label, 'aggregation': m.aggregation.value if m.aggregation else None}
            for m in exhibit.metrics
        ]

    # Table fields
    if hasattr(exhibit, 'columns') and exhibit.columns:
        result['columns'] = exhibit.columns

    # Dynamic selectors
    if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        ms = exhibit.measure_selector
        result['measure_selector'] = {
            'available_measures': ms.available_measures,
        }
        if ms.default_measures:
            result['measure_selector']['default_measures'] = ms.default_measures
        if ms.label:
            result['measure_selector']['label'] = ms.label
        if ms.allow_multiple is not None:
            result['measure_selector']['allow_multiple'] = ms.allow_multiple
        if ms.selector_type:
            result['measure_selector']['selector_type'] = ms.selector_type
        if ms.help_text:
            result['measure_selector']['help_text'] = ms.help_text

    if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        result['dimension_selector'] = {
            'available_dimensions': ds.available_dimensions,
        }
        if ds.default_dimension:
            result['dimension_selector']['default_dimension'] = ds.default_dimension
        if ds.label:
            result['dimension_selector']['label'] = ds.label
        if ds.selector_type:
            result['dimension_selector']['selector_type'] = ds.selector_type
        if ds.applies_to:
            result['dimension_selector']['applies_to'] = ds.applies_to
        if ds.help_text:
            result['dimension_selector']['help_text'] = ds.help_text

    logger.debug(f"_exhibit_to_dict({exhibit_id}): Rebuilt dict with keys: {list(result.keys())}")
    return result


def _normalize_content_for_save(content: str) -> str:
    """
    Normalize content before saving by removing display-only formatting.

    The _format_content_for_display function adds extra indentation for readability,
    but this shouldn't be saved to the file. This function removes that extra
    indentation while preserving the structural YAML indentation.
    """
    import textwrap
    import re

    # Handle $exhibits$ and $filter$ blocks
    pattern = re.compile(r'(\$(?:exhibit|filter|exhibits|filters)\$)\{')

    def normalize_block(text: str) -> str:
        """Normalize a single block by dedenting the YAML content."""
        result = []
        i = 0

        while i < len(text):
            match = pattern.search(text, i)
            if not match:
                result.append(text[i:])
                break

            # Add text before the match
            result.append(text[i:match.start()])

            # Find the matching closing brace
            prefix = match.group(1)
            brace_start = match.end()
            depth = 1
            j = brace_start
            while j < len(text) and depth > 0:
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                j += 1

            if depth == 0:
                # Extract and dedent the YAML content
                yaml_content = text[brace_start:j-1]
                dedented = textwrap.dedent(yaml_content).strip()
                # Rebuild with standard 2-space indent for file format
                indented_lines = []
                for line in dedented.split('\n'):
                    if line.strip():
                        indented_lines.append('  ' + line)
                    else:
                        indented_lines.append('')
                result.append(f"{prefix}{{\n" + '\n'.join(indented_lines) + "\n}")
                i = j
            else:
                # Unmatched braces - keep as is
                result.append(text[i:match.end()])
                i = match.end()

        return ''.join(result)

    return normalize_block(content)


def _reconstruct_collapsible_inner_content(inner_blocks: List[Dict[str, Any]]) -> str:
    """
    Reconstruct the inner content of a collapsible block for editing.

    Args:
        inner_blocks: List of inner block dictionaries

    Returns:
        Reconstructed markdown/exhibit content as a string
    """
    import yaml

    parts = []
    for inner_block in inner_blocks:
        inner_type = inner_block.get('type', 'unknown')
        if inner_type == 'markdown':
            parts.append(inner_block.get('content', ''))
        elif inner_type == 'exhibit':
            exhibit = inner_block.get('exhibit')
            if exhibit:
                exhibit_dict = _exhibit_to_dict(exhibit)
                yaml_content = yaml.dump(exhibit_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
                parts.append(f"$exhibits${{\n{yaml_content}}}")
            else:
                parts.append("$exhibits${\n  type: line_chart\n}")
        elif inner_type == 'error':
            parts.append(f"$exhibits${{\n{inner_block.get('content', '')}\n}}")
        else:
            content = inner_block.get('content')
            if isinstance(content, str):
                parts.append(content)
            else:
                parts.append(str(inner_block))

    return '\n\n'.join(parts)


def _render_inline_editor(
    block: Dict[str, Any],
    block_id: str,
    block_index: int,
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """Render inline editor for a block."""
    import yaml
    import logging

    logger = logging.getLogger(__name__)
    block_type = block.get('type', 'markdown')

    # Log block details for debugging
    logger.debug(f"Rendering editor for block {block_id}: type={block_type}, keys={list(block.keys())}")

    # Get content to edit based on block type
    if block_type == 'markdown':
        original_content = block.get('content', '')
    elif block_type == 'exhibit':
        # Convert exhibit object back to YAML for editing
        exhibit = block.get('exhibit')
        if exhibit:
            exhibit_dict = _exhibit_to_dict(exhibit)
            original_content = f"$exhibits${{\n{yaml.dump(exhibit_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)}}}"
        else:
            original_content = f"$exhibits${{\n  type: line_chart\n  source: \n  x: \n  y: \n}}"
    elif block_type == 'collapsible':
        # Reconstruct collapsible as HTML for editing
        summary = block.get('summary', 'Details')
        inner_blocks = block.get('content', [])
        inner_content = _reconstruct_collapsible_inner_content(inner_blocks)
        original_content = f"<details>\n<summary>{summary}</summary>\n\n{inner_content}\n\n</details>"
    elif block_type == 'error':
        # Show the original YAML content that caused the error
        original_content = f"$exhibits${{\n{block.get('content', '')}\n}}"
    else:
        # Unknown block type - show as string representation
        content = block.get('content')
        if isinstance(content, str):
            original_content = content
        elif content is not None:
            original_content = yaml.dump(content, default_flow_style=False)
        else:
            original_content = str(block)

    content_key = f"edit_content_{block_id}"
    original_key = f"edit_original_{block_id}"
    formatted_key = f"edit_formatted_{block_id}"
    stored_orig_key = f"stored_orig_{block_id}"

    # ALWAYS update original content from current block - don't use stale cache
    # This ensures we use the latest _raw_data after fixes
    cached_original = st.session_state.get(original_key, "")
    if cached_original != original_content:
        # Content changed - clear all cached state for this block
        logger.debug(f"Block {block_id}: content changed, clearing cache")
        for key in [content_key, original_key, formatted_key, stored_orig_key]:
            if key in st.session_state:
                del st.session_state[key]

    st.session_state[original_key] = original_content

    # Format content for display - force reformat if original changed or first time
    stored_original = st.session_state.get(stored_orig_key, "")
    if content_key not in st.session_state or stored_original != original_content:
        formatted_content = _format_content_for_display(original_content)
        st.session_state[content_key] = formatted_content
        st.session_state[stored_orig_key] = original_content
        st.session_state[formatted_key] = True

    # Calculate height based on content - pretty print with extra space
    display_content = st.session_state[content_key]
    line_count = display_content.count('\n') + 1
    # Minimum 300px, add 25px per line, max 600px
    calculated_height = max(300, min(600, line_count * 25 + 100))

    # Use st.code for display preview, text_area for editing
    edited_content = st.text_area(
        "Edit content",
        value=st.session_state[content_key],
        height=calculated_height,
        key=f"textarea_{block_id}",
        label_visibility="collapsed"
    )
    st.session_state[content_key] = edited_content


    # Save/Cancel buttons (inline, no columns)
    save_clicked = st.button("💾 Save", key=f"save_{block_id}", type="primary")
    cancel_clicked = st.button("Cancel", key=f"cancel_edit_{block_id}")

    stored_orig_key = f"stored_orig_{block_id}"
    save_error_key = f"save_error_{block_id}"

    # Display any previous save error
    if save_error_key in st.session_state:
        st.error(st.session_state[save_error_key])

    if save_clicked:
        if on_edit:
            # Normalize the edited content - remove display-only formatting
            # The _format_content_for_display adds extra indentation that shouldn't be saved
            normalized_content = _normalize_content_for_save(edited_content)

            # Set session state for backend to find/replace content
            st.session_state['_content_to_replace'] = st.session_state.get(original_key, original_content)
            st.session_state['_new_content'] = normalized_content

            # Debug: Show what we're trying to save
            with st.expander("Debug: Save Info", expanded=True):
                st.write("**Original content (first 500 chars):**")
                st.code(st.session_state['_content_to_replace'][:500])
                st.write("**Normalized content (first 500 chars):**")
                st.code(normalized_content[:500])

            try:
                on_edit(block_index, normalized_content)
                # If we get here without exception, clear error and close editor
                if save_error_key in st.session_state:
                    del st.session_state[save_error_key]
                set_edit_state(block_id, False)
                for key in [content_key, original_key, formatted_key, stored_orig_key]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            except Exception as e:
                st.session_state[save_error_key] = f"Save failed: {str(e)}"
                import traceback
                st.error(f"Save failed: {str(e)}")
                st.code(traceback.format_exc())
        else:
            st.session_state[save_error_key] = "No save handler configured"

    if cancel_clicked:
        set_edit_state(block_id, False)
        for key in [content_key, original_key, formatted_key, stored_orig_key, save_error_key]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


def render_insert_button(
    block_index: int,
    depth: int,
    flat_id: str,
    on_block_insert: Optional[Callable[[int, str, str], None]] = None
):
    """Render an insert button to add a new block above this position."""
    if not on_block_insert:
        return

    # Calculate indent to match the block depth
    indent_width = min(depth * 0.02, 0.10) if depth > 0 else 0

    if indent_width > 0:
        cols = st.columns([indent_width, 1 - indent_width])
        container = cols[1]
    else:
        container = st.container()

    with container:
        # Use flat_id for unique key since block_index may be duplicated for inner blocks
        insert_key = f"insert_above_{flat_id}"
        if st.button("➕ Add block above", key=insert_key, help="Insert new block"):
            # Default to markdown block with placeholder content
            on_block_insert(block_index, 'markdown', '# New Section\n\nAdd your content here.')
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

    # Insert button at the very top if editable
    if editable and on_block_insert:
        if st.button("➕ Add block at start", key=f"insert_start_{notebook_id}", help="Insert new block at beginning"):
            on_block_insert(-1, 'markdown', '# New Section\n\nAdd your content here.')
            st.rerun()

    # Render each visible block as a flat row
    for block in visible_blocks:
        # Render insert button above each block when editable
        if editable:
            render_insert_button(
                block.get('_index', 0),
                block['_depth'],
                block['_flat_id'],
                on_block_insert
            )

        render_flat_row(
            block,
            notebook_session,
            connection,
            editable=editable,
            on_block_edit=on_block_edit,
            on_block_insert=on_block_insert,
            on_block_delete=on_block_delete
        )
