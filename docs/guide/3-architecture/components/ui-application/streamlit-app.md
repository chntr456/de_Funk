# UI Application - Streamlit App

## Overview

The **Streamlit App** is the main entry point for the de_Funk web interface. It coordinates between notebooks, filters, and exhibits.

## Main Application Structure

```python
# File: app/ui/notebook_app_duckdb.py:1-200

import streamlit as st
from pathlib import Path
from core.context import RepoContext
from models.api.session import UniversalSession
from app.notebook.managers.notebook_manager import NotebookManager

# Page configuration (must be first)
st.set_page_config(
    page_title="de_Funk Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session
@st.cache_resource
def get_context():
    """One RepoContext for entire app."""
    return RepoContext.from_repo_root(connection_type='duckdb')

@st.cache_resource
def get_universal_session():
    """Build UniversalSession (cached)."""
    ctx = get_context()
    return UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo,
        models=['company', 'forecast']
    )

# Main app
def main():
    """Main application entry point."""
    
    # Get cached session
    session = get_universal_session()
    ctx = get_context()
    
    # Create notebook manager
    manager = NotebookManager(
        universal_session=session,
        repo_root=ctx.repo
    )
    
    # Render UI
    render_sidebar(manager)
    render_main_area(manager)
```

## Sidebar Component

```python
def render_sidebar(manager):
    """Render application sidebar."""
    
    with st.sidebar:
        st.title("📊 de_Funk")
        st.markdown("---")
        
        # Notebook selection
        st.subheader("Notebooks")
        notebooks = discover_notebooks(manager.repo_root / "configs" / "notebooks")
        
        # Organize by folder
        folders = organize_by_folder(notebooks)
        
        selected_notebook = None
        for folder, notebook_list in folders.items():
            with st.expander(folder, expanded=True):
                for notebook in notebook_list:
                    if st.button(notebook['name'], key=notebook['path']):
                        selected_notebook = notebook['path']
        
        # Store selection in session state
        if selected_notebook:
            st.session_state['selected_notebook'] = selected_notebook
        
        st.markdown("---")
        
        # Global filters
        st.subheader("Global Filters")
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.date(2024, 1, 1))
        with col2:
            end_date = st.date_input("End Date", value=datetime.date.today())
        
        if start_date and end_date:
            st.session_state['date_filter'] = {'start': str(start_date), 'end': str(end_date)}
```

## Main Area Component

```python
def render_main_area(manager):
    """Render main content area."""
    
    # Get selected notebook from state
    notebook_path = st.session_state.get('selected_notebook')
    
    if not notebook_path:
        # Show welcome screen
        st.title("Welcome to de_Funk Analytics")
        st.markdown("""
        **de_Funk** is a flexible analytics platform for data exploration.
        
        Select a notebook from the sidebar to get started.
        """)
        return
    
    # Load notebook
    try:
        notebook = manager.load_notebook(notebook_path)
    except Exception as e:
        st.error(f"Error loading notebook: {e}")
        return
    
    # Apply global filters
    date_filter = st.session_state.get('date_filter')
    if date_filter:
        manager.update_filter('date', date_filter)
    
    # Render notebook title
    st.title(notebook.title)
    
    # Render filters
    render_notebook_filters(notebook, manager)
    
    st.markdown("---")
    
    # Render exhibits
    render_notebook_exhibits(notebook, manager)
```

## Exhibit Rendering

```python
def render_notebook_exhibits(notebook, manager):
    """Render all exhibits in notebook."""
    
    for exhibit in notebook.exhibits:
        try:
            # Container for exhibit
            with st.container():
                # Exhibit title
                if exhibit.title:
                    st.subheader(exhibit.title)
                
                # Execute exhibit
                with st.spinner(f"Loading {exhibit.title}..."):
                    data = manager.execute_exhibit(exhibit)
                
                # Render based on type
                render_exhibit(exhibit, data)
                
        except Exception as e:
            st.error(f"Error rendering exhibit {exhibit.title}: {e}")

def render_exhibit(exhibit, data):
    """Render individual exhibit."""
    
    exhibit_type = exhibit.type
    
    if exhibit_type == 'line_chart':
        render_line_chart(exhibit, data)
    elif exhibit_type == 'bar_chart':
        render_bar_chart(exhibit, data)
    elif exhibit_type == 'data_table':
        render_data_table(exhibit, data)
    elif exhibit_type == 'metric_cards':
        render_metric_cards(exhibit, data)
    else:
        st.warning(f"Unknown exhibit type: {exhibit_type}")
```

## Running the App

```bash
# Development
streamlit run app/ui/notebook_app_duckdb.py

# Production
streamlit run app/ui/notebook_app_duckdb.py --server.port 8501 --server.address 0.0.0.0

# With custom config
streamlit run app/ui/notebook_app_duckdb.py --server.maxUploadSize 200
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/ui-application/streamlit-app.md`
