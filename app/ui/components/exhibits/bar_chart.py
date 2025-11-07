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

        # Sort by first y-measure for better visualization (descending)
        pdf_sorted = self.pdf.sort_values(by=self.selected_measures[0], ascending=False)

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
