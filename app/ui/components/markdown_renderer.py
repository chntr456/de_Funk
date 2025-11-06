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
            exhibit = block['exhibit']
            exhibit_id = block['id']

            try:
                with st.spinner(f"Loading {exhibit.title}..."):
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
                with st.expander("Show details"):
                    st.exception(e)

        elif block_type == 'error':
            # Render error block
            st.error(f"Error: {block['message']}")
            with st.expander("Show exhibit YAML"):
                st.code(block['content'], language='yaml')


def render_markdown_block(content: str):
    """
    Render a markdown content block.

    Supports:
    - Standard markdown (headers, bold, italic, lists, etc.)
    - HTML tags (for collapsible sections)
    - Code blocks
    - Tables
    - Links and images

    Args:
        content: Markdown content string
    """
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

    # Render HTML in Streamlit
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
    - Better collapsible sections
    - Improved code blocks
    - Enhanced tables
    - Better spacing
    """
    st.markdown("""
    <style>
    /* Collapsible sections (details/summary) */
    details {
        background-color: rgba(28, 131, 225, 0.1);
        border-left: 3px solid #1c83e1;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }

    summary {
        font-weight: 600;
        cursor: pointer;
        user-select: none;
        padding: 0.5rem;
        margin: -0.5rem;
    }

    summary:hover {
        background-color: rgba(28, 131, 225, 0.2);
        border-radius: 4px;
    }

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
