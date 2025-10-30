"""
Filter components for notebook variables.

Provides UI controls for different variable types (date range, multi-select, etc.)
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


@st.cache_data(ttl=300)
def _get_distinct_values(_connection, table: str, column: str) -> List[Any]:
    """
    Query DuckDB for distinct values in a column.

    Args:
        _connection: DataConnection instance (DuckDB or Spark)
        table: Table name to query
        column: Column name to get distinct values from

    Returns:
        Sorted list of distinct values
    """
    try:
        # Build query to get distinct values
        query = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY {column}"
        df = _connection.query(query)
        pdf = _connection.to_pandas(df)

        # Convert to list
        values = pdf[column].tolist()
        return values
    except Exception as e:
        st.warning(f"Could not load dynamic options for {column}: {str(e)}")
        return []


def render_filters_section(notebook_config, notebook_session, connection=None):
    """
    Render the filters section for a notebook.

    Args:
        notebook_config: NotebookConfig with variables
        notebook_session: NotebookSession for filter context
        connection: Optional DataConnection for dynamic filter options
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
                filter_values[var_id] = render_multi_select_filter(
                    var_id, variable, connection=connection
                )

            elif variable.type == VariableType.SINGLE_SELECT:
                filter_values[var_id] = render_single_select_filter(
                    var_id, variable, connection=connection
                )

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


def render_multi_select_filter(var_id: str, variable, connection=None) -> List[Any]:
    """
    Render multi-select filter with dynamic options from DuckDB.

    Args:
        var_id: Variable identifier
        variable: Variable configuration
        connection: Optional DataConnection for querying dynamic options

    Returns:
        List of selected values
    """
    # Determine options source
    if variable.options:
        # Static options from YAML
        options = variable.options
    elif hasattr(variable, 'source') and variable.source and connection:
        # Dynamic options from DuckDB query
        # Source is a SourceReference object with model, node, column
        source_ref = variable.source
        table = source_ref.node  # e.g., "fact_prices"
        column = source_ref.column  # e.g., "ticker"

        if not column:
            # If no column specified, use the variable id as column name
            column = var_id

        options = _get_distinct_values(connection, table, column)

        if not options:
            # Fallback to default if query fails
            options = variable.default if variable.default else []
    else:
        # No options source, use default
        options = variable.default if variable.default else []

    default = variable.default if variable.default else []

    # Filter default to only include values that exist in options
    if default and options:
        default = [d for d in default if d in options]

    return st.multiselect(
        variable.display_name,
        options=options,
        default=default,
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_single_select_filter(var_id: str, variable, connection=None) -> Any:
    """
    Render single-select filter with dynamic options from DuckDB.

    Args:
        var_id: Variable identifier
        variable: Variable configuration
        connection: Optional DataConnection for querying dynamic options

    Returns:
        Selected value
    """
    # Determine options source
    if variable.options:
        # Static options from YAML
        options = variable.options
    elif hasattr(variable, 'source') and variable.source and connection:
        # Dynamic options from DuckDB query
        # Source is a SourceReference object with model, node, column
        source_ref = variable.source
        table = source_ref.node  # e.g., "fact_prices"
        column = source_ref.column  # e.g., "ticker"

        if not column:
            # If no column specified, use the variable id as column name
            column = var_id

        options = _get_distinct_values(connection, table, column)

        if not options:
            # Fallback to default if query fails
            options = [variable.default] if variable.default else []
    else:
        # No options source, use default
        options = [variable.default] if variable.default else []

    default = variable.default

    return st.selectbox(
        variable.display_name,
        options=options,
        index=options.index(default) if default and default in options else 0,
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
