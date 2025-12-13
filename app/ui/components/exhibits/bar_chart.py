"""
Bar chart exhibit component with enhanced Plotly visualization.

Renders categorical comparisons as interactive bar charts with:
- Proper ordering by value or category
- Interactive hover tooltips
- Zoom and selection tools
- Theme support
- Dynamic measure and dimension selection with grouped bars
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from .base_renderer import BaseExhibitRenderer


class BarChartRenderer(BaseExhibitRenderer):
    """Bar chart renderer."""

    def render_chart(self):
        """Render the bar chart with selected measures and dimension."""
        if not hasattr(self.exhibit, 'x_axis') or not self.exhibit.x_axis:
            st.warning("Bar chart requires x_axis configuration")
            return

        x_col = self.exhibit.x_axis.dimension

        # Check for static aggregation (e.g., aggregation: sum in exhibit options)
        pdf_to_use = self.pdf
        agg_method = None

        # Check exhibit options for aggregation
        if hasattr(self.exhibit, 'options') and self.exhibit.options:
            agg_method = self.exhibit.options.get('aggregation')

        # If aggregation is specified, group by x-axis and aggregate
        if agg_method and x_col in pdf_to_use.columns:
            agg_map = {
                'avg': 'mean', 'mean': 'mean',
                'sum': 'sum', 'min': 'min', 'max': 'max',
                'count': 'count', 'first': 'first', 'last': 'last'
            }
            pandas_agg = agg_map.get(agg_method, 'sum')

            # Build aggregation dict for numeric columns
            agg_dict = {}
            for col in self.selected_measures:
                if col in pdf_to_use.columns:
                    agg_dict[col] = pandas_agg

            if agg_dict:
                try:
                    pdf_to_use = pdf_to_use.groupby(x_col, as_index=False).agg(agg_dict)
                except Exception as e:
                    import logging
                    logging.warning(f"Bar chart aggregation failed: {e}")

        # Sort by first y-measure for better visualization (descending)
        pdf_sorted = pdf_to_use.sort_values(by=self.selected_measures[0], ascending=False)

        # Create figure based on number of measures
        if len(self.selected_measures) == 1:
            # Single measure - use px.bar for simplicity
            y_col = self.selected_measures[0]
            fig = px.bar(
                pdf_sorted,
                x=x_col,
                y=y_col,
                color=self.selected_dimension if self.selected_dimension and self.selected_dimension in pdf_sorted.columns else None,
                labels={
                    x_col: self.exhibit.x_axis.label or x_col.replace('_', ' ').title(),
                    y_col: self.exhibit.y_axis.label or y_col.replace('_', ' ').title() if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis else y_col.replace('_', ' ').title()
                },
                hover_data={x_col: True, y_col: ':.2f'},
            )
        else:
            # Multiple measures - create grouped bars
            fig = go.Figure()

            for measure in self.selected_measures:
                fig.add_trace(go.Bar(
                    x=pdf_sorted[x_col],
                    y=pdf_sorted[measure],
                    name=measure.replace('_', ' ').title(),
                    hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
                ))

            # Update layout for grouped bars
            x_label = self.exhibit.x_axis.label or x_col.replace('_', ' ').title()
            y_label = self.exhibit.y_axis.label if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis and self.exhibit.y_axis.label else "Value"
            fig.update_layout(
                barmode='group',
                xaxis_title=x_label,
                yaxis_title=y_label
            )

        # Apply theme
        fig = self.apply_theme_to_figure(fig)

        # Update hover mode
        fig.update_layout(hovermode='closest')

        # Update grid settings for bar charts
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True)

        # Better bar styling
        fig.update_traces(
            marker=dict(line=dict(width=0)),
            hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
        )

        # Enable interactivity
        fig = self.enable_interactivity(fig)

        # Render chart
        config = self.get_plotly_config()
        st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{self.exhibit.id}")


def render_bar_chart(exhibit, pdf: pd.DataFrame):
    """
    Render bar chart exhibit.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data
    """
    renderer = BarChartRenderer(exhibit, pdf)
    renderer.render()


def get_bar_chart_html(exhibit, pdf: pd.DataFrame) -> str:
    """
    Get bar chart as embeddable HTML for CSS grid rendering.

    Features:
    - Aggregates large datasets to prevent browser overload
    - Uses Plotly dropdown menus for measure selection
    - Supports all the same configurations as the Streamlit version

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data

    Returns:
        HTML string with embedded Plotly chart and interactive dropdowns
    """
    import plotly.io as pio
    from config.logging import get_logger
    logger = get_logger(__name__)

    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Bar chart requires x_axis configuration</div>"

    x_col = exhibit.x_axis.dimension

    # Get available measures from measure_selector or y_axis
    available_measures = []
    default_measures = []
    if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'available_measures') and ms.available_measures:
            available_measures = [m for m in ms.available_measures if m in pdf.columns]
        if hasattr(ms, 'default_measures') and ms.default_measures:
            default_measures = [m for m in ms.default_measures if m in pdf.columns]
    elif hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
            if isinstance(exhibit.y_axis.measure, list):
                available_measures = [m for m in exhibit.y_axis.measure if m in pdf.columns]
            else:
                available_measures = [exhibit.y_axis.measure] if exhibit.y_axis.measure in pdf.columns else []
        elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
            available_measures = [m for m in exhibit.y_axis.measures if m in pdf.columns]
        default_measures = available_measures[:1] if available_measures else []

    if not available_measures:
        # Fallback: find numeric columns
        available_measures = [c for c in pdf.columns if pd.api.types.is_numeric_dtype(pdf[c]) and c != x_col][:5]
        default_measures = available_measures[:1]

    if not available_measures:
        return "<div>No numeric measures found for bar chart</div>"

    if not default_measures:
        default_measures = available_measures[:1]

    # Get selected dimension (use default from dimension_selector or color_by)
    selected_dimension = None
    if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'default_dimension') and ds.default_dimension:
            selected_dimension = ds.default_dimension if ds.default_dimension in pdf.columns else None
    elif hasattr(exhibit, 'color_by') and exhibit.color_by:
        selected_dimension = exhibit.color_by if exhibit.color_by in pdf.columns else None

    # Check for static aggregation
    agg_method = 'sum'  # Default aggregation for bar charts
    if hasattr(exhibit, 'options') and exhibit.options:
        agg_method = exhibit.options.get('aggregation', 'sum')

    agg_map = {
        'avg': 'mean', 'mean': 'mean',
        'sum': 'sum', 'min': 'min', 'max': 'max',
        'count': 'count', 'first': 'first', 'last': 'last'
    }
    pandas_agg = agg_map.get(agg_method, 'sum')

    # Limit dimension values for large datasets
    MAX_BARS = 50
    MAX_DIMENSION_VALUES = 10

    # Aggregate data
    group_cols = [x_col]
    if selected_dimension and selected_dimension in pdf.columns:
        # Limit dimension values
        top_dims = pdf[selected_dimension].value_counts().head(MAX_DIMENSION_VALUES).index.tolist()
        pdf = pdf[pdf[selected_dimension].isin(top_dims)]
        group_cols.append(selected_dimension)

    agg_dict = {m: pandas_agg for m in available_measures if m in pdf.columns}
    if agg_dict:
        try:
            pdf_agg = pdf.groupby(group_cols, as_index=False).agg(agg_dict)
        except Exception as e:
            logger.warning(f"Bar chart aggregation failed: {e}")
            pdf_agg = pdf
    else:
        pdf_agg = pdf

    # Limit number of bars
    if len(pdf_agg) > MAX_BARS:
        # Keep top N by first default measure
        pdf_agg = pdf_agg.nlargest(MAX_BARS, default_measures[0])

    # Sort by first default measure
    pdf_sorted = pdf_agg.sort_values(by=default_measures[0], ascending=False)

    logger.debug(f"Bar chart HTML: {len(pdf_sorted)} bars after aggregation, measures={available_measures}")

    # Build figure with all measures as traces
    fig = go.Figure()
    trace_info = []

    for measure in available_measures:
        is_visible = measure in default_measures
        if selected_dimension and selected_dimension in pdf_sorted.columns:
            # Create grouped bars by dimension
            for dim_val in pdf_sorted[selected_dimension].unique():
                df_subset = pdf_sorted[pdf_sorted[selected_dimension] == dim_val]
                fig.add_trace(go.Bar(
                    x=df_subset[x_col],
                    y=df_subset[measure],
                    name=f"{dim_val}",
                    visible=is_visible,
                    legendgroup=str(dim_val),
                ))
                trace_info.append((measure, dim_val))
        else:
            fig.add_trace(go.Bar(
                x=pdf_sorted[x_col],
                y=pdf_sorted[measure],
                name=measure.replace('_', ' ').title(),
                visible=is_visible,
            ))
            trace_info.append((measure, None))

    # Build dropdown menus for measure selection
    buttons = []
    for measure in available_measures:
        visibility = [info[0] == measure for info in trace_info]
        buttons.append(dict(
            label=measure.replace('_', ' ').title(),
            method='update',
            args=[{'visible': visibility},
                  {'title': f"{exhibit.title} - {measure.replace('_', ' ').title()}" if exhibit.title else measure.replace('_', ' ').title()}]
        ))

    # Style the figure
    fig.update_layout(
        title=exhibit.title if exhibit.title else None,
        barmode='group' if selected_dimension else 'relative',
        hovermode='closest',
        margin=dict(l=40, r=40, t=60 if len(buttons) > 1 else 40, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        updatemenus=[
            dict(
                active=available_measures.index(default_measures[0]) if default_measures and default_measures[0] in available_measures else 0,
                buttons=buttons,
                direction='down',
                showactive=True,
                x=0.0,
                xanchor='left',
                y=1.15,
                yanchor='top',
                bgcolor='white',
                bordercolor='#ccc',
                font=dict(size=11),
            )
        ] if len(buttons) > 1 else []
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True)

    # Get height from exhibit config
    height = 350
    if hasattr(exhibit, 'height') and exhibit.height:
        height = exhibit.height
    elif hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    # Convert to HTML
    html = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': True, 'responsive': True}
    )

    return f'<div style="height: {height}px; width: 100%;">{html}</div>'
