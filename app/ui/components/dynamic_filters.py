"""
Dynamic filter rendering component.

Renders filters with database-driven options and session state management.
"""

import streamlit as st
from typing import Any, List, Optional
from datetime import date, datetime, timedelta
from app.notebook.filters.dynamic import (
    FilterCollection,
    FilterConfig,
    FilterType,
    FilterSource,
)


def render_dynamic_filters(
    filter_collection: FilterCollection,
    notebook_session,
    connection,
    storage_service
):
    """
    Render dynamic filters in the sidebar.

    Args:
        filter_collection: Collection of filter configurations
        notebook_session: NotebookSession for data access
        connection: Database connection
        storage_service: Storage service for querying options
    """
    if not filter_collection or not filter_collection.filters:
        return

    st.header("🔍 Filters")

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

    # Track if any filter changed
    filter_changed = False

    # Render each filter
    for filter_id, filter_config in filter_collection.filters.items():
        changed = render_filter(
            filter_config,
            filter_collection,
            notebook_session,
            connection,
            storage_service
        )
        if changed:
            filter_changed = True

    # If any filter changed, update session and rerun
    if filter_changed:
        st.rerun()


def render_filter(
    filter_config: FilterConfig,
    filter_collection: FilterCollection,
    notebook_session,
    connection,
    storage_service
) -> bool:
    """
    Render a single filter.

    Args:
        filter_config: Filter configuration
        filter_collection: Parent filter collection
        notebook_session: Notebook session
        connection: Database connection
        storage_service: Storage service

    Returns:
        bool: True if filter value changed
    """
    filter_id = filter_config.id
    filter_state = filter_collection.get_state(filter_id)

    # Get current value - PRIORITY ORDER:
    # 1. Session state (user interaction)
    # 2. Filter state current_value (merged notebook + folder context)
    session_key = f"filter_{filter_id}"

    # Use filter_state.current_value which already has merged folder + notebook values
    # (set by _merge_filters_unified() in load_notebook())
    default_value = filter_state.current_value if filter_state.current_value is not None else filter_config.default

    current_value = st.session_state.get(session_key, default_value)

    # Render based on filter type
    if filter_config.type == FilterType.DATE_RANGE:
        new_value = render_date_range_filter(filter_config, current_value)

    elif filter_config.type == FilterType.SELECT:
        new_value = render_select_filter(
            filter_config,
            current_value,
            connection,
            storage_service,
            notebook_session
        )

    elif filter_config.type == FilterType.NUMBER_RANGE:
        new_value = render_number_range_filter(filter_config, current_value)

    elif filter_config.type == FilterType.TEXT_SEARCH:
        new_value = render_text_search_filter(filter_config, current_value)

    elif filter_config.type == FilterType.BOOLEAN:
        new_value = render_boolean_filter(filter_config, current_value)

    elif filter_config.type == FilterType.SLIDER:
        new_value = render_slider_filter(filter_config, current_value)

    else:
        st.warning(f"Filter type not implemented: {filter_config.type}")
        return False

    # Check if value changed
    changed = new_value != current_value

    # Update state
    if changed:
        st.session_state[session_key] = new_value
        filter_collection.update_value(filter_id, new_value)

    return changed


def render_date_range_filter(filter_config: FilterConfig, current_value: Any) -> Any:
    """Render date range filter."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    # Parse current value
    if isinstance(current_value, dict):
        start_date = parse_date(current_value.get('start'))
        end_date = parse_date(current_value.get('end'))
    else:
        # Default to last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    col1, col2 = st.columns(2)

    with col1:
        start = st.date_input(
            "Start",
            value=start_date,
            key=f"date_start_{filter_config.id}"
        )

    with col2:
        end = st.date_input(
            "End",
            value=end_date,
            key=f"date_end_{filter_config.id}"
        )

    return {'start': str(start), 'end': str(end)}


def render_select_filter(
    filter_config: FilterConfig,
    current_value: Any,
    connection,
    storage_service,
    notebook_session
) -> Any:
    """Render select filter with dynamic options."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    # Get options
    if filter_config.options:
        # Static options
        options = filter_config.options
    elif filter_config.source:
        # Dynamic options from database
        options = get_filter_options_from_db(
            filter_config.source,
            connection,
            storage_service
        )
    else:
        # No options specified - try to infer from filter ID
        options = []

    if not options:
        st.warning(f"No options available for {filter_config.label}")
        return None

    # Render multi-select or single-select
    if filter_config.multi:
        # Ensure current_value is a list
        if current_value is None:
            current_value = []
        elif not isinstance(current_value, list):
            current_value = [current_value]

        # Filter current_value to only include values that exist in options
        # This prevents Streamlit errors when folder context has values not in the dataset
        valid_defaults = [v for v in current_value if v in options]

        selected = st.multiselect(
            "Select options",
            options=options,
            default=valid_defaults,
            placeholder=filter_config.placeholder or "Choose options...",
            key=f"select_{filter_config.id}"
        )
        return selected
    else:
        # Single select
        index = 0
        if current_value and current_value in options:
            index = options.index(current_value)

        selected = st.selectbox(
            "Select option",
            options=options,
            index=index,
            placeholder=filter_config.placeholder or "Choose an option...",
            key=f"select_{filter_config.id}"
        )
        return selected


