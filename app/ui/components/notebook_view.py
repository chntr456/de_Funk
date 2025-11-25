"""
Notebook view component.

Handles rendering of notebook exhibits in layout sections.
Supports both YAML and Markdown notebook formats.
"""

import streamlit as st
from typing import Optional, Callable
from app.notebook.schema import ExhibitType
from .exhibits import (
    render_metric_cards,
    render_line_chart,
    render_bar_chart,
    render_data_table,
)
from .exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart
from .exhibits.forecast_chart import render_forecast_chart, render_forecast_metrics_table


def render_notebook_exhibits(
    notebook_id: str,
    notebook_config,
    notebook_session,
    connection,
    editable: bool = False,
    on_block_edit: Optional[Callable[[int, str], None]] = None,
    on_block_insert: Optional[Callable[[int, str, str], None]] = None,
    on_block_delete: Optional[Callable[[int], None]] = None,
    on_header_edit: Optional[Callable[[int, str], None]] = None
):
    """
    Render all notebook exhibits according to layout.

    Args:
        notebook_id: Unique identifier for the notebook
        notebook_config: NotebookConfig with exhibits and layout
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        editable: Whether blocks can be edited inline
        on_block_edit: Callback when a block is edited
        on_block_insert: Callback when a block is inserted
        on_block_delete: Callback when a block is deleted
        on_header_edit: Callback when a header is renamed
    """
    # Check if this is a markdown notebook
    if hasattr(notebook_config, '_is_markdown') and notebook_config._is_markdown:
        from .markdown_renderer import render_markdown_notebook, apply_markdown_styles
        apply_markdown_styles()
        render_markdown_notebook(
            notebook_config,
            notebook_session,
            connection,
            notebook_id=notebook_id,
            editable=editable,
            on_block_edit=on_block_edit,
            on_block_insert=on_block_insert,
            on_block_delete=on_block_delete,
            on_header_edit=on_header_edit
        )
    else:
        # Render YAML notebook (traditional layout sections)
        for section in notebook_config.layout:
            render_section(section, notebook_config, notebook_session, connection)


def render_section(section, notebook_config, notebook_session, connection):
    """
    Render a layout section.

    Args:
        section: Section config with title, exhibits, columns
        notebook_config: NotebookConfig for exhibit lookup
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for pandas conversion
    """
    if section.title:
        st.subheader(section.title)
    if section.description:
        st.markdown(section.description)

    # Create columns if specified
    if section.columns > 1:
        cols = st.columns(section.columns)
        for i, exhibit_id in enumerate(section.exhibits):
            with cols[i % section.columns]:
                render_exhibit(exhibit_id, notebook_config, notebook_session, connection)
    else:
        for exhibit_id in section.exhibits:
            render_exhibit(exhibit_id, notebook_config, notebook_session, connection)


def render_exhibit(exhibit_id: str, notebook_config, notebook_session, connection):
    """
    Render a single exhibit.

    Args:
        exhibit_id: ID of the exhibit to render
        notebook_config: NotebookConfig for exhibit lookup
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for pandas conversion (DuckDB or Spark)
    """
    # Find exhibit
    exhibit = None
    for ex in notebook_config.exhibits:
        if ex.id == exhibit_id:
            exhibit = ex
            break

    if not exhibit:
        available_ids = [ex.id for ex in notebook_config.exhibits]
        st.error(f"Exhibit not found: {exhibit_id}")
        st.caption(f"Available exhibits: {available_ids}")
        st.caption(f"Notebook: {notebook_config.notebook.title if hasattr(notebook_config, 'notebook') else 'Unknown'}")
        return

    # Get data for exhibit
    try:
        with st.spinner(f"Loading {exhibit.title}..."):
            df = notebook_session.get_exhibit_data(exhibit_id)
            # Use connection to convert to pandas (works with DuckDB or Spark)
            pdf = connection.to_pandas(df)

        # Render based on type
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
