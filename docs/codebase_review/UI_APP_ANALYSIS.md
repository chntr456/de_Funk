# de_Funk Application & UI Layer Analysis

## Executive Summary

The de_Funk application is a **professional analytics platform** built on Streamlit with a sophisticated multi-layer architecture. It enables users to explore dimensional models through **interactive markdown-based notebooks** with dynamic filters and visualizations. The system uses a **two-tier data flow**:

1. **Data Pipeline** (scripts + orchestration): API → Bronze (raw) → Silver (dimensional models) → Storage
2. **UI Pipeline** (app + notebooks): User filters → Data queries → Exhibit rendering → Browser display

The application is **well-structured** but has **some opportunities for consolidation** and simplification.

---

## 1. APPLICATION ARCHITECTURE OVERVIEW

### 1.1 High-Level Structure

```
de_Funk/
├── app/                          # UI and notebook system
│   ├── ui/                       # Streamlit UI layer
│   │   ├── notebook_app_duckdb.py    # Main entry point (DuckDB backend)
│   │   └── components/               # Reusable UI components
│   ├── notebook/                 # Notebook parsing & management
│   │   ├── parsers/              # Markdown/YAML parsing
│   │   ├── managers/             # Notebook lifecycle
│   │   ├── filters/              # Filter context & engine
│   │   ├── exhibits/             # Exhibit rendering framework
│   │   └── schema.py             # Data structures
│   └── services/                 # Business logic (simplified)
│
├── models/                       # Domain models & sessions
│   ├── api/                      # High-level APIs
│   │   ├── session.py            # UniversalSession (cross-model access)
│   │   ├── graph.py              # Model dependency graph
│   │   └── dal.py                # Storage routing
│   ├── base/                     # BaseModel foundation
│   ├── builders/                 # Model construction utilities
│   ├── measures/                 # Measure calculation framework
│   └── implemented/              # Domain models (equity, corporate, etc.)
│
├── core/                         # Core infrastructure
│   ├── context.py                # RepoContext (config + connection)
│   ├── session/                  # Session management
│   │   └── filters.py            # Backend-agnostic filters
│   └── config/                   # Configuration system
│
├── orchestration/                # Pipeline orchestration
│   ├── orchestrator.py           # Main orchestrator
│   ├── common/                   # Shared utilities
│   └── pipelines/                # Pipeline definitions
│
├── scripts/                      # Operational scripts (27 total)
│   ├── build_all_models.py      # Build all Silver layers
│   ├── rebuild_model.py          # Rebuild single model
│   ├── run_forecasts.py          # Generate forecasts
│   ├── test_*.py                 # Testing scripts
│   └── ...
│
├── run_app.py                    # UI launcher (Streamlit)
└── run_full_pipeline.py          # Full ETL orchestration
```

### 1.2 Key Technologies

**Backend:**
- **DuckDB** (primary) - 10-100x faster than Spark for interactive queries
- **Spark** (optional) - For large-scale batch processing
- **Streamlit** - Web UI framework
- **Plotly** - Interactive visualizations

**Storage:**
- **Parquet** (Bronze/Silver) - Columnar data format
- **DuckDB catalog** - Metadata and query workspace

**Configuration:**
- **YAML** - Model definitions
- **JSON** - API endpoints and storage mappings
- **Python dataclasses** - Type-safe config models

---

## 2. NOTEBOOK SYSTEM

### 2.1 Notebook Architecture

The notebook system is the **core user-facing feature**. Users interact with markdown-based notebooks that combine:

- **Markdown content** - Analysis text, insights, explanations
- **Filter definitions** - `$filter${...}` blocks for user inputs
- **Exhibits** - `$exhibits${...}` blocks for visualizations
- **Folder contexts** - Shared filters across notebook families

### 2.2 Notebook Parsing Pipeline

```
Markdown File (*.md)
    ↓
[MarkdownNotebookParser]
    ↓ (regex extraction)
Front Matter (YAML metadata)
    ├→ id, title, description, models, author, created
    │
Filters Section (YAML blocks)
    ├→ date_range, multi_select, single_select filters
    │
Exhibits (YAML blocks in markdown)
    ├→ metric_cards, line_chart, bar_chart, data_table, etc.
    │
Content Blocks (markdown + exhibits interspersed)
    ↓
[NotebookConfig] data structure
    ├→ _content_blocks: List of markdown and exhibit blocks
    ├→ _is_markdown: True (markdown format flag)
    ├→ variables: Dict[str, Variable]
    └→ exhibits: List[Exhibit]
```

### 2.3 Notebook Manager

**File:** `/home/user/de_Funk/app/notebook/managers/notebook_manager.py`

**Responsibilities:**
- Load and parse markdown notebooks
- Manage notebook state and filter context
- Prepare exhibit data for rendering
- Delegate queries to UniversalSession
- Handle folder-based filter contexts

**Key Features:**
- Only markdown format supported (YAML deprecated)
- Lazy loading of notebook content
- Folder-scoped filter contexts via `.filter_context.yaml`
- Session injection for cross-model queries

```python
# Usage pattern
notebook_manager = NotebookManager(
    universal_session=session,
    repo_root=repo_root,
    notebooks_root=notebooks_root
)

config = notebook_manager.load_notebook("path/to/notebook.md")
# Config now has parsed filters, exhibits, and content blocks
```

