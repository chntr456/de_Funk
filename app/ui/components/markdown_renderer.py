"""
Markdown renderer component for notebook UI.

Renders markdown content with embedded exhibits and collapsible sections.
"""

import streamlit as st
import markdown
from typing import Dict, Any, List
from app.notebook.schema import NotebookConfig


def render_markdown_notebook(notebook_config: NotebookConfig, notebook_session, connection):
    """
    Render a markdown-based notebook.

    Args:
        notebook_config: NotebookConfig with markdown content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
    """
    if not hasattr(notebook_config, '_content_blocks') or not notebook_config._content_blocks:
        st.error("This notebook has no markdown content blocks")
        return

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
    for block in notebook_config._content_blocks:
        block_type = block['type']

        if block_type == 'markdown':
            # Render markdown content
            render_markdown_block(block['content'])

        elif block_type == 'exhibit':
            # Render exhibit
            render_exhibit_block(block, notebook_session, connection)

        elif block_type == 'collapsible':
            # Render collapsible section with st.expander
            render_collapsible_section(block, notebook_session, connection)

        elif block_type == 'error':
            # Render error block
            st.error(f"Error: {block['message']}")
            with st.expander("Show exhibit YAML"):
                st.code(block['content'], language='yaml')


def render_exhibit_block(block: Dict[str, Any], notebook_session, connection):
    """
    Render a single exhibit block.

    Supports collapsible exhibits via exhibit.collapsible flag.
    Auto-wraps exhibits with selectors in a collapsible section.

    Args:
        block: Content block with exhibit data
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
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
                pdf = connection.to_pandas(df)

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
                render_forecast_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.FORECAST_METRICS_TABLE:
                render_forecast_metrics_table(exhibit, pdf)
            else:
                st.warning(f"Exhibit type not yet implemented: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering exhibit: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    # Wrap in expander if collapsible or has selectors
    if is_collapsible:
        with st.expander(collapsible_title, expanded=collapsible_expanded):
            _render_exhibit_content()
    else:
        _render_exhibit_content()


def render_collapsible_section(block: Dict[str, Any], notebook_session, connection):
    """
    Render a collapsible section using st.expander.

    Args:
        block: Content block with summary and inner content
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
    """
    summary = block['summary']
    inner_blocks = block['content']

    # Use st.expander for collapsible sections
    with st.expander(summary, expanded=False):
        # Render inner content blocks
        for inner_block in inner_blocks:
            inner_type = inner_block['type']

            if inner_type == 'markdown':
                # Pass in_collapsible=True to prevent nested expanders
                render_markdown_block(inner_block['content'], in_collapsible=True)

            elif inner_type == 'exhibit':
                render_exhibit_block(inner_block, notebook_session, connection)

            elif inner_type == 'error':
                st.error(f"Error: {inner_block['message']}")
                # Don't use expander - already inside one
                st.caption("Exhibit YAML:")
                st.code(inner_block['content'], language='yaml')


def render_markdown_block(content: str, in_collapsible: bool = False):
    """
    Render a markdown content block.

    Text paragraphs are wrapped in a collapsible "📄 Details" expander
    to enable a clean view of just exhibits and headers (unless already
    inside a collapsible section to avoid nesting).

    Supports:
    - Standard markdown (headers, bold, italic, lists, etc.)
    - HTML tags (for collapsible sections)
    - Code blocks
    - Tables
    - Links and images

    Args:
        content: Markdown content string
        in_collapsible: True if already rendering inside a collapsible section
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
        # Already inside a collapsible section - don't nest expanders
        st.markdown(html, unsafe_allow_html=True)
    else:
        # Wrap text paragraphs in collapsible section for clean view
        with st.expander("📄 Details", expanded=False):
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
