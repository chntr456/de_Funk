# De_Funk Codebase Structure Analysis

## Executive Summary

The de_Funk project is a data analytics platform with a modern architecture consisting of:
- **Multi-model data pipelines** (Company, Forecast, BLS, Chicago, Polygon data sources)
- **Dual session management** systems (ModelSession, UniversalSession, NotebookSession)
- **Two UI implementations** (Spark-based and DuckDB-based notebooks)
- **Notebook-driven analytics** with markdown/YAML support

**Total Scope:** ~3000+ Python files, ~4 main application layers
**Key Challenge:** Three parallel session systems need consolidation per documented plan

---

## 1. Overall Project Structure

### Directory Tree (Top Level)

```
/home/user/de_Funk/
├── app/                      # Application layer (UIs, services)
├── core/                      # Core abstractions (connections, context)
├── datapipelines/            # Data ingestion pipelines
├── models/                    # Data models and sessions
├── orchestration/            # Spark/scheduling orchestration
├── configs/                   # Configuration files
├── storage/                   # Local storage layer
├── scripts/                   # Utility and pipeline scripts
├── docs/                      # Documentation
└── utils/                     # Utility functions
```

### Core Directories

#### `/app` - Application Layer
```
app/
├── notebook/                 # Notebook execution engine
│   ├── api/
│   │   └── notebook_session.py          # UI-specific session (DuckDB)
│   ├── exhibits/             # Visualization rendering
│   ├── filters/              # Filter management & dynamic filters
│   ├── schema.py             # Notebook schema definitions
│   ├── parser.py             # YAML parser
│   ├── markdown_parser.py    # Markdown parser
│   └── __init__.py
├── ui/                       # Streamlit UIs
│   ├── streamlit_app.py      # Legacy Spark-based UI
│   ├── notebook_app_duckdb.py # Modern DuckDB-based UI
│   ├── components/           # Reusable UI components
│   └── ...
└── services/                 # Business logic services
    └── storage_service.py    # DuckDB storage access
```

#### `/models` - Data Models & Sessions
```
models/
├── api/                      # Session APIs
│   ├── session.py            # ModelSession & UniversalSession
│   ├── services.py           # PricesAPI, NewsAPI, CompanyAPI
│   ├── dal.py                # Data access layer abstractions
│   └── types.py
├── base/                     # Base classes
│   ├── service.py            # BaseAPI abstract class
│   ├── forecast_model.py
│   └── model.py
├── implemented/              # Concrete implementations
│   ├── company/              # Company model (prices, news, company data)
│   ├── forecast/             # Forecast model
│   └── core/                 # Shared utilities
├── registry.py               # ModelRegistry (model discovery)
└── __init__.py
```

#### `/core` - Core Abstractions
```
core/
├── context.py                # RepoContext (setup/initialization)
├── connection.py             # DataConnection abstraction
├── duckdb_connection.py      # DuckDB implementation
└── validation.py
```

#### `/datapipelines` - Data Ingestion
```
datapipelines/
├── base/                     # Base classes (HTTP client, registry, key pool)
├── facets/                   # Core facet definitions
├── ingestors/                # Spark-based ingestors
└── providers/                # Data source implementations
    ├── bls/                  # Bureau of Labor Statistics
    ├── chicago/              # Chicago city data
    └── polygon/              # Stock market data
```

---

## 2. Session Management Architecture

### Three Parallel Session Systems

#### **System 1: ModelSession (Legacy)**
- **File:** `models/api/session.py` (lines 15-98)
- **Purpose:** Legacy single-model session for Spark
- **Backend:** Spark only (hardcoded for CompanyModel)
- **API:**
  ```python
  session = ModelSession(spark, repo_root, storage_cfg)
  session.ensure_built() -> (dims, facts)
  session.silver_path_df(path_id)
  session.get_dimension_df(model_name, node_name)
  session.get_fact_df(model_name, node_name)
  ```