### 2.4 Filter System

**Architecture:**
```
User Filter Input (UI widget)
    ↓ (Streamlit session state)
[FilterContext] - Stores current filter values
    ↓
[FilterEngine] - Applies filters to DataFrames
    ├→ Support for DuckDB and Spark
    ├→ Backend-agnostic implementation
    └→ Supports: date_range, multi_select, single_select, number, text
    ↓
Filtered Data → Exhibit Rendering
```

**Filter Types:**
1. **date_range** - Start/end dates with presets (-30d, today, etc.)
2. **multi_select** - Multiple values (e.g., ticker list)
3. **single_select** - One value from options
4. **slider** - Numeric range with min/max
5. **text** - Free-form text input
6. **number** - Numeric input

**Dynamic Filter Options:**
- Options loaded from database queries
- Source: `{model: equity, table: fact_equity_prices, column: ticker}`
- Cached for 5 minutes with Streamlit `@st.cache_data(ttl=300)`

**Folder-Scoped Contexts:**
- `.filter_context.yaml` files in notebook folders
- Filters shared by all notebooks in folder
- Isolated across folders (different filter sets per folder)

### 2.5 Exhibit System

**Core Exhibit Types:**

1. **Metric Cards** - Summary KPIs with values and comparisons
2. **Line Chart** - Time series with multiple series
3. **Bar Chart** - Categorical aggregations
4. **Data Table** - Sortable, paginated data display
5. **Weighted Aggregate Chart** - Multi-stock weighted indices
6. **Forecast Chart** - Actual vs predicted with confidence bounds
7. **Scatter/Heatmap** - Advanced visualizations (framework ready)

**Exhibit Configuration Example:**
```yaml
type: line_chart
source: equity.fact_equity_prices
x: trade_date
y: close
color: ticker
title: Stock Price Trends
measure_selector:
  available_measures: [open, close, high, low, volume_weighted]
  default_measures: [close]
dimension_selector:
  available_dimensions: [ticker, sector]
  applies_to: color
interactive: true
collapsible: true
```

**Exhibit Rendering Flow:**
```
Exhibit Config
    ↓
[Exhibit Type Renderer] (e.g., LineChartRenderer)
    ├→ Load data via UniversalSession
    ├→ Apply filters from FilterContext
    ├→ Process measure/dimension selectors
    ├→ Transform to Plotly figure
    │
Plotly Figure
    ↓
[Streamlit Component]
    ├→ Render title & description
    ├→ Show selector UI (measure, dimension)
    ├→ Display interactive chart
    └→ Handle click events (cross-filtering)
```

**Dynamic Selectors:**

1. **Measure Selector** - Choose which metrics to display
   - Checkbox, multiselect, or radio UI
   - Updates chart y-axes dynamically
   
2. **Dimension Selector** - Choose grouping/coloring dimension
   - Radio or selectbox UI
   - Updates chart color_by or group_by

---

## 3. UI COMPONENTS & STREAMLIT APPLICATION

### 3.1 Main Application Entry Point

**File:** `/home/user/de_Funk/app/ui/notebook_app_duckdb.py`

**Key Responsibilities:**
1. Initialize session state (repo context, model registry, sessions)
2. Render page layout (header, sidebar, main content)
3. Manage open notebooks as tabs
4. Coordinate filter sidebar with main content

**Session State Management:**
```python
st.session_state.open_tabs          # List of open notebook tabs
st.session_state.active_tab         # Currently active notebook
st.session_state.edit_mode          # Per-notebook edit mode toggle
st.session_state.theme              # 'dark' or 'light' theme
st.session_state.repo_context       # RepoContext instance
st.session_state.model_registry     # Model registry
st.session_state.universal_session  # Cross-model session
st.session_state.notebook_manager   # Notebook manager
```

**Layout Structure:**
```
┌─────────────────────────────────────────────────┐
│  ✏️ Edit | 🔍 Filters | 🌙 Theme              │ (toolbar)
├──────────────────────────────────────────────────┤
│  Notebook1  Notebook2  Notebook3  + More...    │ (tabs)
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐      ┌──────────────────────┐ │
│  │ SIDEBAR      │      │   MAIN CONTENT       │ │
│  │              │      │                      │ │
│  │ 📚 Notebooks │      │  #### Heading        │ │
│  │ ├─ Folder1   │      │                      │ │
│  │ │ ├─ Note1   │      │  $filter${...}      │ │
│  │ │ └─ Note2   │      │                      │ │
│  │ │            │      │  Markdown content    │ │
│  │ ├─ Folder2   │      │                      │ │
│  │ │ └─ Note3   │      │  $exhibits${...}    │ │
│  │ │            │      │                      │ │
│  │ 🎛️ Filters   │      │ [Chart visualization]│
│  │ ├─ Date      │      │                      │ │
│  │ ├─ Ticker    │      │ More markdown...     │ │
│  │ └─ Volume    │      │                      │ │
│  │              │      │ [Table or other]    │ │
│  │ 🔗 Model     │      │                      │ │
│  │    Graph     │      │                      │ │
│  └──────────────┘      └──────────────────────┘ │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 3.2 UI Components

**Sidebar Navigator** (`app/ui/components/sidebar.py`)
- Scans for markdown notebooks
- Groups by directory
- Renders clickable items
- Opens notebooks as new tabs
- Shows model graph metrics

**Filter Components** (`app/ui/components/filters.py`)
- Renders UI widgets for each filter type
- Caches dynamic options from database
- Manages Streamlit widget keys
- Clears filter state on folder change

**Notebook View** (`app/ui/components/notebook_view.py`)
- Routes between markdown and YAML rendering
- Dispatches exhibits to appropriate renderers
- Handles layout sections

**Exhibit Renderers** (`app/ui/components/exhibits/`)
- `line_chart.py` - Line charts with Plotly
- `bar_chart.py` - Bar charts
- `data_table.py` - Sortable/paginated tables
- `metric_cards.py` - KPI summary cards
- `forecast_chart.py` - Actual vs predicted
- `weighted_aggregate_chart_model.py` - Index charts
- `measure_selector.py` - Dynamic measure selection UI
- `dimension_selector.py` - Dynamic dimension selection UI
- `base_renderer.py` - Common renderer functionality

**Markdown Renderer** (`app/ui/components/markdown_renderer.py`)
- Renders markdown content inline
- Embeds exhibits within content
- Supports `<details>` collapsible sections
- Maintains reading flow

### 3.3 Exhibit Rendering Pipeline

```
Exhibit Config (YAML in markdown)
    ↓
