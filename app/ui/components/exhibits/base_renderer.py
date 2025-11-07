"""
Base exhibit renderer class.

Provides common functionality for all exhibit types including:
- Measure selector rendering and logic
- Dimension selector rendering and logic
- Auto-detection of grouping dimensions
- Session state management
"""

import streamlit as st
import pandas as pd
from typing import List, Optional, Tuple
from abc import ABC, abstractmethod


class BaseExhibitRenderer(ABC):
    """Base class for all exhibit renderers."""

    def __init__(self, exhibit, pdf: pd.DataFrame):
        """
        Initialize base renderer.

        Args:
            exhibit: Exhibit configuration
            pdf: Pandas DataFrame with data
        """
        self.exhibit = exhibit
        self.pdf = pdf
        self.selected_measures: List[str] = []
        self.selected_dimension: Optional[str] = None

    def render(self):
        """
        Main render method that orchestrates the exhibit rendering.

        This method:
        1. Renders title and description
        2. Renders each selector in its own independent expander (can be collapsed separately)
        3. Calls child class's render_chart() method

        Note: Each selector gets its own expander at the same level (not nested).
        This allows users to collapse/expand each selector independently.
        """
        # Render title and description
        if self.exhibit.title:
            st.subheader(self.exhibit.title)

        if self.exhibit.description:
            st.caption(self.exhibit.description)

        # Validate data
        if self.pdf.empty:
            st.info("No data available for selected filters")
            return

        # Check if we have selectors
        has_measure_selector = hasattr(self.exhibit, 'measure_selector') and self.exhibit.measure_selector
        has_dimension_selector = hasattr(self.exhibit, 'dimension_selector') and self.exhibit.dimension_selector

        # Render measure selector in its own expander
        if has_measure_selector:
            with st.expander("📊 Select Measures", expanded=True):
                self.selected_measures = self._process_measures()
        else:
            self.selected_measures = self._process_measures()

        # Render dimension selector in its own expander
        if has_dimension_selector:
            with st.expander("🔀 Select Grouping Dimension", expanded=True):
                self.selected_dimension = self._process_dimension()
        else:
            self.selected_dimension = self._process_dimension()

        # Validate measures
        if not self.selected_measures:
            st.warning("No valid measures configured")
            return

        # Add divider before chart if we had any selectors
        if has_measure_selector or has_dimension_selector:
            st.markdown("---")

        # Call child class's chart rendering method
        self.render_chart()

    def _process_measures(self) -> List[str]:
        """
        Process and return selected measures.

        Returns:
            List of selected measure column names
        """
        from .measure_selector import render_measure_selector

        measures = []

        # Check if dynamic measure selector is configured
        if hasattr(self.exhibit, 'measure_selector') and self.exhibit.measure_selector:
            # Render measure selector and get selected measures
            measures = render_measure_selector(
                exhibit_id=self.exhibit.id,
                measure_selector_config=self.exhibit.measure_selector,
                available_columns=self.pdf.columns.tolist()
            )
        # Otherwise use y_axis configuration
        elif hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis:
            if hasattr(self.exhibit.y_axis, 'measures') and self.exhibit.y_axis.measures:
                measures = self.exhibit.y_axis.measures
            elif hasattr(self.exhibit.y_axis, 'measure') and self.exhibit.y_axis.measure:
                measures = [self.exhibit.y_axis.measure]

        # Filter to only those present in the dataframe
        return [m for m in measures if m in self.pdf.columns]

    def _process_dimension(self) -> Optional[str]:
        """
        Process and return selected dimension for coloring/grouping.

        Returns:
            Selected dimension column name or None
        """
        from .dimension_selector import render_dimension_selector

        dimension = None

        # Check if dynamic dimension selector is configured
        if hasattr(self.exhibit, 'dimension_selector') and self.exhibit.dimension_selector:
            # Render dimension selector and get selected dimension
            dimension = render_dimension_selector(
                exhibit_id=self.exhibit.id,
                dimension_selector_config=self.exhibit.dimension_selector,
                available_columns=self.pdf.columns.tolist()
            )
        else:
            # Use static color_by if no dimension selector
            dimension = self.exhibit.color_by if hasattr(self.exhibit, 'color_by') else None

        # Auto-detect dimension if not specified
        if not dimension:
            auto_detect_dimensions = ['ticker', 'symbol', 'stock', 'exchange', 'sector', 'category']
            for dim in auto_detect_dimensions:
                if dim in self.pdf.columns:
                    dimension = dim
                    break

        return dimension

    @abstractmethod
    def render_chart(self):
        """
        Render the actual chart.

        This method must be implemented by child classes.
        At this point, self.selected_measures and self.selected_dimension are available.
        """
        pass

    def get_axis_config(self) -> Tuple[Optional[str], str]:
        """
        Get x-axis and primary y-axis configuration.

        Returns:
            Tuple of (x_column, y_label)
        """
        x_col = None
        y_label = "Value"

        if hasattr(self.exhibit, 'x_axis') and self.exhibit.x_axis:
            x_col = self.exhibit.x_axis.dimension
            if self.exhibit.x_axis.label:
                x_label = self.exhibit.x_axis.label

        if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis:
            if self.exhibit.y_axis.label:
                y_label = self.exhibit.y_axis.label

        return x_col, y_label

    def apply_theme_to_figure(self, fig):
        """
        Apply current theme (light/dark) to a Plotly figure.

        Args:
            fig: Plotly figure object

        Returns:
            Modified figure with theme applied
        """
        theme = st.session_state.get('theme', 'light')

        if theme == 'dark':
            fig.update_layout(
                plot_bgcolor='#1E2130',
                paper_bgcolor='#1E2130',
                font=dict(color='#FAFAFA', size=12),
                xaxis=dict(
                    gridcolor='#3A3D45',
                    showgrid=True,
                    zeroline=False
                ),
                yaxis=dict(
                    gridcolor='#3A3D45',
                    showgrid=True,
                    zeroline=False
                ),
                legend=dict(
                    bgcolor='#262730',
                    bordercolor='#3A3D45',
                    borderwidth=1
                )
            )
        else:
            fig.update_layout(
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#F8F9FA',
                font=dict(size=12),
                xaxis=dict(
                    gridcolor='#E0E0E0',
                    showgrid=True,
                    zeroline=False
                ),
                yaxis=dict(
                    gridcolor='#E0E0E0',
                    showgrid=True,
                    zeroline=False
                ),
                legend=dict(
                    bgcolor='#FFFFFF',
                    bordercolor='#E0E0E0',
                    borderwidth=1
                )
            )

        # Common layout settings
        fig.update_layout(
            showlegend=True,
            height=400,
            margin=dict(l=10, r=10, t=10, b=10),
        )

        return fig

    def enable_interactivity(self, fig):
        """
        Enable interactive features on a Plotly chart.

        Args:
            fig: Plotly figure object

        Returns:
            Modified figure with interactivity enabled
        """
        if self.exhibit.interactive:
            from .click_events import enable_chart_selection
            fig = enable_chart_selection(fig, self.exhibit.id)

        return fig

    def get_plotly_config(self) -> dict:
        """
        Get standard Plotly configuration for charts.

        Returns:
            Dictionary of Plotly config options
        """
        return {
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'{self.exhibit.id}',
                'height': 600,
                'width': 1200,
                'scale': 2
            }
        }
