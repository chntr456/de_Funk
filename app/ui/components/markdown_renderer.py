"""
Markdown renderer component for notebook UI.

Renders markdown content with embedded exhibits and collapsible sections.
Uses ToggleContainer instead of st.expander to avoid nesting issues.
"""

import streamlit as st
import markdown
from typing import Dict, Any, List, Optional, Callable, Union
from app.notebook.schema import NotebookConfig
from .toggle_container import ToggleContainer, apply_toggle_styles


def render_markdown_notebook(
    notebook_config: NotebookConfig,
    notebook_session,
    connection,
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render a markdown-based notebook.

    Args:
        notebook_config: NotebookConfig with markdown content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        editable: Whether blocks can be edited inline
        on_block_edit: Callback when a block is edited (block_index, new_content)
    """
    if not hasattr(notebook_config, '_content_blocks') or not notebook_config._content_blocks:
        st.error("This notebook has no markdown content blocks")
        return

    # Apply toggle container styles
    apply_toggle_styles()

    # Import exhibit renderers
    from .exhibits import (
        render_metric_cards,
        render_line_chart,
        render_bar_chart,
        render_data_table,
    )
    from .exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart
    from .exhibits.forecast_chart import render_forecast_chart, render_forecast_metrics_table

    # Render each content block
    for block_index, block in enumerate(notebook_config._content_blocks):
        block_type = block['type']

        # Wrap in editable container if enabled
        if editable:
            render_editable_block_wrapper(
                block_index=block_index,
                block=block,
                notebook_session=notebook_session,
                connection=connection,
                on_edit=on_block_edit
            )
        else:
            # Standard rendering
            if block_type == 'markdown':
                render_markdown_block(block['content'], block_index=block_index)

            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection)

            elif block_type == 'collapsible':
                render_collapsible_section(block, notebook_session, connection, block_index=block_index)

            elif block_type == 'error':
                render_error_block(block, block_index=block_index)


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
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Wrap a content block with editing controls.

    Provides inline editing capability for individual blocks.

    Args:
        block_index: Index of this block
        block: Content block data
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        on_edit: Callback when block is edited
    """
    block_type = block['type']

    # Generate unique key for this block's edit state
    edit_key = f"block_edit_mode_{block_index}"

    # Initialize edit state
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    is_editing = st.session_state[edit_key]

    # Create container for the block with edit controls
    col_content, col_edit = st.columns([0.95, 0.05])

    with col_edit:
        # Edit button (only for markdown blocks)
        if block_type == 'markdown':
            if is_editing:
                if st.button("✕", key=f"cancel_edit_{block_index}", help="Cancel editing"):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                if st.button("✏️", key=f"start_edit_{block_index}", help="Edit this block"):
                    st.session_state[edit_key] = True
                    st.rerun()

    with col_content:
        if is_editing and block_type == 'markdown':
            # Edit mode for markdown
            _render_block_editor(block_index, block, on_edit)
        else:
            # View mode
            if block_type == 'markdown':
                render_markdown_block(block['content'], block_index=block_index)
            elif block_type == 'exhibit':
                render_exhibit_block(block, notebook_session, connection)
            elif block_type == 'collapsible':
                render_collapsible_section(block, notebook_session, connection, block_index=block_index)
            elif block_type == 'error':
                render_error_block(block, block_index=block_index)


def _render_block_editor(
    block_index: int,
    block: Dict[str, Any],
    on_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render inline editor for a content block.

    Args:
        block_index: Index of the block being edited
        block: Block data containing content
        on_edit: Callback when content is saved
    """
    content = block.get('content', '')
    edit_key = f"block_edit_mode_{block_index}"
    content_key = f"block_content_{block_index}"

    # Store original content for comparison
    if content_key not in st.session_state:
        st.session_state[content_key] = content

    # Editor
    st.markdown("**Editing Block**")

    edited_content = st.text_area(
        "Content",
        value=st.session_state[content_key],
        height=200,
        key=f"editor_textarea_{block_index}",
        label_visibility="collapsed"
    )

    # Update stored content
    st.session_state[content_key] = edited_content

    # Action buttons
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6])

    with col1:
        if st.button("💾 Save", key=f"save_block_{block_index}", type="primary"):
            # Call the on_edit callback if provided
            if on_edit:
                on_edit(block_index, edited_content)

            # Exit edit mode
            st.session_state[edit_key] = False
            st.success("Block saved!")
            st.rerun()

    with col2:
        if st.button("Cancel", key=f"cancel_block_{block_index}"):
            # Reset content and exit edit mode
            st.session_state[content_key] = content
            st.session_state[edit_key] = False
            st.rerun()

    # Show preview
    with ToggleContainer(
        "Preview",
        expanded=True,
        container_id=f"preview_{block_index}",
        style="minimal"
    ) as tc:
        if tc.is_open:
            md = markdown.Markdown(
                extensions=['extra', 'codehilite', 'nl2br', 'sane_lists', 'toc']
            )
            html = md.convert(edited_content)
            st.markdown(html, unsafe_allow_html=True)
