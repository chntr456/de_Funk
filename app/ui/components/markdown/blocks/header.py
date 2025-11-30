"""
Header block renderers.

Handles rendering of notebook headers and filter section headers.
"""

import streamlit as st

from app.notebook.schema import NotebookConfig


def render_notebook_header(notebook_config: NotebookConfig):
    """
    Render notebook header with metadata.

    Args:
        notebook_config: NotebookConfig with metadata
    """
    metadata = notebook_config.notebook

    # Title
    st.title(metadata.title)

    # Metadata row
    cols = st.columns([0.3, 0.3, 0.2, 0.2])

    with cols[0]:
        if metadata.description:
            st.caption(metadata.description)

    with cols[1]:
        if metadata.author:
            st.caption(f"👤 {metadata.author}")

    with cols[2]:
        if metadata.updated:
            st.caption(f"📅 {metadata.updated}")

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
