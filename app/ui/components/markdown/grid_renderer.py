"""
Grid layout renderer for exhibit groups.

Renders multiple exhibits in configurable grid patterns.
Supports two modes:
1. HTML Grid: Single HTML block with CSS Grid (crisp, no Streamlit padding)
2. Streamlit Columns: Falls back to st.columns for non-HTML exhibits

Note: Uses streamlit.components.v1.html() instead of st.html() to enable
JavaScript execution for features like synchronized scrolling.
"""

import streamlit as st
import streamlit.components.v1 as components
import markdown as md
from typing import List, Dict, Any, Callable, Optional

from app.notebook.schema import GridConfig, GridGap, GridBlock, GridTemplate


def markdown_to_html(content: str) -> str:
    """
    Convert markdown content to HTML for use in grid cells.

    Args:
        content: Markdown string

    Returns:
        HTML string with basic styling
    """
    # Convert markdown to HTML
    html = md.markdown(content, extensions=['extra', 'nl2br', 'sane_lists'])

    # Wrap in a styled container
    return f'''<div class="markdown-cell" style="padding: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6;">
        <style>
            .markdown-cell h1, .markdown-cell h2, .markdown-cell h3, .markdown-cell h4 {{
                margin-top: 0;
                margin-bottom: 0.5em;
                color: #1a1a1a;
            }}
            .markdown-cell h3 {{ font-size: 1.2em; }}
            .markdown-cell p {{ margin: 0.5em 0; color: #333; }}
            .markdown-cell ul, .markdown-cell ol {{ margin: 0.5em 0; padding-left: 1.5em; }}
            .markdown-cell li {{ margin: 0.25em 0; }}
            .markdown-cell strong {{ font-weight: 600; }}
            .markdown-cell code {{ background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }}
        </style>
        {html}
    </div>'''


# Gap size mappings (pixels)
GAP_SIZES = {
    GridGap.NONE: 0,
    GridGap.SM: 4,
    GridGap.MD: 8,
    GridGap.LG: 16,
    GridGap.XL: 24,
}

# Background colors for different cell types
CELL_BACKGROUNDS = {
    'markdown': '#f8f9fa',  # Light gray for markdown cells
    'exhibit': '#ffffff',   # White for exhibit cells
}


