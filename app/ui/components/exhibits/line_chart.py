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

    Features:
    - Aggregates large datasets to prevent browser overload
    - Uses Plotly dropdown menus for measure/dimension selection
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

    # Get x column
    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Line chart requires x_axis configuration</div>"

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
        return "<div>No numeric measures found for line chart</div>"

    if not default_measures:
        default_measures = available_measures[:1]

    # Get available dimensions from dimension_selector
    available_dimensions = []
    default_dimension = None
    if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'available_dimensions') and ds.available_dimensions:
            available_dimensions = [d for d in ds.available_dimensions if d in pdf.columns]
        if hasattr(ds, 'default_dimension') and ds.default_dimension:
            default_dimension = ds.default_dimension if ds.default_dimension in pdf.columns else None
    elif hasattr(exhibit, 'color_by') and exhibit.color_by:
        if exhibit.color_by in pdf.columns:
            available_dimensions = [exhibit.color_by]
            default_dimension = exhibit.color_by

    # Aggregate data to handle large datasets
    # Group by x_col and dimension (if selected), taking mean of measures
    MAX_POINTS_PER_LINE = 500
    MAX_DIMENSION_VALUES = 10

    # Filter to top dimension values by frequency if too many
    if default_dimension and default_dimension in pdf.columns:
        top_dims = pdf[default_dimension].value_counts().head(MAX_DIMENSION_VALUES).index.tolist()
        pdf = pdf[pdf[default_dimension].isin(top_dims)]
        group_cols = [x_col, default_dimension]
    else:
        group_cols = [x_col]

    # Aggregate data
    agg_dict = {m: 'mean' for m in available_measures if m in pdf.columns}
    if agg_dict:
        try:
            pdf_agg = pdf.groupby(group_cols, as_index=False).agg(agg_dict)
        except Exception as e:
            logger.warning(f"Aggregation failed: {e}")
            pdf_agg = pdf
    else:
        pdf_agg = pdf

    # Further sample if still too large
    if len(pdf_agg) > MAX_POINTS_PER_LINE * MAX_DIMENSION_VALUES:
        pdf_agg = pdf_agg.sample(n=MAX_POINTS_PER_LINE * MAX_DIMENSION_VALUES, random_state=42)

    # Sort by x-axis
    pdf_sorted = pdf_agg.sort_values(by=x_col)

    logger.debug(f"Line chart HTML: {len(pdf_sorted)} points after aggregation, measures={available_measures}, dim={default_dimension}")

    # Build figure with all measures as traces (for dropdown switching)
    fig = go.Figure()

    # Track trace indices for dropdown visibility
    trace_info = []  # [(measure, dimension_value or None)]

    if default_dimension and default_dimension in pdf_sorted.columns:
        dim_values = pdf_sorted[default_dimension].unique().tolist()
        for measure in available_measures:
            for dim_val in dim_values:
                df_subset = pdf_sorted[pdf_sorted[default_dimension] == dim_val]
                # Determine visibility: visible if this is a default measure
                is_visible = measure in default_measures
                fig.add_trace(go.Scatter(
                    x=df_subset[x_col],
                    y=df_subset[measure],
                    name=f"{dim_val} - {measure.replace('_', ' ').title()}",
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3),
                    visible=is_visible,
                    legendgroup=str(dim_val),
                ))
                trace_info.append((measure, dim_val))
    else:
        for measure in available_measures:
            is_visible = measure in default_measures
            fig.add_trace(go.Scatter(
                x=pdf_sorted[x_col],
                y=pdf_sorted[measure],
                name=measure.replace('_', ' ').title(),
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=3),
                visible=is_visible,
            ))
            trace_info.append((measure, None))

    # Build dropdown menus for measure selection
    buttons = []
    for measure in available_measures:
        # Visibility array: True for traces matching this measure
        visibility = [info[0] == measure for info in trace_info]
        buttons.append(dict(
            label=measure.replace('_', ' ').title(),
            method='update',
            args=[{'visible': visibility},
                  {'title': f"{exhibit.title} - {measure.replace('_', ' ').title()}" if exhibit.title else measure.replace('_', ' ').title()}]
        ))

    # Add "All Measures" option if multiple measures
    if len(available_measures) > 1:
        buttons.insert(0, dict(
            label='All Measures',
            method='update',
            args=[{'visible': [True] * len(trace_info)},
                  {'title': exhibit.title if exhibit.title else 'All Measures'}]
        ))

    # Style the figure
    fig.update_layout(
        title=exhibit.title if exhibit.title else None,
        hovermode='x unified',
        margin=dict(l=40, r=40, t=60 if buttons else 40, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        updatemenus=[
            dict(
                active=0 if len(available_measures) > 1 else available_measures.index(default_measures[0]) if default_measures else 0,
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

    # Get height from exhibit config
    height = 450
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
