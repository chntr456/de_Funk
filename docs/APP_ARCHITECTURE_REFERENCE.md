# App/ Directory - Complete Architecture Reference

**Generated:** 2025-11-22
**Purpose:** Complete reference for all app/ directory components with ALL methods and classes

---

## 1. NOTEBOOK PARSING SYSTEM

### 1.1 MarkdownNotebookParser (app/notebook/parsers/markdown_parser.py - 593 lines)

**Purpose:** Parse markdown-based notebooks with YAML front matter, filters, and exhibits

#### Class: MarkdownNotebookParser

**Attributes:**
- `repo_root: Path` - Repository root path

**Methods (13 methods):**

```python
def __init__(repo_root: Optional[Path] = None)
    # Initialize parser with repo root

def parse_file(notebook_path: str) → NotebookConfig
    # Parse a markdown notebook file

def parse_markdown(content: str) → NotebookConfig
    # Parse markdown content into NotebookConfig

- _extract_front_matter(content: str) → Optional[Dict[str, Any]]
    # Extract and parse YAML front matter

- _extract_dynamic_filters(content: str) → FilterCollection
    # Extract filters using $filter${...} syntax

- _old_parse_filter_default(default_str: str, var_type: VariableType) → Any
    # Parse default value based on variable type (DEPRECATED)

- _old_parse_filter_options(default_str: str, var_type: VariableType) → Optional[List[Any]]
    # Parse options for multi_select filters (DEPRECATED)

- _extract_exhibits(content: str) → Tuple[List[Exhibit], List[Dict[str, Any]]]
    # Extract exhibits from markdown content and handle collapsible sections

- _add_content_with_collapsibles(...) → int
    # Add content blocks, processing any collapsible section placeholders

- _parse_exhibit(exhibit_yaml: str, exhibit_id: str) → Exhibit
    # Parse exhibit YAML into Exhibit object
    # Supports streamlined syntax (x/y instead of x_axis/y_axis)

- _build_config(front_matter, filter_collection, exhibits, content_blocks) → NotebookConfig
    # Build NotebookConfig from parsed components
```

**Regex Patterns:**
- `FRONT_MATTER_PATTERN`: `^---\s*\n(.*?)\n---\s*\n`
- `FILTER_PATTERN`: `\$filters?\$\{\s*\n(.*?)\n\}`
- `EXHIBIT_PATTERN`: `\$exhibits?\$\{\s*\n(.*?)\n\}`
- `DETAILS_PATTERN`: `<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>`

---

### 1.2 NotebookManager (app/notebook/managers/notebook_manager.py - 945 lines)

**Purpose:** Manages notebook lifecycle, filters, model sessions, and exhibit data retrieval

#### Class: NotebookManager

**Attributes:**
```python
notebook_config: NotebookConfig
repo_root: Path
universal_session: UniversalSession
model_sessions: Dict[str, Any]  # Model name → model instance
folder_context: Optional[FolderContext]
filter_context: Dict[str, Any]
```

**Methods (19 methods):**

```python
def __init__(notebook_config, repo_root, universal_session, folder_context=None)
    # Initialize notebook manager

def load_notebook(notebook_path: str) → NotebookConfig
    # Load notebook from file (static factory method)

- _initialize_model_sessions()
    # Initialize all models from notebook config

def get_model_session(model_name: str) → Optional[Any]
    # Get model instance by name

def get_filter_context() → Dict[str, Any]
    # Get current filter context (merged folder + session state)

def get_current_folder() → Optional[Path]
    # Get current folder path

- _merge_filters_unified(folder_filters: Dict[str, Any])
    # Merge folder filters with session state filters

- _sync_session_state_to_filters()
    # Sync Streamlit session state to filter_context

- _create_filter_config_from_value(filter_id: str, value: Any)
    # Create FilterConfig from session state value

def get_folder_display_name() → str
    # Get display name for current folder

def update_filters(filter_values: Dict[str, Any])
    # Update filter context with new values

def get_exhibit_data(exhibit_id: str) → Any
    # Get data for specific exhibit (MAIN DATA RETRIEVAL METHOD)

- _find_exhibit(exhibit_id: str) → Optional[Exhibit]
    # Find exhibit by ID in notebook config

- _extract_required_columns(exhibit: Exhibit) → Optional[List[str]]
    # Extract required columns from exhibit config

- _determine_aggregation(exhibit: Exhibit) → tuple[Optional[List[str]], Optional[Dict[str, str]]]
    # Determine group_by and aggregations from exhibit

- _parse_source(source: str) → tuple[str, str]
    # Parse source string 'model.table' into (model_name, table_name)

- _build_filters(exhibit: Exhibit) → Dict[str, Any]
    # Build filters from exhibit config + current filter context

- _get_weighted_aggregate_data(exhibit: Exhibit) → Any
    # Get data for weighted aggregate exhibits

def get_exhibit_list() → List[Dict[str, Any]]
    # Get list of all exhibits in notebook

def get_notebook_metadata() → Dict[str, Any]
    # Get notebook metadata
```

