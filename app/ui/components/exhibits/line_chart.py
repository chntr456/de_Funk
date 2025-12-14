"""
Line chart exhibit component with enhanced Plotly visualization.

Renders time series or categorical data as interactive line charts with:
- Proper time ordering
- Interactive hover tooltips
- Zoom, pan, and selection tools
- Theme support
- Dynamic measure and dimension selection
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from .base_renderer import BaseExhibitRenderer


class LineChartRenderer(BaseExhibitRenderer):
    """Line chart renderer."""

    def render_chart(self):
        """Render the line chart with selected measures and dimension."""
        if not hasattr(self.exhibit, 'x_axis') or not self.exhibit.x_axis:
            st.warning("Line chart requires x_axis configuration")
            return

        x_col = self.exhibit.x_axis.dimension

        # Sort by x-axis for proper time ordering
        pdf_sorted = self.pdf.sort_values(by=x_col)

        # Create figure based on number of measures
        if len(self.selected_measures) == 1:
            # Single measure - use px.line for simplicity
            y_col = self.selected_measures[0]
            fig = px.line(
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
            # Multiple measures - use graph_objects for more control
            fig = go.Figure()

            if self.selected_dimension and self.selected_dimension in pdf_sorted.columns:
                # Create lines for each measure+dimension combination
                for measure in self.selected_measures:
                    for dim_val in pdf_sorted[self.selected_dimension].unique():
                        df_subset = pdf_sorted[pdf_sorted[self.selected_dimension] == dim_val]
                        fig.add_trace(go.Scatter(
                            x=df_subset[x_col],
                            y=df_subset[measure],
                            name=f"{dim_val} - {measure.replace('_', ' ').title()}",
                            mode='lines+markers',
                            line=dict(width=2.5),
                            marker=dict(size=4),
                            hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
                        ))
            else:
                # No dimension, just plot each measure as a separate line
                for measure in self.selected_measures:
                    fig.add_trace(go.Scatter(
                        x=pdf_sorted[x_col],
                        y=pdf_sorted[measure],
                        name=measure.replace('_', ' ').title(),
                        mode='lines+markers',
                        line=dict(width=2.5),
                        marker=dict(size=4),
                        hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
                    ))

            # Update axis labels
            x_label = self.exhibit.x_axis.label or x_col.replace('_', ' ').title()

            # Get y-axis label, ensuring it's always a string
            if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis and hasattr(self.exhibit.y_axis, 'label') and self.exhibit.y_axis.label:
                y_label = self.exhibit.y_axis.label
                # If label is a list (shouldn't happen but handle gracefully), join it
                if isinstance(y_label, list):
                    y_label = ", ".join(str(l) for l in y_label)
            else:
                # Default label for multiple measures
                if len(self.selected_measures) > 1:
                    y_label = "Value"
                else:
                    y_label = self.selected_measures[0].replace('_', ' ').title()

            fig.update_xaxes(title_text=x_label)
            fig.update_yaxes(title_text=y_label)

        # Apply theme
        fig = self.apply_theme_to_figure(fig)

        # Update hover mode for multiple traces
        fig.update_layout(hovermode='x unified')

        # Better line styling for single measure charts
        if len(self.selected_measures) == 1:
            fig.update_traces(
                line=dict(width=2.5),
                mode='lines+markers',
                marker=dict(size=4),
                hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
            )

        # Enable interactivity
        fig = self.enable_interactivity(fig)

        # Render chart
        config = self.get_plotly_config()
        st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{self.exhibit.id}")


def render_line_chart(exhibit, pdf: pd.DataFrame):
    """
    Render line chart exhibit.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data
    """
    renderer = LineChartRenderer(exhibit, pdf)
    renderer.render()


def get_line_chart_html(exhibit, pdf: pd.DataFrame) -> str:
    """
    Get line chart as embeddable HTML for CSS grid rendering.

    Renders the chart based on YAML-defined measures and dimensions,
    matching the existing exhibit paradigm. Measure/dimension selectors
    are handled separately by the sidebar UI, not embedded in the chart.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data

    Returns:
        HTML string with embedded Plotly chart
    """
    import plotly.io as pio
    from config.logging import get_logger
    logger = get_logger(__name__)

    # Get x column
    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        # Try 'x' shorthand
        x_col = getattr(exhibit, 'x', None)
        if not x_col:
            return "<div>Line chart requires x_axis configuration</div>"
    else:
        x_col = exhibit.x_axis.dimension

    if x_col not in pdf.columns:
        return f"<div>X column '{x_col}' not found in data</div>"

    # Get measures from YAML config
    # Priority: y_axis.measure > y_axis.measures > y shorthand > measure_selector defaults
    measures = []
    if hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
            if isinstance(exhibit.y_axis.measure, list):
                measures = exhibit.y_axis.measure
            else:
                measures = [exhibit.y_axis.measure]
        elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
            measures = exhibit.y_axis.measures
    elif hasattr(exhibit, 'y') and exhibit.y:
        if isinstance(exhibit.y, list):
            measures = exhibit.y
        else:
            measures = [exhibit.y]
    elif hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'default_measures') and ms.default_measures:
            measures = ms.default_measures
        elif hasattr(ms, 'available_measures') and ms.available_measures:
            measures = ms.available_measures[:1]  # Use first available

    # Filter to columns that exist
    measures = [m for m in measures if m in pdf.columns]

    if not measures:
        # Fallback: find numeric columns
        measures = [c for c in pdf.columns if pd.api.types.is_numeric_dtype(pdf[c]) and c != x_col][:3]

    if not measures:
        return "<div>No numeric measures found for line chart</div>"

    # Get color/dimension from YAML config
    color_col = None
    if hasattr(exhibit, 'color_by') and exhibit.color_by and exhibit.color_by in pdf.columns:
        color_col = exhibit.color_by
    elif hasattr(exhibit, 'color') and exhibit.color and exhibit.color in pdf.columns:
        color_col = exhibit.color
    elif hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'default_dimension') and ds.default_dimension and ds.default_dimension in pdf.columns:
            color_col = ds.default_dimension

    # Limit data size for browser performance
    MAX_POINTS_PER_LINE = 500
    MAX_DIMENSION_VALUES = 10

    # Filter to top dimension values by frequency if too many
    if color_col:
        unique_vals = pdf[color_col].nunique()
        if unique_vals > MAX_DIMENSION_VALUES:
            top_dims = pdf[color_col].value_counts().head(MAX_DIMENSION_VALUES).index.tolist()
            pdf = pdf[pdf[color_col].isin(top_dims)]
        group_cols = [x_col, color_col]
    else:
        group_cols = [x_col]

    # Aggregate data if too large
    agg_dict = {m: 'mean' for m in measures}
    if len(pdf) > MAX_POINTS_PER_LINE * (MAX_DIMENSION_VALUES if color_col else 1):
        try:
            pdf = pdf.groupby(group_cols, as_index=False).agg(agg_dict)
        except Exception as e:
            logger.warning(f"Aggregation failed: {e}")

    # Sort by x-axis
    pdf = pdf.sort_values(by=x_col)

    logger.debug(f"Line chart HTML: {len(pdf)} points, measures={measures}, color={color_col}")

    # Build figure
    fig = go.Figure()

    if color_col:
        dim_values = pdf[color_col].unique().tolist()
        for measure in measures:
            for dim_val in dim_values:
                df_subset = pdf[pdf[color_col] == dim_val]
                name = f"{dim_val}" if len(measures) == 1 else f"{dim_val} - {measure.replace('_', ' ').title()}"
                fig.add_trace(go.Scatter(
                    x=df_subset[x_col],
                    y=df_subset[measure],
                    name=name,
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3),
                    legendgroup=str(dim_val),
                ))
    else:
        for measure in measures:
            fig.add_trace(go.Scatter(
                x=pdf[x_col],
                y=pdf[measure],
                name=measure.replace('_', ' ').title(),
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=3),
            ))

    # Style the figure
    fig.update_layout(
        title=exhibit.title if hasattr(exhibit, 'title') and exhibit.title else None,
        hovermode='x unified',
        margin=dict(l=40, r=40, t=40 if not (hasattr(exhibit, 'title') and exhibit.title) else 60, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
    )

    # Get height from exhibit config
    height = 400
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
