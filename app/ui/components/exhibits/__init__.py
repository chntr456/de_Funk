"""
Exhibit rendering components.

Each exhibit type has its own module for rendering.

The get_exhibit_html() function provides a unified interface for getting
HTML output from any exhibit type, used for CSS grid layouts.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union
import pandas as pd

from config.logging import get_logger
from app.notebook.schema import ColumnReference


def _extract_field_name(col_ref: Union[ColumnReference, str, None]) -> Optional[str]:
    """Extract field name from ColumnReference object or return string as-is."""
    if col_ref is None:
        return None
    if isinstance(col_ref, ColumnReference):
        return col_ref.field
    return col_ref

from .metric_cards import render_metric_cards
from .line_chart import get_line_chart_html
from .bar_chart import get_bar_chart_html
from .data_table import render_data_table
from .weighted_aggregate_chart import render_weighted_aggregate_chart
from .forecast_chart import render_forecast_chart, render_forecast_metrics_table

logger = get_logger(__name__)


def get_exhibit_html(
    exhibit: Any,
    pdf: pd.DataFrame,
    model_schema: Optional[Dict] = None,
    selected_measures: Optional[list] = None,
    selected_dimension: Optional[str] = None,
) -> Optional[str]:
    """
    Get HTML string from any exhibit type for CSS grid embedding.

    This is the unified dispatcher that routes to the appropriate
    HTML export function based on exhibit type.

    Args:
        exhibit: Exhibit configuration object with a 'type' attribute
        pdf: Pandas DataFrame with data
        model_schema: Optional model schema (used by great_table for column groups)
        selected_measures: Optional list of selected measures (from UI selector)
        selected_dimension: Optional selected dimension for grouping (from UI selector)

    Returns:
        HTML string or None if the exhibit type doesn't support HTML export
    """
    if pdf is None or pdf.empty:
        return '<div style="color: #888; padding: 8px;">No data available</div>'

    # Normalize exhibit type to string for comparison
    exhibit_type = _get_exhibit_type_string(exhibit)

    if not exhibit_type:
        logger.warning(f"Could not determine exhibit type for {exhibit}")
        return None

    logger.debug(f"get_exhibit_html: type={exhibit_type}, selected_measures={selected_measures}, selected_dimension={selected_dimension}")

    try:
        # Great Tables
        if exhibit_type == 'great_table':
            from .great_table import get_great_table_html
            return get_great_table_html(exhibit, pdf, model_schema)

        # Line Charts
        if exhibit_type == 'line_chart':
            from .line_chart import get_line_chart_html
            return get_line_chart_html(exhibit, pdf, selected_measures, selected_dimension)

        # Bar Charts
        if exhibit_type == 'bar_chart':
            from .bar_chart import get_bar_chart_html
            return get_bar_chart_html(exhibit, pdf, selected_measures, selected_dimension)

        # Data Tables (fallback to simple HTML table)
        if exhibit_type == 'data_table':
            return _get_data_table_html(exhibit, pdf)

        # Metric Cards
        if exhibit_type == 'metric_cards':
            return _get_metric_cards_html(exhibit, pdf)

        # Scatter Charts (similar to line chart)
        if exhibit_type == 'scatter_chart':
            return _get_scatter_chart_html(exhibit, pdf)

        # Heatmap
        if exhibit_type == 'heatmap':
            return _get_heatmap_html(exhibit, pdf)

        # Dual Axis Chart
        if exhibit_type == 'dual_axis_chart':
            return _get_dual_axis_chart_html(exhibit, pdf)

        # Forecast Chart
        if exhibit_type == 'forecast_chart':
            return _get_forecast_chart_html(exhibit, pdf)

        # Weighted Aggregate Chart
        if exhibit_type == 'weighted_aggregate_chart':
            return _get_weighted_aggregate_chart_html(exhibit, pdf)

        # Unknown type - log and return None
        logger.warning(f"Unsupported exhibit type for HTML export: {exhibit_type}")
        return f'<div style="color: #888; padding: 8px;">Exhibit type "{exhibit_type}" not supported in grid view</div>'

    except Exception as e:
        logger.error(f"Error generating HTML for exhibit type {exhibit_type}: {e}")
        return f'<div style="color: #c00; padding: 8px;">Error rendering exhibit: {str(e)}</div>'


def _get_exhibit_type_string(exhibit: Any) -> Optional[str]:
    """Normalize exhibit type to a string."""
    if not hasattr(exhibit, 'type'):
        return None

    exhibit_type = exhibit.type

    # Handle Enum types
    if hasattr(exhibit_type, 'value'):
        return exhibit_type.value

    # Handle string types
    if isinstance(exhibit_type, str):
        return exhibit_type

    return None


def _get_data_table_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for data table exhibit."""
    # Use pandas to_html for simple table rendering
    title_html = f'<h4 style="margin: 0 0 8px 0;">{exhibit.title}</h4>' if exhibit.title else ''
    table_html = pdf.to_html(index=False, classes='dataframe', border=0)

    # Wrap in container with basic styling
    return f'''
    <div style="width: 100%; overflow-x: auto;">
        {title_html}
        <style>
            .dataframe {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
            .dataframe th {{ background: #f5f5f5; padding: 8px; text-align: left; border-bottom: 2px solid #ddd; }}
            .dataframe td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .dataframe tr:hover {{ background: #f9f9f9; }}
        </style>
        {table_html}
    </div>
    '''