def render_number_range_filter(filter_config: FilterConfig, current_value: Any) -> Any:
    """Render number range filter."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    # Parse current value
    if isinstance(current_value, dict):
        min_val = current_value.get('min', filter_config.min_value or 0)
        max_val = current_value.get('max', filter_config.max_value or 100)
    else:
        min_val = filter_config.min_value or 0
        max_val = filter_config.max_value or 100

    col1, col2 = st.columns(2)

    with col1:
        min_input = st.number_input(
            "Min",
            value=float(min_val),
            step=filter_config.step or 1.0,
            key=f"num_min_{filter_config.id}"
        )

    with col2:
        max_input = st.number_input(
            "Max",
            value=float(max_val),
            step=filter_config.step or 1.0,
            key=f"num_max_{filter_config.id}"
        )

    return {'min': min_input, 'max': max_input}


def render_text_search_filter(filter_config: FilterConfig, current_value: Any) -> Any:
    """Render text search filter with optional fuzzy matching."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    search_text = st.text_input(
        "Search",
        value=current_value or "",
        placeholder=filter_config.placeholder or "Enter search term...",
        key=f"text_{filter_config.id}"
    )

    if filter_config.fuzzy_enabled:
        st.caption(f"🔍 Fuzzy matching enabled (threshold: {filter_config.fuzzy_threshold})")

    return search_text if search_text else None


def render_boolean_filter(filter_config: FilterConfig, current_value: Any) -> Any:
    """Render boolean filter."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    checked = st.checkbox(
        filter_config.label,
        value=bool(current_value) if current_value is not None else False,
        key=f"bool_{filter_config.id}"
    )

    return checked


def render_slider_filter(filter_config: FilterConfig, current_value: Any) -> Any:
    """Render slider filter."""
    st.subheader(filter_config.label)

    if filter_config.help_text:
        st.caption(filter_config.help_text)

    min_val = filter_config.min_value or 0
    max_val = filter_config.max_value or 100
    default_val = current_value if current_value is not None else min_val

    # Ensure all values are the same type (float) for Streamlit slider
    value = st.slider(
        "Value",
        min_value=float(min_val),
        max_value=float(max_val),
        value=float(default_val),
        step=float(filter_config.step) if filter_config.step else 1.0,
        key=f"slider_{filter_config.id}"
    )

    return value


@st.cache_data(ttl=300)
def get_filter_options_from_db(
    source: FilterSource,
    _connection,
    _storage_service
) -> List[Any]:
    """
    Get filter options from database using optimized DISTINCT query.

    Args:
        source: FilterSource configuration
        _connection: Database connection
        _storage_service: Storage service

    Returns:
        List of distinct values for the filter
    """
    try:
        # Use SQL to get distinct values (much faster than loading entire table)
        # This is critical for large fact tables (e.g., 10M+ rows)

        # Get model and table path
        model = _storage_service.model_registry.get_model(source.model)
        table_path = model.get_table_path(source.table)

        # For DuckDB, construct table reference
        # table_path is like: Path('storage/silver/equity/facts/fact_equity_prices')
        if table_path.is_dir():
            table_ref = f"read_parquet('{table_path}/*.parquet')"
        else:
            table_ref = f"read_parquet('{table_path}')"

        # Build SQL query for distinct values
        order_clause = f"ORDER BY {source.column}" if source.sort else ""
        limit_clause = f"LIMIT {source.limit}" if source.limit else ""

        sql = f"""
            SELECT DISTINCT {source.column}
            FROM {table_ref}
            WHERE {source.column} IS NOT NULL
            {order_clause}
            {limit_clause}
        """

        # Execute query
        result_df = _connection.conn.execute(sql).fetchdf()
        values = result_df[source.column].tolist()

        return values

    except Exception as e:
        st.error(f"Error loading filter options: {str(e)}")
        # Fallback to old method if SQL fails
        try:
            df = _storage_service.get_table(source.model, source.table, use_cache=True)
            if source.column in df.columns:
                pdf = _connection.to_pandas(df)
                values = pdf[source.column].dropna().unique().tolist()

                if source.sort:
                    values = sorted(values)
                if source.limit:
                    values = values[:source.limit]

                return values
        except:
            pass
        return []


def parse_date(date_str: Any) -> date:
    """Parse date string into date object."""
    if isinstance(date_str, date):
        return date_str
    elif isinstance(date_str, datetime):
        return date_str.date()
    elif isinstance(date_str, str):
        # Try parsing ISO format
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            pass

        # Try relative dates
        if date_str.lower() == 'today':
            return date.today()
        elif date_str.startswith('-'):
            # Relative date (e.g., "-30d")
            import re
            match = re.match(r'-(\d+)([dwmy])', date_str)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == 'd':
                    return date.today() - timedelta(days=amount)
                elif unit == 'w':
                    return date.today() - timedelta(weeks=amount)
                elif unit == 'm':
                    return date.today() - timedelta(days=amount * 30)
                elif unit == 'y':
                    return date.today() - timedelta(days=amount * 365)

    # Default to today
    return date.today()
