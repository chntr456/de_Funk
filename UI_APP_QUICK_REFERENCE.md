# de_Funk UI & App Layer - Quick Reference Guide

## At a Glance

**What is de_Funk?**
A low-code analytics platform where users build dimensional models in YAML and explore them through interactive Markdown notebooks with dynamic filters and visualizations.

**Tech Stack:**
- **UI:** Streamlit + Plotly
- **Backend:** DuckDB (primary) or Spark
- **Models:** Python classes with YAML config
- **Storage:** Parquet (Bronze/Silver) + DuckDB catalog

---

## Application Structure

```
User opens "Stock Analysis.md" notebook
         ↓
┌─────────────────────────────────────────────────┐
│  Streamlit Application (notebook_app_duckdb.py) │ ← run_app.py
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │    SIDEBAR       │  │   MAIN CONTENT   │   │
│  │                  │  │                  │   │
│  │ 📚 Notebooks     │  │  Markdown Text   │   │
│  │ ├─ Folder1       │  │                  │   │
│  │ │ └─ Stock       │  │  🎛️ Filters     │   │
│  │ │   Analysis.md  │  │  ├─ Date Range  │   │
│  │ │                │  │  ├─ Ticker List │   │
│  │ 🎛️ Filters       │  │  └─ Volume Min  │   │
│  │ ├─ 2024-01-01    │  │                  │   │
│  │ ├─ AAPL,MSFT,... │  │  📊 Exhibit 1   │   │
│  │ ├─ 1M+           │  │  ┌──────────────┐   │
│  │                  │  │  │ Line Chart   │   │
│  │ 🔗 Model Graph   │  │  │              │   │
│  └──────────────────┘  │  └──────────────┘   │
│                         │                     │
│                         │  📊 Exhibit 2      │
│                         │  ┌──────────────┐  │
│                         │  │ Data Table   │  │
│                         │  └──────────────┘  │
│                         │                     │
│                         └──────────────────────┘
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│     Notebook Processing Layer                   │
├─────────────────────────────────────────────────┤
│                                                 │
│ [MarkdownNotebookParser]  ← Extract YAML      │
│   ├→ front matter (title, models, author)     │
│   ├→ filters ($filter${...} blocks)           │
│   ├→ exhibits ($exhibits${...} blocks)        │
│   └→ markdown content                          │
│       ↓                                         │
│   [NotebookConfig]  ← Parsed notebook          │
│       ├→ metadata, filters, exhibits, content │
│       └→ _content_blocks (for inline render)  │
│       ↓                                         │
│   [NotebookManager]  ← Lifecycle               │
│       ├→ Load folder context filters           │
│       ├→ Create FilterContext                  │
│       └→ Delegate queries to UniversalSession │
│                                                 │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│     Filter & Query Processing                   │
├─────────────────────────────────────────────────┤
│                                                 │
│ User adjusts filters in sidebar                │
│   ↓                                             │
│ [FilterContext] ← Current filter values        │
│   ├→ trade_date: {start: 2024-01-01, ...}    │
│   ├→ ticker: ["AAPL", "MSFT"]                │
│   └→ volume: {operator: gte, value: 1M}      │
│   ↓                                             │
│ [FilterEngine.apply_filters]                   │
│   ├→ WHERE trade_date BETWEEN ? AND ?         │
│   ├→ AND ticker IN ('AAPL', 'MSFT')          │
│   └→ AND volume >= 1000000                    │
│   ↓ Filtered DataFrame                        │
│                                                 │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│     Data Access & Model Layer                   │
├─────────────────────────────────────────────────┤
│                                                 │
│ [UniversalSession]                             │
│   ├→ session.get_table("equity", "prices")   │
│   ├→ Load model (lazy, cached)                │
│   ├→ Query Parquet files                      │
│   └→ Return pandas DataFrame                   │
│   ↓                                             │
│ [Model Layers]                                 │
│   ├→ Equity Model                             │
│   │  ├─ dim_equity (ticker, company)          │
│   │  └─ fact_equity_prices (OHLCV + metrics) │
│   ├→ Corporate Model                          │
│   ├→ Macro Model                              │
│   └─ ... (other models)                       │
│   ↓                                             │
│ [Parquet Storage]                              │
│   ├→ storage/silver/equity/fact_prices        │
│   ├→ Partitioned by trade_date                │
│   └→ DuckDB handles schema & type inference   │
│                                                 │
└─────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────┐
│     Exhibit Rendering                           │
├─────────────────────────────────────────────────┤
│                                                 │
│ For each exhibit in notebook:                  │
│   1. Load config (type, source, axes)         │
│   2. Query data (get_table + filters)         │
│   3. Render selectors (measure, dimension)    │
│   4. Transform for visualization              │
│   5. Create Plotly figure                     │
│   6. Display in st.plotly_chart()             │
│   ↓                                             │
│ Rendered in Browser ✅                         │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Key Files Explained

### Entry Points
```
run_app.py
├─ Checks if running from repo root
├─ Validates Streamlit installation
└─ Launches: streamlit run app/ui/notebook_app_duckdb.py

