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
        pdf: Pandas DataFrame with data (will be aggregated if needed)
    """
    if exhibit.title:
        st.subheader(exhibit.title)

    if exhibit.metrics:
        cols = st.columns(len(exhibit.metrics))
        for i, metric_config in enumerate(exhibit.metrics):
            with cols[i]:
                measure_id = metric_config.measure

                # Get aggregation method (default to first value if not specified)
                agg_method = 'first'
                if hasattr(metric_config, 'aggregation') and metric_config.aggregation:
                    agg_method = metric_config.aggregation.value

                # Calculate aggregated value
                if measure_id in pdf.columns:
                    if agg_method == 'sum':
                        value = pdf[measure_id].sum()
                    elif agg_method == 'avg':
                        value = pdf[measure_id].mean()
                    elif agg_method == 'min':
                        value = pdf[measure_id].min()
                    elif agg_method == 'max':
                        value = pdf[measure_id].max()
                    elif agg_method == 'count':
                        value = pdf[measure_id].count()
                    else:
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

                    # Use label from config or default to measure name
                    display_name = metric_config.label if hasattr(metric_config, 'label') and metric_config.label else measure_id.replace('_', ' ').title()
                    st.metric(label=display_name, value=formatted)
                else:
                    display_name = metric_config.label if hasattr(metric_config, 'label') and metric_config.label else measure_id.replace('_', ' ').title()
                    st.metric(label=display_name, value="N/A")