def _get_metric_cards_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for metric cards exhibit."""
    import plotly.io as pio
    import plotly.graph_objects as go

    # Get metrics configuration
    metrics = getattr(exhibit, 'metrics', [])
    if not metrics:
        return '<div>No metrics configured</div>'

    # Build indicator figure
    fig = go.Figure()

    for i, metric in enumerate(metrics):
        if hasattr(metric, 'column') and metric.column in pdf.columns:
            value = pdf[metric.column].iloc[0] if len(pdf) > 0 else 0
            label = getattr(metric, 'label', metric.column)

            fig.add_trace(go.Indicator(
                mode="number",
                value=value,
                title={"text": label},
                domain={'row': 0, 'column': i}
            ))

    num_metrics = len(metrics)
    fig.update_layout(
        grid={'rows': 1, 'columns': num_metrics, 'pattern': "independent"},
        margin=dict(l=20, r=20, t=30, b=20),
        height=150,
    )

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="width: 100%;">{html}</div>'


def _get_scatter_chart_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for scatter chart exhibit."""
    import plotly.express as px
    import plotly.io as pio

    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Scatter chart requires x_axis configuration</div>"

    # Extract field names from ColumnReferences
    x_col = _extract_field_name(exhibit.x_axis.dimension)
    y_col = None

    # Get y column from y_axis or measure_selector
    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if hasattr(exhibit.y_axis, 'measure'):
            y_col = _extract_field_name(exhibit.y_axis.measure)
        elif hasattr(exhibit.y_axis, 'dimension'):
            y_col = _extract_field_name(exhibit.y_axis.dimension)
    elif hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'default_measures') and ms.default_measures:
            y_col = _extract_field_name(ms.default_measures[0])

    if not y_col:
        return "<div>No y-axis configured for scatter chart</div>"

    color = _extract_field_name(getattr(exhibit, 'color_by', None))

    fig = px.scatter(
        pdf,
        x=x_col,
        y=y_col,
        color=color if color and color in pdf.columns else None,
        title=exhibit.title if exhibit.title else None,
    )

    fig.update_layout(
        margin=dict(l=40, r=40, t=40 if exhibit.title else 20, b=40),
        template='plotly_white',
    )

    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'


