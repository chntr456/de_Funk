"""
Metric cards exhibit component.

Renders key metrics as styled cards with formatted values.
"""

import streamlit as st
import pandas as pd


def render_metric_cards(exhibit, pdf: pd.DataFrame):
    """
    Render metric cards exhibit.

    Args:
        exhibit: Exhibit configuration with metrics list
        pdf: Pandas DataFrame with aggregated data
    """
    st.subheader(exhibit.title)

    if exhibit.metrics:
        cols = st.columns(len(exhibit.metrics))
        for i, metric_config in enumerate(exhibit.metrics):
            with cols[i]:
                measure_id = metric_config.measure
                if measure_id in pdf.columns:
                    value = pdf[measure_id].iloc[0] if len(pdf) > 0 else 0

                    # Format value based on magnitude
                    if pd.isna(value):
                        formatted = "N/A"
                    elif abs(value) >= 1e9:
                        formatted = f"${value/1e9:.2f}B"
                    elif abs(value) >= 1e6:
                        formatted = f"${value/1e6:.2f}M"
                    elif abs(value) >= 1e3:
                        formatted = f"${value/1e3:.2f}K"
                    else:
                        formatted = f"${value:,.2f}"

                    # Use Streamlit metric with delta styling
                    display_name = measure_id.replace('_', ' ').title()
                    st.metric(label=display_name, value=formatted)
                else:
                    st.metric(label=measure_id.replace('_', ' ').title(), value="N/A")