**Key Workflow:**
```
1. User loads notebook → parse_file()
2. Initialize models → _initialize_model_sessions()
3. User changes filter → update_filters()
4. Render exhibit → get_exhibit_data()
   ├─ Parse source → _parse_source()
   ├─ Build filters → _build_filters()
   ├─ Get data from model → universal_session.get_table()
   └─ Return formatted data
```

---

### 1.3 FilterEngine (app/notebook/filters/engine.py - 351 lines)

**Purpose:** Apply filters to DataFrames in backend-agnostic way

#### Class: FilterEngine

**Methods (14 methods):**

```python
def __init__()
    # Initialize filter engine

def apply_filters(df, filters: List[FilterConfig], backend: str) → DataFrame
    # Apply all filters to DataFrame

def apply_filter(df, filter: FilterConfig, backend: str) → DataFrame
    # Apply single filter to DataFrame

- _apply_date_range_filter(df, filter, backend) → DataFrame
    # Apply date range filter

- _apply_multi_select_filter(df, filter, backend) → DataFrame
    # Apply multi-select filter (ticker IN [...])

- _apply_single_select_filter(df, filter, backend) → DataFrame
    # Apply single select filter

- _apply_number_filter(df, filter, backend) → DataFrame
    # Apply number filter with operator (>, <, =, etc.)

- _apply_text_filter(df, filter, backend) → DataFrame
    # Apply text filter (contains, equals, startswith)

- _apply_boolean_filter(df, filter, backend) → DataFrame
    # Apply boolean filter

- _apply_operator_filter(df, filter, backend) → DataFrame
    # Apply operator-based filter (=, >, <, >=, <=, !=, in, contains)

def get_unique_values(df, column: str, backend: str, limit: int = 1000) → List[Any]
    # Get unique values for column (for filter dropdowns)

def get_min_max(df, column: str, backend: str) → Tuple[Any, Any]
    # Get min/max values for numeric column

def apply_dynamic_time_filter(df, filter: FilterConfig, backend: str) → DataFrame
    # Apply dynamic time filters (last_7_days, last_30_days, etc.)
```

**Supported Filter Types:**
- `date_range` - Date range with start/end
- `multi_select` - Multiple value selection
- `single_select` - Single value dropdown
- `number` - Numeric with operators
- `text` - Text matching
- `boolean` - True/False
- `slider` - Numeric range slider
- `dynamic_time` - Relative date ranges

---

## 2. UI COMPONENTS & STREAMLIT APP

### 2.1 NotebookVaultApp (app/ui/notebook_app_duckdb.py - 905 lines)

**Purpose:** Main Streamlit application for notebook vault UI

#### Class: NotebookVaultApp

**Attributes:**
```python
notebooks: Dict[str, Tuple]  # notebook_id → (path, config)
managers: Dict[str, NotebookManager]  # notebook_id → manager
universal_session: UniversalSession
```

**Methods (16 methods):**

```python
def __init__()
    # Initialize Streamlit app

def run()
    # Main app entry point

- _render_header()
    # Render app header with logo and title

- _render_folder_filter_editor()
    # Render folder filter context editor UI

- _render_filter_context_info_OLD()
    # OLD: Render filter context info (DEPRECATED)

- _get_available_tickers() → List[str]
    # Get available tickers for filter dropdowns

- _render_filters(notebook_config)
    # Render dynamic filters based on notebook config

- _get_active_notebook() → Optional[Tuple]
    # Get currently selected notebook

- _render_filter_editor()
    # Render filter editor panel in sidebar

- _render_main_content()
    # Render main content area (notebooks or graph viewer)

- _render_graph_viewer()
    # Render model graph visualization

- _render_notebook_content(notebook_tuple)
    # Render notebook content (exhibits + markdown)

- _render_edit_mode(notebook_id, notebook_path, notebook_config)
    # Render edit mode for notebook (YAML editor)

- _render_view_mode(notebook_id, notebook_config)
    # Render view mode for notebook (exhibits)

- _render_welcome()
    # Render welcome screen
```

