"""
Base exhibit renderer class.

Provides common functionality for all exhibit types including:
- Measure selector rendering and logic
- Dimension selector rendering and logic
- Auto-detection of grouping dimensions
- Aggregation when switching to non-primary dimensions (e.g., sector index)
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
        self.pdf_original = pdf.copy()  # Keep original for reference
        self.selected_measures: List[str] = []
        self.selected_dimension: Optional[str] = None
        self.is_aggregated: bool = False  # Track if data has been aggregated

    def render(self):
        """
        Main render method that orchestrates the exhibit rendering.

        This method:
        1. Renders title and description
        2. Renders selectors in a single collapsible section with tabs
        3. Calls child class's render_chart() method

        Note: All selectors are grouped in one expander with tabs for easy navigation.
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

        # Check if chart should nest inside expander (defaults to True)
        nest_in_expander = getattr(self.exhibit, 'nest_in_expander', True)

        # Render selectors in a single expander with tabs
        if has_measure_selector or has_dimension_selector:
            with st.expander("⚙️ Configuration", expanded=True):
                # Build tab list with empty "Hide" tab first
                tab_names = ["➖ Hide"]

                if has_measure_selector:
                    tab_names.append("📊 Measures")

                if has_dimension_selector:
                    tab_names.append("🔀 Dimensions")

                # Create tabs
                tabs = st.tabs(tab_names)

                # Tab 0: Hide (empty - creates collapse effect)
                with tabs[0]:
                    pass  # Empty tab for hide effect

                # Tab 1: Measures (if present)
                current_tab = 1
                if has_measure_selector:
                    with tabs[current_tab]:
                        self.selected_measures = self._process_measures()
                    current_tab += 1
                else:
                    self.selected_measures = self._process_measures()

                # Tab 2 or 1: Dimensions (if present)
                if has_dimension_selector:
                    with tabs[current_tab]:
                        self.selected_dimension = self._process_dimension()
                else:
                    self.selected_dimension = self._process_dimension()

                # Validate measures
                if not self.selected_measures:
                    st.warning("No valid measures configured")
                    return

                # Apply aggregation if needed (when grouping by non-primary dimension)
                self._apply_aggregation()

                # Render chart inside or outside expander based on nest_in_expander parameter
                if nest_in_expander:
                    # Render chart inside the expander
                    self.render_chart()

            # If nest_in_expander is False, render chart outside expander
            if not nest_in_expander:
                self.render_chart()
        else:
            # No selectors - process normally
            self.selected_measures = self._process_measures()
            self.selected_dimension = self._process_dimension()

            # Validate measures
            if not self.selected_measures:
                st.warning("No valid measures configured")
                return

            # Apply aggregation if needed
            self._apply_aggregation()

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
                # Handle both single measure and list of measures
                if isinstance(self.exhibit.y_axis.measure, list):
                    measures = self.exhibit.y_axis.measure
                else:
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

    def _apply_aggregation(self):
        """
        Apply aggregation when switching to non-primary dimension.

        When user switches from ticker (primary) to sector (secondary),
        aggregate all stocks within each sector to form a sector index.

        Example:
            - ticker view: AAPL=$150, MSFT=$350, JPM=$170
            - sector view: Technology=avg($150,$350)=$250, Financials=$170
        """
        # Only apply if dimension selector is configured
        if not hasattr(self.exhibit, 'dimension_selector') or not self.exhibit.dimension_selector:
            return

        dim_config = self.exhibit.dimension_selector

        # Check if aggregation is enabled
        if not getattr(dim_config, 'aggregate_on_change', True):
            return

        # Get primary dimension (defaults to first in available_dimensions or 'ticker')
        primary_dim = getattr(dim_config, 'primary_dimension', None)
        if not primary_dim:
            available_dims = getattr(dim_config, 'available_dimensions', [])
            primary_dim = available_dims[0] if available_dims else 'ticker'

        # If selected dimension is the primary, no aggregation needed
        if self.selected_dimension == primary_dim:
            self.is_aggregated = False
            return

        # If selected dimension isn't in the data, skip aggregation
        if self.selected_dimension not in self.pdf.columns:
            return

        # Get x-axis column for grouping (typically trade_date)
        x_col = None
        if hasattr(self.exhibit, 'x_axis') and self.exhibit.x_axis:
            x_col = self.exhibit.x_axis.dimension

        if not x_col or x_col not in self.pdf.columns:
            return

        # Get aggregation method
        agg_method = getattr(dim_config, 'aggregation', 'avg')

        # Map aggregation method to pandas function
        agg_map = {
            'avg': 'mean',
            'mean': 'mean',
            'sum': 'sum',
            'min': 'min',
            'max': 'max',
            'first': 'first',
            'last': 'last',
            'count': 'count',
            'median': 'median'
        }
        pandas_agg = agg_map.get(agg_method, 'mean')

        # Determine columns to aggregate (numeric measures)
        agg_columns = [m for m in self.selected_measures if m in self.pdf.columns]
        if not agg_columns:
            return

        # Build aggregation dict
        agg_dict = {col: pandas_agg for col in agg_columns}

        # Group by x-axis and selected dimension, then aggregate
        try:
            group_cols = [x_col, self.selected_dimension]
            aggregated = self.pdf.groupby(group_cols, as_index=False).agg(agg_dict)

            # Update the dataframe used for rendering
            self.pdf = aggregated
            self.is_aggregated = True

        except Exception as e:
            # If aggregation fails, log and continue with original data
            import logging
            logging.warning(f"Aggregation failed: {e}")
            self.is_aggregated = False

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