[Exhibit Type Detection]
    ├→ metric_cards, line_chart, bar_chart, etc.
    │
[Exhibit Renderer Class]
    ├→ Load data via UniversalSession
    │   └→ session.get_table(model, table)
    ├→ Apply filters via FilterContext
    │   └→ FilterEngine.apply_filters(df, filters)
    ├→ Render measure/dimension selectors
    │   ├→ Let user choose metrics to show
    │   └→ Let user choose dimension for coloring
    ├→ Transform data for visualization
    │   ├→ Group by x/color dimensions
    │   ├→ Aggregate measures
    │   └→ Format for Plotly
    │
[Plotly Figure]
    ├→ Create figure with plotly.express or go
    ├→ Add interactivity (hover, click, range slider)
    ├→ Style with custom theme
    │
[Streamlit Component]
    └→ st.plotly_chart() or st.dataframe()
```

**Example: Line Chart Rendering**

```python
# 1. Load exhibit config
exhibit = notebook_config.exhibits["price_trends"]

# 2. Get data
df = session.get_table("equity", "fact_equity_prices")

# 3. Apply filters
df = FilterEngine.apply_filters(df, filter_context)

# 4. Render selectors
selected_measures = ["close", "volume_weighted"]
selected_dimension = "ticker"

# 5. Transform data
plot_df = df.groupby("trade_date")[selected_measures].agg("mean")

# 6. Create Plotly figure
fig = px.line(
    plot_df,
    x="trade_date",
    y=selected_measures,
    color=selected_dimension,
    title="Stock Price Trends"
)

# 7. Render
st.plotly_chart(fig, use_container_width=True)
```

---

## 4. DATA FLOW: User → UI → Models → Storage

### 4.1 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERACTION LAYER                          │
│                              (Streamlit UI)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User opens notebook  →  Opens notebook in new tab                      │
│      ↓                                                                    │
│  User adjusts filters →  Streamlit session_state updated               │
│      ↓                                                                    │
│  User clicks exhibit  →  Measure/dimension selector updates            │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                      NOTEBOOK MANAGEMENT LAYER                           │
│                   (app/notebook/ + app/ui/components/)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Notebook file (*.md)                                                   │
│      ↓                                                                    │
│  [MarkdownNotebookParser.parse_file]                                   │
│      ├→ Extract front matter → NotebookMetadata                        │
│      ├→ Extract filters → Dict[str, Variable]                          │
│      ├→ Extract exhibits → List[Exhibit]                               │
│      └→ Create content blocks → List[block]                            │
│      ↓                                                                    │
│  [NotebookConfig] data structure                                        │
│      ├→ Metadata, variables, exhibits, content blocks                  │
│      └→ _is_markdown=True, _filter_collection=None                     │
│      ↓                                                                    │
│  [NotebookManager]                                                       │
│      ├→ Manages notebook state                                          │
│      ├→ Loads folder context filters                                    │
│      └→ Delegates queries to UniversalSession                           │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                      FILTER APPLICATION LAYER                            │
│                        (app/notebook/filters/)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [FilterContext]                                                         │
│      ├→ Current filter values from UI                                  │
│      ├→ Filter definitions (type, operator, source)                    │
│      └→ Variables metadata                                              │
│      ↓                                                                    │
│  [FilterEngine.apply_filters]                                           │
│      ├→ For each filter variable:                                      │
│      │   ├→ Get current value from FilterContext                       │
│      │   ├→ Get variable definition (type, operator)                   │
│      │   └→ Apply appropriate SQL WHERE clause                         │
│      │       ├→ date_range: WHERE col BETWEEN ? AND ?                 │
│      │       ├→ multi_select: WHERE col IN (?, ?, ...)                │
│      │       ├→ single_select: WHERE col = ?                          │
│      │       └→ number/slider: WHERE col >= ? AND col <= ?            │
│      ├→ Support for both DuckDB and Spark                             │
│      └→ Push filters down to storage layer                            │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                     DATA ACCESS LAYER (Models)                           │
│                          (models/api/session.py)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [UniversalSession]                                                      │
│      ├→ Initialize with connection (DuckDB or Spark)                    │
│      ├→ Load model config from registry                                │
│      ├→ Instantiate model classes                                      │
│      ├→ Maintain model dependency graph                                │
│      └→ Cache loaded models                                            │
│      ↓                                                                    │
│  [UniversalSession.get_table()]                                         │
│      ├→ Load model (lazy, cached)                                      │
│      ├→ Get table from model                                           │
│      ├→ Auto-join if missing columns (via model graph)                 │
│      ├→ Aggregate if group_by specified                               │
│      ├→ Apply filters (DuckDB or Spark)                                │
│      └→ Return DataFrame (pandas via to_pandas)                        │
│      ↓                                                                    │
│  [BaseModel instance]                                                    │
│      ├→ Loads YAML config (schema, measures, graph)                    │
│      ├→ Has table registry (dimensions, facts)                         │
│      ├→ Can build/rebuild model from Bronze                            │
│      └→ Caches tables in memory                                        │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                      STORAGE LAYER (Files)                               │
│                   (storage/bronze/ + storage/silver/)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Bronze Layer (Raw Data)                                                │
│  ├─ storage/bronze/polygon/                                             │
│  │  ├─ prices/date=2024-01-01/.../*.parquet                           │
│  │  ├─ companies/.../*.parquet                                          │
│  │  └─ ...                                                               │
│  │                                                                        │
│  Silver Layer (Dimensional Models)                                      │
│  ├─ storage/silver/equity/                                              │
│  │  ├─ dim_equity/.../*.parquet                                        │
│  │  ├─ fact_equity_prices/date=2024-01-01/.../*.parquet              │
│  │  └─ ...                                                               │
│  │                                                                        │
│  DuckDB Catalog                                                          │
│  └─ storage/duckdb/analytics.db                                         │
│     ├─ Metadata and schema information                                  │
│     ├─ Views and registered tables                                      │
│     └─ Query workspace (does NOT duplicate data)                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Query Example: From User Filter to Result

**Scenario:** User opens "Stock Analysis" notebook and filters for AAPL prices in Jan 2024

```
1. User Action
   - Sidebar: Select "AAPL" in ticker filter
   - Sidebar: Set date range to 2024-01-01 to 2024-01-31
   - Filter context updates in st.session_state

