# UI Application - State Management

## Overview

Streamlit session state management for persistent user state across re-runs.

## Session State Keys

```python
# Standard state keys
st.session_state = {
    'selected_notebook': str,      # Currently selected notebook path
    'date_filter': dict,           # Global date range filter
    'global_filters': dict,        # All global filters
    'notebook_config': dict,       # Current notebook configuration
    'filter_contexts': dict,       # Filter contexts per folder
    'cached_data': dict           # Cached query results
}
```

## State Initialization

```python
# File: app/ui/streamlit_app.py

def initialize_state():
    """Initialize session state variables."""
    
    if 'selected_notebook' not in st.session_state:
        st.session_state['selected_notebook'] = None
    
    if 'global_filters' not in st.session_state:
        st.session_state['global_filters'] = {}
    
    if 'filter_contexts' not in st.session_state:
        st.session_state['filter_contexts'] = {}
    
    if 'cached_data' not in st.session_state:
        st.session_state['cached_data'] = {}
```

## Filter State Management

```python
def update_filter_state(dimension, values):
    """Update filter in session state."""
    
    if 'global_filters' not in st.session_state:
        st.session_state['global_filters'] = {}
    
    st.session_state['global_filters'][dimension] = values

def get_active_filters():
    """Get all active filters from state."""
    return st.session_state.get('global_filters', {})

def clear_filters():
    """Clear all filters."""
    st.session_state['global_filters'] = {}
```

## Cache Management

```python
@st.cache_data(ttl=3600)
def get_cached_query(query_key, **kwargs):
    """Cache query results for 1 hour."""
    return execute_query(**kwargs)

def invalidate_cache():
    """Clear all cached data."""
    st.cache_data.clear()
    st.session_state['cached_data'] = {}
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/ui-application/state-management.md`