def _get_heatmap_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for heatmap exhibit."""
    import plotly.express as px
    import plotly.io as pio

    x_col = None
    y_col = None
    z_col = None

    # Extract field names from ColumnReferences
    if hasattr(exhibit, 'x_axis') and exhibit.x_axis:
        x_col = _extract_field_name(exhibit.x_axis.dimension)
    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        y_col = _extract_field_name(getattr(exhibit.y_axis, 'dimension', None)) or _extract_field_name(getattr(exhibit.y_axis, 'measure', None))
    if hasattr(exhibit, 'color_by') and exhibit.color_by:
        z_col = _extract_field_name(exhibit.color_by)

    if not all([x_col, y_col, z_col]):
        return "<div>Heatmap requires x_axis, y_axis, and color_by configuration</div>"

    # Pivot data for heatmap
    try:
        pivot_df = pdf.pivot_table(index=y_col, columns=x_col, values=z_col, aggfunc='mean')
        fig = px.imshow(pivot_df, title=exhibit.title if exhibit.title else None)
    except Exception as e:
        return f"<div>Error creating heatmap: {e}</div>"

    fig.update_layout(
        margin=dict(l=40, r=40, t=40, b=40),
    )

    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'


def _get_dual_axis_chart_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for dual axis chart exhibit."""
    import plotly.graph_objects as go
    import plotly.io as pio
    from plotly.subplots import make_subplots

    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Dual axis chart requires x_axis configuration</div>"

    # Extract field names from ColumnReferences
    x_col = _extract_field_name(exhibit.x_axis.dimension)

    # Get primary and secondary measures
    primary_measure = None
    secondary_measure = None

    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        primary_measure = _extract_field_name(getattr(exhibit.y_axis, 'measure', None))
    if hasattr(exhibit, 'y_axis_secondary') and exhibit.y_axis_secondary:
        secondary_measure = _extract_field_name(getattr(exhibit.y_axis_secondary, 'measure', None))

    if not primary_measure:
        return "<div>Dual axis chart requires primary y_axis measure</div>"

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Primary axis
    fig.add_trace(
        go.Scatter(x=pdf[x_col], y=pdf[primary_measure], name=primary_measure.replace('_', ' ').title()),
        secondary_y=False,
    )

    # Secondary axis (if configured)
    if secondary_measure and secondary_measure in pdf.columns:
        fig.add_trace(
            go.Bar(x=pdf[x_col], y=pdf[secondary_measure], name=secondary_measure.replace('_', ' ').title(), opacity=0.6),
            secondary_y=True,
        )

    fig.update_layout(
        title=exhibit.title if exhibit.title else None,
        margin=dict(l=40, r=40, t=40 if exhibit.title else 20, b=40),
        template='plotly_white',
    )

    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'


def _get_forecast_chart_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for forecast chart exhibit."""
    import plotly.graph_objects as go
    import plotly.io as pio

    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Forecast chart requires x_axis configuration</div>"

    # Extract field name from ColumnReference
    x_col = _extract_field_name(exhibit.x_axis.dimension)
    actual_col = getattr(exhibit, 'actual_column', 'actual')
    forecast_col = getattr(exhibit, 'forecast_column', 'forecast')

    fig = go.Figure()

    # Add actual line
    if actual_col in pdf.columns:
        fig.add_trace(go.Scatter(
            x=pdf[x_col], y=pdf[actual_col],
            name='Actual', mode='lines+markers',
            line=dict(color='blue', width=2)
        ))

    # Add forecast line
    if forecast_col in pdf.columns:
        fig.add_trace(go.Scatter(
            x=pdf[x_col], y=pdf[forecast_col],
            name='Forecast', mode='lines',
            line=dict(color='orange', width=2, dash='dash')
        ))

    fig.update_layout(
        title=exhibit.title if exhibit.title else None,
        margin=dict(l=40, r=40, t=40 if exhibit.title else 20, b=40),
        template='plotly_white',
        hovermode='x unified',
    )

    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'


def _get_weighted_aggregate_chart_html(exhibit: Any, pdf: pd.DataFrame) -> str:
    """Generate HTML for weighted aggregate chart exhibit."""
    import plotly.express as px
    import plotly.io as pio

    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Weighted aggregate chart requires x_axis configuration</div>"

    # Extract field names from ColumnReferences
    x_col = _extract_field_name(exhibit.x_axis.dimension)
    y_col = None

    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        y_col = _extract_field_name(getattr(exhibit.y_axis, 'measure', None))

    if not y_col:
        return "<div>Weighted aggregate chart requires y_axis measure</div>"

    fig = px.bar(pdf, x=x_col, y=y_col, title=exhibit.title if exhibit.title else None)

    fig.update_layout(
        margin=dict(l=40, r=40, t=40 if exhibit.title else 20, b=40),
        template='plotly_white',
    )

    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'


__all__ = [
    'render_metric_cards',
    'get_line_chart_html',
    'get_bar_chart_html',
    'render_data_table',
    'render_weighted_aggregate_chart',
    'render_forecast_chart',
    'render_forecast_metrics_table',
    'get_exhibit_html',
]