def _render_matrix_grid(
    grid_config: GridConfig,
    cell_contents: Dict[int, str],
    cell_types: Dict[int, str],
    max_height: Optional[int],
    sync_scroll: bool,
    gap: int,
):
    """
    Render grid using CSS Grid template areas from matrix layout.

    Matrix layout example:
        layout: [[1, 2, 3], [1, 4, 5]]
        - Cell 1 spans 2 rows (appears in both rows, column 1)
        - Cells 2,3 are in row 1, columns 2,3
        - Cells 4,5 are in row 2, columns 2,3

    Args:
        grid_config: Grid configuration with layout matrix
        cell_contents: Dict mapping cell_id -> HTML content
        cell_types: Dict mapping cell_id -> 'markdown' or 'exhibit'
        max_height: Max height for scrollable cells
        sync_scroll: Enable synchronized scrolling
        gap: Gap size in pixels
    """
    import uuid

    layout = grid_config.layout
    sizes = grid_config.sizes or {}
    num_rows = len(layout)
    num_cols = len(layout[0]) if layout else 0

    # Build CSS Grid template areas
    # e.g., [[1,2,3], [1,4,5]] -> "cell1 cell2 cell3" "cell1 cell4 cell5"
    template_areas = []
    for row in layout:
        row_areas = " ".join(f"cell{cell_id}" for cell_id in row)
        template_areas.append(f'"{row_areas}"')
    grid_template_areas = " ".join(template_areas)

    # Build column sizes from config.sizes
    # Determine unique columns and their sizes
    # For each column position, find the cell_id and look up its size
    column_sizes = []
    for col_idx in range(num_cols):
        # Get the cell_id in this column (from first row where it appears)
        cell_id = layout[0][col_idx]
        size = sizes.get(cell_id, "1fr")
        # Ensure size has units
        if isinstance(size, (int, float)):
            size = f"{size}fr"
        elif not any(size.endswith(unit) for unit in ['fr', 'px', '%', 'em', 'rem']):
            size = f"{size}"  # Assume it's already valid
        column_sizes.append(size)
    grid_template_columns = " ".join(column_sizes)

    # Get unique cell IDs (preserving order of first appearance)
    seen = set()
    unique_cells = []
    for row in layout:
        for cell_id in row:
            if cell_id not in seen:
                seen.add(cell_id)
                unique_cells.append(cell_id)

    # Build cell HTML elements
    cells_html = []
    scroll_class = "sync-scroll" if sync_scroll else "grid-scroll"

    for cell_id in unique_cells:
        html = cell_contents.get(cell_id, f'<div style="padding:16px;color:#999;">Cell {cell_id} (empty)</div>')
        cell_type = cell_types.get(cell_id, 'exhibit')
        bg_color = CELL_BACKGROUNDS.get(cell_type, '#ffffff')

        if max_height:
            cell_scroll_style = f"max-height:{max_height}px;overflow-y:auto;overflow-x:auto;"
        else:
            cell_scroll_style = ""

        cells_html.append(f'''<div class="gt-cell-wrapper cell-{cell_id}" style="grid-area:cell{cell_id};display:flex;flex-direction:column;min-width:0;border:1px solid #e0e0e0;background:{bg_color};">
<div class="gt-cell {scroll_class}" style="flex:1;min-height:0;{cell_scroll_style}">{html}</div>
</div>''')

    # Generate unique ID for this grid instance
    grid_id = f"grid-{uuid.uuid4().hex[:8]}"

    # Build sticky header CSS
    sticky_css = f'''
        #{grid_id} .gt-cell thead {{
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
        }}
        #{grid_id} .gt-cell thead th {{
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
        }}
    ''' if max_height else ''

    # Build sync scroll JavaScript
    sync_js = f'''
    <script>
        (function setupScrollSync() {{
            const grid = document.getElementById('{grid_id}');
            if (!grid) return;
            const scrollables = grid.querySelectorAll('.sync-scroll');
            console.log('Matrix grid sync: Found ' + scrollables.length + ' scrollable elements');

            if (scrollables.length < 2) return;

            let isSyncing = false;
            scrollables.forEach(function(el) {{
                el.addEventListener('scroll', function(e) {{
                    if (isSyncing) return;
                    isSyncing = true;
                    const top = this.scrollTop;
                    const left = this.scrollLeft;
                    scrollables.forEach(function(other) {{
                        if (other !== e.target) {{
                            other.scrollTop = top;
                            other.scrollLeft = left;
                        }}
                    }});
                    requestAnimationFrame(function() {{ isSyncing = false; }});
                }});
            }});
            console.log('Matrix grid scroll sync complete');
        }})();
    </script>
    ''' if sync_scroll else ''

    # Build the full HTML
    grid_html = f'''<!DOCTYPE html>
<html>
<head>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}

        #{grid_id} * {{ box-sizing: border-box; }}

        #{grid_id} .gt-cell > div {{
            overflow: visible !important;
            height: auto !important;
            width: 100% !important;
        }}

        #{grid_id} table,
        #{grid_id} .gt_table {{
            width: 100% !important;
            margin: 0 !important;
            border-collapse: collapse !important;
        }}
        #{grid_id} .gt_table_container {{ width: 100% !important; margin: 0 !important; }}

        {sticky_css}
    </style>
</head>
<body>
    <div id="{grid_id}" class="de-funk-grid-wrapper" style="border:1px solid #ddd;border-radius:4px;">
        <div class="de-funk-grid" style="display:grid;grid-template-areas:{grid_template_areas};grid-template-columns:{grid_template_columns};gap:{gap}px;width:100%;">{''.join(cells_html)}</div>
    </div>
    {sync_js}
</body>
</html>'''

    # Calculate component height
    cell_height = max_height if max_height else 400
    component_height = (num_rows * cell_height) + ((num_rows - 1) * gap) + 50  # Extra padding for borders

    components.html(grid_html, height=component_height, scrolling=False)