- **Usage:** 
  - `app/ui/streamlit_app.py` (old Spark UI)
  - Service APIs (PricesAPI, NewsAPI, CompanyAPI) via BaseAPI
- **Status:** ⚠️ **DEPRECATED** - target for removal

**Key Characteristics:**
- Tightly coupled to CompanyModel
- Manual model building (lazy initialization)
- Returns (dims, facts) tuple structure
- No multi-model support

#### **System 2: UniversalSession (Modern Foundation)**
- **File:** `models/api/session.py` (lines 104-268)
- **Purpose:** Model-agnostic, registry-driven session
- **Backend:** Connection-agnostic (designed for Spark, extensible to DuckDB)
- **API:**
  ```python
  session = UniversalSession(connection, storage_cfg, repo_root, models=['company', 'forecast'])
  session.load_model(model_name)
  session.get_table(model_name, table_name)
  session.get_dimension_df(model_name, dim_id)
  session.get_fact_df(model_name, fact_id)
  session.list_models() -> ['company', 'forecast', ...]
  session.list_tables(model_name) -> {dimensions: [...], facts: [...]}
  session.get_model_metadata(model_name)
  ```
- **Usage:**
  - `scripts/build_silver_layer.py`
  - `scripts/run_forecasts.py`
  - `run_full_pipeline.py`
- **Status:** ✅ **RECOMMENDED** - foundation for consolidation

**Key Characteristics:**
- Multi-model support via ModelRegistry
- Dynamic model loading and caching
- Connection-agnostic design
- Clean separation of concerns

#### **System 3: NotebookSession (UI-Specific)**
- **File:** `app/notebook/api/notebook_session.py`
- **Purpose:** Notebook execution + data access for markdown/YAML notebooks
- **Backend:** DuckDB (via SilverStorageService)
- **API:**
  ```python
  session = NotebookSession(connection, model_registry, repo_root)
  session.load_notebook(notebook_path) -> NotebookConfig
  session.update_filters(filter_values)
  session.get_filter_context() -> Dict
  session.get_exhibit_data(exhibit_id) -> DataFrame
  session.get_model_session(model_name)
  ```
- **Usage:**
  - `app/ui/notebook_app_duckdb.py` (new DuckDB UI)
- **Status:** ⚠️ **MIXED CONCERNS** - should be refactored to NotebookManager

**Key Characteristics:**
- Combines parsing + data access (violation of SRP)
- DuckDB-specific implementation
- Notebook-specific features (filters, exhibits)
- 450+ lines with complex filter logic

### Session Compatibility Issues

**Issue 1: API Inconsistency**
```python
# ModelSession
session.get_dimension_df(model_name, node_name)
session.ensure_built() -> (dims, facts)

# UniversalSession
session.get_dimension_df(model_name, dim_id)
session.get_table(model_name, table_name)

# NotebookSession
session.storage_service.get_table(model_name, table_name, filters)
session.get_exhibit_data(exhibit_id)
```

**Issue 2: Backend Type Differences**
| Session | Backend | DataFrame Type | Filter Format |
|---------|---------|----------------|---------------|
| ModelSession | Spark | pyspark.sql.DataFrame | Manual filtering |
| UniversalSession | Spark | pyspark.sql.DataFrame | Manual filtering |
| NotebookSession | DuckDB | duckdb.DuckDBPyRelation | SQL-based filters |

**Issue 3: Duplicate Code**
- Filter application logic exists in 3 places:
  1. `models/base/service.py:54-84` (BaseAPI._apply_filters)
  2. `app/notebook/api/notebook_session.py:180-250` (_build_filters)
  3. `app/services/storage_service.py:80-120` (filter application)

### Current Migration Status

From `/docs/SESSION_CONSOLIDATION_PLAN.md`:
- Phase 1: ✅ Enhanced UniversalSession foundation
- Phase 2: ✅ Service layer migration (BaseAPI updates)
- Phase 3: ✅ UI migration (NotebookManager extraction)
- Phase 4: ✅ Cleanup & documentation

---