2. Notebook Rendering (Streamlit re-run triggered)
   - Load NotebookConfig from markdown
   - Render filters from filter context
   - Render exhibits

3. Exhibit Rendering: Line Chart (Price Trends)
   
   a) Config says: source="equity.fact_equity_prices"
   
   b) Load data:
      df = session.get_table("equity", "fact_equity_prices")
      # Returns all rows from parquet file
      # Columns: ticker, trade_date, open, close, high, low, volume
   
   c) Apply filters:
      filters = {
          "ticker": ["AAPL"],  # from filter context
          "trade_date": {"start": "2024-01-01", "end": "2024-01-31"}
      }
      df_filtered = FilterEngine.apply_filters(df, filters)
      # SQL equivalent:
      # WHERE ticker IN ('AAPL')
      #   AND trade_date >= '2024-01-01'
      #   AND trade_date <= '2024-01-31'
   
   d) Transform for visualization:
      - X axis: trade_date
      - Y axis: close (selected measure)
      - Color by: ticker (only AAPL, so one line)
      - Result: 21 rows (trading days in Jan) with date/close pairs
   
   e) Create Plotly figure:
      fig = px.line(
          df_filtered,
          x="trade_date",
          y="close",
          title="Daily Closing Prices"
      )
   
   f) Render in Streamlit:
      st.plotly_chart(fig, use_container_width=True)

4. Result in Browser
   - Interactive line chart showing AAPL price for Jan 2024
   - Hover to see exact values
   - Range selector to zoom
```

### 4.3 Connection Types

**DuckDB (Default - Recommended)**
```python
# Instant startup, 10-100x faster queries
from models.api.session import UniversalSession

session = UniversalSession(
    connection=duckdb.connect("storage/duckdb/analytics.db"),
    storage_cfg=storage_cfg,
    repo_root=repo_root
)
```

**Spark (Optional - For large data)**
```python
# Powerful but slower startup (~15s), good for batch processing
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("de_Funk") \
    .getOrCreate()

