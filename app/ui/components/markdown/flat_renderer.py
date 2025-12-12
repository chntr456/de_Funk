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
from .grid_renderer import render_exhibit_grid, collect_grid_exhibits, collect_grid_cells, get_grid_info, markdown_to_html


# Session state keys
TOGGLE_STATE_KEY = "flat_renderer_toggle_states"
EDIT_STATE_KEY = "flat_renderer_edit_states"


def _generate_grid_markdown(config, exhibit_blocks: List[Dict[str, Any]], markdown_content: str = None) -> str:
    """
    Generate markdown source from grid config and exhibit blocks.

    Supports both:
    - Matrix layout: layout/sizes/grid_cell for complex grids
    - Legacy template: template/columns for simple grids

    Args:
        config: GridConfig object
        exhibit_blocks: List of exhibit blocks in the grid
        markdown_content: Optional markdown content for cell 1 (matrix mode)

    Returns:
        Markdown string representing the grid
    """
    import yaml

    lines = []

    # Check for matrix layout mode
    if config.layout:
        # Generate new matrix format
        grid_config = {
            'layout': config.layout,
        }
        if config.sizes:
            grid_config['sizes'] = config.sizes
        if config.gap:
            grid_config['gap'] = config.gap.value if hasattr(config.gap, 'value') else config.gap
        if config.sync_scroll:
            grid_config['sync_scroll'] = True

        # Format as multi-line YAML for readability
        lines.append("$grid${")
        lines.append("  layout:")
        for row in config.layout:
            lines.append(f"    - {row}")
        if config.sizes:
            lines.append("  sizes:")
            for cell_id, size in config.sizes.items():
                lines.append(f"    {cell_id}: {size}")
        if config.gap:
            gap_val = config.gap.value if hasattr(config.gap, 'value') else config.gap
            lines.append(f"  gap: {gap_val}")
        if config.sync_scroll:
            lines.append("  sync_scroll: true")
        lines.append("}")
        lines.append("")

        # Add markdown content if provided (goes to cell 1)
        if markdown_content:
            lines.append(markdown_content.strip())
            lines.append("")
    else:
        # Generate legacy format
        template_name = config.template.value if config.template else f"{config.columns}col"
        gap_name = config.gap.value if config.gap else "none"
        lines.append(f"$grid${{template: {template_name}, gap: {gap_name}}}")
        lines.append("")

    # Each exhibit
    for block in exhibit_blocks:
        exhibit = block.get('exhibit')
        if exhibit:
            # Use raw data if available, otherwise reconstruct
            if hasattr(exhibit, '_raw_data') and exhibit._raw_data:
                exhibit_yaml = yaml.dump(exhibit._raw_data, default_flow_style=False, sort_keys=False)
            else:
                # Reconstruct basic exhibit data
                exhibit_data = {
                    'type': exhibit.type.value if hasattr(exhibit.type, 'value') else str(exhibit.type),
                    'source': exhibit.source,
                    'title': exhibit.title or '',
                }
                # Include grid_cell if set
                if hasattr(exhibit, 'grid_cell') and exhibit.grid_cell:
                    exhibit_data['grid_cell'] = exhibit.grid_cell
                if exhibit.theme:
                    exhibit_data['theme'] = exhibit.theme
                if hasattr(exhibit, 'scroll') and exhibit.scroll:
                    exhibit_data['scroll'] = True
                if hasattr(exhibit, 'max_height') and exhibit.max_height:
                    exhibit_data['max_height'] = exhibit.max_height
                exhibit_yaml = yaml.dump(exhibit_data, default_flow_style=False, sort_keys=False)

            lines.append("$exhibits${")
            # Indent YAML content
            for yaml_line in exhibit_yaml.strip().split('\n'):
                lines.append(f"  {yaml_line}")
            lines.append("}")
            lines.append("")

    # Grid end
    lines.append("$/grid$")

    return '\n'.join(lines)


