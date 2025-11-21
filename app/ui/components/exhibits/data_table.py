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

    # Debug: Check what type we're actually receiving
    if not isinstance(pdf, pd.DataFrame):
        st.error(f"⚠️ Expected pandas DataFrame, got {type(pdf).__name__}")
        st.caption(f"Has .data attribute: {hasattr(pdf, 'data')}")
        if hasattr(pdf, 'data'):
            st.caption(f"Data type: {type(pdf.data).__name__}")
            pdf = pdf.data  # Extract data if it's a QueryResult

    # Debug: Check data types
    if isinstance(pdf, pd.DataFrame):
        # Check for problematic columns
        problematic = []
        for col in pdf.columns:
            if pdf[col].dtype == 'object':
                sample = pdf[col].iloc[0] if len(pdf) > 0 else None
                if sample is not None and not isinstance(sample, (str, int, float, bool)):
                    problematic.append((col, type(sample).__name__))

        if problematic:
            st.warning(f"⚠️ Found {len(problematic)} columns with non-primitive types:")
            for col, dtype in problematic:
                st.caption(f"  - {col}: {dtype}")

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
