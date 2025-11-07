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
            y_label = self.exhibit.y_axis.label if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis and self.exhibit.y_axis.label else "Value"
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
