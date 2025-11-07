# Filter Architecture - Unified Design

## Overview

This document describes the complete, unified filter architecture that ensures consistent behavior across folder contexts, notebook sessions, and data queries.

## Architecture Principles

### 1. Folder-Level Isolation

**Key Concept**: Filters are scoped to folders, completely isolated across folder boundaries.

```
configs/notebooks/
├── Financial Analysis/
│   ├── .filter_context.yaml       (ticker=[AAPL, MSFT])
│   └── stock_analysis.md
└── Market Trends/
    ├── .filter_context.yaml       (ticker=[GOOG])
    └── trend_analysis.md
```

Switching from Financial Analysis → Market Trends triggers a complete filter reset.

### 2. Single Source of Truth

**FilterContext** is the authoritative source for all filter values:

```
FilterContext
├── _values: Dict[str, Any]        ← Source of truth
├── variables: Dict[str, Variable]  ← Schema/validation
└── get_all() → Dict                ← Query interface
```

All components read from and write to FilterContext, never maintaining separate state.

### 3. Streamlit Widget State Management

**Critical Issue**: Streamlit widgets persist their values in `st.session_state` across reruns.

**Problem Scenario**:
```python
# Folder A
st.multiselect("Ticker", options=[...], default=['AAPL'], key="filter_ticker")
# st.session_state['filter_ticker'] = ['AAPL']

# User switches to Folder B
st.multiselect("Ticker", options=[...], default=['GOOG'], key="filter_ticker")
# Streamlit IGNORES default=['GOOG'] because key already exists!
# Widget shows ['AAPL'] instead of ['GOOG']
```

**Solution**: Detect folder changes and clear widget state:

```python
# Track current folder
current_folder = str(notebook_session.get_current_folder())

# Detect change
if st.session_state.last_filter_folder != current_folder:
    # Clear all filter widget keys
    keys_to_delete = [k for k in st.session_state.keys() if k.startswith('filter_')]
    for key in keys_to_delete:
        del st.session_state[key]

    # Update tracker
    st.session_state.last_filter_folder = current_folder
```

This ensures widgets recreate with fresh defaults from the new folder context.

## Complete Data Flow

### Load Phase

```
┌─────────────────────────────────────────────────────────┐
│ 1. USER OPENS NOTEBOOK                                  │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 2. NotebookManager.load_notebook()                      │
│    ├─ Detect folder: get_folder_for_notebook()          │
│    ├─ Load folder filters: get_filters(folder)          │
│    ├─ Create FilterContext with notebook variables      │
│    └─ Apply folder filters to FilterContext             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 3. FilterContext initialized                            │
│    _values = {                                          │
│      'ticker': ['AAPL', 'MSFT'],    ← from folder       │
│      'trade_date': {...},            ← from folder       │
│      'volume': 5000000               ← from folder       │
│    }                                                    │
└─────────────────────────────────────────────────────────┘
```

### Render Phase

```
┌─────────────────────────────────────────────────────────┐
│ 4. render_filters_section() called                      │
│    ├─ Detect folder change                              │
│    ├─ Clear widget state if folder changed              │
│    └─ Get filter_context.get_all()                      │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 5. For each variable, render widget:                    │
│    render_multi_select_filter()                         │
│    ├─ Get current value from filter_context             │
│    ├─ Set as widget default                             │
│    └─ Widget key: "filter_{var_id}"                     │
│                                                         │
│    st.multiselect(                                      │
│      options=loaded_from_db,                            │
│      default=['AAPL', 'MSFT'],  ← from filter_context  │
│      key="filter_ticker"                                │
│    )                                                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 6. Collect widget return values                         │
│    filter_values = {                                    │
│      'ticker': widget_return_value,                     │
│      'trade_date': widget_return_value,                 │
│      ...                                                │
│    }                                                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 7. Update FilterContext                                 │
│    notebook_session.update_filters(filter_values)       │
│    ├─ Updates in-memory FilterContext                   │
│    ├─ Updates folder context manager                    │
│    └─ Persists to .filter_context.yaml                  │
└─────────────────────────────────────────────────────────┘
```

### Query Phase

