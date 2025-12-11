"""
Grid layout renderer for exhibit groups.

Renders multiple exhibits in configurable grid patterns.
Supports two modes:
1. HTML Grid: Single HTML block with CSS Grid (crisp, no Streamlit padding)
2. Streamlit Columns: Falls back to st.columns for non-HTML exhibits
"""

import streamlit as st
from typing import List, Dict, Any, Callable, Optional

from app.notebook.schema import GridConfig, GridGap, GridBlock, GridTemplate


# Gap size mappings (pixels)
GAP_SIZES = {
    GridGap.NONE: 0,
    GridGap.SM: 4,
    GridGap.MD: 8,
    GridGap.LG: 16,
    GridGap.XL: 24,
}


def render_html_grid(
    grid_config: GridConfig,
    html_contents: List[str],
    titles: Optional[List[str]] = None,
    max_height: Optional[int] = None,
):
    """
    Render multiple HTML blocks in a pure CSS Grid layout.

    This creates a single HTML block with no Streamlit padding - crisp exhibits.
    All exhibits scroll together (linked scrolling) with sticky headers.

    Args:
        grid_config: Grid configuration
        html_contents: List of HTML strings to render in grid cells
        titles: Optional list of titles for each cell
        max_height: Optional max height for scrollable grid (enables linked scrolling)
    """
    if not html_contents:
        return

    gap = GAP_SIZES.get(grid_config.gap, 0)
    num_items = len(html_contents)

    # Determine grid template based on config
    if grid_config.template == GridTemplate.TWO_BY_TWO:
        grid_template = "1fr 1fr"
        num_cols = 2
    elif grid_config.template == GridTemplate.ONE_TWO:
        grid_template = "1fr 2fr"
        num_cols = 2
    elif grid_config.template == GridTemplate.TWO_ONE:
        grid_template = "2fr 1fr"
        num_cols = 2
    elif grid_config.template == GridTemplate.THREE_COL:
        grid_template = "1fr 1fr 1fr"
        num_cols = 3
    elif grid_config.template == GridTemplate.FOUR_COL:
        grid_template = "1fr 1fr 1fr 1fr"
        num_cols = 4
    else:
        # Default based on columns setting
        num_cols = grid_config.columns or 2
        grid_template = " ".join(["1fr"] * num_cols)

    # Calculate rows needed
    num_rows = (num_items + num_cols - 1) // num_cols

    # Build grid cells HTML - each cell fills its space completely
    cells_html = []
    for i, html in enumerate(html_contents):
        title = titles[i] if titles and i < len(titles) else None
        title_html = f'<div class="gt-title" style="font-weight: 600; padding: 4px 8px; font-size: 13px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0;">{title}</div>' if title else ''

        # Cell styling: fill container, left-align, no internal margins
        cells_html.append(f'''<div class="gt-cell-wrapper" style="display:flex;flex-direction:column;min-width:0;border:1px solid #e0e0e0;background:#fff;">
{title_html}
<div class="gt-cell" style="flex:1;">{html}</div>
</div>''')

    # Scroll wrapper style - only if max_height specified
    scroll_style = f"max-height:{max_height}px;overflow:auto;" if max_height else ""

    # Combine into CSS Grid with linked scrolling and sticky headers
    grid_html = f'''<style>
        .de-funk-grid-wrapper * {{ box-sizing: border-box; }}
        .de-funk-grid-wrapper table,
        .de-funk-grid-wrapper .gt_table {{
            width: 100% !important;
            margin: 0 !important;
            border-collapse: collapse !important;
        }}
        .de-funk-grid-wrapper .gt-cell > div {{ width: 100% !important; }}
        .de-funk-grid-wrapper .gt_table_container {{ width: 100% !important; margin: 0 !important; }}
        /* Sticky headers - titles stick at top of scroll container */
        .de-funk-grid-wrapper .gt-title {{
            position: sticky;
            top: 0;
            z-index: 20;
        }}
        /* Sticky table headers within cells */
        .de-funk-grid-wrapper thead,
        .de-funk-grid-wrapper .gt_col_headings {{
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .de-funk-grid-wrapper th {{
            position: sticky;
            top: 0;
            z-index: 10;
        }}
    </style>
    <div class="de-funk-grid-wrapper" style="{scroll_style}border:1px solid #ddd;border-radius:4px;">
        <div class="de-funk-grid" style="display:grid;grid-template-columns:{grid_template};gap:{gap}px;width:100%;">{''.join(cells_html)}</div>
    </div>'''

    st.html(grid_html)


def render_exhibit_grid(
    grid_config: GridConfig,
    exhibit_blocks: List[Dict[str, Any]],
    render_exhibit_fn: Callable[[Dict[str, Any]], None],
    get_html_fn: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
):
    """
    Render a group of exhibits in a grid layout.

    Args:
        grid_config: Grid configuration (columns, rows, gap, etc.)
        exhibit_blocks: List of exhibit blocks to render
        render_exhibit_fn: Function to render a single exhibit block
        get_html_fn: Optional function to get HTML string from exhibit (for pure HTML grid)
    """
    if not exhibit_blocks:
        st.warning("Grid: No exhibit blocks to render")
        return

    # Try HTML-based grid first (crisp, no Streamlit padding)
    if get_html_fn:
        html_contents = []
        titles = []
        failed_blocks = []
        for i, block in enumerate(exhibit_blocks):
            html = get_html_fn(block)
            if html:
                html_contents.append(html)
                exhibit = block.get('exhibit')
                titles.append(exhibit.title if exhibit and hasattr(exhibit, 'title') else None)
            else:
                failed_blocks.append(i)

        if len(html_contents) == len(exhibit_blocks):
            # All exhibits provided HTML - use pure CSS Grid
            # Debug: uncomment to verify CSS Grid is being used
            # st.caption("🟢 CSS Grid Mode")

            # Determine max_height for linked scrolling
            max_height = getattr(grid_config, 'max_height', None)
            scroll = getattr(grid_config, 'scroll', False)
            if scroll and not max_height:
                max_height = 500  # Default scroll height

            render_html_grid(grid_config, html_contents, titles, max_height=max_height)
            return
        elif failed_blocks:
            # Debug: show which blocks failed HTML extraction
            st.caption(f"⚠️ Falling back to columns (blocks {failed_blocks} failed HTML)")

    # Fallback to Streamlit columns
    row_specs = grid_config.get_row_specs()
    gap = GAP_SIZES.get(grid_config.gap, 0)

    # Flatten exhibits into iterator
    exhibit_iter = iter(exhibit_blocks)

    # Render each row
    for row_idx, row_spec in enumerate(row_specs):
        st_gap = "small" if grid_config.gap in [GridGap.SM, GridGap.NONE] else "medium"
        cols = st.columns(row_spec, gap=st_gap)

        for col_idx, col in enumerate(cols):
            try:
                exhibit_block = next(exhibit_iter)
                with col:
                    render_exhibit_fn(exhibit_block)
            except StopIteration:
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