## 3. Notebook Structure

### Notebook Formats Supported

The system supports two notebook formats:

#### **Format A: Markdown Notebooks** (Modern)
- **File extension:** `.md`
- **Parser:** `MarkdownNotebookParser` (app/notebook/markdown_parser.py)
- **Structure:**
  ```markdown
  ---
  id: notebook_id
  title: Notebook Title
  description: ...
  tags: [...]
  models: [company, forecast]
  author: ...
  ---
  
  $filter${...}      # Inline filter definitions
  
  # Heading
  
  Description text
  
  $exhibits${...}    # Inline exhibit definitions
  
  <details>...</details>  # Collapsible sections
  ```
- **Example:** `/configs/notebooks/stock_analysis.md` (109 lines)

#### **Format B: YAML Notebooks** (Legacy)
- **File extension:** `.yaml`
- **Parser:** `NotebookParser` (app/notebook/parser.py)
- **Structure:**
  ```yaml
  version: 1
  notebook:
    id: notebook_id
    title: ...
  graph:
    models:
      - name: company
        nodes: [...]
    bridges: [...]
  variables:
    var_id:
      type: date_range
      display_name: ...
  exhibits:
    - id: exhibit_id
      type: line_chart
      source: model.table
  ```

### Notebook Components

#### 1. **Metadata** (NotebookMetadata)
```python
@dataclass
class NotebookMetadata:
    id: str
    title: str
    description: Optional[str]
    author: Optional[str]
    created: Optional[str]
    updated: Optional[str]
    tags: Optional[List[str]]
```

#### 2. **Filters/Variables** (Variable)
```python
@dataclass
class Variable:
    id: str
    type: VariableType  # date_range, multi_select, number, etc.
    display_name: str
    default: Any
    source: Optional[SourceReference]  # For dynamic options
    description: Optional[str]
    options: Optional[List[Any]]
```

**VariableType Enum:**
- `DATE_RANGE` - Date range picker
- `MULTI_SELECT` - Multi-select dropdown
- `SINGLE_SELECT` - Single select dropdown
- `NUMBER` - Numeric input
- `TEXT` - Text input
- `BOOLEAN` - Boolean toggle

#### 3. **Exhibits** (Exhibit) - Visualizations
```python
@dataclass
class Exhibit:
    id: str
    type: ExhibitType
    title: str
    source: str  # "model.table" format
    filters: Optional[Dict[str, Any]]
    x_axis: Optional[AxisConfig]
    y_axis: Optional[AxisConfig]
    # ... many more visualization configs
```

**ExhibitType Enum:**
- `METRIC_CARDS` - KPI cards
- `LINE_CHART` - Time series
- `BAR_CHART` - Bar chart
- `SCATTER_CHART` - Scatter plot
- `DUAL_AXIS_CHART` - Twin axis
- `HEATMAP` - Heatmap
- `DATA_TABLE` - Data grid
- `WEIGHTED_AGGREGATE_CHART` - Multi-stock index
- `FORECAST_CHART` - Forecast visualization

#### 4. **Dynamic Filters** (New System)
```python
@dataclass
class FilterConfig:
    id: str
    type: FilterType  # date_range, select, number_range, text_search, slider
    label: str
    source: Optional[FilterSource]  # {model, table, column}
    default: Any
    operator: FilterOperator  # equals, in, gte, contains, etc.
    multi: bool
    options: Optional[List[Any]]
    # UI configuration
    placeholder: Optional[str]
    help_text: Optional[str]
```

### Notebook Configuration (NotebookConfig)
```python
@dataclass
class NotebookConfig:
    version: str
    notebook: NotebookMetadata
    graph: GraphConfig
    variables: Dict[str, Variable]
    exhibits: List[Exhibit]
    layout: List[Section]
    dimensions: Optional[List[Dimension]]
    measures: Optional[List[Measure]]
    exports: Optional[List[ExportConfig]]
```

### Sample Notebooks

Located in `/configs/notebooks/`:

1. **stock_analysis.md** (109 lines)
   - Stock price analysis with dynamic filters
   - Metrics, trend analysis, volume comparison

2. **forecast_analysis.md** (148 lines)
   - Forecast model results
   - Accuracy metrics, predictions

3. **aggregate_stock_analysis.md** (169 lines)
   - Market-level aggregates (weighted indices)
   - Equal-weighted vs volume-weighted indexes

4. **stock_analysis_dynamic.md** (135 lines)
   - Advanced dynamic filters with database-driven options

---

## 4. Types and Interfaces

### Core Type Hierarchies

#### **Session Types**
```
┌─────────────────────┐
│  ModelSession       │  (Legacy)
│  - Spark only       │
│  - CompanyModel     │
│  - ensure_built()   │
└─────────────────────┘

┌─────────────────────────────┐
│  UniversalSession           │  (Modern Foundation)
│  - Connection-agnostic      │
│  - Multi-model              │
│  - get_table()              │
│  - load_model()             │
└─────────────────────────────┘

┌──────────────────────────────┐
│  NotebookSession             │  (Refactor to Manager)
│  - Notebook parsing          │
│  - Data access (delegates)   │
│  - Filter management         │
└──────────────────────────────┘
```

#### **Connection Types**
```
DataConnection (ABC)
├── SparkConnection (Fully implemented)
├── DuckDBConnection (Implemented)
└── [Future] GraphDBConnection, ArrowConnection
```

#### **Variable Types (Filters)**
```
VariableType (Enum)
├── DATE_RANGE
├── MULTI_SELECT
├── SINGLE_SELECT
├── NUMBER
├── TEXT
└── BOOLEAN

FilterType (Enum)  # More granular
├── DATE_RANGE
├── SELECT
├── NUMBER_RANGE
├── TEXT_SEARCH
├── SLIDER
└── BOOLEAN
```

#### **Exhibit Types (Visualizations)**
```
ExhibitType (Enum)
├── METRIC_CARDS
├── LINE_CHART
├── BAR_CHART
├── SCATTER_CHART
├── DUAL_AXIS_CHART
├── HEATMAP
├── DATA_TABLE
├── PIVOT_TABLE
├── WEIGHTED_AGGREGATE_CHART
├── FORECAST_CHART
└── FORECAST_METRICS_TABLE
```

#### **Measure Types**
```
MeasureType (Enum)
├── SIMPLE              # Single aggregation
├── WEIGHTED_AVERAGE    # Two-column weighted avg
├── WEIGHTED_AGGREGATE  # Multi-stock index
├── CALCULATION         # Expression-based
├── WINDOW_FUNCTION     # With window spec
└── RATIO               # A/B calculation
```

### Key Interfaces

#### **BaseAPI (Abstract Service)**
```python
class BaseAPI(ABC):
    def __init__(self, session, model_name: str)
    def _get_table(self, table_name: str) -> DataFrame
    def _apply_filters(self, df, filters: Dict) -> DataFrame
```

**Implementations:**
- `PricesAPI` (company.fact_prices)
- `NewsAPI` (company.fact_news)
- `CompanyAPI` (company dimensions)

#### **DataConnection (Abstract Connection)**
```python
class DataConnection(ABC):
    def read_table(path, format) -> DataFrame
    def apply_filters(df, filters) -> DataFrame
    def to_pandas(df) -> pd.DataFrame
    def count(df) -> int
    def cache(df) -> DataFrame
    def stop()
```

#### **NotebookParser (YAML)**
```python
class NotebookParser:
    def parse_file(notebook_path: str) -> NotebookConfig
    def parse_dict(data: Dict) -> NotebookConfig
    def _parse_variables(data) -> Dict[str, Variable]
    def _parse_exhibits(data) -> List[Exhibit]
    def _parse_dimensions(data) -> List[Dimension]
    def _parse_measures(data) -> List[Measure]
```

