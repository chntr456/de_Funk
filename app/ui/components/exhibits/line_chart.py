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

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with data

    Returns:
        HTML string with embedded Plotly chart
    """
    import plotly.io as pio

    # Create renderer to build the figure
    renderer = LineChartRenderer(exhibit, pdf)

    # Get x column
    if not hasattr(exhibit, 'x_axis') or not exhibit.x_axis:
        return "<div>Line chart requires x_axis configuration</div>"

    x_col = exhibit.x_axis.dimension

    # Sort by x-axis for proper time ordering
    pdf_sorted = pdf.sort_values(by=x_col)

    # Get selected measures (use defaults from measure_selector or y_axis)
    selected_measures = []
    if hasattr(exhibit, 'measure_selector') and exhibit.measure_selector:
        ms = exhibit.measure_selector
        if hasattr(ms, 'default_measures') and ms.default_measures:
            selected_measures = ms.default_measures
        elif hasattr(ms, 'available_measures') and ms.available_measures:
            selected_measures = [ms.available_measures[0]]
    elif hasattr(exhibit, 'y_axis') and exhibit.y_axis:
        if hasattr(exhibit.y_axis, 'measure') and exhibit.y_axis.measure:
            if isinstance(exhibit.y_axis.measure, list):
                selected_measures = exhibit.y_axis.measure
            else:
                selected_measures = [exhibit.y_axis.measure]
        elif hasattr(exhibit.y_axis, 'measures') and exhibit.y_axis.measures:
            selected_measures = exhibit.y_axis.measures

    if not selected_measures:
        return "<div>No measures configured for line chart</div>"

    # Get selected dimension (use default from dimension_selector or color_by)
    selected_dimension = None
    if hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector:
        ds = exhibit.dimension_selector
        if hasattr(ds, 'default_dimension') and ds.default_dimension:
            selected_dimension = ds.default_dimension
    elif hasattr(exhibit, 'color_by') and exhibit.color_by:
        selected_dimension = exhibit.color_by

    # Build the figure
    if len(selected_measures) == 1:
        y_col = selected_measures[0]
        fig = px.line(
            pdf_sorted,
            x=x_col,
            y=y_col,
            color=selected_dimension if selected_dimension and selected_dimension in pdf_sorted.columns else None,
            labels={
                x_col: exhibit.x_axis.label or x_col.replace('_', ' ').title(),
                y_col: exhibit.y_axis.label if hasattr(exhibit, 'y_axis') and exhibit.y_axis and exhibit.y_axis.label else y_col.replace('_', ' ').title()
            },
        )
    else:
        fig = go.Figure()
        if selected_dimension and selected_dimension in pdf_sorted.columns:
            for measure in selected_measures:
                for dim_val in pdf_sorted[selected_dimension].unique():
                    df_subset = pdf_sorted[pdf_sorted[selected_dimension] == dim_val]
                    fig.add_trace(go.Scatter(
                        x=df_subset[x_col],
                        y=df_subset[measure],
                        name=f"{dim_val} - {measure.replace('_', ' ').title()}",
                        mode='lines+markers',
                        line=dict(width=2),
                        marker=dict(size=3),
                    ))
        else:
            for measure in selected_measures:
                fig.add_trace(go.Scatter(
                    x=pdf_sorted[x_col],
                    y=pdf_sorted[measure],
                    name=measure.replace('_', ' ').title(),
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=3),
                ))

    # Style the figure
    fig.update_layout(
        title=exhibit.title if exhibit.title else None,
        hovermode='x unified',
        margin=dict(l=40, r=40, t=40 if exhibit.title else 20, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
    )

    # Get height from exhibit config
    height = 300
    if hasattr(exhibit, 'options') and exhibit.options and exhibit.options.get('height'):
        height = exhibit.options['height']

    # Convert to HTML (without full HTML wrapper, just the div)
    html = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': True, 'responsive': True}
    )

    # Wrap in a container with proper height
    return f'<div style="height: {height}px; width: 100%;">{html}</div>'