session = UniversalSession(
    connection=spark,
    storage_cfg=storage_cfg,
    repo_root=repo_root
)
```

---

## 5. ORCHESTRATION & SCRIPTS ECOSYSTEM

### 5.1 Orchestration Flow

**File:** `/home/user/de_Funk/orchestration/orchestrator.py`

The orchestrator coordinates the complete ETL pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│              run_full_pipeline.py (Main Entry)              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  STEP 1: Build Calendar Dimension (Core Model)            │
│  └─ create_calendar_table()                               │
│     └─ storage/bronze/calendar_seed/*.parquet            │
│                                                              │
│  STEP 2: Ingest Company Data (Bronze Layer)               │
│  └─ CompanyPolygonIngestor.run_all()                     │
│     ├─ Query Polygon API for top N companies             │
│     ├─ Fetch prices, company info, news                  │
│     └─ Write to storage/bronze/polygon/.../*parquet      │
│                                                              │
│  STEP 3: Build Company Model (Silver Layer)               │
│  └─ CompanyModel.build() + write_tables()                │
│     ├─ Load Bronze data (raw prices, company info)       │
│     ├─ Build dimensions (dim_company, dim_exchange)      │
│     ├─ Build facts (fact_prices, fact_news)              │
│     └─ Write to storage/silver/equity/.../*parquet       │
│                                                              │
│  STEP 4: Generate Forecasts (Forecast Model)             │
│  └─ run_forecast_model()                                 │
│     ├─ For each ticker (top 100 by market cap)          │
│     ├─ Run ARIMA/Prophet on historical prices           │
│     └─ Write predictions to Silver                       │
│                                                              │
│  STEP 5: Build Other Models                              │
│  └─ run_macro_model(), run_city_finance_model()         │
│     ├─ Similar pattern: Bronze → Silver                 │
│     └─ Write to storage/silver/{model}/.../*parquet     │
│                                                              │
│  STEP 6: Launch UI                                       │
│  └─ subprocess.run(["streamlit", "run", ...])           │
│     └─ Browser opens to http://localhost:8501          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Main Scripts

**Entry Points:**

| Script | Purpose | Output |
|--------|---------|--------|
| `run_app.py` | Launch Streamlit UI | Browser at localhost:8501 |
| `run_full_pipeline.py` | Complete ETL (API→Silver→UI) | All storage layers + app |

**Build & Management:**

| Script | Purpose | Triggered By |
|--------|---------|--------------|
| `build_all_models.py` | Build all Silver layer models | Manual or post-ingestion |
| `rebuild_model.py` | Rebuild single model | Development, testing |
| `reset_model.py` | Clear model data | Data reset |
| `clear_and_refresh.py` | Clear cache + rebuild | Full refresh |

**Data Operations:**

| Script | Purpose |
|--------|---------|
| `run_forecasts.py` | Generate ARIMA/Prophet forecasts |
| `run_company_data_pipeline.py` | Ingest company data from Polygon |
| `reingest_exchanges.py` | Re-ingest exchange data |
| `verify_cross_model_edges.py` | Validate model relationships |

**Testing:**

| Script | Purpose |
|--------|---------|
| `test_all_models.py` | Test all model implementations |
| `test_pipeline_e2e.py` | End-to-end pipeline test |
| `test_domain_model_integration_duckdb.py` | DuckDB backend tests |
| `test_domain_model_integration_spark.py` | Spark backend tests |
| `test_ui_integration.py` | UI system tests |

**Utility Scripts:**

| Script | Purpose |
|--------|---------|
| `migrate_to_delta.py` | Convert Parquet to Delta format |
| `investigate_ticker_count.py` | Analyze data coverage |
| `validate_migration.py` | Verify data integrity |
| `verify_ticker_count.py` | Check ticker statistics |

### 5.3 Script Execution Pattern

Modern scripts use `python -m` module syntax for better import handling:

```bash
# Old pattern (still works)
python scripts/test_all_models.py

# New pattern (recommended)
python -m scripts.test_all_models

# With arguments
python -m scripts.rebuild_model --model equity --skip-ingestion
```

---

## 6. KEY INTEGRATION POINTS

### 6.1 RepoContext - The Glue

**File:** `/home/user/de_Funk/core/context.py`

Central configuration object that ties everything together:

```python
class RepoContext:
    """Central context for repo, connection, config."""
    repo: Path                    # Repository root
    connection: DuckDB/Spark      # Database connection
    config: AppConfig             # Type-safe config
    storage_cfg: Dict             # Storage paths
    polygon_cfg: Dict             # Polygon API config
    bls_cfg: Dict                 # BLS API config
    
    @classmethod
    def from_repo_root(
        cls,
        connection_type="duckdb"
    ) -> RepoContext:
        """Auto-discover config and create context."""
```

**Usage:**
```python
# In notebook_app_duckdb.py
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Access everything from one object
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage_cfg,
    repo_root=ctx.repo
)
```

### 6.2 Model Registry - Dynamic Discovery

**File:** `/home/user/de_Funk/models/registry.py`

Auto-discovers and loads models from YAML configs:

```python
registry = ModelRegistry(models_dir="configs/models")

# Get config (YAML)
config = registry.get_model_config("equity")

# Get class (Python)
model_class = registry.get_model_class("equity")
# Falls back to BaseModel if no custom class
```

**Model Dependency Graph:**
```
Tier 0 (Foundation):
  └─ core (calendar dimension)

Tier 1 (Independent):
  ├─ equity (securities)
  ├─ corporate (companies)
  └─ macro (economic indicators)

Tier 2 (Dependent):
  ├─ etf (depends: equity)
  └─ forecast (depends: equity)

Tier 3 (Advanced):
  └─ city_finance (municipal data)
```

### 6.3 Model Graph - Relationship Mapping

**File:** `/home/user/de_Funk/models/api/graph.py`

Maps relationships between model tables:

```
EquityModel
├─ dim_equity (ticker, company, exchange)
├─ fact_equity_prices (ticker_date granularity)
└─ Graph edges:
   ├─ fact_equity_prices.ticker → dim_equity.ticker
   ├─ dim_equity.company_id → corporate.dim_company.id
   └─ fact_equity_prices.trade_date → core.dim_calendar.date