#### **MarkdownNotebookParser (Markdown)**
```python
class MarkdownNotebookParser:
    def parse_file(notebook_path: str) -> NotebookConfig
    def _extract_front_matter(content) -> Dict
    def _extract_filters(content) -> List[FilterConfig]
    def _extract_exhibits(content) -> List[Exhibit]
```

#### **FilterContext (Filter State Management)**
```python
class FilterContext:
    def __init__(variables: Dict[str, Variable])
    def get(var_id) -> Any
    def set(var_id, value)
    def update(values: Dict)
    def get_all() -> Dict
    def reset()
    def create_exhibit_context(exhibit_filters) -> FilterContext
```

---

## 5. Application Architecture

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     UI Layer (Streamlit)                     │
├─────────────────────────────────────────────────────────────┤
│  Option A: streamlit_app.py (Spark)                          │
│  Option B: notebook_app_duckdb.py (DuckDB)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼────────────┐
         │           │            │
         ▼           ▼            ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────────┐
│NotebookMgr  │ │Service APIs  │ │SilverStorageSvc  │
├─────────────┤ ├──────────────┤ ├──────────────────┤
│ • Parser    │ │ • PricesAPI  │ │ • DuckDB wrapper │
│ • Filters   │ │ • NewsAPI    │ │ • Caching        │
│ • Exhibits  │ │ • CompanyAPI │ │ • Filter app     │
└──────┬──────┘ └──────┬───────┘ └────────┬─────────┘
       │                │                  │
       └────────────────┼──────────────────┘
                        │
         ┌──────────────▼────────────────┐
         │    UniversalSession           │
         │    (THE CONSOLIDATION TARGET) │
         ├──────────────────────────────┤
         │ • Multi-model support         │
         │ • Connection-agnostic         │
         │ • Dynamic model loading       │
         │ • Caching layer               │
         │ • Filter application          │
         └────────┬─────────────┬────────┘
                  │             │
        ┌─────────▼──┐  ┌───────▼──────┐
        │  Spark     │  │  DuckDB      │
        │Connection  │  │Connection    │
        └────────────┘  └──────────────┘
                  │             │
        ┌─────────▼──────┬──────▼──────┐
        │  Bronze/Silver │   DuckDB    │
        │  (Parquet)     │   Database  │
        └────────────────┴─────────────┘
```

### Detailed Architecture Components

#### **Layer 1: Presentation (UI)**

**Legacy Option: streamlit_app.py**
- Uses ModelSession directly
- Spark-based (slow for interactive queries)
- Components:
  - CompanyExplorerApp class
  - Cached factories for Spark context
  - Tabs: Prices, News, Company
  - Widgets: date inputs, ticker multiselect

**Modern Option: notebook_app_duckdb.py**
- Uses NotebookSession + DuckDB
- Fast interactive queries (10-100x faster)
- Components:
  - NotebookVaultApp class
  - SidebarNavigator for notebook browsing
  - render_filters_section() for dynamic filters
  - render_notebook_exhibits() for visualizations
  - Professional theme support

#### **Layer 2: Business Logic**

**Notebook Manager (Refactored from NotebookSession)**
- Responsibilities:
  - Load/parse notebooks (YAML or Markdown)
  - Manage filter state (FilterContext)
  - Initialize model sessions
  - Prepare exhibit data
- Does NOT directly query (delegates to UniversalSession)

**Service APIs (BaseAPI subclasses)**
- PricesAPI: Stock price queries
- NewsAPI: News data queries
- CompanyAPI: Company metadata queries
- Pattern: Typed wrappers around UniversalSession

**SilverStorageService**
- Generic data access wrapper
- Caches DataFrames
- Applies filters
- DuckDB-specific optimization

#### **Layer 3: Data Access (Unified Session)**

**UniversalSession** (THE CONSOLIDATION TARGET)
```
Responsibilities:
├── Model registry integration
├── Dynamic model loading
├── Multi-model support
├── Backend abstraction
├── Filter application
├── Caching strategies
└── Cross-model queries
```

**Key Methods:**
```python
load_model(model_name) -> BaseModel
get_table(model_name, table_name) -> DataFrame
get_dimension_df(model_name, dim_id) -> DataFrame
get_fact_df(model_name, fact_id) -> DataFrame
list_models() -> List[str]
list_tables(model_name) -> Dict[str, List[str]]
get_model_metadata(model_name) -> Dict
```

#### **Layer 4: Connection Abstraction**

**DataConnection (Abstract)**
```
Implementations:
├── SparkConnection (pyspark.sql.SparkSession)
├── DuckDBConnection (duckdb.DuckDBPyConnection)
└── [Future] GraphDBConnection, ArrowConnection

