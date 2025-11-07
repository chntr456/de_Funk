"""
Filter components for notebook variables.

Provides UI controls for different variable types (date range, multi-select, etc.)
All filters are folder-scoped (shared within folder, isolated across folders).
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


@st.cache_data(ttl=300)
def _get_distinct_values(_connection, _storage_service, model: str, table: str, column: str) -> List[Any]:
    """
    Query database for distinct values in a column.

    Args:
        _connection: DataConnection instance (DuckDB or Spark)
        _storage_service: StorageService instance to access tables
        model: Model name (e.g., "company")
        table: Table name (e.g., "fact_prices")
        column: Column name to get distinct values from

    Returns:
        Sorted list of distinct values
    """
    try:
        # Use storage service to load the table (returns relation/dataframe)
        # This handles the parquet file path resolution
        df = _storage_service.get_table(model, table, use_cache=True)

        # Convert to pandas
        pdf = _connection.to_pandas(df)

        # Get distinct values from pandas, sorted
        if column in pdf.columns:
            values = pdf[column].dropna().unique().tolist()
            values.sort()  # Sort the values
            return values
        else:
            st.warning(f"Column '{column}' not found in {table}")
            return []
    except Exception as e:
        st.warning(f"Could not load dynamic options for {column}: {str(e)}")
        return []


def render_filters_section(notebook_config, notebook_session, connection=None, storage_service=None):
    """
    Render the filters section for a notebook.

    Args:
        notebook_config: NotebookConfig with variables
        notebook_session: NotebookSession for filter context
        connection: Optional DataConnection for dynamic filter options
        storage_service: Optional StorageService for loading table data
    """
    st.subheader("🎛️ Filters")

    # Import here to avoid circular dependency
    from app.notebook.schema import VariableType

    # CRITICAL: Clear filter widget state when folder changes
    # This ensures widgets don't retain old values from previous folders
    current_folder = str(notebook_session.get_current_folder()) if hasattr(notebook_session, 'get_current_folder') else None
    if current_folder:
        # Track the last folder we rendered filters for
        if 'last_filter_folder' not in st.session_state:
            st.session_state.last_filter_folder = None

        # If folder changed, clear all filter widget keys from session state
        if st.session_state.last_filter_folder != current_folder:
            # Find all filter widget keys and delete them
            keys_to_delete = [k for k in st.session_state.keys() if k.startswith('filter_')]
            for key in keys_to_delete:
                del st.session_state[key]

            # Update tracked folder
            st.session_state.last_filter_folder = current_folder

    # Create a scrollable container for filters
    with st.container():
        filter_context = notebook_session.get_filter_context()
        filter_values = {}

        # First, render auto-generated folder filters (not defined in notebook)
        extra_folder_filters = getattr(notebook_session, '_extra_folder_filters', {})
        if extra_folder_filters:
            st.caption("📁 **Folder Filters** (applied automatically)")
            for var_id, value in extra_folder_filters.items():
                # Skip if already defined in notebook variables
                if notebook_config.variables and var_id in notebook_config.variables:
                    continue

                # Auto-generate widget based on value type
                result = render_auto_filter(var_id, value)
                if result is not None:
                    filter_values[var_id] = result

            if extra_folder_filters:
                st.divider()

        # Then render notebook-defined variables
        if notebook_config.variables:
            for var_id, variable in notebook_config.variables.items():
                if variable.type == VariableType.DATE_RANGE:
                    filter_values[var_id] = render_date_range_filter(var_id, variable, notebook_session)

                elif variable.type == VariableType.MULTI_SELECT:
                    filter_values[var_id] = render_multi_select_filter(
                        var_id, variable, notebook_session=notebook_session,
                        connection=connection, storage_service=storage_service
                    )

                elif variable.type == VariableType.SINGLE_SELECT:
                    filter_values[var_id] = render_single_select_filter(
                        var_id, variable, notebook_session=notebook_session,
                        connection=connection, storage_service=storage_service
                    )

                elif variable.type == VariableType.NUMBER:
                    filter_values[var_id] = render_number_filter(var_id, variable, notebook_session)

                elif variable.type == VariableType.BOOLEAN:
                    filter_values[var_id] = render_boolean_filter(var_id, variable, notebook_session)

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


def render_multi_select_filter(var_id: str, variable, notebook_session=None, connection=None, storage_service=None) -> List[Any]:
    """
    Render multi-select filter with dynamic options from database.

    Args:
        var_id: Variable identifier
        variable: Variable configuration
        notebook_session: NotebookSession for filter context (to get folder filter values)
        connection: Optional DataConnection for querying dynamic options
        storage_service: Optional StorageService for loading table data

    Returns:
        List of selected values
    """
    # Determine options source - prioritize dynamic source over static options
    if hasattr(variable, 'source') and variable.source and connection and storage_service:
        # Dynamic options from database query (PRIORITY)
        # Source is a SourceReference object with model, node, column
        source_ref = variable.source
        model = source_ref.model  # e.g., "company"
        table = source_ref.node  # e.g., "fact_prices"
        column = source_ref.column  # e.g., "ticker"

        if not column:
            # If no column specified, use the variable id as column name
            column = var_id

        options = _get_distinct_values(connection, storage_service, model, table, column)

        # Show indicator that dynamic loading is active
        if options:
            st.caption(f"ℹ️ {len(options)} options loaded from {table}.{column}")

        if not options:
            # Fallback to static options or default if query fails
            st.warning(f"⚠️ Could not load dynamic options from {table}.{column}, using fallback")
            options = variable.options if variable.options else (variable.default if variable.default else [])
    elif variable.options:
        # Static options from YAML (fallback)
        options = variable.options
    else:
        # No options source, use default
        options = variable.default if variable.default else []

    # Get current value from filter context (includes folder filters)
    default = variable.default if variable.default else []
    if notebook_session:
        filter_context = notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)
        if current_value is not None:
            # Use folder filter value if available
            if isinstance(current_value, list):
                default = current_value
            else:
                default = [current_value]

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


def render_single_select_filter(var_id: str, variable, notebook_session=None, connection=None, storage_service=None) -> Any:
    """
    Render single-select filter with dynamic options from database.

    Args:
        var_id: Variable identifier
        variable: Variable configuration
        notebook_session: NotebookSession for filter context (to get folder filter values)
        connection: Optional DataConnection for querying dynamic options
        storage_service: Optional StorageService for loading table data

    Returns:
        Selected value
    """
    # Determine options source - prioritize dynamic source over static options
    if hasattr(variable, 'source') and variable.source and connection and storage_service:
        # Dynamic options from database query (PRIORITY)
        # Source is a SourceReference object with model, node, column
        source_ref = variable.source
        model = source_ref.model  # e.g., "company"
        table = source_ref.node  # e.g., "fact_prices"
        column = source_ref.column  # e.g., "ticker"

        if not column:
            # If no column specified, use the variable id as column name
            column = var_id

        options = _get_distinct_values(connection, storage_service, model, table, column)

        # Show indicator that dynamic loading is active
        if options:
            st.caption(f"ℹ️ {len(options)} options loaded from {table}.{column}")

        if not options:
            # Fallback to static options or default if query fails
            st.warning(f"⚠️ Could not load dynamic options from {table}.{column}, using fallback")
            options = variable.options if variable.options else ([variable.default] if variable.default else [])
    elif variable.options:
        # Static options from YAML (fallback)
        options = variable.options
    else:
        # No options source, use default
        options = [variable.default] if variable.default else []

    # Get current value from filter context (includes folder filters)
    default = variable.default
    if notebook_session:
        filter_context = notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)
        if current_value is not None:
            default = current_value

    return st.selectbox(
        variable.display_name,
        options=options,
        index=options.index(default) if default and default in options else 0,
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_number_filter(var_id: str, variable, notebook_session=None) -> float:
    """Render number filter."""
    default = variable.default if variable.default is not None else 0.0

    # Get current value from filter context (includes folder filters)
    if notebook_session:
        filter_context = notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)
        if current_value is not None:
            default = current_value

    return st.number_input(
        variable.display_name,
        value=float(default),
        key=f"filter_{var_id}",
        help=variable.description,
    )


def render_boolean_filter(var_id: str, variable, notebook_session=None) -> bool:
    """Render boolean filter."""
    default = variable.default if variable.default is not None else False

    # Get current value from filter context (includes folder filters)
    if notebook_session:
        filter_context = notebook_session.get_filter_context()
        current_value = filter_context.get(var_id)
        if current_value is not None:
            default = current_value

    return st.checkbox(
        variable.display_name,
        value=default,
        key=f"filter_{var_id}",
        help=variable.description,
    )

def render_auto_filter(var_id: str, value: Any) -> Any:
    """
    Auto-generate filter widget based on value type from folder context.
    
    This allows folder filters to create UI widgets even when notebook
    doesn't define the filter variables.
    
    Args:
        var_id: Variable identifier
        value: Current value from folder context
        
    Returns:
        Widget return value
    """
    # Friendly label from var_id
    label = var_id.replace('_', ' ').title()
    
    # Auto-detect widget type from value
    if isinstance(value, list):
        # Multi-select
        return st.multiselect(
            label,
            options=value,
            default=value,
            key=f"filter_{var_id}",
            help=f"Folder filter: {var_id}"
        )
    
    elif isinstance(value, dict):
        if 'start' in value and 'end' in value:
            # Date range
            from datetime import datetime
            start_val = value['start']
            end_val = value['end']
            
            if isinstance(start_val, str):
                start_val = datetime.fromisoformat(start_val.replace('Z', '+00:00')).date()
            if isinstance(end_val, str):
                end_val = datetime.fromisoformat(end_val.replace('Z', '+00:00')).date()
                
            start_date = st.date_input(
                f"{label} (Start)",
                value=start_val,
                key=f"filter_{var_id}_start"
            )
            end_date = st.date_input(
                f"{label} (End)",
                value=end_val,
                key=f"filter_{var_id}_end"
            )
            return {'start': start_date, 'end': end_date}
        
        elif 'min' in value or 'max' in value:
            # Number range
            min_val = value.get('min', 0)
            max_val = value.get('max', 1000000)
            return st.slider(
                label,
                min_value=float(min_val),
                max_value=float(max_val),
                value=(float(min_val), float(max_val)),
                key=f"filter_{var_id}"
            )
        else:
            # Unknown dict type - show as text
            st.caption(f"**{label}**: {value}")
            return value
    
    elif isinstance(value, bool):
        # Boolean
        return st.checkbox(
            label,
            value=value,
            key=f"filter_{var_id}"
        )
    
    elif isinstance(value, (int, float)):
        # Number
        return st.number_input(
            label,
            value=float(value),
            key=f"filter_{var_id}"
        )
    
    elif isinstance(value, str):
        # Text input
        return st.text_input(
            label,
            value=value,
            key=f"filter_{var_id}"
        )
    
    else:
        # Unknown type - show as caption
        st.caption(f"**{label}**: {value}")
        return value