run_full_pipeline.py
├─ Step 1: Build calendar dimension
├─ Step 2: Ingest company data from Polygon API
├─ Step 3: Build Silver layer models
├─ Step 4: Generate forecasts
└─ Step 6: Launch UI
```

### Core Application

| File | Purpose | Lines | Key Classes |
|------|---------|-------|------------|
| `app/ui/notebook_app_duckdb.py` | Main Streamlit app | 300 | NotebookVaultApp |
| `app/notebook/managers/notebook_manager.py` | Notebook lifecycle | 200 | NotebookManager |
| `app/notebook/parsers/markdown_parser.py` | Parse .md files | 400 | MarkdownNotebookParser |
| `app/notebook/schema.py` | Data structures | 350 | NotebookConfig, Exhibit, Variable |
| `app/notebook/filters/engine.py` | Apply filters | 300 | FilterEngine |
| `app/notebook/filters/context.py` | Filter state | 100 | FilterContext |
| `models/api/session.py` | Data access | 1062 | UniversalSession |
| `core/context.py` | Configuration | 200 | RepoContext |

### UI Components

| File | Purpose |
|------|---------|
| `app/ui/components/sidebar.py` | Notebook navigation |
| `app/ui/components/filters.py` | Filter widget rendering |
| `app/ui/components/notebook_view.py` | Main content routing |
| `app/ui/components/exhibits/base_renderer.py` | Common exhibit logic |
| `app/ui/components/exhibits/line_chart.py` | Line chart rendering |
| `app/ui/components/exhibits/bar_chart.py` | Bar chart rendering |
| `app/ui/components/exhibits/metric_cards.py` | KPI cards |
| `app/ui/components/exhibits/data_table.py` | Table rendering |
| `app/ui/components/exhibits/forecast_chart.py` | Forecast visualization |
| `app/ui/components/exhibits/weighted_aggregate_chart_model.py` | Index charts |
| `app/ui/components/exhibits/measure_selector.py` | Measure selection UI |
| `app/ui/components/exhibits/dimension_selector.py` | Dimension selection UI |

---

## Data Types & Enums

### Variable Types (Filters)
```python
class VariableType(Enum):
    DATE_RANGE = "date_range"       # Date picker with start/end
    MULTI_SELECT = "multi_select"   # Checkboxes or dropdown (multiple)
    SINGLE_SELECT = "single_select" # Radio or dropdown (one)
    NUMBER = "number"               # Numeric input
    TEXT = "text"                   # Text input
    BOOLEAN = "boolean"             # Checkbox
```

### Exhibit Types
```python
class ExhibitType(Enum):
    METRIC_CARDS = "metric_cards"                      # KPI summary
    LINE_CHART = "line_chart"                          # Time series
    BAR_CHART = "bar_chart"                            # Categories
    SCATTER_CHART = "scatter_chart"                    # X-Y plot
    DUAL_AXIS_CHART = "dual_axis_chart"               # Two Y axes
    HEATMAP = "heatmap"                               # Matrix
    DATA_TABLE = "data_table"                          # Sortable table
    PIVOT_TABLE = "pivot_table"                        # Pivoted table
    WEIGHTED_AGGREGATE_CHART = "weighted_aggregate_chart"  # Index
    FORECAST_CHART = "forecast_chart"                  # Actual + predicted
    FORECAST_METRICS_TABLE = "forecast_metrics_table"  # Forecast stats
    CUSTOM_COMPONENT = "custom_component"              # Plugin
```

---

## Filter Syntax

**In Markdown Notebook:**
```markdown
---
id: my_notebook
title: My Analysis
models: [equity, corporate]
---

# Date Range Filter
$filter${
  id: trade_date
  type: date_range
  label: Select Dates
  default: {start: "-30d", end: "today"}
  help_text: Choose date range for analysis
}

# Multi-Select with Database Values
$filter${
  id: ticker
  type: multi_select
  label: Stock Tickers
  source: {model: equity, table: fact_equity_prices, column: ticker}
  multi: true
  help_text: Select stocks to analyze
}

