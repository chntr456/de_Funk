"""
Exhibit block renderer.

Handles rendering of data visualization exhibits including:
- Metric cards
- Line charts
- Bar charts
- Data tables
- Weighted aggregate charts
- Forecast charts
- Great Tables (publication-quality tables)

Uses unified HTML-based rendering for consistency between grid and non-grid views.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Dict, Any

from ..toggle_container import ToggleContainer


def render_exhibit_block(block: Dict[str, Any], notebook_session, connection, in_collapsible: bool = False):
    """
    Render a single exhibit block.

    Supports collapsible exhibits via exhibit.collapsible flag.
    Auto-wraps exhibits with selectors in a collapsible section.

    Args:
        block: Content block with exhibit data
        notebook_session: NotebookSession for data retrieval
        connection: DataConnection for converting to pandas
        in_collapsible: True if already rendering inside a collapsible section
    """
    exhibit = block['exhibit']
    exhibit_id = block['id']

    # Import exhibit renderers
    from app.ui.components.exhibits import (
        render_metric_cards,
        render_data_table,
        get_exhibit_html,
    )
    from app.ui.components.exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart
    from app.ui.components.exhibits.forecast_chart import render_forecast_chart, render_forecast_metrics_table
    from app.ui.components.exhibits.great_table import render_great_table

    # Check if exhibit has selectors
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector
    has_selectors = has_measure_selector or has_dimension_selector

    def _render_chart_controls():
        """Render chart controls (dimension/measure selectors) in a collapsible expander."""
        if not has_selectors:
            return None, None

        selected_dim = None
        selected_measures = None

        with st.expander("⚙️ Chart Controls", expanded=False):
            col1, col2 = st.columns(2)

            # Dimension selector
            if has_dimension_selector:
                ds = exhibit.dimension_selector
                available_dims = getattr(ds, 'available_dimensions', [])

                if len(available_dims) > 1:
                    with col1:
                        default_dim = getattr(ds, 'default_dimension', available_dims[0])
                        dim_state_key = f"dim_selector_{exhibit_id}"

                        if dim_state_key not in st.session_state:
                            st.session_state[dim_state_key] = default_dim

                        selected_dim = st.selectbox(
                            "Group By",
                            options=available_dims,
                            index=available_dims.index(st.session_state[dim_state_key]) if st.session_state[dim_state_key] in available_dims else 0,
                            key=f"{dim_state_key}_select",
                            format_func=lambda x: x.replace('_', ' ').title()
                        )
                        st.session_state[dim_state_key] = selected_dim
                elif available_dims:
                    selected_dim = available_dims[0]

            # Measure selector (multi-select)
            if has_measure_selector:
                ms = exhibit.measure_selector
                available_measures = getattr(ms, 'available_measures', [])

                if len(available_measures) > 1:
                    with col2:
                        default_measures = getattr(ms, 'default_measures', available_measures[:1])
                        measure_state_key = f"measure_selector_{exhibit_id}"

                        if measure_state_key not in st.session_state:
                            st.session_state[measure_state_key] = default_measures

                        selected_measures = st.multiselect(
                            "Measures",
                            options=available_measures,
                            default=st.session_state[measure_state_key],
                            key=f"{measure_state_key}_select",
                            format_func=lambda x: x.replace('_', ' ').title()
                        )
                        # Ensure at least one measure is selected
                        if not selected_measures:
                            selected_measures = default_measures[:1]
                        st.session_state[measure_state_key] = selected_measures

        return selected_dim, selected_measures

    # Check if exhibit should be rendered in collapsible section
    # NOTE: Don't auto-wrap exhibits with selectors - they'll create their own individual expanders
    is_collapsible = getattr(exhibit, 'collapsible', False) and not has_selectors
    collapsible_title = getattr(exhibit, 'collapsible_title', None) or exhibit.title
    collapsible_expanded = getattr(exhibit, 'collapsible_expanded', True)

    # Render function to execute the actual exhibit rendering
    def _render_exhibit_content():
        try:
            with st.spinner(f"Loading {exhibit.title or 'exhibit'}..."):
                # Get data for exhibit
                # NOTE: NotebookManager.get_exhibit_data already handles aggregation
                # via _determine_aggregation() which checks dimension_selector state
                df = notebook_session.get_exhibit_data(exhibit_id)
                pdf = connection.to_pandas(df)

            # Render based on type
            from de_funk.notebook.schema import ExhibitType
            if exhibit.type == ExhibitType.METRIC_CARDS:
                render_metric_cards(exhibit, pdf)
            elif exhibit.type == ExhibitType.LINE_CHART:
                # Render chart controls (collapsible expander) and get selections
                selected_dim, selected_measures = _render_chart_controls()
                html = get_exhibit_html(
                    exhibit, pdf,
                    selected_measures=selected_measures,
                    selected_dimension=selected_dim
                )
                if html:
                    height = getattr(exhibit, 'height', None) or 400
                    components.html(html, height=height + 50, scrolling=False)
                else:
                    st.warning("Could not render line chart")
            elif exhibit.type == ExhibitType.BAR_CHART:
                # Render chart controls (collapsible expander) and get selections
                selected_dim, selected_measures = _render_chart_controls()
                html = get_exhibit_html(
                    exhibit, pdf,
                    selected_measures=selected_measures,
                    selected_dimension=selected_dim
                )
                if html:
                    height = getattr(exhibit, 'height', None) or 350
                    components.html(html, height=height + 50, scrolling=False)
                else:
                    st.warning("Could not render bar chart")
            elif exhibit.type == ExhibitType.DATA_TABLE:
                render_data_table(exhibit, pdf)
            elif exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
                render_weighted_aggregate_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.FORECAST_CHART:
                render_forecast_chart(exhibit, pdf, in_collapsible=in_collapsible)
            elif exhibit.type == ExhibitType.FORECAST_METRICS_TABLE:
                render_forecast_metrics_table(exhibit, pdf)
            elif exhibit.type == ExhibitType.GREAT_TABLE:
                render_great_table(exhibit, pdf)
            else:
                st.warning(f"Exhibit type not yet implemented: {exhibit.type}")

        except Exception as e:
            st.error(f"Error rendering exhibit: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    # Wrap in ToggleContainer if collapsible
    if is_collapsible:
        with ToggleContainer(
            collapsible_title,
            expanded=collapsible_expanded,
            container_id=f"exhibit_{exhibit_id}",
            style="card"
        ) as tc:
            if tc.is_open:
                _render_exhibit_content()
    else:
        _render_exhibit_content()
