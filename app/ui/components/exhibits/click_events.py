"""
Click event handlers for exhibits.

Provides interactive clicking and selection capabilities for exhibits.
"""

import streamlit as st
from typing import Optional, Dict, Any, Callable


def enable_chart_selection(fig, exhibit_id: str, on_click_callback: Optional[Callable] = None):
    """
    Enable click/selection events on a Plotly chart.

    Args:
        fig: Plotly figure object
        exhibit_id: Unique exhibit ID for session state
        on_click_callback: Optional callback function to execute on click

    Returns:
        Modified figure with selection enabled
    """
    # Enable selection mode in Plotly
    fig.update_layout(
        clickmode='event+select',
        dragmode='select',  # Allow box/lasso selection
        selectdirection='any'
    )

    # Update traces to support selection
    fig.update_traces(
        selected=dict(marker=dict(opacity=1.0, size=8, color='yellow')),
        unselected=dict(marker=dict(opacity=0.3))
    )

    return fig


def get_selected_data(exhibit_id: str) -> Optional[Dict[str, Any]]:
    """
    Get currently selected data points from an exhibit.

    Args:
        exhibit_id: Unique exhibit ID

    Returns:
        Dictionary with selected data information, or None if nothing selected
    """
    session_key = f"chart_selection_{exhibit_id}"
    return st.session_state.get(session_key, None)


def store_selection(exhibit_id: str, selected_points: Dict[str, Any]):
    """
    Store selected data points in session state.

    Args:
        exhibit_id: Unique exhibit ID
        selected_points: Dictionary with selected point information
    """
    session_key = f"chart_selection_{exhibit_id}"
    st.session_state[session_key] = selected_points


def clear_selection(exhibit_id: str):
    """
    Clear selected data points from session state.

    Args:
        exhibit_id: Unique exhibit ID
    """
    session_key = f"chart_selection_{exhibit_id}"
    if session_key in st.session_state:
        del st.session_state[session_key]


def render_selection_info(exhibit_id: str):
    """
    Render information about currently selected points.

    Args:
        exhibit_id: Unique exhibit ID
    """
    selected = get_selected_data(exhibit_id)

    if selected and selected.get('point_indices'):
        num_points = len(selected['point_indices'])
        st.info(f"📍 {num_points} point(s) selected. Selection data available in session state.")

        # Add a clear button
        if st.button("Clear Selection", key=f"clear_selection_{exhibit_id}"):
            clear_selection(exhibit_id)
            st.rerun()


def add_click_interactivity(fig, exhibit_id: str, show_selection_info: bool = True):
    """
    Add full click interactivity to a chart including selection mode and info display.

    This is a convenience function that combines:
    - Enabling chart selection
    - Showing selection information
    - Providing clear selection button

    Args:
        fig: Plotly figure object
        exhibit_id: Unique exhibit ID
        show_selection_info: Whether to show selection information UI

    Returns:
        Modified figure with interactivity enabled
    """
    # Enable selection
    fig = enable_chart_selection(fig, exhibit_id)

    # Show selection info if enabled
    if show_selection_info:
        render_selection_info(exhibit_id)

    return fig