CorporateModel
├─ dim_company (company details)
├─ fact_company_fundamentals (quarterly financials)
└─ Graph edges:
   ├─ fact_company_fundamentals.company_id → dim_company.id
   └─ fact_company_fundamentals.period_end → core.dim_calendar.date
```

**Auto-Join Logic:**
- User requests columns not in base table
- System queries graph for join paths
- Auto-joins through relationships
- Transparent to user

### 6.4 Configuration System

**Files:**
- `/home/user/de_Funk/config/loader.py` - ConfigLoader
- `/home/user/de_Funk/config/models.py` - Type-safe dataclasses
- `/home/user/de_Funk/config/constants.py` - Defaults

**Configuration Precedence:**
1. Environment variables (`.env` file)
2. Explicit parameters (passed to loader)
3. Configuration files (JSON/YAML in `configs/`)
4. Default values

**Example:**
```python
from config import ConfigLoader

loader = ConfigLoader()
config = loader.load(connection_type="duckdb")

# Type-safe access
print(config.connection.type)       # "duckdb"
print(config.storage["roots"]["silver"])  # "storage/silver"
print(config.apis.get("polygon"))   # API config dict
```

---

## 7. COMPLEXITY ANALYSIS & CONSOLIDATION OPPORTUNITIES

### 7.1 What's Working Well ✅

1. **Clean Separation of Concerns**
   - App layer (Streamlit UI)
   - Notebook system (parsing, management, rendering)
   - Data layer (models, sessions, storage)
   - Orchestration (scripts, pipelines)

2. **Flexible Architecture**
   - Backend-agnostic (DuckDB, Spark)
   - Model-agnostic (any domain with YAML config)
   - Exhibit-extensible (add new visualization types)

3. **Strong Type Safety**
   - Dataclass models for all configs
   - Type hints throughout
   - Schema validation

4. **Good Documentation**
   - CLAUDE.md is comprehensive
   - Examples and notebooks demonstrate usage
   - Clear code organization

### 7.2 Areas of Complexity

#### 7.2.1 **Exhibit Rendering Split**

**Problem:**
- Exhibit logic split between TWO modules:
  1. `app/notebook/exhibits/` - Base classes (rarely used)
  2. `app/ui/components/exhibits/` - Actual Streamlit renderers (workhorse)

**Current Structure:**
```
app/notebook/exhibits/
├─ base.py (BaseExhibit abstract class)
├─ charts.py (empty placeholder)
├─ renderer.py (ExhibitRenderer stub)
├─ metrics.py (empty)
├─ tables.py (empty)
└─ layout.py (empty)

app/ui/components/exhibits/
├─ base_renderer.py (BaseExhibitRenderer - does actual work!)
├─ line_chart.py (render_line_chart function)
├─ bar_chart.py (render_bar_chart function)
├─ metric_cards.py
├─ forecast_chart.py
├─ measure_selector.py
├─ dimension_selector.py
└─ weighted_aggregate_chart_model.py
```

**Issue:** Users must understand that actual exhibit logic is in `app/ui/components/exhibits/`, not `app/notebook/exhibits/`

**Opportunity:**
- Consolidate all exhibit rendering into single `app/notebook/exhibits/` module
- Move UI-specific logic to `app/ui/components/` (theme, layout)
- Clear separation: exhibit logic vs UI presentation

#### 7.2.2 **Notebook Module Structure**

**Current:**
```
app/notebook/
├─ managers/
│  └─ notebook_manager.py (notebook lifecycle)
├─ parsers/
│  ├─ markdown_parser.py
│  ├─ yaml_parser.py (deprecated)
│  └─ __init__.py
├─ filters/
│  ├─ context.py (FilterContext)
│  ├─ dynamic.py (FilterConfig types)
│  ├─ engine.py (FilterEngine)
│  ├─ types.py (FilterOperator)
│  └─ __init__.py
├─ exhibits/
│  ├─ base.py (mostly empty)
│  └─ ... (other empty files)
├─ api/
│  └─ notebook_session.py (legacy, not used?)
├─ schema.py (large, 350+ lines)
├─ folder_context.py
└─ markdown_parser_filter_helpers.py
```

**Issues:**
- Too many sub-modules (filters/ has 4 files for what could be 1-2)
- schema.py is huge (should be split)
- Some legacy code (YAML parser, NotebookSession)
- Unclear module boundaries

**Opportunity:**
- Consolidate filters/ into 2-3 focused files
- Split schema.py by concern (notebook, filters, exhibits, variables)
- Remove deprecated YAML parser and NotebookSession
- Clarify public API in `__init__.py` files

#### 7.2.3 **Scripts Ecosystem**

**Problem:**
- 27 operational scripts in `/scripts/` directory
- Mix of concerns: build, test, debug, utility, migration
- Naming inconsistent (build_all_models.py vs rebuild_model.py)
- Some scripts very large (600+ lines)
- Difficult to discover what exists

**Current Structure:**
```
scripts/
├─ build_all_models.py (600+ lines) - Build all Silver
├─ build_silver_layer.py - Wrapper for build?
├─ rebuild_model.py (400+ lines) - Rebuild single model
├─ reset_model.py - Reset single model
├─ run_full_pipeline.py - Full ETL (not in scripts/)
├─ run_forecasts.py - Generate forecasts
├─ test_all_models.py (300+ lines) - Test script
├─ test_pipeline_e2e.py (600+ lines) - E2E test
├─ test_*.py - Many test scripts
├─ migrate_to_delta.py - Schema migration
├─ validate_migration.py - Validation utility
├─ verify_*.py - Various verification scripts
└─ examples/ - Code examples

