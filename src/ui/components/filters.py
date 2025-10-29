"""
Filter components for notebook variables.

Provides UI controls for different variable types (date range, multi-select, etc.)
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Any


def render_filters_section(notebook_config, notebook_session):
    """
    Render the filters section for a notebook.

    Args:
        notebook_config: NotebookConfig with variables
        notebook_session: NotebookSession for filter context
    """
    st.subheader("🎛️ Filters")

    # Import here to avoid circular dependency
    from src.notebook.schema import VariableType

    # Create a scrollable container for filters
    with st.container():
        filter_context = notebook_session.get_filter_context()
        filter_values = {}

        # Render each variable as a filter control
        for var_id, variable in notebook_config.variables.items():
            if variable.type == VariableType.DATE_RANGE:
                filter_values[var_id] = render_date_range_filter(var_id, variable, notebook_session)

            elif variable.type == VariableType.MULTI_SELECT:
                filter_values[var_id] = render_multi_select_filter(var_id, variable)

            elif variable.type == VariableType.SINGLE_SELECT:
                filter_values[var_id] = render_single_select_filter(var_id, variable)

            elif variable.type == VariableType.NUMBER:
                filter_values[var_id] = render_number_filter(var_id, variable)

            elif variable.type == VariableType.BOOLEAN:
                filter_values[var_id] = render_boolean_filter(var_id, variable)

        # Update filter context
        if filter_values:
            notebook_session.update_filters(filter_values)


def render_date_range_filter(var_id: str, variable, notebook_session) -> Dict[str, datetime]:
    """Render date range filter."""
    filter_context = notebook_session.get_filter_context()
    current_value = filter_context.get(var_id)

    if current_value and isinstance(current_value, dict):
        default_start = current_value['start']
        default_end = current_value['end']
        if isinstance(default_start, datetime):
            default_start = default_start.date()
        if isinstance(default_end, datetime):
            default_end = default_end.date()
    else:
        default_start = datetime.now().date() - timedelta(days=30)
        default_end = datetime.now().date()

    start_date = st.date_input(
        f"{variable.display_name} (Start)",
        value=default_start,
        key=f"filter_{var_id}_start",
    )

    end_date = st.date_input(
        f"{variable.display_name} (End)",
        value=default_end,
        key=f"filter_{var_id}_end",
    )

    return {
        'start': datetime.combine(start_date, datetime.min.time()),
        'end': datetime.combine(end_date, datetime.min.time()),
    }


def render_multi_select_filter(var_id: str, variable) -> List[Any]:
    """Render multi-select filter."""
    if variable.options:
        options = variable.options
    elif not variable.source:
        options = variable.default if variable.default else []
    else:
        options = variable.default if variable.default else []

    default = variable.default if variable.default else []

    return st.multiselect(
        variable.display_name,
        options=options,
        default=default,
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_single_select_filter(var_id: str, variable) -> Any:
    """Render single-select filter."""
    options = variable.options if variable.options else []
    default = variable.default

    return st.selectbox(
        variable.display_name,
        options=options,
        index=options.index(default) if default in options else 0,
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_number_filter(var_id: str, variable) -> float:
    """Render number filter."""
    default = variable.default if variable.default is not None else 0.0

    return st.number_input(
        variable.display_name,
        value=float(default),
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_boolean_filter(var_id: str, variable) -> bool:
    """Render boolean filter."""
    default = variable.default if variable.default is not None else False

    return st.checkbox(
        variable.display_name,
        value=default,
        key=f"filter_{var_id}",
        help=variable.description,
    )