```
┌─────────────────────────────────────────────────────────┐
│ 8. render_exhibit() called for each exhibit             │
│    notebook_session.get_exhibit_data(exhibit_id)        │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 9. Load raw data                                        │
│    df = session.get_table(model, table)                 │
│    # Unfiltered DataFrame                               │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 10. Build filters from FilterContext                    │
│     _build_filters(exhibit)                             │
│     ├─ Get filter_context.get_all()                     │
│     ├─ Convert to FilterEngine format                   │
│     └─ Return filter dict                               │
│                                                         │
│     filters = {                                         │
│       'ticker': ['AAPL', 'MSFT'],                      │
│       'trade_date': {'min': '2024-10-01', ...},        │
│       'volume': {'min': 5000000}                        │
│     }                                                   │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 11. Apply filters to data                               │
│     FilterEngine.apply_from_session(df, filters, ...)   │
│     ├─ Detect backend (Spark or DuckDB)                 │
│     ├─ Build WHERE clause                               │
│     └─ Return filtered DataFrame                        │
│                                                         │
│     DuckDB: df.filter("ticker IN ('AAPL','MSFT')")     │
│     Spark: df.filter(F.col("ticker").isin(...))        │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 12. Render exhibit with filtered data                   │
│     Metric cards, charts, tables show only:             │
│     - ticker IN (AAPL, MSFT)                           │
│     - trade_date BETWEEN 2024-10-01 AND 2024-12-31     │
│     - volume >= 5000000                                 │
└─────────────────────────────────────────────────────────┘
```

## Critical Synchronization Points

### Point 1: Folder Change Detection

**Location**: `app/ui/components/filters.py` lines 64-80

**Purpose**: Ensure widgets don't retain stale values when switching folders

**Mechanism**:
```python
current_folder = str(notebook_session.get_current_folder())
if st.session_state.last_filter_folder != current_folder:
    # Clear all filter_* keys
    keys_to_delete = [k for k in st.session_state.keys() if k.startswith('filter_')]
    for key in keys_to_delete:
        del st.session_state[key]
```

**Result**: Fresh widget state for new folder context

### Point 2: FilterContext Pre-Population

**Location**: `app/notebook/managers/notebook_manager.py` lines 115-129

**Purpose**: Initialize FilterContext with folder filter values

**Mechanism**:
```python
# Load folder filters
folder_filters = self.folder_context_manager.get_filters(new_folder)

# Create FilterContext with notebook variables
self.filter_context = FilterContext(self.notebook_config.variables)

# Apply folder filters (only matching variables)
if folder_filters:
    valid_filters = {k: v for k, v in folder_filters.items()
                    if k in self.notebook_config.variables}
    if valid_filters:
        self.filter_context.update(valid_filters)
```

**Result**: FilterContext contains folder filter values as defaults

### Point 3: Widget Default Values

**Location**: `app/ui/components/filters.py` lines 173-183 (multi_select example)

**Purpose**: Show folder filter values in widgets

**Mechanism**:
```python
# Get current value from filter context (includes folder filters)
default = variable.default if variable.default else []
if notebook_session:
    filter_context = notebook_session.get_filter_context()
    current_value = filter_context.get(var_id)
    if current_value is not None:
        if isinstance(current_value, list):
            default = current_value
        else:
            default = [current_value]

st.multiselect(..., default=default, key=f"filter_{var_id}")
```

**Result**: Widgets pre-populated with folder context values

### Point 4: Filter Application to Queries

**Location**: `app/notebook/managers/notebook_manager.py` lines 282-284

**Purpose**: Apply filters to database queries

**Mechanism**:
```python
# Get exhibit data
df = self.session.get_table(model_name, table_name)

# Build filters from FilterContext
filters = self._build_filters(exhibit)

# Apply via FilterEngine
df = FilterEngine.apply_from_session(df, filters, self.session)
```

**Result**: Data queries execute with current filter values

## Two Filter Systems

The codebase supports two filter systems for backward compatibility:

### Legacy System (Old Notebooks)

**Trigger**: `notebook_config.variables` exists

**Components**:
- `render_filters_section()` - UI rendering
- `FilterContext` - State management
- `_build_filters()` - Query conversion

**Characteristics**:
- Defined in `$filter$` blocks or YAML `variables`
- Static types (DATE_RANGE, MULTI_SELECT, etc.)
- Folder context via `.filter_context.yaml`

### Dynamic System (New Notebooks)

**Trigger**: `notebook_config._filter_collection` exists

**Components**:
- `render_dynamic_filters()` - UI rendering
- `FilterCollection` - State management
- `get_active_filters()` - Query conversion

**Characteristics**:
- Defined in markdown with `$filter${...}` blocks
- Dynamic database-driven options
- Session state management

**Both systems** now have folder change detection to ensure correct state management.

## State Persistence

### In-Memory State

```
NotebookManager
├── filter_context: FilterContext      ← Current filter values
├── current_folder: Path                ← Current folder
└── model_sessions: Dict                ← Cached model data
```

### Streamlit Session State