Total: 27 scripts, ~4000+ lines of code
```

**Opportunities:**
- Create CLI tool (e.g., `python -m de_funk` with subcommands)
  ```bash
  python -m de_funk build --model equity
  python -m de_funk test --suite integration
  python -m de_funk migrate --format delta
  ```
- Move tests to proper test framework (pytest structure)
- Group related scripts into modules:
  - `scripts/build/` - build_all, rebuild, reset
  - `scripts/data/` - ingest, migrate, validate
  - `scripts/test/` - test scripts
  - `scripts/util/` - verification, analysis

#### 7.2.4 **Services Layer**

**Current:**
```
app/services/
├─ notebook_service.py (200+ lines, mostly unused)
├─ storage_service.py (legacy)
└─ __init__.py
```

**Problem:**
- `NotebookService` exists but isn't used (app uses `NotebookManager` instead)
- `storage_service.py` is legacy (superseded by `UniversalSession`)
- Unclear what services are actually live vs deprecated

**Opportunity:**
- Remove unused services
- Or consolidate into proper service layer if needed
- For now: just document what's active

#### 7.2.5 **Session/Connection Abstraction**

**Current:**
```
core/session/filters.py       # Backend-agnostic filters
models/api/session.py         # UniversalSession
models/api/dal.py             # StorageRouter
core/context.py               # RepoContext
```

**Problem:**
- Multiple layers of abstraction doing similar things
- Unclear which is the "real" session object
- Two different session concepts (RepoContext, UniversalSession)

**Opportunity:**
- Document the abstraction clearly
- Consider consolidating RepoContext into UniversalSession
- Or make RepoContext factory for sessions

### 7.3 Recommended Consolidations

**Priority 1 (High Value, Low Risk):**

1. **Consolidate Exhibit Rendering** (2-3 days)
   - Move all renderers from `app/ui/components/exhibits/` → `app/notebook/exhibits/`
   - Keep theme/layout in UI components
   - Clear separation: logic vs presentation

2. **Clean Up Filters Module** (1-2 days)
   - Consolidate `filters/` from 4 files → 2 files
     - `context.py` (FilterContext, filter state)
     - `engine.py` (FilterEngine, apply_filters logic)
   - Move types into context
   - Remove dynamic.py if unused

3. **Remove Dead Code** (1 day)
   - Remove `app/services/notebook_service.py` (unused)
   - Remove `app/services/storage_service.py` (legacy)
   - Remove `app/notebook/api/notebook_session.py` (unused)
   - Remove deprecated YAML parser
   - Update tests

**Priority 2 (Medium Value, Medium Risk):**

4. **Create CLI Tool** (3-5 days)
   - Consolidate 27 scripts into `python -m de_funk` CLI
   - Subcommands: build, test, ingest, migrate, validate
   - Better discoverability and UX

5. **Split schema.py** (2 days)
   - Split 350+ line schema.py into:
     - `notebook_schema.py` (NotebookConfig, NotebookMetadata)
     - `filter_schema.py` (Variable, FilterConfig, etc.)
     - `exhibit_schema.py` (Exhibit, ExhibitType, etc.)
   - Clear module contracts

6. **Consolidate Sessions** (2-3 days)
   - Document abstraction layers clearly
   - Consider merging RepoContext into UniversalSession
   - Or create factory pattern for better separation

**Priority 3 (Nice to Have):**

7. **Exhibit Type Registry** (2 days)
   - Create registry for dynamic exhibit types
   - Enable plugins for custom exhibits
   - Better extensibility

8. **Notebook Version Migration** (2 days)
   - Create migration tool for notebook format changes
   - Version notebook configs in YAML

---

## 8. USER INTERACTION FLOWS

### 8.1 Typical User Journey

```
1. Start Application
   ↓
   python run_app.py
   ↓
   - Initialize RepoContext (config + connection)
   - Load ModelRegistry (discover models)
   - Create UniversalSession (cross-model access)
   - Create NotebookManager (notebook handling)
   - Launch Streamlit app
   ↓

2. User Opens Sidebar
   ↓
   - SidebarNavigator scans configs/notebooks/
   - Shows directory tree of available notebooks
   - User clicks notebook to open
   ↓

3. Notebook Opens in Tab
   ↓
   - NotebookManager.load_notebook(path)
   - MarkdownNotebookParser.parse_file(path)
   - Extract metadata, filters, exhibits, content
   - Create NotebookConfig object
   - Store in Streamlit session state
   ↓

4. Filters Rendered in Sidebar
   ↓
   - For each variable in NotebookConfig:
     - Determine variable type (date_range, select, etc.)
     - Render appropriate Streamlit widget
     - Load options from database if dynamic source
   - User adjusts filters
   - Streamlit session state updated
   ↓

5. Exhibits Rendered in Main Area
   ↓
   - For each exhibit in content blocks:
     a) Render markdown before exhibit
     b) Load exhibit data:
        - Call session.get_table(model, table)
        - Apply filters via FilterEngine
        - Transform data for visualization
     c) Render measure/dimension selectors
     d) Create and display Plotly chart
     e) Render markdown after exhibit
   ↓

