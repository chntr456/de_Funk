"""
Dimension selector component for exhibits.

Provides interactive UI for selecting which dimension to use for grouping/coloring.
"""

import streamlit as st
from typing import List, Optional
from app.notebook.schema import DimensionSelectorConfig


def render_dimension_selector(
    exhibit_id: str,
    dimension_selector_config: DimensionSelectorConfig,
    available_columns: Optional[List[str]] = None
) -> str:
    """
    Render dimension selector UI and return selected dimension.

    Args:
        exhibit_id: Unique exhibit ID for session state key
        dimension_selector_config: Configuration for the dimension selector
        available_columns: Optional list of columns available in the data
                          (used to validate dimension existence)

    Returns:
        Selected dimension name
    """
    # Generate unique session state key for this exhibit
    session_key = f"dimension_selector_{exhibit_id}"

    # Get available dimensions from config
    available_dimensions = dimension_selector_config.available_dimensions

    # Filter to only include dimensions that exist in the data
    if available_columns:
        available_dimensions = [d for d in available_dimensions if d in available_columns]

    if not available_dimensions:
        st.warning("No valid dimensions available")
        return dimension_selector_config.default_dimension or ""

    # Initialize session state with default
    if session_key not in st.session_state:
        if dimension_selector_config.default_dimension and dimension_selector_config.default_dimension in available_dimensions:
            default_selected = dimension_selector_config.default_dimension
        else:
            # Use first available dimension as default
            default_selected = available_dimensions[0]

        st.session_state[session_key] = default_selected

    # Get label for the selector
    label = dimension_selector_config.label or "Select Dimension"

    # Render selector based on type
    selector_type = dimension_selector_config.selector_type

    if selector_type == "radio":
        # Render radio buttons (horizontal)
        if dimension_selector_config.help_text:
            st.caption(dimension_selector_config.help_text)

        current_value = st.session_state[session_key]
        selected_dimension = st.radio(
            label=label,  # Use actual label for accessibility
            options=available_dimensions,
            index=available_dimensions.index(current_value) if current_value in available_dimensions else 0,
            format_func=lambda x: x.replace('_', ' ').title(),
            horizontal=True,
            key=f"{session_key}_radio",
            label_visibility="visible"  # Show label for accessibility
        )
        st.session_state[session_key] = selected_dimension

    elif selector_type == "selectbox":
        # Render selectbox dropdown
        current_value = st.session_state[session_key]
        selected_dimension = st.selectbox(
            label=label,
            options=available_dimensions,
            index=available_dimensions.index(current_value) if current_value in available_dimensions else 0,
            help=dimension_selector_config.help_text,
            format_func=lambda x: x.replace('_', ' ').title(),
            key=f"{session_key}_selectbox"
        )
        st.session_state[session_key] = selected_dimension

    else:
        # Default to selectbox if unknown type
        current_value = st.session_state[session_key]
        selected_dimension = st.selectbox(
            label=label,
            options=available_dimensions,
            index=available_dimensions.index(current_value) if current_value in available_dimensions else 0,
            help=dimension_selector_config.help_text,
            format_func=lambda x: x.replace('_', ' ').title(),
            key=f"{session_key}_default"
        )
        st.session_state[session_key] = selected_dimension

    return selected_dimension


def get_selected_dimension(exhibit_id: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get currently selected dimension from session state without rendering UI.

    Args:
        exhibit_id: Unique exhibit ID
        default: Default dimension if none selected

    Returns:
        Selected dimension name, or None if not initialized
    """
    session_key = f"dimension_selector_{exhibit_id}"
    return st.session_state.get(session_key, default)