```
st.session_state
├── last_filter_folder: str             ← Track folder changes
├── filter_ticker: List[str]            ← Widget value (cleared on folder change)
├── filter_trade_date_start: date       ← Widget value (cleared on folder change)
└── ... (other filter_* keys)
```

### Persistent Storage

```
.filter_context.yaml files
├── filters: Dict[str, Any]             ← Filter values
└── metadata: Dict                      ← Timestamps, folder info
```

## Filter Format Transformations

### Stage 1: Folder Context (YAML)

```yaml
filters:
  ticker:
    - AAPL
    - MSFT
  trade_date:
    start: "2024-10-01"
    end: "2024-12-31"
  volume: 5000000
```

### Stage 2: FilterContext (Python)

```python
FilterContext._values = {
    'ticker': ['AAPL', 'MSFT'],
    'trade_date': {
        'start': datetime(2024, 10, 1),
        'end': datetime(2024, 12, 31)
    },
    'volume': 5000000
}
```

### Stage 3: FilterEngine Format

```python
filters = {
    'ticker': ['AAPL', 'MSFT'],           # IN clause
    'trade_date': {                       # BETWEEN clause
        'min': '2024-10-01',
        'max': '2024-12-31'
    },
    'volume': {'min': 5000000}            # GTE clause
}
```

### Stage 4: Backend Query

**DuckDB**:
```sql
SELECT * FROM table
WHERE ticker IN ('AAPL', 'MSFT')
  AND trade_date BETWEEN '2024-10-01' AND '2024-12-31'
  AND volume >= 5000000
```

**Spark**:
```python
df.filter(F.col("ticker").isin(['AAPL', 'MSFT']))
  .filter((F.col("trade_date") >= "2024-10-01") &
          (F.col("trade_date") <= "2024-12-31"))
  .filter(F.col("volume") >= 5000000)
```

## Debugging & Troubleshooting

### Issue: Filters don't match data

**Symptom**: Widget shows "GOOG" but data shows AAPL records

**Root Cause**: Widget state persisted from previous folder

**Check**:
1. Verify folder change detection is working
2. Check `st.session_state.last_filter_folder`
3. Ensure `filter_*` keys are being cleared

**Fix**: Verify lines 64-80 in `filters.py` are executing

### Issue: Filters not pre-populating

**Symptom**: Widgets show notebook defaults instead of folder filter values

**Root Cause**: FilterContext not initialized with folder filters

**Check**:
1. Verify `.filter_context.yaml` exists in folder
2. Check filter names match notebook variable IDs exactly
3. Verify `load_notebook()` is applying folder filters

**Fix**: Verify lines 115-129 in `notebook_manager.py` are executing

### Issue: Data not filtered

**Symptom**: Exhibits show all data, ignoring filters

**Root Cause**: FilterEngine not being called or filters not built correctly

**Check**:
1. Verify `_build_filters()` is returning non-empty dict
2. Check `FilterEngine.apply_from_session()` is being called
3. Verify backend detection is correct (Spark vs DuckDB)

**Fix**: Add logging to `get_exhibit_data()` to trace filter application

## Best Practices

### 1. Always Scope Filters to Folders

Create `.filter_context.yaml` at the folder level, not per-notebook. This ensures all notebooks in a folder share the same analytical context.

### 2. Match Variable Names Exactly

Filter names in `.filter_context.yaml` must exactly match notebook variable IDs:

```yaml
# Notebook defines: $filter${id: ticker, ...}
# Filter context MUST use same ID:
filters:
  ticker: [AAPL, MSFT]  # ✓ Matches
  tickers: [AAPL, MSFT] # ✗ Won't work
```

### 3. Reset Filters When Switching Contexts

The system automatically resets on folder changes. Don't try to manually preserve filters across folders - this violates folder isolation.

### 4. Use FilterContext as Source of Truth

Never maintain filter state outside of FilterContext. Always read from and write to FilterContext.

### 5. Test Folder Switching

When developing, test switching between folders to ensure filters reset correctly:

1. Open notebook in Folder A
2. Note filter values
3. Switch to notebook in Folder B
4. Verify filters changed to Folder B's context
5. Verify data reflects Folder B filters

## Summary

The unified filter architecture ensures:

✅ **Folder-level isolation** - Complete reset when switching folders
✅ **Single source of truth** - FilterContext is authoritative
✅ **Widget state management** - Automatic cleanup on folder changes
✅ **Consistent data queries** - Filters always applied via FilterEngine
✅ **Backend compatibility** - Works with Spark and DuckDB
✅ **Backward compatibility** - Supports both legacy and dynamic filter systems

This design eliminates filter/data mismatches and ensures reproducible analytical views.
