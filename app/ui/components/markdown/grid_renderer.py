"""
Grid layout renderer for exhibit groups.

Renders multiple exhibits in configurable grid patterns using
Streamlit's column system.
"""

import streamlit as st
from typing import List, Dict, Any, Callable, Optional

from app.notebook.schema import GridConfig, GridGap, GridBlock


# Gap size mappings (pixels for container margins)
GAP_SIZES = {
    GridGap.NONE: 0,
    GridGap.SM: 8,
    GridGap.MD: 16,
    GridGap.LG: 24,
    GridGap.XL: 32,
}


def render_exhibit_grid(
    grid_config: GridConfig,
    exhibit_blocks: List[Dict[str, Any]],
    render_exhibit_fn: Callable[[Dict[str, Any]], None],
):
    """
    Render a group of exhibits in a grid layout.

    Args:
        grid_config: Grid configuration (columns, rows, gap, etc.)
        exhibit_blocks: List of exhibit blocks to render
        render_exhibit_fn: Function to render a single exhibit block
    """
    if not exhibit_blocks:
        return

    row_specs = grid_config.get_row_specs()
    gap = GAP_SIZES.get(grid_config.gap, 16)

    # Apply gap styling
    if gap > 0:
        st.markdown(
            f"""
            <style>
            .grid-exhibit-container {{
                margin-bottom: {gap}px;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

    # Flatten exhibits into iterator
    exhibit_iter = iter(exhibit_blocks)

    # Render each row
    for row_idx, row_spec in enumerate(row_specs):
        # Determine Streamlit gap setting based on our gap config
        st_gap = "small" if grid_config.gap in [GridGap.SM, GridGap.NONE] else "medium"

        # Create columns for this row
        cols = st.columns(row_spec, gap=st_gap)

        # Render exhibits into columns
        for col_idx, col in enumerate(cols):
            try:
                exhibit_block = next(exhibit_iter)
                with col:
                    # Wrap in container for styling
                    with st.container():
                        render_exhibit_fn(exhibit_block)
            except StopIteration:
                # No more exhibits, leave remaining cells empty
                with col:
                    st.empty()

        # Add row gap (except after last row)
        if row_idx < len(row_specs) - 1 and gap > 0:
            st.markdown(f'<div style="height: {gap}px"></div>', unsafe_allow_html=True)


def render_simple_grid(
    columns: int,
    exhibit_blocks: List[Dict[str, Any]],
    render_exhibit_fn: Callable[[Dict[str, Any]], None],
    gap: GridGap = GridGap.MD,
):
    """
    Render exhibits in a simple N-column grid.

    Exhibits flow left-to-right, top-to-bottom.

    Args:
        columns: Number of columns
        exhibit_blocks: List of exhibit blocks
        render_exhibit_fn: Render function for each exhibit
        gap: Gap size between exhibits
    """
    if not exhibit_blocks:
        return

    gap_px = GAP_SIZES.get(gap, 16)

    # Calculate number of rows needed
    num_exhibits = len(exhibit_blocks)
    num_rows = (num_exhibits + columns - 1) // columns

    exhibit_iter = iter(exhibit_blocks)

    # Determine Streamlit gap setting
    st_gap = "small" if gap in [GridGap.SM, GridGap.NONE] else "medium"

    for row in range(num_rows):
        cols = st.columns(columns, gap=st_gap)
        for col in cols:
            try:
                exhibit_block = next(exhibit_iter)
                with col:
                    with st.container():
                        render_exhibit_fn(exhibit_block)
            except StopIteration:
                break

        # Add row gap (except after last row)
        if row < num_rows - 1 and gap_px > 0:
            st.markdown(f'<div style="height: {gap_px}px"></div>', unsafe_allow_html=True)


def collect_grid_exhibits(
    content_blocks: List[Dict[str, Any]],
    grid_index: int
) -> List[Dict[str, Any]]:
    """
    Collect all exhibit blocks belonging to a specific grid.

    Args:
        content_blocks: All content blocks from notebook
        grid_index: Index of the grid to collect exhibits for

    Returns:
        List of exhibit blocks belonging to the grid
    """
    grid_exhibits = []
    in_grid = False

    for block in content_blocks:
        block_type = block.get('type')

        if block_type == 'grid_start' and block.get('grid_index') == grid_index:
            in_grid = True
            continue

        if block_type == 'grid_end' and block.get('grid_index') == grid_index:
            in_grid = False
            continue

        if in_grid and block_type == 'exhibit':
            grid_exhibits.append(block)

    return grid_exhibits


def get_grid_config_from_blocks(
    content_blocks: List[Dict[str, Any]],
    grid_index: int
) -> Optional[GridConfig]:
    """
    Get GridConfig for a specific grid from content blocks.

    Args:
        content_blocks: All content blocks
        grid_index: Index of the grid

    Returns:
        GridConfig or None if not found
    """
    for block in content_blocks:
        if block.get('type') == 'grid_start' and block.get('grid_index') == grid_index:
            return block.get('config')
    return None


def is_in_grid(block: Dict[str, Any]) -> bool:
    """
    Check if a block is part of a grid.

    Args:
        block: Content block to check

    Returns:
        True if the block belongs to a grid
    """
    return block.get('grid_index') is not None


def get_grid_info(
    content_blocks: List[Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """
    Build a mapping of grid index to grid information.

    Args:
        content_blocks: All content blocks

    Returns:
        Dict mapping grid_index to {config, exhibit_ids, start_block_idx}
    """
    grid_info = {}

    for idx, block in enumerate(content_blocks):
        if block.get('type') == 'grid_start':
            grid_idx = block.get('grid_index')
            grid_info[grid_idx] = {
                'config': block.get('config'),
                'exhibit_ids': [],
                'start_block_idx': idx,
                'end_block_idx': None,
            }
        elif block.get('type') == 'grid_end':
            grid_idx = block.get('grid_index')
            if grid_idx in grid_info:
                grid_info[grid_idx]['end_block_idx'] = idx
        elif block.get('type') == 'exhibit':
            grid_idx = block.get('grid_index')
            if grid_idx is not None and grid_idx in grid_info:
                grid_info[grid_idx]['exhibit_ids'].append(block.get('id'))

    return grid_info