6. User Interacts with Chart
   ↓
   - Hover: See data point values
   - Range select: Zoom into date range
   - Click: Cross-filter (if enabled)
   - Measure selector: Change metrics shown
   - Dimension selector: Change grouping
   ↓

7. UI Re-renders
   ↓
   - Streamlit detects state change
   - Re-runs script from top
   - Notebooks reloaded
   - Data re-queried with new filters
   - Charts re-rendered with new selections
   ↓

8. Switch Notebook
   ↓
   - Click different tab
   - Streamlit session state updates active_tab
   - Filters in sidebar refresh for new notebook
   - New notebook content renders
   ↓
```

### 8.2 Data Query Journey

```
User selects filter value
    ↓
Streamlit session_state updated
    ↓
App.py re-runs from top
    ↓
render_filters_section() reads session_state
    ↓
Exhibit renders
    ↓
Calls session.get_table("equity", "fact_equity_prices")
    ↓
UniversalSession.get_table()
    ├─ Check cache
    ├─ If not cached:
    │  └─ Call EquityModel.get_table()
    │     ├─ Check table cache
    │     ├─ If not cached:
    │     │  └─ Read from Parquet file
    │     │     storage/silver/equity/fact_equity_prices/
    │     └─ Cache in memory
    │
    └─ Return DataFrame
    ↓
Apply filters:
    FilterEngine.apply_filters(df, filter_context)
    ├─ For each filter:
    │  ├─ Get value from session state
    │  ├─ Get variable definition
    │  └─ Build WHERE clause
    │     e.g.: WHERE ticker IN ('AAPL') AND trade_date >= '2024-01-01'
    │
    └─ Return filtered DataFrame
    ↓
Transform for visualization:
    ├─ Group by x-axis dimension (trade_date)
    ├─ Aggregate measures (avg/sum/max/min of close)
    ├─ Prepare for Plotly
    │
    └─ Return transformation data
    ↓
Create Plotly figure:
    fig = px.line(data, x=date, y=close, ...)
    ↓
Render in Streamlit:
    st.plotly_chart(fig)
    ↓
Display in browser
```

---

## 9. PERFORMANCE CONSIDERATIONS

### 9.1 Caching Strategy

**Streamlit Caching:**
```python
# Filter options cached for 5 minutes
@st.cache_data(ttl=300)
def _get_distinct_values(_connection, _storage_service, ...):
    # Query database for unique values
    # Underscore prefix tells Streamlit not to hash parameter
    pass
```

**Model Caching:**
- Models loaded once in UniversalSession
- Tables cached in memory after first load
- Subsequent queries hit in-memory cache

**DuckDB Advantages:**
- 10-100x faster than Spark for interactive queries
- No JVM startup (~1s vs ~15s)
- Perfect for dashboard/notebook workloads
- In-process, no network overhead

### 9.2 Query Optimization

**Filter Pushdown:**
- Filters applied as early as possible
- Database applies WHERE before aggregation
- Reduces data transferred

**Lazy Loading:**
- Models loaded on demand
- Tables loaded on first query
- Only requested columns read

**Partitioning:**
- Silver tables partitioned by time (trade_date)
- Queries pruned to relevant partitions
- Scan only necessary files

---

## 10. SUMMARY & RECOMMENDATIONS

### Key Strengths
1. ✅ Clean layered architecture
2. ✅ Backend-agnostic design (DuckDB, Spark)
3. ✅ Type-safe throughout
4. ✅ Professional Streamlit UI
5. ✅ Flexible notebook system
6. ✅ Good documentation

### Key Weaknesses
1. ❌ Exhibit logic split across two modules
2. ❌ Filters module fragmented (4 files for simple concept)
3. ❌ 27 operational scripts hard to discover/maintain
4. ❌ Large monolithic files (schema.py, build_all_models.py)
5. ❌ Some dead code (services, parsers)
6. ❌ Multiple session/abstraction layers confusing

### Top 3 Quick Wins
1. **Consolidate exhibits** (1 day) - Move UI logic to central location
2. **Clean up filters** (1 day) - Reduce from 4 files to 2
3. **Remove dead code** (1 day) - Delete unused services and parsers

### Long-Term Improvements
1. **Create CLI tool** for scripts (3-5 days)
2. **Split schema.py** into focused modules (2 days)
3. **Refactor session layers** for clarity (2-3 days)

### For New Contributors
1. **Start with CLAUDE.md** - Good overview
2. **Explore notebooks first** - See user interaction
3. **Read notebook_app_duckdb.py** - Understand app structure
4. **Check examples/notebooks** - See feature patterns
5. **Models are key** - Understand BaseModel before filters/exhibits

---

## 11. TECHNICAL DEBT AUDIT

| Item | Severity | Effort | Impact |
|------|----------|--------|--------|
| Exhibit logic split | Medium | 2-3 days | Clarity |
| Filters module fragmented | Low | 1 day | Discoverability |
| 27 scripts | Medium | 3-5 days | Maintainability |
| Large monolithic files | Low | 2 days | Readability |
| Dead code | Low | 1 day | Cleanliness |
| Session abstraction unclear | Medium | 2-3 days | Clarity |
| **TOTAL** | | **11-16 days** | **Significant** |

All are relatively low-risk, incremental improvements that would make the codebase more maintainable without architectural changes.

