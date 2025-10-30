"""
Notebook view component.

Handles rendering of notebook exhibits in layout sections.
"""

import streamlit as st
from src.notebook.schema import ExhibitType
from .exhibits import (
    render_metric_cards,
    render_line_chart,
    render_bar_chart,
    render_data_table,
)


def render_notebook_exhibits(notebook_id: str, notebook_config, notebook_session, connection):
    """
    Render all notebook exhibits according to layout.

    Args:
        notebook_id: Unique identifier for the notebook
        notebook_config: NotebookConfig with exhibits and layout
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas (DuckDB or Spark)
    """
    # Render layout sections
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
        st.error(f"Exhibit not found: {exhibit_id}")
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
        else:
            st.warning(f"Exhibit type not yet implemented: {exhibit.type}")

    except Exception as e:
        st.error(f"Error rendering exhibit: {str(e)}")
        with st.expander("Show details"):
            st.exception(e)