def render_html_grid(
    grid_config: GridConfig,
    html_contents: List[str],
    titles: Optional[List[str]] = None,
    max_height: Optional[int] = None,
    sync_scroll: bool = False,
    cell_contents: Optional[Dict[int, str]] = None,
    cell_types: Optional[Dict[int, str]] = None,
):
    """
    Render multiple HTML blocks in a pure CSS Grid layout.

    This creates a single HTML block with no Streamlit padding - crisp exhibits.
    Optionally syncs scrolling across all cells with sticky headers.

    Supports multiple layout modes:
    1. Matrix layout: grid_config.layout = [[1,2,3], [1,4,5]] with cell_contents dict
       - Cell IDs that repeat across rows span those rows
       - Uses CSS Grid template areas for precise positioning
    2. Sequential layout: html_contents list rendered left-to-right, top-to-bottom

    Args:
        grid_config: Grid configuration
        html_contents: List of HTML strings (for sequential mode)
        titles: Optional list of titles for each cell
        max_height: Optional max height for scrollable grid
        sync_scroll: Enable synchronized scrolling across all grid cells (default False)
        cell_contents: Dict mapping cell_id -> HTML content (for matrix mode)
        cell_types: Dict mapping cell_id -> content type ('markdown' or 'exhibit')
    """
    gap = GAP_SIZES.get(grid_config.gap, 0)

    # Check for matrix layout mode
    if grid_config.layout and cell_contents:
        _render_matrix_grid(
            grid_config, cell_contents, cell_types or {},
            max_height, sync_scroll, gap
        )
        return

    # Fall back to sequential mode
    if not html_contents:
        return

    num_items = len(html_contents)

    # Standard grid layout
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
    scroll_class = "sync-scroll" if sync_scroll else "grid-scroll"
    for i, html in enumerate(html_contents):
        if max_height:
            wrapper_height = f"height:{max_height}px;"
            cell_scroll_style = f"max-height:{max_height}px;overflow-y:scroll;overflow-x:auto;"
        else:
            wrapper_height = ""
            cell_scroll_style = ""

        cells_html.append(f'''<div class="gt-cell-wrapper" style="display:flex;flex-direction:column;min-width:0;border:1px solid #e0e0e0;{wrapper_height}">
<div class="gt-cell {scroll_class}" style="flex:1;min-height:0;{cell_scroll_style}">{html}</div>
</div>''')

    # Generate unique ID for this grid instance
    import uuid
    grid_id = f"grid-{uuid.uuid4().hex[:8]}"

    # Build sticky header CSS (always applied for scrollable grids)
    sticky_css = f'''
        /* Sticky headers - lock thead at top of scroll container */
        #{grid_id} .gt-cell thead {{
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
        }}
        #{grid_id} .gt-cell thead th {{
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
        }}
    ''' if max_height else ''

    # Build sync scroll JavaScript (only when sync_scroll is enabled)
    sync_js = f'''
    <script>
        // Sync scrolling setup - runs immediately when DOM is ready
        (function setupScrollSync() {{
            const grid = document.getElementById('{grid_id}');
            if (!grid) {{
                console.error('Grid not found: {grid_id}');
                return;
            }}
            const scrollables = grid.querySelectorAll('.sync-scroll');
            console.log('Sync scroll setup: Found ' + scrollables.length + ' scrollable elements in {grid_id}');

            if (scrollables.length < 2) {{
                console.log('Not enough scrollables for sync');
                return;
            }}

            let isSyncing = false;

            scrollables.forEach(function(el, idx) {{
                el.addEventListener('scroll', function(e) {{
                    if (isSyncing) return;
                    isSyncing = true;
                    const top = this.scrollTop;
                    const left = this.scrollLeft;
                    scrollables.forEach(function(other) {{
                        if (other !== e.target) {{
                            other.scrollTop = top;
                            other.scrollLeft = left;
                        }}
                    }});
                    requestAnimationFrame(function() {{ isSyncing = false; }});
                }});
            }});
            console.log('Scroll sync setup complete for {grid_id}');
        }})();
    </script>
    ''' if sync_scroll else ''

    # Combine into CSS Grid layout
    grid_html = f'''<!DOCTYPE html>
<html>
<head>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}

        #{grid_id} * {{ box-sizing: border-box; }}

        /* CRITICAL: Remove GT's wrapper overflow so our container handles scrolling */
        #{grid_id} .gt-cell > div {{
            overflow: visible !important;
            height: auto !important;
            width: 100% !important;
        }}

        #{grid_id} table,
        #{grid_id} .gt_table {{
            width: 100% !important;
            margin: 0 !important;
            border-collapse: collapse !important;
        }}
        #{grid_id} .gt_table_container {{ width: 100% !important; margin: 0 !important; }}

        {sticky_css}
    </style>
</head>
<body>
    <div id="{grid_id}" class="de-funk-grid-wrapper" style="border:1px solid #ddd;border-radius:4px;">
        <div class="de-funk-grid" style="display:grid;grid-template-columns:{grid_template};gap:{gap}px;width:100%;">{''.join(cells_html)}</div>
    </div>
    {sync_js}
</body>
</html>'''

    # Calculate component height based on grid structure
    # For row-based grids, calculate total height needed
    cell_height = max_height if max_height else 400
    component_height = (num_rows * cell_height) + ((num_rows - 1) * gap) + 20  # 20px padding

    # Use components.html which allows JavaScript execution (unlike st.html)
    components.html(grid_html, height=component_height, scrolling=False)


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
            # Determine max_height for linked scrolling
            # Default to scrolling enabled for grids (better UX)
            max_height = getattr(grid_config, 'max_height', None)
            scroll = getattr(grid_config, 'scroll', True)  # Default to True for grids
            sync_scroll = getattr(grid_config, 'sync_scroll', False)  # Default sync off

            if scroll and not max_height:
                max_height = 400  # Default scroll height

            render_html_grid(grid_config, html_contents, titles, max_height=max_height, sync_scroll=sync_scroll)
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


