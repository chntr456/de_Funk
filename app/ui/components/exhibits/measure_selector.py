"""
Measure selector component for exhibits.

Provides interactive UI for selecting which measures to display in exhibits.
"""

import streamlit as st
from typing import List, Optional
from de_funk.notebook.schema import MeasureSelectorConfig


def render_measure_selector(
    exhibit_id: str,
    measure_selector_config: MeasureSelectorConfig,
    available_columns: Optional[List[str]] = None
) -> List[str]:
    """
    Render measure selector UI and return selected measures.

    Args:
        exhibit_id: Unique exhibit ID for session state key
        measure_selector_config: Configuration for the measure selector
        available_columns: Optional list of columns available in the data
                          (used to validate measure existence)

    Returns:
        List of selected measure names
    """
    # Generate unique session state key for this exhibit
    session_key = f"measure_selector_{exhibit_id}"

    # Get available measures from config
    available_measures = measure_selector_config.available_measures

    # Filter to only include measures that exist in the data
    if available_columns:
        available_measures = [m for m in available_measures if m in available_columns]

    # Initialize session state with defaults
    if session_key not in st.session_state:
        if measure_selector_config.default_measures:
            # Use configured defaults
            default_selected = [
                m for m in measure_selector_config.default_measures
                if m in available_measures
            ]
        else:
            # Default to all available measures
            default_selected = available_measures.copy()

        st.session_state[session_key] = default_selected

    # Get label for the selector
    label = measure_selector_config.label or "Select Measures"

    # Render selector based on type
    selector_type = measure_selector_config.selector_type

    if selector_type == "checkbox":
        # Render checkbox group
        st.markdown(f"**{label}**")
        if measure_selector_config.help_text:
            st.caption(measure_selector_config.help_text)

        # Create columns for checkboxes (3 per row)
        cols_per_row = 3
        num_measures = len(available_measures)
        num_rows = (num_measures + cols_per_row - 1) // cols_per_row

        selected = []
        for row in range(num_rows):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                measure_idx = row * cols_per_row + col_idx
                if measure_idx < num_measures:
                    measure = available_measures[measure_idx]
                    with cols[col_idx]:
                        # Format measure name for display
                        display_name = measure.replace('_', ' ').title()
                        is_checked = measure in st.session_state[session_key]

                        # Checkbox
                        checked = st.checkbox(
                            display_name,
                            value=is_checked,
                            key=f"{session_key}_{measure}"
                        )

                        if checked:
                            selected.append(measure)

        # Update session state
        st.session_state[session_key] = selected

    elif selector_type == "multiselect":
        # Render multiselect dropdown
        selected = st.multiselect(
            label=label,
            options=available_measures,
            default=st.session_state[session_key],
            help=measure_selector_config.help_text,
            format_func=lambda x: x.replace('_', ' ').title(),
            key=f"{session_key}_multiselect"
        )
        st.session_state[session_key] = selected

    elif selector_type == "radio":
        # Render radio buttons (single selection)
        selected_measure = st.radio(
            label=label,
            options=available_measures,
            index=available_measures.index(st.session_state[session_key][0])
            if st.session_state[session_key] else 0,
            help=measure_selector_config.help_text,
            format_func=lambda x: x.replace('_', ' ').title(),
            horizontal=True,
            key=f"{session_key}_radio"
        )
        selected = [selected_measure]
        st.session_state[session_key] = selected

    else:
        # Default to multiselect if unknown type
        selected = st.multiselect(
            label=label,
            options=available_measures,
            default=st.session_state[session_key],
            help=measure_selector_config.help_text,
            format_func=lambda x: x.replace('_', ' ').title(),
            key=f"{session_key}_default"
        )
        st.session_state[session_key] = selected

    return selected


def get_selected_measures(exhibit_id: str, default: Optional[List[str]] = None) -> Optional[List[str]]:
    """
    Get currently selected measures from session state without rendering UI.

    Args:
        exhibit_id: Unique exhibit ID
        default: Default measures if none selected

    Returns:
        List of selected measure names, or None if not initialized
    """
    session_key = f"measure_selector_{exhibit_id}"
    return st.session_state.get(session_key, default)