def flatten_blocks(
    blocks: List[Dict[str, Any]],
    parent_id: Optional[str] = None,
    depth: int = 0,
    counter: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Flatten nested block structure into a flat list with hierarchy metadata.

    Args:
        blocks: List of blocks (may have 'children' for nested content)
        parent_id: ID of the parent block (None for root level)
        depth: Current nesting depth
        counter: Mutable counter list [count] to ensure globally unique IDs

    Returns:
        Flat list of blocks with added metadata:
        - _flat_id: Unique ID for this block
        - _depth: Nesting depth (0 = root)
        - _parent_id: ID of parent block (None for root)
        - _has_children: Whether this block has children
        - _is_header: Whether this is a header block
    """
    flat_list = []

    # Initialize counter on first call (use list for mutability across recursion)
    if counter is None:
        counter = [0]

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

        # Generate globally unique ID using counter
        flat_id = f"block_{counter[0]}_{depth}"
        counter[0] += 1

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
        elif block_type == 'grid_start':
            grid_idx = block.get('grid_index', 0)
            config = block.get('config')
            template_name = config.template.value if config and config.template else f"{config.columns}col" if config else "grid"
            label = f"Grid Layout ({template_name})"
            icon = "🔲"
        elif block_type == 'grid_end':
            label = "End Grid"
            icon = "🔳"
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

        # Recursively flatten children (pass counter for globally unique IDs)
        if children:
            child_blocks = flatten_blocks(children, flat_id, depth + 1, counter)
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
    elif block_type in ('grid_start', 'grid_end'):
        # Grid markers are handled at a higher level (render_flat_notebook)
        # They don't render anything directly
        pass
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
            # Use exhibit_to_syntax for proper YAML formatting
            from .utils import exhibit_to_syntax
            exhibit = inner_block.get('exhibit')
            if exhibit:
                parts.append(exhibit_to_syntax(exhibit))
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
        # Use exhibit_to_syntax for proper YAML formatting with correct indentation
        from .utils import exhibit_to_syntax
        exhibit = block.get('exhibit')
        if exhibit:
            original_content = exhibit_to_syntax(exhibit)
        else:
            original_content = "$exhibits${\n  type: line_chart\n  source: \n  x: \n  y: \n}"
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

    # Build grid info from content blocks to handle grid rendering
    grid_info = get_grid_info(notebook_config._content_blocks)
    rendered_in_grid = set()  # Track exhibit IDs that have been rendered in grids

    # Insert button at the very top if editable
    if editable and on_block_insert:
        if st.button("➕ Add block at start", key=f"insert_start_{notebook_id}", help="Insert new block at beginning"):
            on_block_insert(-1, 'markdown', '# New Section\n\nAdd your content here.')
            st.rerun()

    # Render each visible block as a flat row
    for block in visible_blocks:
        block_type = block.get('type', 'unknown')

        # Handle grid_start: render all exhibits in the grid as a grid layout
        if block_type == 'grid_start':
            # Render insert button above grid when editable
            if editable:
                render_insert_button(
                    block.get('_index', 0),
                    block['_depth'],
                    block['_flat_id'],
                    on_block_insert
                )

            grid_idx = block.get('grid_index')
            if grid_idx is not None and grid_idx in grid_info:
                # Collect all cells (both markdown and exhibits) for this grid
                grid_cell_blocks = collect_grid_cells(
                    notebook_config._content_blocks,
                    grid_idx
                )
                # Also collect just exhibits for backwards compatibility
                grid_exhibit_blocks = [b for b in grid_cell_blocks if b.get('type') == 'exhibit']

                if grid_cell_blocks:
                    config = grid_info[grid_idx].get('config')
                    if config:
                        # Extract markdown content from grid cells (for matrix layout)
                        grid_markdown_blocks = [b for b in grid_cell_blocks if b.get('type') == 'markdown']
                        grid_markdown_content = '\n\n'.join(b.get('content', '') for b in grid_markdown_blocks)

                        # Render grid label with edit controls when editable
                        if editable:
                            # Show layout type in label
                            if config.layout:
                                layout_name = f"Matrix {len(config.layout[0])}x{len(config.layout)}"
                            elif config.template:
                                layout_name = config.template.value
                            else:
                                layout_name = f"{config.columns}col"
                            grid_cols = st.columns([0.85, 0.08, 0.07])
                            with grid_cols[0]:
                                st.markdown(f"**🔲 Grid Layout ({layout_name})**")
                            with grid_cols[1]:
                                edit_key = f"edit_grid_{block['_flat_id']}"
                                if st.button("✏️", key=edit_key, help="Edit grid"):
                                    set_edit_state(block['_flat_id'], True)
                                    st.rerun()
                            with grid_cols[2]:
                                delete_key = f"delete_grid_{block['_flat_id']}"
                                if st.button("🗑️", key=delete_key, help="Delete grid"):
                                    if on_block_delete:
                                        on_block_delete(block.get('_index', 0))
                                        st.rerun()

                            # Show editor if in edit state
                            if get_edit_state(block['_flat_id']):
                                # Generate markdown source for the grid
                                grid_source = _generate_grid_markdown(config, grid_exhibit_blocks, grid_markdown_content)

                                # Store original in session state for the edit handler
                                original_key = f"grid_original_{block['_flat_id']}"
                                if original_key not in st.session_state:
                                    st.session_state[original_key] = grid_source

                                st.markdown("**📝 Grid Source Editor**")
                                st.caption("Edit the grid layout and exhibits. Changes will regenerate the grid.")

                                editor_key = f"grid_editor_{block['_flat_id']}"
                                edited_source = st.text_area(
                                    "Grid Markdown",
                                    value=st.session_state.get(original_key, grid_source),
                                    height=400,
                                    key=editor_key,
                                    label_visibility="collapsed"
                                )

                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("💾 Save", key=f"save_grid_{block['_flat_id']}", type="primary"):
                                        if on_block_edit:
                                            # Set the content_to_replace - use generated content (starts with $grid$)
                                            st.session_state['_content_to_replace'] = grid_source
                                            on_block_edit(block.get('_index', 0), edited_source)
                                            if original_key in st.session_state:
                                                del st.session_state[original_key]
                                        set_edit_state(block['_flat_id'], False)
                                        st.rerun()
                                with col2:
                                    if st.button("Cancel", key=f"cancel_grid_{block['_flat_id']}"):
                                        if original_key in st.session_state:
                                            del st.session_state[original_key]
                                        set_edit_state(block['_flat_id'], False)
                                        st.rerun()

                        # Define a render function that works with our exhibit blocks
                        def render_single_exhibit(exhibit_block):
                            render_exhibit_block(exhibit_block, notebook_session, connection)

                        # Define HTML extraction function for pure CSS Grid rendering
                        def get_cell_html(cell_block):
                            """Get HTML from exhibit, markdown, or markdown_block for CSS Grid layout."""
                            block_type = cell_block.get('type')

                            # Handle explicit $markdown${} blocks
                            if block_type == 'markdown_block':
                                content = cell_block.get('content', '')
                                if content:
                                    return markdown_to_html(content)
                                return None

                            # Handle implicit markdown blocks
                            if block_type == 'markdown':
                                content = cell_block.get('content', '')
                                if content:
                                    return markdown_to_html(content)
                                return None

                            # Handle exhibit blocks
                            exhibit = cell_block.get('exhibit')
                            if not exhibit:
                                return None

                            # Only Great Tables support HTML extraction currently
                            from app.notebook.schema import ExhibitType

                            # Check if type matches (handle both enum and string)
                            is_great_table = (
                                exhibit.type == ExhibitType.GREAT_TABLE or
                                exhibit.type == 'great_table' or
                                (hasattr(exhibit.type, 'value') and exhibit.type.value == 'great_table')
                            )

                            if not is_great_table:
                                return None

                            try:
                                from app.ui.components.exhibits.great_table import get_great_table_html
                                exhibit_id = cell_block.get('id')
                                df = notebook_session.get_exhibit_data(exhibit_id)
                                pdf = connection.to_pandas(df)
                                html = get_great_table_html(exhibit, pdf)
                                return html
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                return None

                        # Check for matrix layout mode
                        if config.layout:
                            # Matrix mode: map cell IDs to content
                            from .grid_renderer import render_html_grid
                            import logging
                            logger = logging.getLogger(__name__)

                            cell_contents = {}
                            cell_types = {}

                            # Debug: log grid configuration
                            logger.info(f"Matrix grid layout: {config.layout}")
                            logger.info(f"Matrix grid sizes: {config.sizes}")
                            logger.info(f"Grid cell blocks count: {len(grid_cell_blocks)}")
                            for i, cb in enumerate(grid_cell_blocks):
                                cb_type = cb.get('type')
                                if cb_type == 'exhibit':
                                    ex = cb.get('exhibit')
                                    gc = getattr(ex, 'grid_cell', None) if ex else None
                                    logger.info(f"  Block {i}: type={cb_type}, grid_cell={gc}, title={getattr(ex, 'title', 'N/A') if ex else 'N/A'}")
                                else:
                                    logger.info(f"  Block {i}: type={cb_type}")

                            # Assign cells based on type and grid_cell attribute
                            # Priority: explicit grid_cell > markdown default to 1 > auto-assign
                            next_cell_id = 1
                            for cell_block in grid_cell_blocks:
                                block_type = cell_block.get('type')

                                if block_type == 'markdown_block':
                                    # Explicit $markdown${} block with grid_cell assignment
                                    cell_id = cell_block.get('grid_cell', 1)  # Default to cell 1
                                    html = get_cell_html(cell_block)
                                    if html:
                                        cell_contents[cell_id] = html
                                        cell_types[cell_id] = 'markdown'

                                elif block_type == 'markdown':
                                    # Implicit markdown goes to cell 1 by default
                                    cell_id = 1
                                    html = get_cell_html(cell_block)
                                    if html:
                                        cell_contents[cell_id] = html
                                        cell_types[cell_id] = 'markdown'

                                elif block_type == 'exhibit':
                                    exhibit = cell_block.get('exhibit')
                                    # Get cell assignment from exhibit
                                    cell_id = getattr(exhibit, 'grid_cell', None) if exhibit else None
                                    if cell_id is None:
                                        # Auto-assign to next available cell (skipping cell 1 if markdown claimed it)
                                        next_cell_id = max(next_cell_id, 2) if 1 in cell_contents else next_cell_id
                                        cell_id = next_cell_id
                                        next_cell_id += 1

                                    html = get_cell_html(cell_block)
                                    if html:
                                        cell_contents[cell_id] = html
                                        cell_types[cell_id] = 'exhibit'

                            # Debug: log final cell mapping
                            logger.info(f"Final cell_contents keys: {list(cell_contents.keys())}")
                            logger.info(f"Final cell_types: {cell_types}")

                            # Get scroll settings
                            max_height = getattr(config, 'max_height', None)
                            scroll = getattr(config, 'scroll', True)
                            sync_scroll = getattr(config, 'sync_scroll', False)

                            if scroll and not max_height:
                                max_height = 400

                            # Render using matrix grid
                            render_html_grid(
                                config,
                                html_contents=[],  # Not used in matrix mode
                                max_height=max_height,
                                sync_scroll=sync_scroll,
                                cell_contents=cell_contents,
                                cell_types=cell_types
                            )
                        else:
                            # Sequential mode: render grid normally
                            render_exhibit_grid(
                                config,
                                grid_cell_blocks,
                                render_single_exhibit,
                                get_html_fn=get_cell_html
                            )

                        # Mark these exhibits as rendered
                        for eb in grid_exhibit_blocks:
                            rendered_in_grid.add(eb.get('id'))
                    else:
                        st.warning(f"Grid {grid_idx}: No config found")
                else:
                    st.warning(f"Grid {grid_idx}: No exhibits collected")
            continue

        # Skip grid_end markers
        if block_type == 'grid_end':
            continue

        # Skip exhibits that were already rendered in a grid
        if block_type == 'exhibit':
            exhibit_id = block.get('id')
            if exhibit_id in rendered_in_grid:
                continue

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
