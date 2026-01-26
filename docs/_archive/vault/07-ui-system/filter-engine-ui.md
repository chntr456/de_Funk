# Filter Engine (UI)

**Dynamic filtering system for interactive notebooks**

Files: `app/notebook/filters/`
Note: Different from `core/session/filters.py` (backend filtering)

---

## Overview

The UI Filter Engine provides **dynamic, user-driven filtering** for notebook visualizations. Users interact with filter widgets (date pickers, multi-selects, etc.) and the filter engine applies those selections to data queries.

**Key Distinction**:
- **Core FilterEngine** (`core/session/filters.py`): Backend filter application to DataFrames
- **UI Filter Engine** (`app/notebook/filters/`): UI widget rendering + filter state management

---

## Architecture

```
Filter Widget (Streamlit) → Filter State → FilterEngine → Query with Filters → DataFrame
```

**Components**:
1. **Filter Types** (`filters/types.py`) - Type definitions
2. **Filter Context** (`filters/context.py`) - Folder-level filter inheritance
3. **Dynamic Filters** (`filters/dynamic.py`) - Runtime filter creation
4. **Filter Engine** (`filters/engine.py`) - Filter application logic

---

## Filter Types

**File**: `app/notebook/filters/types.py`

```python
class FilterType(Enum):
    DATE_RANGE = "date_range"
    MULTI_SELECT = "multi_select"
    SINGLE_SELECT = "single_select"
    NUMBER_RANGE = "number_range"
    TEXT_INPUT = "text_input"
    BOOLEAN = "boolean"
```

---

## Filter Configuration

### Date Range

```yaml
$filter${
type: date_range
label: Trade Date Range
column: trade_date
default:
  start: 2024-01-01
  end: 2024-12-31
}
```

**Streamlit Widget**: `st.date_input()`

---

### Multi-Select

```yaml
$filter${
type: multi_select
label: Select Tickers
column: ticker
source:
  type: dimension
  model: stocks
  dimension: dim_stock
  column: ticker
default: [AAPL, MSFT, GOOGL]
}
```

**Streamlit Widget**: `st.multiselect()`

**Source Types**:
- `dimension` - Load values from model dimension
- `static` - Hardcoded list of options
- `query` - Dynamic SQL query

---

### Single Select

```yaml
$filter${
type: single_select
label: Exchange
column: exchange_id
options: [NYSE, NASDAQ, AMEX]
default: NYSE
}
```

**Streamlit Widget**: `st.selectbox()`

---

### Number Range

```yaml
$filter${
type: number_range
label: Price Range
column: close
min: 0
max: 1000
step: 10
default:
  min: 50
  max: 500
}
```

**Streamlit Widget**: `st.slider()`

---

## Filter Context

**Purpose**: Inherit filters from parent folders

**File**: `app/notebook/filters/context.py`

**Pattern**: Place `.filter_context.yaml` in folder to apply filters to all notebooks in that folder

**Example**:
```
configs/notebooks/stocks/
├── .filter_context.yaml  # Applies to all notebooks in stocks/
├── price-analysis.md
└── volume-analysis.md
```

**.filter_context.yaml**:
```yaml
filters:
  - type: date_range
    label: Date Range
    column: trade_date
    default:
      start: 2024-01-01
      end: 2024-12-31

  - type: multi_select
    label: Tickers
    column: ticker
    source:
      type: dimension
      model: stocks
      dimension: dim_stock
      column: ticker
```

**Benefits**:
- DRY (Don't Repeat Yourself) - define common filters once
- Consistency across related notebooks
- Easy to update filters for entire section

---

## Filter State Management

**File**: `app/notebook/filters/engine.py`

Streamlit session state stores current filter values:

```python
# Initialize filter state
if 'filters' not in st.session_state:
    st.session_state.filters = {}

# Store filter value
st.session_state.filters['ticker'] = ['AAPL', 'MSFT']
st.session_state.filters['trade_date'] = {
    'start': '2024-01-01',
    'end': '2024-12-31'
}
```

---

## Filter Application Flow

```
1. User interacts with filter widget
   ↓
2. Widget value stored in st.session_state.filters
   ↓
3. Notebook queries data with filters
   ↓
4. FilterEngine converts filter state to SQL WHERE clause
   ↓
5. Query executed with filters
   ↓
6. Filtered data rendered in exhibits
```

---

## Dynamic Filter Source

**Purpose**: Load filter options from model dimensions

**Example**:
```python
# Load ticker options from dim_stock
source = {
    'type': 'dimension',
    'model': 'stocks',
    'dimension': 'dim_stock',
    'column': 'ticker'
}

options = load_filter_options(source)
# ['AAPL', 'MSFT', 'GOOGL', ...]

# Render multi-select
selected = st.multiselect('Select Tickers', options=options)
```

---

## Filter Widget Rendering

**File**: `app/notebook/ui/` (Streamlit components)

```python
def render_date_range_filter(filter_config):
    """Render date range filter widget."""
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            f"{filter_config['label']} (Start)",
            value=filter_config['default']['start']
        )

    with col2:
        end_date = st.date_input(
            f"{filter_config['label']} (End)",
            value=filter_config['default']['end']
        )

    return {'start': start_date, 'end': end_date}
```

---

## Filter Query Integration

Filters are passed to UniversalSession queries:

```python
# Get filter state
filters = st.session_state.filters

# Build filter dict for query
query_filters = {
    'ticker': filters.get('ticker', []),
    'trade_date': {
        'gte': filters.get('trade_date', {}).get('start'),
        'lte': filters.get('trade_date', {}).get('end')
    }
}

# Execute query with filters
df = session.query("""
    SELECT * FROM stocks.fact_stock_prices
    WHERE ticker IN :ticker
      AND trade_date BETWEEN :start_date AND :end_date
""", filters=query_filters)
```

---

## Related Documentation

- [Notebook System](notebook-system.md) - Filter integration in notebooks
- [NotebookParser](notebook-parser.md) - Parsing filter syntax
- [Exhibits](exhibits.md) - How filters affect visualizations
- [Core FilterEngine](../01-core-components/filter-engine.md) - Backend filter application