# Volume Slider
$filter${
  id: min_volume
  type: slider
  label: Minimum Trading Volume
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 0
  operator: gte
}
```

---

## Exhibit Syntax

**In Markdown Notebook:**
```markdown
## Price Trends

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Stock Prices Over Time
  measure_selector: {
    available_measures: [open, close, high, low],
    default_measures: [close],
    label: "Select Price Metrics"
  }
  interactive: true
  collapsible: true
}

## Top Stocks

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, trade_date, close, volume]
  sortable: true
  searchable: true
  pagination: true
  page_size: 20
}
```

---

## Folder Context (Shared Filters)

**In `configs/notebooks/my_folder/.filter_context.yaml`:**
```yaml
# Filters shared by all notebooks in this folder
filters:
  date_range:
    id: period
    type: date_range
    label: Analysis Period
    default: {start: "2024-01-01", end: "today"}
    
  ticker:
    id: companies
    type: multi_select
    label: Companies
    source: {model: equity, table: fact_equity_prices, column: ticker}
```

---

## Common Operations

### Opening a Notebook
```
1. Run: python run_app.py
2. Browser opens to http://localhost:8501
3. Click notebook in sidebar
4. Notebook opens in new tab
5. Adjust filters in sidebar
6. Exhibits update automatically
```

### Adding a New Notebook
```
1. Create file: configs/notebooks/my_analysis.md
2. Add YAML front matter with metadata
3. Add $filter${...} blocks for filters
4. Add $exhibits${...} blocks for visualizations
5. Save and refresh browser
6. Click notebook in sidebar to open
```

### Adding a New Filter
```
1. In notebook markdown, add:

$filter${
  id: my_filter_id
  type: [date_range|multi_select|number|...]
  label: User-Friendly Label
  source: {model: model_name, table: table_name, column: column_name}
  default: {value}
  help_text: Help text for users
}

2. Use in exhibits:
   - Filters automatically apply to all exhibits
   - Data filtered via FilterEngine
   - Results update in real-time
```

### Adding a New Visualization
```
1. In notebook markdown, add:

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: My Chart
}

2. Supported types: metric_cards, line_chart, bar_chart, 
   data_table, forecast_chart, weighted_aggregate_chart

3. Each exhibit loads data, applies filters, renders
```

---

## Module Dependency Map

```
notebook_app_duckdb.py
├─ RepoContext
│  ├─ ConfigLoader (config/loader.py)
│  └─ Connection (DuckDB)
├─ ModelRegistry (models/registry.py)
│  └─ BaseModel (models/base/model.py)
├─ UniversalSession (models/api/session.py)
│  ├─ ModelRegistry
│  ├─ ModelGraph (models/api/graph.py)
│  └─ FilterEngine (core/session/filters.py)
├─ NotebookManager (app/notebook/managers/notebook_manager.py)
│  ├─ MarkdownNotebookParser (app/notebook/parsers/markdown_parser.py)
│  ├─ NotebookConfig (app/notebook/schema.py)
│  ├─ FilterContext (app/notebook/filters/context.py)
│  └─ FolderFilterContextManager (app/notebook/folder_context.py)
├─ SidebarNavigator (app/ui/components/sidebar.py)
│  └─ NotebookManager
├─ render_filters_section() (app/ui/components/filters.py)
│  └─ FilterContext
└─ render_notebook_exhibits() (app/ui/components/notebook_view.py)
   ├─ Exhibit renderers (app/ui/components/exhibits/*.py)
   ├─ UniversalSession
   └─ FilterEngine
```

---

## Debugging Tips

**Notebook won't load?**
- Check markdown syntax: `$filter${...}` and `$exhibits${...}` must be exact
- Verify YAML in filter blocks is valid (check indentation)
- Use notebook_app_duckdb.py console for error messages

**Filters not appearing?**
- Confirm filters have `id:` field
- Check that source column exists in data
- Clear browser cache and refresh

**Exhibit shows no data?**
- Check source: `{model: X, table: Y}` exists
- Verify columns in exhibit config exist in data
- Check filters aren't too restrictive
- Look at browser console for SQL errors

**Performance slow?**
- DuckDB is fast; if slow, likely hitting database limit
- Check if data is too large for DuckDB (use Spark)
- Add partitioning to Silver layer tables
- Use columnar format (Parquet is good)

---

## See Also

- `UI_APP_ANALYSIS.md` - Full 1300-line technical analysis
- `CLAUDE.md` - Project overview and conventions
- `configs/notebooks/*.md` - Example notebooks
- `models/implemented/*/` - Example domain models
