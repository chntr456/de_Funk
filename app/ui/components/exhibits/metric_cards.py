"""
Metric cards exhibit component.

Renders key metrics as styled cards with formatted values.
"""

import streamlit as st
import pandas as pd
from typing import List
from app.notebook.schema import MetricConfig, AggregationType, ColumnReference
from .measure_selector import render_measure_selector


def _extract_field_name(measure):
    """Extract field name from ColumnReference or model.table.column string."""
    if isinstance(measure, ColumnReference):
        return measure.field
    if isinstance(measure, str) and '.' in measure:
        return measure.split('.')[-1]
    return measure


def render_metric_cards(exhibit, pdf: pd.DataFrame):
    """
    Render metric cards exhibit.

    Args:
        exhibit: Exhibit configuration with metrics list or measure_selector
        pdf: Pandas DataFrame with data (will be aggregated if needed)
    """
    if exhibit.title:
        st.subheader(exhibit.title)

    # Determine which metrics to display
    metrics_to_render = []

    # Check if dynamic measure selector is configured
    if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        # Render measure selector and get selected measures
        selected_measures = render_measure_selector(
            exhibit_id=exhibit.id,
            measure_selector_config=exhibit.measure_selector,
            available_columns=pdf.columns.tolist()
        )

        # Create metric configs for selected measures
        for measure in selected_measures:
            # Use default aggregation from measure_selector options or avg
            default_agg = AggregationType.AVG
            if (hasattr(exhibit, 'options') and exhibit.options and
                    'default_aggregation' in exhibit.options):
                default_agg = AggregationType(exhibit.options['default_aggregation'])

            metrics_to_render.append(MetricConfig(
                measure=measure,
                label=measure.replace('_', ' ').title(),
                aggregation=default_agg
            ))

    # Otherwise use static metrics configuration
    elif exhibit.metrics:
        metrics_to_render = exhibit.metrics

    # Render metric cards
    if metrics_to_render:
        # Add a small divider if we have a measure selector
        if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
            st.markdown("---")

        cols = st.columns(len(metrics_to_render))
        for i, metric_config in enumerate(metrics_to_render):
            with cols[i]:
                _render_single_metric_card(metric_config, pdf)


def _render_single_metric_card(metric_config: MetricConfig, pdf: pd.DataFrame):
    """
    Render a single metric card.

    Args:
        metric_config: Metric configuration
        pdf: Pandas DataFrame with data
    """
    measure_id = _extract_field_name(metric_config.measure)

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
        elif agg_method == 'count_distinct':
            value = pdf[measure_id].nunique()
        elif agg_method == 'first':
            value = pdf[measure_id].iloc[0] if len(pdf) > 0 else 0
        elif agg_method == 'last':
            value = pdf[measure_id].iloc[-1] if len(pdf) > 0 else 0
        else:
            value = pdf[measure_id].iloc[0] if len(pdf) > 0 else 0

        # Format value - use config format if provided, otherwise smart defaults
        fmt = getattr(metric_config, 'format', None)
        if pd.isna(value):
            formatted = "N/A"
        elif fmt:
            # Use explicit format string from config
            try:
                formatted = f"{value:{fmt}}"
            except (ValueError, KeyError):
                formatted = str(value)
        elif agg_method == 'count' or agg_method == 'count_distinct':
            # Count metrics shouldn't have currency formatting
            formatted = f"{int(value):,}"
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
