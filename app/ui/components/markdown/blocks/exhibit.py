"""
Exhibit block renderer.

Handles rendering of data visualization exhibits including:
- Metric cards
- Line charts
- Bar charts
- Data tables
- Weighted aggregate charts
- Forecast charts
"""

import streamlit as st
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
        render_line_chart,
        render_bar_chart,
        render_data_table,
    )
    from app.ui.components.exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart
    from app.ui.components.exhibits.forecast_chart import render_forecast_chart, render_forecast_metrics_table

    # Check if exhibit has selectors
    has_measure_selector = hasattr(exhibit, 'measure_selector') and exhibit.measure_selector
    has_dimension_selector = hasattr(exhibit, 'dimension_selector') and exhibit.dimension_selector
    has_selectors = has_measure_selector or has_dimension_selector

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
                df = notebook_session.get_exhibit_data(exhibit_id)
                pdf = connection.to_pandas(df)

            # Render based on type
            from app.notebook.schema import ExhibitType
            if exhibit.type == ExhibitType.METRIC_CARDS:
                render_metric_cards(exhibit, pdf)
            elif exhibit.type == ExhibitType.LINE_CHART:
                render_line_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.BAR_CHART:
                render_bar_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.DATA_TABLE:
                render_data_table(exhibit, pdf)
            elif exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
                render_weighted_aggregate_chart(exhibit, pdf)
            elif exhibit.type == ExhibitType.FORECAST_CHART:
                render_forecast_chart(exhibit, pdf, in_collapsible=in_collapsible)
            elif exhibit.type == ExhibitType.FORECAST_METRICS_TABLE:
                render_forecast_metrics_table(exhibit, pdf)
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
