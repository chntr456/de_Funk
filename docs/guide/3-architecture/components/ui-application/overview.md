# UI Application Component - Overview

## Introduction

The **UI Application Component** provides the interactive Streamlit-based web interface for de_Funk. It renders notebooks, handles user interactions, manages state, and coordinates between the UI layer and backend systems.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                  Streamlit Application                 │
└────────────────────────────────────────────────────────┘

Browser (User)
    │
    ├─► Streamlit App (app/ui/streamlit_app.py)
    │       │
    │       ├─► Sidebar (notebook selection, global filters)
    │       ├─► Main Area (notebook content, exhibits)
    │       └─► State Management (session_state)
    │
    └─► Components (app/ui/components/)
            ├─► Notebook View (notebook_view.py)
            ├─► Dynamic Filters (dynamic_filters.py)
            ├─► Exhibits (exhibits/*.py)
            │   ├─► Charts (line, bar, forecast)
            │   ├─► Tables (data_table.py)
            │   └─► Metrics (metric_cards.py)
            └─► Theme (theme.py)
```

## Key Components

### 1. Streamlit App (`app/ui/streamlit_app.py`)
- Main application entry point
- Page configuration
- Session management
- Route handling

### 2. Notebook View (`app/ui/components/notebook_view.py`)
- Renders notebook content
- Executes exhibits
- Handles filter updates
- Manages notebook state

### 3. Components (`app/ui/components/`)
- Reusable UI widgets
- Chart components
- Table components
- Filter components

### 4. State Management (`session_state`)
- Persistent session state
- Filter state
- Cached data
- Navigation state

## Application Flow

```
1. INITIALIZATION
   ┌──────────────────┐
   │ Start App        │
   │ - Load config    │
   │ - Create session │
   └────────┬─────────┘
            │
2. SIDEBAR   ▼
   ┌──────────────────┐
   │ Render Sidebar   │
   │ - List notebooks │
   │ - Global filters │
   │ - Select notebook│
   └────────┬─────────┘
            │
3. MAIN AREA ▼
   ┌──────────────────┐
   │ Load Notebook    │
   │ - Parse markdown │
   │ - Extract exhibits│
   └────────┬─────────┘
            │
4. RENDER    ▼
   ┌──────────────────┐
   │ For each exhibit:│
   │ - Execute query  │
   │ - Apply filters  │
   │ - Render visual  │
   └──────────────────┘
```

## Usage Example

```python
# File: app/ui/streamlit_app.py

import streamlit as st
from core.context import RepoContext
from models.api.session import UniversalSession
from app.notebook.managers.notebook_manager import NotebookManager

# Initialize
@st.cache_resource
def get_session():
    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    return UniversalSession(ctx.connection, ctx.storage, ctx.repo, models=['company'])

# Main app
def main():
    st.set_page_config(page_title="de_Funk Analytics", layout="wide")
    
    session = get_session()
    manager = NotebookManager(session, repo_root=session.repo_root)
    
    # Sidebar
    with st.sidebar:
        st.title("de_Funk")
        
        # Notebook selection
        notebooks = list_notebooks()
        selected = st.selectbox("Select Notebook", notebooks)
        
        # Global filters
        st.subheader("Global Filters")
        ticker_filter = st.multiselect("Tickers", get_tickers())
    
    # Main area
    if selected:
        notebook = manager.load_notebook(selected)
        
        # Apply filters
        if ticker_filter:
            manager.update_filter('ticker', ticker_filter)
        
        # Render notebook
        render_notebook(notebook, manager)

if __name__ == "__main__":
    main()
```

## Caching Strategy

```python
# Resource caching (connection, session)
@st.cache_resource
def get_universal_session():
    """Cache for entire app lifecycle."""
    return UniversalSession(...)

# Data caching (query results)
@st.cache_data(ttl=3600)
def get_price_data(ticker, start_date, end_date):
    """Cache for 1 hour."""
    return session.get_table('company', 'fact_prices')
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/ui-application/overview.md`
