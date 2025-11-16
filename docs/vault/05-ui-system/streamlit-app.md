# Streamlit App

**Interactive UI for notebooks and analytics**

Files: `app/ui/`, `app/notebook/`
Entry Point: `run_app.py` or `run_app.sh`

---

## Overview

The Streamlit app provides an **interactive web interface** for exploring notebooks, executing queries, and visualizing data. It's the primary user interface for de_Funk analytics.

**Technology**: Streamlit (Python web framework for data apps)

---

## Architecture

```
Streamlit UI
├── Sidebar → Notebook navigation
├── Main Area → Notebook content
│   ├── Markdown → Rich text
│   ├── Filters → Dynamic filtering
│   └── Exhibits → Charts and tables
└── Session State → Filter values, cache
```

---

## Application Structure

```
app/
├── ui/
│   ├── notebook_app_duckdb.py    # Main app (DuckDB backend)
│   ├── components/               # Reusable UI components
│   └── utils/                    # UI utilities
└── notebook/
    ├── managers/                 # Notebook management
    ├── parsers/                  # Markdown parsing
    ├── filters/                  # Filter system
    └── exhibits/                 # Visualization rendering
```

---

## Running the App

**Via Script**:
```bash
# DuckDB backend (recommended - fast)
./run_app.sh

# Or directly
python run_app.py
```

**Direct Streamlit**:
```bash
streamlit run app/ui/notebook_app_duckdb.py
```

**URL**: Opens browser to `http://localhost:8501`

---

## App Components

### Sidebar (Navigation)

**Features**:
- Notebook folder tree
- Notebook search
- Model selector
- Settings

**Code**:
```python
with st.sidebar:
    st.title("de_Funk Analytics")

    # Notebook navigation
    selected_notebook = st.selectbox(
        "Select Notebook",
        options=notebook_list
    )

    # Model selector
    selected_models = st.multiselect(
        "Active Models",
        options=['equity', 'corporate', 'macro'],
        default=['equity']
    )
```

---

### Main Area (Content)

**Sections**:
1. **Notebook Title** - From YAML front matter
2. **Filters** - Dynamic filter widgets
3. **Content Blocks** - Markdown + exhibits interleaved
4. **Export** - Download data/charts

---

### Filter Panel

**Rendering**:
```python
def render_filters(filters):
    """Render all filters for notebook."""
    st.subheader("Filters")

    for filter_config in filters:
        if filter_config.type == FilterType.DATE_RANGE:
            render_date_range_filter(filter_config)
        elif filter_config.type == FilterType.MULTI_SELECT:
            render_multi_select_filter(filter_config)
        # ...
```

**Layout**: Filters displayed in expandable section above exhibits

---

### Exhibit Rendering

**Integration**:
```python
def render_notebook_content(notebook_config):
    """Render notebook content blocks."""
    for block in notebook_config.content_blocks:
        if block['type'] == 'markdown':
            st.markdown(block['content'])

        elif block['type'] == 'exhibit':
            exhibit_renderer.render_exhibit(block['exhibit'])

        elif block['type'] == 'collapsible':
            with st.expander(block['summary']):
                render_collapsible_content(block['content'])
```

---

## Session State

**Purpose**: Persist state across Streamlit reruns

**Stored State**:
```python
st.session_state = {
    'filters': {...},                # Current filter values
    'selected_notebook': 'analysis', # Current notebook
    'session': UniversalSession(),   # Data session
    'cache': {...}                   # Query cache
}
```

**Access**:
```python
# Read
current_filters = st.session_state.get('filters', {})

# Write
st.session_state.filters = {'ticker': ['AAPL']}
```

---

## Caching

**Streamlit Cache Decorators**:

```python
@st.cache_data
def load_notebook(notebook_path):
    """Cache parsed notebooks."""
    parser = MarkdownNotebookParser()
    return parser.parse_file(notebook_path)

@st.cache_resource
def get_session():
    """Cache database session (singleton)."""
    return UniversalSession(backend='duckdb')
```

**Benefits**:
- Faster page loads
- Reduced database queries
- Better user experience

---

## Performance Optimization

**Strategies**:

1. **Use DuckDB backend** (10-100x faster than Spark)
2. **Cache parsed notebooks** (`@st.cache_data`)
3. **Cache data queries** (`@st.cache_data(ttl=300)`)
4. **Lazy load exhibits** (render only visible)
5. **Pagination for tables** (limit rows displayed)

---

## Deployment

**Local Development**:
```bash
python run_app.py
```

**Production Options**:
- Streamlit Cloud
- Docker container
- AWS/GCP/Azure deployment

**Configuration**:
```toml
# .streamlit/config.toml
[server]
port = 8501
enableCORS = false

[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
```

---

## Error Handling

**User-Friendly Errors**:
```python
try:
    df = session.query(sql, filters=filters)
except Exception as e:
    st.error(f"Query failed: {str(e)}")
    st.exception(e)  # Show full traceback in expander
```

**Fallback UI**: Show error message but continue rendering other exhibits

---

## Related Documentation

- [Notebook System](notebook-system.md) - Notebook format
- [Filter Engine](filter-engine-ui.md) - Filter UI
- [Exhibits](exhibits.md) - Visualization rendering
- [UniversalSession](../01-core-components/universal-session.md) - Data queries