Responsibilities:
├── Read tables from storage
├── Apply filters to DataFrames
├── Convert to different formats
├── Manage caching
└── Handle resources
```

#### **Layer 5: Storage**

**Bronze Layer** (Raw Data)
- Parquet files organized by provider
- `/storage/bronze/{provider}/{table}/`

**Silver Layer** (Processed Data)
- Parquet files from model builds
- `/storage/silver/{model}/{table}/`
- DuckDB views for fast queries

---

## 6. Core Dependencies Map

### Direct Dependencies (Session Consumers)

| Component | Current Session | Lines | Risk | Migration |
|-----------|-----------------|-------|------|-----------|
| streamlit_app.py | ModelSession | ~400 | Medium | Replace with UniversalSession |
| notebook_app_duckdb.py | NotebookSession | ~350 | High | Use NotebookManager + UniversalSession |
| PricesAPI/NewsAPI | BaseAPI → ModelSession | ~600 | Medium | Update BaseAPI to require UniversalSession |
| build_silver_layer.py | UniversalSession | ~150 | Low | Already compatible |
| run_forecasts.py | UniversalSession | ~200 | Low | Already compatible |

### Transitive Dependencies

```
UniversalSession
├── ModelRegistry (dynamic model loading)
├── DataConnection (backend abstraction)
├── RepoContext (initialization)
├── BaseModel (model interface)
└── Storage configuration

NotebookSession
├── NotebookParser / MarkdownNotebookParser
├── FilterContext
├── ModelRegistry
├── SilverStorageService
└── UniversalSession (indirectly)

BaseAPI
├── Session (ModelSession OR UniversalSession)
├── Model-specific logic
└── Filter application
```

---

## 7. State Management Patterns

### Filter State Management

**Old Pattern: FilterContext**
```python
# In NotebookSession.__init__
self.filter_context: Optional[FilterContext] = None

# In load_notebook()
self.filter_context = FilterContext(self.notebook_config.variables)

# In update_filters()
if self.filter_context is not None:
    self.filter_context.update(filter_values)

# In get_exhibit_data()
context_filters = self.filter_context.get_all()
# Convert to SQL/Spark filters
```

**New Pattern: Dynamic FilterCollection**
```python
# In markdown notebooks (inline $filter${...})
class FilterCollection:
    def get_active_filters() -> Dict
    def get_filter(filter_id) -> FilterConfig
```

**Coexistence:** NotebookSession supports both patterns (lines 249-310)

### Session Caching Strategy

**Streamlit Session State:**
```python
if 'open_tabs' not in st.session_state:
    st.session_state.open_tabs = []
    
if 'notebook_model_sessions' not in st.session_state:
    st.session_state.notebook_model_sessions = {}  # Per-notebook caching
```

**Cached Factories:**
```python
@st.cache_resource
def get_repo_context():
    return RepoContext.from_repo_root(connection_type="duckdb")

@st.cache_resource
def get_notebook_session(_ctx, _model_registry):
    return NotebookSession(_ctx.connection, _model_registry, _ctx.repo)
```

---

## 8. Configuration & Registry

### Model Registry Pattern

**Location:** `models/registry.py`
**Purpose:** Central discovery of data models

```python
class ModelRegistry:
    def __init__(models_dir: Path)
    def list_models() -> List[str]
    def get_model_config(model_name) -> Dict
    def get_model_class(model_name) -> Type[BaseModel]
    def get_model_instance(model_name) -> BaseModel