**Key UI Flow:**
```
1. _render_header() - Logo + title
2. Sidebar:
   ├─ _render_filter_editor()
   └─ Notebook selector
3. Main content:
   ├─ _render_graph_viewer() (if selected)
   └─ _render_notebook_content()
      ├─ _render_filters() - Dynamic filters
      ├─ Markdown content
      └─ Exhibits (charts, tables, metrics)
```

---

### 2.2 Exhibit Renderers (app/ui/components/exhibits/*.py)

#### Base Renderer (app/ui/components/exhibits/base_renderer.py)

```python
class BaseExhibitRenderer:
    def __init__(session: UniversalSession, notebook_manager: NotebookManager)

    def render(exhibit: Exhibit) → None
        # Render exhibit (abstract method)

    def _get_data(exhibit: Exhibit) → DataFrame
        # Get data for exhibit from notebook_manager
```

#### Line Chart Renderer (app/ui/components/exhibits/line_chart.py)

```python
class LineChartRenderer(BaseExhibitRenderer):
    def render(exhibit: Exhibit) → None
        # Render interactive line chart using Plotly
        # Supports: multiple y-axes, color grouping, dynamic legends
```

#### Bar Chart Renderer (app/ui/components/exhibits/bar_chart.py)

```python
class BarChartRenderer(BaseExhibitRenderer):
    def render(exhibit: Exhibit) → None
        # Render bar chart using Plotly
        # Supports: grouped bars, stacked bars, horizontal/vertical
```

#### Data Table Renderer (app/ui/components/exhibits/data_table.py)

```python
class DataTableRenderer(BaseExhibitRenderer):
    def render(exhibit: Exhibit) → None
        # Render interactive data table
        # Supports: pagination, sorting, searching, download
```

#### Metric Cards Renderer (app/ui/components/exhibits/metric_cards.py)

```python
class MetricCardsRenderer(BaseExhibitRenderer):
    def render(exhibit: Exhibit) → None
        # Render metric cards (KPIs)
        # Shows: value, label, delta, trend
```

#### Weighted Aggregate Chart (app/ui/components/exhibits/weighted_aggregate_chart.py)

```python
class WeightedAggregateChartRenderer(BaseExhibitRenderer):
    def render(exhibit: Exhibit) → None
        # Render weighted aggregate chart
        # Calculate weighted averages/sums
```

---

## 3. SERVICES LAYER

### 3.1 NotebookService (app/services/notebook_service.py)

**Purpose:** Business logic for notebook operations

```python
class NotebookService:
    def __init__(repo_root: Path)

    def discover_notebooks(folder: str = 'configs/notebooks') → Dict[str, Tuple]
        # Discover all notebooks in folder
        # Returns: {notebook_id: (path, config)}

    def load_notebook(path: str) → NotebookConfig
        # Load and parse notebook from path

    def save_notebook(path: str, config: NotebookConfig)
        # Save notebook config to file

    def get_folder_structure() → Dict
        # Get hierarchical folder structure
```

### 3.2 StorageService (app/services/storage_service.py)

**Purpose:** Storage operations for notebooks and data

```python
class StorageService:
    def __init__(storage_config: Dict)

    def list_notebooks() → List[str]
        # List all notebook files

    def read_notebook(path: str) → str
        # Read notebook file content

    def write_notebook(path: str, content: str)
        # Write notebook content to file

    def delete_notebook(path: str)
        # Delete notebook file
```

---

## 4. DATA FLOW ARCHITECTURE

### 4.1 Notebook Rendering Flow

```
User → Streamlit UI → NotebookManager → UniversalSession → BaseModel → Bronze/Silver Data
  ↓                      ↓                    ↓                  ↓
Selects filter    get_exhibit_data()   get_table()      get_table()
  ↓                      ↓                    ↓                  ↓
Filter UI         Build filters        Apply filters      Load from Parquet
  ↓                      ↓                    ↓                  ↓
Exhibit           Parse source         Join tables        Transform data
  rendered          'model.table'        (if needed)
```

### 4.2 Filter Application Flow

```
1. User changes filter in UI
   ↓
2. Streamlit updates session_state
   ↓
3. NotebookManager._sync_session_state_to_filters()
   ↓
4. filter_context updated
   ↓
5. get_exhibit_data() called
   ↓
6. _build_filters() merges exhibit filters + context filters
   ↓
7. UniversalSession.get_table(filters=merged_filters)
   ↓
8. FilterEngine.apply_filters()
   ↓
9. Backend-specific filter application (Spark or DuckDB)
   ↓
10. Filtered data returned to exhibit renderer
```

