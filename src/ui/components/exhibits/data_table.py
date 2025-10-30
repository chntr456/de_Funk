"""
Data table exhibit component.

Renders tabular data with optional download functionality.
"""

import streamlit as st
import pandas as pd


def render_data_table(exhibit, pdf: pd.DataFrame):
    """
    Render data table exhibit.

    Args:
        exhibit: Exhibit configuration with columns, download settings
        pdf: Pandas DataFrame with data to display
    """
    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    # Display dataframe
    st.dataframe(
        pdf,
        use_container_width=True,
        hide_index=True,
    )

    # Download button if enabled
    if exhibit.download:
        csv = pdf.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{exhibit.id}.csv",
            mime="text/csv",
        )
