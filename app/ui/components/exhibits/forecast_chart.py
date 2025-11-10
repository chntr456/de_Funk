"""
Time series prediction chart exhibit component.

Renders time series data with predictions and confidence intervals:
- Historical actual values (solid line)
- Predicted values (dashed line)
- Confidence intervals (shaded areas)
- Interactive hover tooltips
- Multiple model comparison via dimension selector
- Theme support
- Standard BaseExhibitRenderer pattern

This is a general-purpose prediction chart that works with any time series
data with actuals and predictions, not just stock forecasts.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from .base_renderer import BaseExhibitRenderer


class PredictionChartRenderer(BaseExhibitRenderer):
    """
    General-purpose time series prediction chart renderer.

    Expects data with a unified schema containing both actuals and predictions
    in the same DataFrame. Example schema:

    date       | ticker | model_name | actual | predicted | upper_bound | lower_bound
    -----------|--------|------------|--------|-----------|-------------|------------
    2024-01-01 | AAPL   | ARIMA_30d  | 150.0  | null      | null        | null
    2024-01-02 | AAPL   | ARIMA_30d  | 152.0  | null      | null        | null
    2024-01-03 | AAPL   | ARIMA_30d  | null   | 153.5     | 155.0       | 152.0
    """

    def __init__(self, exhibit, pdf: pd.DataFrame, in_collapsible: bool = False):
        """
        Initialize prediction chart renderer.

        Args:
            exhibit: Exhibit configuration
            pdf: DataFrame with unified time series + predictions
            in_collapsible: True if already rendering inside a collapsible section
        """
        super().__init__(exhibit, pdf)
        self.in_collapsible = in_collapsible

        # Optional styling configuration
        self.actual_column = getattr(exhibit, 'actual_column', None)
        self.predicted_column = getattr(exhibit, 'predicted_column', None)
        self.confidence_bounds = getattr(exhibit, 'confidence_bounds', None)

        # For multiselect dimension filtering
        self.selected_dimension_values = None

    def _process_dimension(self):
        """
        Override to handle multiselect dimension values for forecast filtering.

        Returns:
            Selected dimension name (str) or tuple of (dimension_name, selected_values)
        """
        from .dimension_selector import render_dimension_selector

        dimension = None

        # Check if dynamic dimension selector is configured
        if hasattr(self.exhibit, 'dimension_selector') and self.exhibit.dimension_selector:
            # Check if this is multiselect type
            selector_type = self.exhibit.dimension_selector.selector_type

            if selector_type == "multiselect":
                # Render dimension selector and get dimension + selected values
                result = render_dimension_selector(
                    exhibit_id=self.exhibit.id,
                    dimension_selector_config=self.exhibit.dimension_selector,
                    available_columns=self.pdf.columns.tolist(),
                    pdf=self.pdf  # Pass dataframe for value extraction
                )
                if isinstance(result, tuple):
                    dimension, self.selected_dimension_values = result
                else:
                    dimension = result
            else:
                # Standard selector (radio/selectbox)
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
            auto_detect_dimensions = ['model_name', 'ticker', 'symbol', 'stock']
            for dim in auto_detect_dimensions:
                if dim in self.pdf.columns:
                    dimension = dim
                    break

        return dimension

    def render(self):
        """Override render to handle collapsible sections."""
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

        # Define the configuration UI rendering function
        def render_configuration_ui():
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

            # Render chart
            self.render_chart()

        # If already in a collapsible section, don't create another expander
        if self.in_collapsible:
            render_configuration_ui()
        elif has_measure_selector or has_dimension_selector:
            # Create configuration expander
            with st.expander("⚙️ Configuration", expanded=True):
                render_configuration_ui()
        else:
            # No selectors - process and render directly
            self.selected_measures = self._process_measures()
            self.selected_dimension = self._process_dimension()

            if not self.selected_measures:
                st.warning("No valid measures configured")
                return

            self.render_chart()

    def render_chart(self):
        """Render the time series prediction chart with confidence intervals."""
        if not hasattr(self.exhibit, 'x_axis') or not self.exhibit.x_axis:
            st.warning("Prediction chart requires x_axis configuration")
            return

        x_col = self.exhibit.x_axis.dimension

        # Sort by x-axis for proper time ordering
        pdf_sorted = self.pdf.sort_values(by=x_col)

        # Create plotly figure
        fig = go.Figure()

        # Color palette
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#8B5A3C']

        # Determine which measures get special styling
        actual_measures = [self.actual_column] if self.actual_column and self.actual_column in self.selected_measures else []
        predicted_measures = [self.predicted_column] if self.predicted_column and self.predicted_column in self.selected_measures else []

        # Remaining measures (neither actual nor predicted)
        other_measures = [m for m in self.selected_measures
                         if m not in actual_measures and m not in predicted_measures]

        # Add confidence interval bands if configured
        if self.confidence_bounds and len(self.confidence_bounds) == 2:
            lower_col, upper_col = self.confidence_bounds

            if lower_col in pdf_sorted.columns and upper_col in pdf_sorted.columns:
                if self.selected_dimension and self.selected_dimension in pdf_sorted.columns:
                    # Get dimension values to render (same filtering as predictions)
                    all_dim_values = pdf_sorted[self.selected_dimension].unique()

                    if self.selected_dimension_values:
                        dim_values_to_render = [v for v in all_dim_values
                                               if pd.notna(v) and v in self.selected_dimension_values]
                    else:
                        dim_values_to_render = [v for v in all_dim_values if pd.notna(v)]

                    # Create confidence bands for each selected dimension value
                    for dim_val in dim_values_to_render:
                        df_subset = pdf_sorted[pdf_sorted[self.selected_dimension] == dim_val].copy()

                        # Filter out nulls for confidence bands
                        df_subset = df_subset.dropna(subset=[lower_col, upper_col])

                        if not df_subset.empty:
                            fig.add_trace(go.Scatter(
                                x=pd.concat([df_subset[x_col], df_subset[x_col][::-1]]),
                                y=pd.concat([df_subset[upper_col], df_subset[lower_col][::-1]]),
                                fill='toself',
                                fillcolor='rgba(174, 174, 174, 0.2)',
                                line=dict(color='rgba(255,255,255,0)'),
                                showlegend=False,
                                name=f'{dim_val} CI',
                                hoverinfo='skip'
                            ))
                else:
                    # Single confidence band
                    df_ci = pdf_sorted.dropna(subset=[lower_col, upper_col])

                    if not df_ci.empty:
                        fig.add_trace(go.Scatter(
                            x=pd.concat([df_ci[x_col], df_ci[x_col][::-1]]),
                            y=pd.concat([df_ci[upper_col], df_ci[lower_col][::-1]]),
                            fill='toself',
                            fillcolor='rgba(174, 174, 174, 0.2)',
                            line=dict(color='rgba(255,255,255,0)'),
                            showlegend=False,
                            name='Confidence Interval',
                            hoverinfo='skip'
                        ))

        # Render actual values (solid lines)
        for measure in actual_measures:
            self._add_line_trace(
                fig, pdf_sorted, x_col, measure,
                line_style='solid',
                line_width=2.5,
                color=colors[0]
            )

        # Render predicted values (dashed lines)
        color_offset = len(actual_measures)
        for i, measure in enumerate(predicted_measures):
            self._add_line_trace(
                fig, pdf_sorted, x_col, measure,
                line_style='dash',
                line_width=2.5,
                color=colors[(color_offset + i) % len(colors)]
            )

        # Render other measures (normal lines)
        color_offset = len(actual_measures) + len(predicted_measures)
        for i, measure in enumerate(other_measures):
            self._add_line_trace(
                fig, pdf_sorted, x_col, measure,
                line_style='solid',
                line_width=2,
                color=colors[(color_offset + i) % len(colors)]
            )

        # Apply theme from base class
        fig = self.apply_theme_to_figure(fig)

        # Update axis labels
        x_label = self.exhibit.x_axis.label or x_col.replace('_', ' ').title()
        y_label = self.exhibit.y_axis.label if hasattr(self.exhibit, 'y_axis') and self.exhibit.y_axis and self.exhibit.y_axis.label else "Value"

        fig.update_layout(
            xaxis_title=x_label,
            yaxis_title=y_label,
            hovermode='x unified',
            height=500,
            legend=dict(x=0.01, y=0.99)
        )

        # Enable interactivity
        if hasattr(self.exhibit, 'interactive') and self.exhibit.interactive:
            fig = self.enable_interactivity(fig)

        # Render chart
        config = self.get_plotly_config()
        st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{self.exhibit.id}")

    def _add_line_trace(self, fig, pdf_sorted, x_col, measure, line_style='solid', line_width=2, color=None):
        """
        Add a line trace to the figure.

        Args:
            fig: Plotly figure
            pdf_sorted: Sorted DataFrame
            x_col: X-axis column name
            measure: Measure column name
            line_style: 'solid', 'dash', 'dot', etc.
            line_width: Line width
            color: Line color (hex or rgb)
        """
        # Special handling for actuals - always show regardless of dimension filter
        is_actual = (measure == self.actual_column)

        if self.selected_dimension and self.selected_dimension in pdf_sorted.columns and not is_actual:
            # Get dimension values to render
            all_dim_values = pdf_sorted[self.selected_dimension].unique()

            # Filter by selected values if multiselect is active
            if self.selected_dimension_values:
                dim_values_to_render = [v for v in all_dim_values
                                       if not pd.isna(v) and v in self.selected_dimension_values]
            else:
                dim_values_to_render = [v for v in all_dim_values if not pd.isna(v)]

            # Create separate lines for each dimension value (for predictions)
            for dim_val in dim_values_to_render:
                df_subset = pdf_sorted[pdf_sorted[self.selected_dimension] == dim_val].copy()

                # Filter out nulls
                df_subset = df_subset.dropna(subset=[measure])

                if not df_subset.empty:
                    fig.add_trace(go.Scatter(
                        x=df_subset[x_col],
                        y=df_subset[measure],
                        name=f"{dim_val} - {measure.replace('_', ' ').title()}",
                        mode='lines+markers',
                        line=dict(color=color, width=line_width, dash=line_style),
                        marker=dict(size=4),
                        hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
                    ))
        else:
            # Single line for the measure (actuals or no dimension selected)
            df_measure = pdf_sorted.dropna(subset=[measure])

            if not df_measure.empty:
                fig.add_trace(go.Scatter(
                    x=df_measure[x_col],
                    y=df_measure[measure],
                    name=measure.replace('_', ' ').title(),
                    mode='lines+markers',
                    line=dict(color=color, width=line_width, dash=line_style),
                    marker=dict(size=4),
                    hovertemplate='<b>%{x}</b><br>%{y:.2f}<extra></extra>'
                ))


def render_forecast_chart(exhibit, pdf: pd.DataFrame = None, in_collapsible: bool = False):
    """
    Render time series prediction chart.

    Args:
        exhibit: Exhibit configuration
        pdf: DataFrame with unified time series + predictions
        in_collapsible: True if already rendering inside a collapsible section
    """
    renderer = PredictionChartRenderer(exhibit, pdf, in_collapsible=in_collapsible)
    renderer.render()


def render_forecast_metrics_table(exhibit, pdf: pd.DataFrame = None):
    """
    Render forecast metrics as a table.

    Args:
        exhibit: Exhibit configuration
        pdf: DataFrame with forecast metrics
    """
    st.subheader(exhibit.title if hasattr(exhibit, 'title') and exhibit.title else "Forecast Metrics")

    if hasattr(exhibit, 'description') and exhibit.description:
        st.caption(exhibit.description)

    if pdf is None or pdf.empty:
        st.info("No metrics data available")
        return

    # Display metrics table
    st.dataframe(
        pdf,
        use_container_width=True,
        hide_index=True
    )

    # Show summary statistics if numeric columns exist
    numeric_cols = pdf.select_dtypes(include=['float64', 'int64']).columns.tolist()

    if numeric_cols and len(numeric_cols) >= 4:
        st.subheader("Summary Statistics")

        cols = st.columns(min(4, len(numeric_cols)))

        for i, col in enumerate(numeric_cols[:4]):
            with cols[i]:
                st.metric(f"Avg {col.replace('_', ' ').title()}", f"{pdf[col].mean():.4f}")