def collect_grid_cells(
    content_blocks: List[Dict[str, Any]],
    grid_index: int
) -> List[Dict[str, Any]]:
    """
    Collect all cell blocks (markdown and exhibits) belonging to a specific grid.

    This function collects both markdown content and exhibits as grid cells,
    preserving their order. Markdown blocks become text cells in the grid.

    Args:
        content_blocks: All content blocks from notebook
        grid_index: Index of the grid to collect cells for

    Returns:
        List of cell blocks (both markdown and exhibit types) belonging to the grid
    """
    grid_cells = []
    in_grid = False

    for block in content_blocks:
        block_type = block.get('type')

        if block_type == 'grid_start' and block.get('grid_index') == grid_index:
            in_grid = True
            continue

        if block_type == 'grid_end' and block.get('grid_index') == grid_index:
            in_grid = False
            continue

        if in_grid:
            if block_type == 'exhibit':
                grid_cells.append(block)
            elif block_type == 'markdown_block':
                # Explicit $markdown${} block with grid_cell assignment
                grid_cells.append(block)
            elif block_type == 'markdown':
                # Only include substantial markdown content (not just whitespace/separators)
                content = block.get('content', '').strip()
                # Skip horizontal rules and empty content
                if content and content not in ('---', '***', '___'):
                    grid_cells.append(block)

    return grid_cells


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