```

**Configuration Files:** `/configs/models/`
- `company.yaml` - Stock/company data model
- `forecast.yaml` - Forecast model
- `macro.yaml` - Macro data model
- `city_finance.yaml` - Municipal finance model

### Context Initialization Pattern

**File:** `core/context.py` (RepoContext)

```python
@dataclass
class RepoContext:
    repo: Path
    spark: Any
    polygon_cfg: Dict
    storage: Dict
    connection: Optional[DataConnection]
    connection_type: str  # "spark" or "duckdb"

    @classmethod
    def from_repo_root(cls, connection_type=None):
        # Auto-detect repo root
        # Load configs from /configs/
        # Create connection (Spark or DuckDB)
        # Return initialized context
```

---

## 9. Key Files Summary

### Session Management Files (Core of Consolidation)

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `models/api/session.py` | ~270 lines | ModelSession + UniversalSession | ⚠️ Needs refactoring |
| `app/notebook/api/notebook_session.py` | ~450 lines | Notebook execution + data access | ⚠️ Needs splitting |
| `app/services/storage_service.py` | ~150 lines | DuckDB storage wrapper | 🟡 Will be deprecated |
| `models/base/service.py` | ~85 lines | BaseAPI abstraction | ✅ Needs update for UniversalSession |

### Notebook Components Files

| File | Lines | Purpose |
|------|-------|---------|
| `app/notebook/schema.py` | ~300 | Type definitions (Variable, Exhibit, etc.) |
| `app/notebook/parser.py` | ~450 | YAML notebook parser |
| `app/notebook/markdown_parser.py` | ~500 | Markdown notebook parser |
| `app/notebook/filters/context.py` | ~228 | Filter state management |
| `app/notebook/filters/dynamic.py` | ~150+ | Dynamic filter types |

### UI Components Files

| File | Lines | Purpose |
|------|-------|---------|
| `app/ui/streamlit_app.py` | ~180 | Legacy Spark UI |
| `app/ui/notebook_app_duckdb.py` | ~350+ | Modern DuckDB UI |
| `app/ui/components/notebook_view.py` | ~400+ | Exhibit rendering |
| `app/ui/components/sidebar.py` | ~300+ | Notebook navigation |
| `app/ui/components/filters.py` | ~350+ | Filter UI rendering |

### Configuration Files

| File | Purpose |
|------|---------|
| `/configs/models/company.yaml` | Company model schema |
| `/configs/notebooks/*.md` | Markdown notebooks (4 samples) |
| `/configs/storage.json` | Storage configuration |
| `/configs/polygon_endpoints.json` | API endpoints |

---

## 10. Consolidation Readiness Assessment

### What's Already in Place ✅

1. **UniversalSession** is well-designed:
   - Multi-model support via ModelRegistry
   - Connection-agnostic (can support both Spark and DuckDB)
   - Clean API (get_table, load_model, etc.)
   - Proper caching strategy

2. **DataConnection abstraction** exists:
   - Abstract base class defined
   - SparkConnection implemented
   - DuckDBConnection partially implemented

3. **Filter infrastructure** is mature:
   - FilterContext for state management
   - Dynamic FilterCollection for new system
   - Coexistence support for migration

4. **Notebook parsing** is robust:
   - Both YAML and Markdown parsers implemented
   - Schema definitions complete
   - Validation in place

### What Needs Work ⚠️

1. **NotebookSession** mixing concerns:
   - Parsing logic coupled with data access
   - Should be refactored to NotebookManager
   - FilterContext logic should move to UI layer

2. **BaseAPI compatibility shims**:
   - Lines 42-52 in `models/base/service.py` support both ModelSession and UniversalSession
   - Should be removed in consolidation

3. **SilverStorageService** redundancy:
   - Very similar to UniversalSession
   - Should be deprecated or refactored into UniversalSession

4. **Filter application duplication**:
   - 3 places apply filters differently
   - Should be consolidated in UniversalSession or DataConnection

### Proposed Directory Structure (Post-Consolidation)

```
models/
├── api/
│   ├── session.py          # UniversalSession ONLY (ModelSession removed)
│   ├── services.py         # PricesAPI, NewsAPI, CompanyAPI (updated)
│   ├── dal.py
│   └── types.py
├── base/
│   ├── service.py          # BaseAPI (simplified, no shims)
│   ├── model.py
│   └── forecast_model.py
└── implemented/
    ├── company/            # Company model
    ├── forecast/           # Forecast model
    └── core/

app/
├── notebook/
│   ├── api/
│   │   ├── notebook_manager.py    # NEW: Parsing + rendering (no data access)
│   │   └── __init__.py
│   ├── schema.py           # UNCHANGED: Type definitions
│   ├── parser.py           # UNCHANGED: YAML parser
│   ├── markdown_parser.py  # UNCHANGED: Markdown parser
│   ├── exhibits/           # UNCHANGED: Visualization rendering
│   └── filters/
│       ├── context.py      # MOVED: To UI layer
│       └── dynamic.py      # UNCHANGED: Filter types
├── ui/
│   ├── notebook_app_duckdb.py  # Updated: Uses NotebookManager + UniversalSession
│   ├── streamlit_app.py        # Updated: Uses UniversalSession only
│   └── components/             # UNCHANGED: UI rendering logic
└── services/
    └── storage_service.py  # DEPRECATED: Functionality moved to UniversalSession
```

---

## 11. Implementation Priorities

### Phase 1: Strengthen UniversalSession
**Status:** ✅ Done per consolidation plan

**Tasks:**
- [x] Add DuckDB backend support
- [x] Unify filter API
- [x] Add caching layer
- [x] Create test suite

### Phase 2: Migrate Service Layer
**Status:** ✅ Done per consolidation plan

**Tasks:**
- [x] Update BaseAPI (remove shims)
- [x] Update PricesAPI, NewsAPI, CompanyAPI
- [x] Test service APIs
- [x] Update scripts

### Phase 3: Refactor UI Layer
**Status:** ⏳ In progress per consolidation plan

**Tasks:**
- [ ] Create NotebookManager (extract from NotebookSession)
- [ ] Update streamlit_app.py (use UniversalSession)
- [ ] Update notebook_app_duckdb.py (use NotebookManager + UniversalSession)
- [ ] Test both UIs thoroughly

### Phase 4: Cleanup & Documentation
**Status:** ⏳ In progress per consolidation plan

**Tasks:**
- [ ] Deprecate ModelSession (add warnings)
- [ ] Remove compatibility shims
- [ ] Deprecate SilverStorageService
- [ ] Update all documentation
- [ ] Performance testing

---

## 12. Critical Success Factors

### Testing Requirements
- UniversalSession tests (90%+ coverage)
- Integration tests for both Spark and DuckDB
- UI regression tests for both apps
- Service API integration tests
- End-to-end notebook tests

### Performance Targets
- Notebook load time: <2.5s
- Query latency (DuckDB): <75ms
- Query latency (Spark): <600ms
- Memory usage: <250MB

### Code Quality Goals
- Reduce code duplication by 30%+
- Improve test coverage to >85%
- Eliminate compatibility shims
- Complete architecture documentation

---

## Conclusion

The de_Funk codebase is well-architected with clear separation of concerns. The consolidation plan to unify around UniversalSession is **sound and feasible** because:

1. **UniversalSession** is already the superior design (multi-model, connection-agnostic)
2. **NotebookSession** can be refactored to NotebookManager (extracting parsing from data access)
3. **Filter logic** can be centralized (already attempted with FilterContext)
4. **Services** can be simplified (remove compatibility shims)
5. **Both UIs** can work with the same unified backend

The phased approach minimizes risk while delivering incremental value. The main challenge is thorough testing of both Spark and DuckDB backends to ensure no regressions.