### 4.3 Cross-Model Join Flow

```
Exhibit config: source: "stocks.fact_prices"
                enrich_with: ["company.sector", "company.name"]
   ↓
NotebookManager.get_exhibit_data()
   ↓
UniversalSession.get_table(
    model_name='stocks',
    table_name='fact_prices',
    enrich_with=['company.sector', 'company.name']
)
   ↓
UniversalSession._plan_auto_joins()
   ├─ Find company.sector in company.dim_company
   ├─ Discover join key: stocks.company_id = company.company_id
   └─ Build join plan
   ↓
UniversalSession._execute_auto_joins()
   ├─ Load stocks.fact_prices
   ├─ Load company.dim_company
   ├─ Join on company_id
   └─ Select columns (prices + sector + name)
   ↓
Return enriched DataFrame to exhibit
```

---

## 5. KEY ARCHITECTURAL PATTERNS

### 5.1 Separation of Concerns

- **Parsers** - Parse markdown/YAML into structured config
- **Managers** - Orchestrate data retrieval and filtering
- **Services** - Business logic for notebooks and storage
- **Renderers** - UI rendering for exhibits
- **Engines** - Backend-agnostic data operations

### 5.2 Dependency Injection

```python
NotebookManager(
    notebook_config=config,        # Injected config
    universal_session=session,     # Injected session
    folder_context=context         # Injected context
)
```

### 5.3 Strategy Pattern

```python
# Different renderers for different exhibit types
renderers = {
    ExhibitType.LINE_CHART: LineChartRenderer,
    ExhibitType.BAR_CHART: BarChartRenderer,
    ExhibitType.DATA_TABLE: DataTableRenderer,
    ExhibitType.METRIC_CARDS: MetricCardsRenderer
}

renderer = renderers[exhibit.type](session, manager)
renderer.render(exhibit)
```

### 5.4 Backend Abstraction

```python
# FilterEngine supports both Spark and DuckDB
if backend == 'spark':
    df = df.filter(F.col(column) == value)
elif backend == 'duckdb':
    df = df.filter(pl.col(column) == value)
```

---

## 6. COMPONENT STATISTICS

### Files by Category

**Parsing:**
- 3 parser files
- 2 schema files
- 593 lines (MarkdownNotebookParser)

**Management:**
- 1 manager file (945 lines)
- 4 filter files (engine, context, dynamic, types)

**UI Components:**
- 1 main app (905 lines)
- 12 exhibit renderers
- 10 component files (filters, sidebar, markdown renderer, etc.)

**Services:**
- 2 service files
- notebook_service.py
- storage_service.py

**Total: 51 Python files in app/**

---

## 7. INTEGRATION POINTS

### 7.1 App → Models Integration

```python
# NotebookManager uses UniversalSession to access models
session = UniversalSession(backend='duckdb', config=config)
manager = NotebookManager(notebook_config, repo_root, session)

# Get data from stocks model
data = manager.get_exhibit_data('exhibit_1')
```

### 7.2 App → Ingestion Integration

```python
# Notebooks query data that was ingested by pipelines
# Bronze: storage/bronze/securities_prices_daily/
# Silver: storage/silver/stocks/fact_prices/
# App: Queries via UniversalSession → BaseModel → Silver tables
```

### 7.3 App → Config Integration

```python
# All notebooks defined in configs/notebooks/*.md
# All models defined in configs/models/*.yaml
# App reads from configs/ directory
```

---

## 8. FUTURE IMPROVEMENTS (From Analysis)

### 8.1 Notebook Redesign Proposal

**Problem:** Monolithic notebook_app_duckdb.py (905 lines)

**Solution:** Modular architecture
- Separate components (header, sidebar, filters, exhibits)
- Component-based rendering
- Reduce code duplication
- Improve testability

### 8.2 Debugging System

**Problem:** No configurable debugging/logging

**Solution:** Debugging framework
- Toggle debug modes (filter debug, query debug, render debug)
- Performance metrics
- Error boundaries
- Detailed logs

### 8.3 Memory Optimization

**Problem:** Facet postprocess() loads entire DataFrame

**Solution:** Streaming architecture
- Chunk-based processing
- Incremental writes
- Memory-efficient aggregations

---

**Total Methods Documented:** 62+ methods across 8+ major classes
**Total Components:** 51 Python files
**Architecture Depth:** 3 layers (Parsing → Management → UI)
