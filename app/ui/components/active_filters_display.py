"""
Active filters display component.

Shows currently selected filter values dynamically from session state.
"""

import streamlit as st
from de_funk.notebook.filters.dynamic import FilterCollection, FilterType


def render_active_filters_summary(filter_collection: FilterCollection):
    """
    Render a summary of currently active filter values from session state.

    This displays the actual current values users have selected, not defaults.

    Args:
        filter_collection: Collection of filter configurations
    """
    if not filter_collection or not filter_collection.filters:
        return

    # Collect current filter values from session state
    active_filters = {}

    for filter_id, filter_config in filter_collection.filters.items():
        session_key = f"filter_{filter_id}"

        # Get value from session state
        if session_key in st.session_state:
            value = st.session_state[session_key]
        else:
            # Fall back to filter_state current_value
            filter_state = filter_collection.get_state(filter_id)
            value = filter_state.current_value if filter_state else filter_config.default

        # Only include if value is set (not None/empty)
        if value is not None and value != '' and value != []:
            active_filters[filter_config.label] = (value, filter_config.type)

    # Render summary
    if active_filters:
        with st.expander("📊 Active Filters", expanded=False):
            for label, (value, filter_type) in active_filters.items():
                formatted_value = _format_filter_value(value, filter_type)
                st.markdown(f"**{label}**: {formatted_value}")
    else:
        st.info("ℹ️ No filters currently active")


def _format_filter_value(value, filter_type: FilterType) -> str:
    """
    Format filter value for display.

    Args:
        value: Filter value
        filter_type: Type of filter

    Returns:
        Formatted string representation
    """
    if filter_type == FilterType.DATE_RANGE:
        if isinstance(value, dict):
            start = value.get('start', '')
            end = value.get('end', '')
            return f"`{start}` to `{end}`"
        return str(value)

    elif filter_type == FilterType.SELECT:
        if isinstance(value, list):
            if len(value) > 3:
                display_items = ', '.join(f"`{v}`" for v in value[:3])
                return f"{display_items} ... (+ {len(value) - 3} more)"
            else:
                return ', '.join(f"`{v}`" for v in value)
        return f"`{value}`"

    elif filter_type == FilterType.NUMBER_RANGE:
        if isinstance(value, dict):
            min_val = value.get('min', '')
            max_val = value.get('max', '')
            return f"`{min_val}` to `{max_val}`"
        return str(value)

    elif filter_type == FilterType.SLIDER:
        return f"`{value}`"

    elif filter_type == FilterType.BOOLEAN:
        return "✅ Yes" if value else "❌ No"

    elif filter_type == FilterType.TEXT_SEARCH:
        return f"`{value}`"

    else:
        return f"`{value}`"
