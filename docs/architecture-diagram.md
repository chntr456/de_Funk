# de_Funk Architecture - Call Organization

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER / APPLICATION LAYER                          │
│  (Notebooks, UI, CLI, Scripts)                                              │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENTRY POINT: RepoContext                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ RepoContext.from_repo_root()                                         │   │
│  │  - Loads configs (storage.json, polygon_endpoints.json)             │   │
│  │  - Creates Connection (Spark or DuckDB)                             │   │
│  │  - Returns initialized context                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Returns: {connection, storage_cfg, polygon_cfg, repo_root}                 │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CORE SESSION: UniversalSession                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ UniversalSession(connection, storage_cfg, repo_root)                │   │
│  │                                                                      │   │
│  │  Properties:                                                         │   │
│  │   • connection: Spark or DuckDB                                     │   │
│  │   • storage_cfg: Storage configuration                              │   │
│  │   • registry: ModelRegistry instance                                │   │
│  │   • backend: 'spark' or 'duckdb' (auto-detected)                    │   │
│  │   • _models: Cache of loaded model instances                        │   │
│  │                                                                      │   │
│  │  Key Methods:                                                        │   │
│  │   • load_model(model_name) → BaseModel                              │   │
│  │   • get_table(model, table) → DataFrame                             │   │
│  │   • get_dimension_df(model, dim) → DataFrame                        │   │
│  │   • get_fact_df(model, fact) → DataFrame                            │   │
│  │   • list_models() → List[str]                                       │   │
│  │   • list_tables(model) → Dict                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ↓
                          ┌──────────────────────┐
                          │   MODEL REGISTRY     │
                          │  ┌──────────────┐    │
                          │  │ Discovers &  │    │
                          │  │ Loads Models │    │
                          │  │              │    │
                          │  │ Sources:     │    │
                          │  │  - YAML      │    │
                          │  │    configs   │    │
                          │  │  - Python    │    │
                          │  │    classes   │    │
                          │  │              │    │
                          │  │ Returns:     │    │
                          │  │  - ModelCfg  │    │
                          │  │  - ModelCls  │    │
                          │  └──────────────┘    │
                          └──────────────────────┘
                                     │
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MODEL LAYER: BaseModel (Graph-Based)                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ BaseModel(connection, storage_cfg, model_cfg, params)              │   │
│  │                                                                      │   │
│  │  Properties:                                                         │   │
│  │   • connection: Database connection                                 │   │
│  │   • model_cfg: YAML configuration with graph definition             │   │
│  │   • storage_router: StorageRouter instance                          │   │
│  │   • backend: 'spark' or 'duckdb'                                    │   │
│  │   • _dims: Cached dimensions (from nodes)                           │   │
│  │   • _facts: Cached facts (from nodes + paths)                       │   │
│  │                                                                      │   │
│  │  GRAPH-DRIVEN BUILD LIFECYCLE:                                      │   │
│  │   1. build() → 3-Phase Graph Building from YAML                     │   │
│  │                                                                      │   │
│  │      PHASE 1: Build Nodes                                           │   │
│  │      • _build_nodes() - For each node in graph.nodes:               │   │
│  │        ├─ Load from Bronze (via StorageRouter)                      │   │
│  │        ├─ Apply 'select' (column mapping/aliasing)                  │   │
│  │        ├─ Apply 'derive' (computed columns like SHA1)               │   │
│  │        └─ Return node as DataFrame                                  │   │
│  │                                                                      │   │
│  │      PHASE 2: Validate Edges                                        │   │
│  │      • _apply_edges() - For each edge in graph.edges:               │   │
│  │        ├─ Check nodes exist                                         │   │
│  │        ├─ Validate join columns                                     │   │
│  │        ├─ Dry-run join (limit 1)                                    │   │
│  │        └─ Raise error if invalid                                    │   │
│  │                                                                      │   │
│  │      PHASE 3: Materialize Paths                                     │   │
│  │      • _materialize_paths() - For each path in graph.paths:         │   │
│  │        ├─ Parse hops (e.g. "fact_prices -> dim_company -> ...")     │   │
│  │        ├─ Join nodes in sequence (left joins)                       │   │
│  │        ├─ Handle column deduplication                               │   │
│  │        └─ Return joined DataFrame as path                           │   │
│  │                                                                      │   │
│  │   2. get_table(name) → Returns dimension or fact DataFrame          │   │
│  │   3. get_dimension_df(id) → Returns dimension node                  │   │
│  │   4. get_fact_df(id) → Returns fact node or materialized path       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────┬───────────────────────────┘
               │                                  │
               │                                  │
      ┌────────┴────────┐              ┌─────────┴──────────┐
      │                 │              │                    │
      ↓                 ↓              ↓                    ↓
┌──────────┐    ┌──────────┐   ┌──────────┐      ┌──────────┐
│ Company  │    │  Macro   │   │ Forecast │      │City Fin. │
│  Model   │    │  Model   │   │  Model   │      │  Model   │
│          │    │          │   │          │      │          │
│ Sources: │    │ Sources: │   │ Sources: │      │ Sources: │
│ Polygon  │    │   BLS    │   │ Company  │      │ Chicago  │
│   API    │    │   API    │   │  Model   │      │   Data   │
│          │    │          │   │ (Silver) │      │  Portal  │
│          │    │          │   │          │      │          │
│ Tables:  │    │ Tables:  │   │ Tables:  │      │ Tables:  │
│ • dims:  │    │ • dims:  │   │ • facts: │      │ • dims:  │
│   - co.  │    │   - eco. │   │   - fore │      │   - comm │
│   - exch │    │   series │   │   - metr │      │   - area │
│ • facts: │    │ • facts: │   │   - reg. │      │ • facts: │
│   - price│    │   - unem │   │          │      │   - (TBD)│
│   - news │    │   - cpi  │   │          │      │          │
│          │    │   - emp  │   │          │      │          │
│          │    │   - wage │   │          │      │          │
└──────────┘    └──────────┘   └──────────┘      └──────────┘
      │                 │              │                 │
      └─────────────────┴──────────────┴─────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER: Data Access Layer                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ StorageRouter(storage_cfg)                                          │   │
│  │  • bronze_path(table) → Path to Bronze data                         │   │
│  │  • silver_path(rel) → Path to Silver data                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌───────────────────────────┐    ┌─────────────────────────────────┐      │
│  │ BronzeTable               │    │ SilverPath                       │      │
│  │  • read() → Raw data      │    │  • read() → Dimensional data     │      │
│  │  • Parquet format         │    │  • Parquet format                │      │
│  │  • Partitioned by date    │    │  • Star schema                   │      │
│  └───────────────────────────┘    └─────────────────────────────────┘      │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHYSICAL STORAGE: File System                        │
│                                                                              │
│  storage/                                                                    │
│  ├── bronze/                    ← Raw ingested data                         │
│  │   ├── polygon/               ← Polygon.io data                           │
│  │   ├── bls/                   ← BLS economic data                         │
│  │   └── chicago/               ← Chicago Data Portal                       │
│  │                                                                           │
│  ├── silver/                    ← Dimensional models                        │
│  │   ├── company/               ← Company model tables                      │
│  │   │   ├── dims/              ← Dimensions                                │
│  │   │   └── facts/             ← Facts                                     │
│  │   ├── macro/                 ← Macro model tables                        │
│  │   ├── forecast/              ← Forecast model tables                     │
│  │   └── city_finance/          ← City finance tables                       │
│  │                                                                           │
│  └── duckdb/                    ← DuckDB database (optional)                │
│      └── analytics.db           ← Persistent DuckDB file                    │
└─────────────────────────────────────────────────────────────────────────────┘


═════════════════════════════════════════════════════════════════════════════
   CROSS-CUTTING UTILITIES (callable from any layer)
═════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                             FILTER ENGINE                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Static utility class for backend-agnostic filtering                 │   │
│  │                                                                      │   │
│  │  Methods:                                                            │   │
│  │   • apply_filters(df, filters, backend) → Filtered DF               │   │
│  │   • apply_from_session(df, filters, session)                        │   │
│  │   • build_filter_sql(filters) → SQL WHERE clause                    │   │
│  │                                                                      │   │
│  │  Filter Types:                                                       │   │
│  │   • Exact match: {'ticker': 'AAPL'}                                 │   │
│  │   • IN clause: {'ticker': ['AAPL', 'MSFT']}                         │   │
│  │   • Range: {'trade_date': {'min': '2024-01-01', 'max': '...'}}     │   │
│  │   • Operators: min, max, gt, lt, gte, lte                           │   │
│  │                                                                      │   │
│  │  Backends Supported:                                                 │   │
│  │   • Spark: Uses F.col() and DataFrame.filter()                      │   │
│  │   • DuckDB: Uses SQL WHERE clauses                                  │   │
│  │                                                                      │   │
│  │  Usage Locations:                                                    │   │
│  │   ✓ User notebooks and scripts                                      │   │
│  │   ✓ UniversalSession methods                                        │   │
│  │   ✓ Individual model methods                                        │   │
│  │   ✓ UI components                                                   │   │
│  │   ✓ Any code with a DataFrame                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

Note: FilterEngine is NOT owned by any component - it's a standalone utility
      that can be imported and used anywhere in the codebase.
```

---

## Call Flow Example: Querying Stock Prices

```
1. User Code:
   ┌────────────────────────────────────────────────────────────┐
   │ from core.context import RepoContext                       │
   │ from models.api.session import UniversalSession            │
   │ from core.session.filters import FilterEngine              │
   │                                                             │
   │ ctx = RepoContext.from_repo_root()                         │
   │ session = UniversalSession(ctx.connection, ctx.storage,    │
   │                            ctx.repo)                        │
   │                                                             │
   │ # Query with filters                                       │
   │ prices = session.get_fact_df('company', 'fact_prices')     │
   │                                                             │
   │ # Apply filters using FilterEngine (user can call directly)│
   │ filters = {'ticker': ['AAPL', 'MSFT'],                     │
   │            'trade_date': {'min': '2024-01-01'}}            │
   │ filtered = FilterEngine.apply_from_session(prices,         │
   │                                            filters, session)│
   └────────────────────────────────────────────────────────────┘
                                │
                                ↓
2. UniversalSession.get_fact_df():
   ┌────────────────────────────────────────────────────────────┐
   │ • Calls load_model('company')                              │
   │ • ModelRegistry finds company.yaml config                  │
   │ • ModelRegistry finds CompanyModel class                   │
   │ • Instantiates CompanyModel(connection, cfg, ...)         │
   │ • Injects session reference for cross-model queries       │
   │ • Caches in _models['company']                            │
   └────────────────────────────────────────────────────────────┘
                                │
                                ↓
3. CompanyModel.get_fact_df('fact_prices'):
   ┌────────────────────────────────────────────────────────────┐
   │ • Checks if model is built (_is_built flag)               │
   │ • If not built, calls build() - 3-PHASE GRAPH BUILD:      │
   │                                                            │
   │   PHASE 1: _build_nodes()                                 │
   │   ├─ For each node in graph.nodes:                        │
   │   │   ├─ Load from Bronze:                                │
   │   │   │   ├─ StorageRouter.bronze_path('prices_daily')    │
   │   │   │   └─ BronzeTable.read() → DataFrame               │
   │   │   ├─ Apply 'select' (column mapping/aliasing)         │
   │   │   └─ Apply 'derive' (computed columns)                │
   │   │                                                        │
   │   │ Result: nodes = {'dim_company': df1,                  │
   │   │                  'fact_prices': df2,                  │
   │   │                  'dim_exchange': df3}                 │
   │   │                                                        │
   │   PHASE 2: _apply_edges()                                 │
   │   ├─ For each edge in graph.edges:                        │
   │   │   ├─ Verify nodes exist                               │
   │   │   ├─ Extract join keys from 'on'                      │
   │   │   └─ Dry-run join (limit 1) to validate              │
   │   │                                                        │
   │   │ Result: All edges validated ✓                         │
   │   │                                                        │
   │   PHASE 3: _materialize_paths()                           │
   │   └─ For each path in graph.paths:                        │
   │       ├─ Parse hops: "fact_prices -> dim_company -> ..."  │
   │       ├─ Join nodes sequentially (left joins)             │
   │       └─ Handle column deduplication                      │
   │                                                            │
   │     Result: paths = {'prices_with_company': joined_df}    │
   │                                                            │
   │ • Separates dims (dim_*) and facts (fact_* + paths)       │
   │ • Caches results: _dims, _facts, _is_built = True         │
   │ • Returns cached _facts['fact_prices']                    │
   └────────────────────────────────────────────────────────────┘
                                │
                                ↓
4. FilterEngine.apply_from_session():
   ┌────────────────────────────────────────────────────────────┐
   │ • Detects backend from session.backend ('spark'/'duckdb') │
   │ • Calls _apply_spark_filters() OR _apply_duckdb_filters() │
   │   ├─ Spark: df.filter(F.col('ticker').isin(['AAPL',...])  │
   │   └─ DuckDB: df.filter("ticker IN ('AAPL', 'MSFT')")      │
   │ • Returns filtered DataFrame                               │
   └────────────────────────────────────────────────────────────┘
                                │
                                ↓
5. Result:
   ┌────────────────────────────────────────────────────────────┐
   │ Filtered DataFrame with:                                   │
   │  - Only AAPL & MSFT tickers                                │
   │  - Only dates >= 2024-01-01                                │
   │  - Ready for .to_pandas() or further operations            │
   └────────────────────────────────────────────────────────────┘
```

---

## Graph-Based Model Architecture

### Overview

de_Funk uses a **graph-based model architecture** where all models are defined declaratively in YAML using a graph structure with three key components:

1. **Nodes** - Tables (dimensions and facts) loaded from Bronze with transformations
2. **Edges** - Relationships between tables (foreign keys)
3. **Paths** - Materialized views created by joining nodes along edges

This approach provides:
- **Declarative Configuration**: Model structure in YAML, not code
- **Automatic Validation**: Edge validation ensures referential integrity
- **Join Materialization**: Complex multi-hop joins defined as paths
- **Backend Agnostic**: Same graph works with Spark or DuckDB
- **Code Reuse**: BaseModel implements all graph logic generically

### Graph Structure Example (Company Model)

```yaml
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker        # Source table in Bronze
      select:                         # Column mappings
        ticker: ticker
        company_name: name
        exchange_code: exchange_code
      derive:                         # Computed columns
        company_id: "sha1(ticker)"
      tags: [dim, entity]
      unique_key: [ticker]

    - id: fact_prices
      from: bronze.prices_daily
      select:
        trade_date: trade_date
        ticker: ticker
        open: open
        close: close
        volume: volume
      tags: [fact, prices]

    - id: dim_exchange
      from: bronze.exchanges
      select:
        exchange_code: code
        exchange_name: name
      tags: [dim, ref]

  edges:                             # Define relationships
    - from: fact_prices
      to: dim_company
      on: ["ticker=ticker"]
      type: many_to_one
      description: "Prices belong to a company"

    - from: dim_company
      to: dim_exchange
      on: ["exchange_code=exchange_code"]
      type: many_to_one
      description: "Company lists on an exchange"

  paths:                             # Multi-hop joins
    - id: prices_with_company
      hops: "fact_prices -> dim_company -> dim_exchange"
      description: "Prices with full company and exchange context"
      tags: [canonical, analytics]
```

### 3-Phase Graph Building Process

When a model is first accessed, BaseModel executes a 3-phase build process:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Build Nodes                                                    │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  For each node in graph.nodes:                                           │
│    1. Load source table from Bronze                                      │
│       ├─ StorageRouter resolves logical name → physical path             │
│       └─ BronzeTable.read() loads Parquet files                          │
│                                                                           │
│    2. Apply 'select' transformations                                     │
│       ├─ Column selection (keep only specified columns)                  │
│       ├─ Column renaming (alias columns)                                 │
│       └─ Backend-agnostic (works with Spark or DuckDB)                   │
│                                                                           │
│    3. Apply 'derive' transformations                                     │
│       ├─ Computed columns (e.g., SHA1 hash, concatenation)               │
│       ├─ Expression evaluation                                           │
│       └─ Support for: sha1(), concat(), column refs, etc.                │
│                                                                           │
│    4. Store in nodes dictionary: nodes[node_id] = DataFrame              │
│                                                                           │
│  Result: Dictionary of node_id → DataFrame                               │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: Validate Edges                                                 │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  For each edge in graph.edges:                                           │
│    1. Verify both nodes exist                                            │
│       ├─ Check 'from' node in nodes dictionary                           │
│       └─ Check 'to' node in nodes dictionary                             │
│                                                                           │
│    2. Extract join keys from 'on' specification                          │
│       ├─ Parse format: ["ticker=ticker", "date=date"]                    │
│       └─ Or infer from common columns                                    │
│                                                                           │
│    3. Dry-run validation join                                            │
│       ├─ Join left.limit(1) with right.limit(1)                          │
│       ├─ Check join columns exist                                        │
│       ├─ Verify join executes without error                              │
│       └─ Raise ValueError if validation fails                            │
│                                                                           │
│  Result: All edges validated, referential integrity confirmed            │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Materialize Paths                                              │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  For each path in graph.paths:                                           │
│    1. Parse hops specification                                           │
│       ├─ String format: "fact_prices -> dim_company -> dim_exchange"     │
│       └─ Or list format: ["fact_prices", "dim_company", "dim_exchange"]  │
│                                                                           │
│    2. Execute sequential joins                                           │
│       ├─ Start with first node: df = nodes[fact_prices]                  │
│       │                                                                   │
│       ├─ For each hop:                                                   │
│       │   ├─ Get right DataFrame: nodes[dim_company]                     │
│       │   ├─ Find edge definition for join keys                          │
│       │   ├─ Execute left join with dedupe strategy                      │
│       │   └─ Prefix duplicate columns (e.g., dim_company__name)          │
│       │                                                                   │
│       └─ Continue joining remaining nodes in chain                       │
│                                                                           │
│    3. Store in paths dictionary: paths[path_id] = joined_df              │
│                                                                           │
│  Result: Dictionary of path_id → Materialized view DataFrame             │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ↓
                            ┌────────────────────┐
                            │  Separate by Type  │
                            │                    │
                            │  dims = nodes      │
                            │    where id starts │
                            │    with "dim_"     │
                            │                    │
                            │  facts = nodes +   │
                            │    paths where id  │
                            │    starts with     │
                            │    "fact_"         │
                            └────────────────────┘
```

### Benefits of Graph-Based Architecture

1. **Declarative**: Model structure in YAML, minimal code
2. **Validation**: Automatic referential integrity checking
3. **Reusability**: BaseModel implements graph logic once for all models
4. **Maintainability**: Change table relationships without code changes
5. **Documentation**: Graph structure is self-documenting
6. **Flexibility**: Easy to add new nodes, edges, or paths
7. **Backend Agnostic**: Same graph works with Spark or DuckDB
8. **Type Safety**: Edge validation catches schema mismatches early

### Node Types and Naming Conventions

- **Dimensions** (`dim_*`): Entity tables with unique keys
  - Examples: `dim_company`, `dim_exchange`, `dim_calendar`
  - Loaded from Bronze reference tables
  - Typically small lookup tables

- **Facts** (`fact_*`): Event/transaction tables
  - Examples: `fact_prices`, `fact_news`, `fact_unemployment`
  - Loaded from Bronze event tables
  - Typically large timeseries data

- **Paths** (any name): Materialized joins
  - Examples: `prices_with_company`, `news_with_company`
  - Created by joining nodes along edges
  - Stored as facts (queryable like any fact table)

---

## Component Responsibilities

### **RepoContext** (Entry Point)
- **Purpose**: Bootstrap application environment
- **Responsibilities**:
  - Locate repository root
  - Load configuration files
  - Create database connection (Spark or DuckDB)
  - Return initialized context
- **Used by**: User scripts, notebooks, UI, tests

### **UniversalSession** (Orchestrator)
- **Purpose**: Single interface for all model access
- **Responsibilities**:
  - Dynamic model loading via registry
  - Cross-model queries and joins
  - Session injection for model dependencies
  - Backend detection (Spark/DuckDB)
  - Model instance caching
- **Key Feature**: Model-agnostic API - works with any model

### **ModelRegistry** (Discovery)
- **Purpose**: Catalog and instantiate models
- **Responsibilities**:
  - Discover YAML configs in `configs/models/`
  - Load model configurations
  - Map model names to Python classes
  - Lazy-import model classes
  - Provide model metadata (tables, measures, schema)
- **Registration**: Automatic by convention or manual
- **Ownership**: Created and owned by UniversalSession

### **FilterEngine** (Cross-Cutting Utility)
- **Purpose**: Backend-agnostic filtering
- **Responsibilities**:
  - Detect backend type from session
  - Apply filters (exact, range, IN clause)
  - Translate filters to Spark or DuckDB syntax
  - Build SQL WHERE clauses
- **Key Characteristic**: **Standalone static utility** - not owned by any component
- **Usage**: Can be imported and called from anywhere:
  - User notebooks
  - UniversalSession
  - Individual models
  - UI components
  - Any code with a DataFrame
- **Benefits**: Eliminates code duplication across codebase

### **BaseModel** (Graph-Based Model Foundation)
- **Purpose**: Generic graph-based model implementation
- **Responsibilities**:
  - **Graph Building**: 3-phase YAML-driven graph construction
    - Phase 1: Build nodes from Bronze with transformations
    - Phase 2: Validate edges (referential integrity)
    - Phase 3: Materialize paths (multi-hop joins)
  - **Node Loading**: Read from Bronze, apply select/derive transformations
  - **Edge Validation**: Dry-run joins to verify relationships
  - **Path Materialization**: Execute multi-table joins with column deduplication
  - **Table Caching**: Lazy loading with in-memory caching
  - **Backend Abstraction**: Transparent Spark/DuckDB support
  - **Metadata**: Expose relations, measures, schema from YAML
- **Pattern**: All models inherit from BaseModel
- **Key Innovation**: Graph structure defined in YAML, not code

### **Specific Models** (Domain Logic)
- **CompanyModel**: Stock market data (Polygon.io)
- **MacroModel**: Economic indicators (BLS)
- **ForecastModel**: ML predictions (trained on Company)
- **CityFinanceModel**: Municipal data (Chicago Data Portal)
- **Responsibilities**:
  - Implement domain-specific hooks
  - Override build steps if needed
  - Provide custom methods
  - Define YAML configuration

### **StorageRouter** (Path Resolution)
- **Purpose**: Resolve logical names to physical paths
- **Responsibilities**:
  - Map table names to file paths
  - Handle Bronze vs Silver storage
  - Support multiple storage roots
  - Enable storage abstraction

### **BronzeTable / SilverPath** (Data Access)
- **Purpose**: Read data from physical storage
- **Responsibilities**:
  - Abstract Parquet file reading
  - Handle schema merging (Bronze)
  - Support DataFrame caching (Silver)
  - Provide clean API for data loading

---

## Data Flow Patterns

### **Ingestion Models** (Bronze → Silver)
```
API/Source → Ingestor → Bronze Storage
                           ↓
                    Model.build()
                     (transforms)
                           ↓
                    Silver Storage
```
**Examples**: Company, Macro, CityFinance

### **Analytics Models** (Silver → Silver)
```
Silver Storage (Input) → Model.build()
                           ↓
                    Silver Storage (Output)
```
**Examples**: Forecast

### **Query Pattern**
```
User → UniversalSession → Model → StorageRouter → Physical Storage
         ↓                  ↓            ↑
    FilterEngine      Cached DFs        │
         │                               │
         └───────────────────────────────┘
    (FilterEngine can be called anywhere in the flow)
```

---

## Key Design Principles

1. **Graph-Based Architecture**: Models defined as graphs (nodes, edges, paths) in YAML
2. **Declarative Configuration**: Model structure in YAML, not imperative code
3. **3-Phase Build Process**: Nodes → Edges → Paths with validation at each stage
4. **Lazy Loading**: Models and graphs built only when first accessed
5. **Caching**: Loaded models, nodes, and paths cached in memory
6. **Backend Agnostic**: Same graph works with Spark or DuckDB transparently
7. **Referential Integrity**: Edge validation ensures joins are valid before materialization
8. **Path Materialization**: Complex multi-hop joins defined declaratively and auto-executed
9. **Cross-Model Access**: Models can query other models via session injection
10. **Filter Centralization**: Single FilterEngine utility for all filtering logic
11. **Convention Over Configuration**: Auto-discovery of models by naming convention
12. **Utility Pattern**: FilterEngine is a standalone cross-cutting utility

---

## Configuration Files

### **storage.json**
```json
{
  "connection": {"type": "spark"},
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  },
  "tables": {
    "prices_daily": {"rel": "polygon/prices_daily"},
    "news": {"rel": "polygon/news"},
    ...
  }
}
```

### **Model YAML** (e.g., `configs/models/company.yaml`)
```yaml
model: company
version: 1
tags: [equities, polygon, us]

depends_on:
  - core

storage:
  root: storage/silver/company
  format: parquet

schema:
  dimensions:
    dim_company:
      path: dims/dim_company
      columns: {ticker: string, company_name: string, ...}
      primary_key: [ticker]

  facts:
    fact_prices:
      path: facts/fact_prices
      columns: {trade_date: date, ticker: string, ...}
      partitions: [trade_date]

graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      select: {...}

  edges:
    - from: fact_prices
      to: dim_company
      on: ["ticker=ticker"]

  paths:
    - id: prices_with_company
      hops: "fact_prices -> dim_company -> dim_exchange"
```

---

## Extension Points

### Adding a New Model

1. **Create YAML**: `configs/models/your_model.yaml`
2. **Create Python Class** (optional): `models/implemented/your_model/model.py`
3. **Inherit BaseModel**: Implement hooks if needed
4. **Access via Session**: `session.load_model('your_model')`

### Adding Cross-Model Queries

```python
class YourModel(BaseModel):
    def after_build(self, dims, facts):
        # Access other models via self.session
        calendar = self.session.get_dimension_df('core', 'dim_calendar')

        # Join with your data
        enriched = facts['your_fact'].join(calendar, on='date')

        return dims, facts
```

### Using FilterEngine Anywhere

```python
# Import and use FilterEngine from any layer
from core.session.filters import FilterEngine

# Define filters
filters = {
    'ticker': ['AAPL', 'MSFT'],
    'volume': {'min': 1000000},
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
}

# Option 1: Use with session (auto-detects backend)
filtered_df = FilterEngine.apply_from_session(df, filters, session)

# Option 2: Specify backend explicitly
filtered_df = FilterEngine.apply_filters(df, filters, backend='spark')

# Option 3: Build SQL for manual queries
where_clause = FilterEngine.build_filter_sql(filters)
# Returns: "ticker IN ('AAPL', 'MSFT') AND volume >= 1000000 AND ..."
```

---

This architecture provides a clean separation of concerns, enables code reuse, and supports both Spark and DuckDB backends transparently. FilterEngine is positioned as a true utility that any component can leverage, rather than being owned by a specific layer.

---

## Markdown Notebook Syntax

de_Funk supports **markdown-based notebooks** with embedded YAML front matter, dynamic filters, and interactive visualizations. This provides a declarative, version-control-friendly way to build analytics notebooks.

### Document Structure

```markdown
---
# YAML Front Matter
id: my_notebook
title: "My Analytics Notebook"
models: [company, macro]
---

# Notebook Content

Regular markdown content here...

$filters${
  # Filter definitions
}

More markdown...

$exhibits${
  # Visualization definitions
}
```

---

## `$filters$` Syntax

The `$filters${}` block defines **dynamic filters** that render in the sidebar and allow users to interactively filter data. Filters can pull options dynamically from the database and support fuzzy matching, range selections, and more.

### Filter Block Structure

```markdown
$filters${
  # Filter 1
  ---
  # Filter 2
  ---
  # Filter 3
}
```

Each filter is defined in YAML and separated by `---`.

### Basic Filter Example

```yaml
id: ticker
label: Stock Tickers
multi: true
default: ["AAPL", "MSFT"]
```

This creates a multi-select dropdown for the `ticker` column with default selections.

### Filter Types

#### 1. **Select Filter** (Single or Multi-Select)

```yaml
id: ticker
type: select
label: Select Stocks
multi: true  # Allow multiple selections
required: false
placeholder: Choose tickers...
help_text: Select one or more stock tickers
```

**With Dynamic Options from Database:**

```yaml
id: ticker
label: Stock Tickers
source: {model: company, table: dim_company, column: ticker}
multi: true
```

**Short form:**

```yaml
id: ticker
label: Stock Tickers
source: company.dim_company.ticker
multi: true
```

**With Static Options:**

```yaml
id: market_cap_bucket
label: Market Cap
type: select
options: ["Small Cap", "Mid Cap", "Large Cap", "Mega Cap"]
multi: false
```

#### 2. **Date Range Filter**

```yaml
id: trade_date
type: date_range
label: Date Range
operator: between
default: {start: "2024-01-01", end: "2024-12-31"}
help_text: Select date range for analysis
```

**With Relative Dates:**

```yaml
id: trade_date
type: date_range
label: Date Range
default: {start: "-30d", end: "today"}
```

#### 3. **Number Range Filter**

```yaml
id: volume
type: number_range
label: Volume Range
operator: between
min_value: 0
max_value: 100000000
step: 1000000
default: {min: 1000000, max: 50000000}
```

#### 4. **Slider Filter**

```yaml
id: confidence_threshold
type: slider
label: Confidence Threshold
min_value: 0.0
max_value: 1.0
step: 0.1
default: 0.8
```

#### 5. **Text Search Filter**

```yaml
id: company_name
type: text_search
label: Search Company
operator: contains
placeholder: Type to search...
fuzzy_enabled: true
fuzzy_threshold: 0.7
```

**Fuzzy Matching:**

```yaml
id: ticker_search
type: text_search
label: Find Ticker
operator: fuzzy
fuzzy_enabled: true
fuzzy_threshold: 0.6  # 0-1 similarity threshold
help_text: Fuzzy match ticker symbols
```

#### 6. **Boolean Filter**

```yaml
id: is_active
type: boolean
label: Active Only
default: true
```

### Filter Operators

Filters support various comparison operators:

```yaml
id: close_price
label: Close Price
operator: gte  # Greater than or equal
min_value: 0
default: 100
```

**Available Operators:**
- `equals` - Exact match
- `not_equals` - Not equal
- `in` - In list (default for multi-select)
- `not_in` - Not in list
- `gt` - Greater than
- `gte` - Greater than or equal
- `lt` - Less than
- `lte` - Less than or equal
- `between` - Between two values (for ranges)
- `contains` - String contains
- `starts_with` - String starts with
- `ends_with` - String ends with
- `fuzzy` - Fuzzy text matching

### Advanced Filter Features

#### Applying Filters to Different Columns

```yaml
id: stock_filter
label: Stock Selection
source: company.dim_company.ticker
apply_to: stock_ticker  # Apply to different column name
multi: true
```

#### Required Filters

```yaml
id: trade_date
type: date_range
label: Date Range
required: true
default: {start: "2024-01-01", end: "2024-12-31"}
```

#### Filter Source Configuration

**Full specification:**

```yaml
id: ticker
label: Stock Tickers
source:
  model: company
  table: dim_company
  column: ticker
  distinct: true  # Get unique values
  sort: true      # Sort alphabetically
  limit: 100      # Limit to top 100
```

### Complete Filter Examples

**Example 1: Stock Analysis Filters**

```markdown
$filters${
id: ticker
label: Stock Tickers
source: company.dim_company.ticker
multi: true
default: ["AAPL", "MSFT", "GOOGL"]
---
id: trade_date
type: date_range
label: Analysis Period
operator: between
default: {start: "-90d", end: "today"}
---
id: min_volume
type: number_range
label: Minimum Volume
operator: gte
default: 1000000
help_text: Filter by trading volume
}
```

**Example 2: Economic Indicators**

```markdown
$filters${
id: series_id
label: Economic Series
source: macro.dim_economic_series.series_id
multi: true
---
id: date_range
type: date_range
label: Time Period
default: {start: "2020-01-01", end: "today"}
---
id: search_series
type: text_search
label: Search Series
operator: fuzzy
fuzzy_enabled: true
placeholder: Search for indicators...
}
```

---

## `$exhibits$` Syntax

The `$exhibits${}` block defines **interactive visualizations** that are rendered inline in the notebook. Exhibits can be charts, tables, metric cards, or custom components.

### Exhibit Block Structure

```markdown
$exhibits${
type: line_chart
title: "Stock Prices Over Time"
# ... configuration
}
```

### Exhibit Types

#### 1. **Metric Cards**

Display key metrics as cards with optional comparisons.

```yaml
type: metric_cards
title: "Key Metrics"
source: company.fact_prices
metrics:
  - measure: close
    label: "Average Close"
    aggregation: avg
  - measure: volume
    label: "Total Volume"
    aggregation: sum
  - measure: volume_weighted
    label: "VWAP"
    aggregation: avg
```

**With Comparisons:**

```yaml
type: metric_cards
source: company.fact_prices
metrics:
  - measure: close
    label: "Close Price"
    aggregation: avg
    comparison:
      period: previous  # or: year_ago, custom
      label: "vs. Previous Period"
```

#### 2. **Line Chart**

Time series visualization.

```yaml
type: line_chart
title: "Stock Price Trends"
source: company.fact_prices
x: trade_date
x_label: "Date"
y: close
y_label: "Close Price ($)"
color: ticker
legend: true
interactive: true
```

**With Multiple Y-Axes:**

```yaml
type: line_chart
title: "Price vs Volume"
source: company.fact_prices
x: trade_date
y: close
y_label: "Price"
y2: volume
y2_label: "Volume"
color: ticker
```

**Streamlined Syntax (shorthand):**

```yaml
type: line_chart
title: "Prices"
source: company.fact_prices
x: trade_date
y: close
color: ticker
```

#### 3. **Bar Chart**

Categorical comparisons.

```yaml
type: bar_chart
title: "Average Price by Stock"
source: company.fact_prices
x: ticker
y: close
aggregation: avg
sort: {by: y, order: desc}
```

**Grouped Bar Chart:**

```yaml
type: bar_chart
title: "Quarterly Revenue"
source: company.fact_prices
x: year_quarter
y: volume
color: ticker
```

#### 4. **Scatter Chart**

Correlation analysis.

```yaml
type: scatter_chart
title: "Price vs Volume Correlation"
source: company.fact_prices
x: volume
y: close
color: ticker
size: volume_weighted
interactive: true
```

#### 5. **Heatmap**

Matrix visualization for correlations or pivot data.

```yaml
type: heatmap
title: "Price Correlation Matrix"
source: company.fact_prices
x: ticker
y: trade_date
value: close
aggregation: avg
```

#### 6. **Data Table**

Interactive data table with sorting, pagination, and download.

```yaml
type: data_table
title: "Stock Prices"
source: company.fact_prices
columns:
  - ticker
  - trade_date
  - open
  - high
  - low
  - close
  - volume
pagination: true
page_size: 50
sortable: true
searchable: true
download: true
sort: {by: trade_date, order: desc}
```

#### 7. **Pivot Table**

Cross-tabulation analysis.

```yaml
type: pivot_table
title: "Average Prices by Stock and Quarter"
source: company.fact_prices
rows: [ticker]
columns: [year_quarter]
values: [close]
aggregation: avg
```

#### 8. **Dual Axis Chart**

Two measures with different scales.

```yaml
type: dual_axis_chart
title: "Price and Volume Trends"
source: company.fact_prices
x: trade_date
y: close
y_label: "Price ($)"
y2: volume
y2_label: "Volume"
color: ticker
```

#### 9. **Weighted Aggregate Chart**

Multi-stock indices with custom weighting.

```yaml
type: weighted_aggregate_chart
title: "Market Cap Weighted Index"
source: company.fact_prices
x: trade_date
y: close
weighting: market_cap
aggregate_by: trade_date
group_by: [trade_date]
value_measures: [close]
```

**Weighting Methods:**
- `equal` - Equal weighting
- `market_cap` - Market cap weighted
- `volume` - Volume weighted
- `price` - Price weighted
- `volatility` - Inverse volatility weighted

#### 10. **Forecast Chart**

ML predictions with confidence intervals.

```yaml
type: forecast_chart
title: "Price Forecasts"
source: forecast.forecast_price
x: prediction_date
y: predicted_close
lower_bound: lower_bound
upper_bound: upper_bound
color: ticker
```

### Interactive Features

#### Dynamic Measure Selection

Allow users to choose which measures to display.

```yaml
type: line_chart
title: "Stock Metrics"
source: company.fact_prices
x: trade_date
measure_selector:
  available_measures: [close, open, high, low, volume_weighted]
  default_measures: [close]
  label: "Select Metrics"
  allow_multiple: true
  selector_type: checkbox
  help_text: "Choose metrics to display"
color: ticker
```

**Selector Types:**
- `checkbox` - Multiple selection checkboxes
- `dropdown` - Dropdown menu
- `radio` - Single selection radio buttons

#### Dynamic Dimension Selection

Allow users to choose grouping dimension.

```yaml
type: bar_chart
title: "Average Metrics"
source: company.fact_prices
y: close
aggregation: avg
dimension_selector:
  available_dimensions: [ticker, exchange_code, year_quarter]
  default_dimension: ticker
  label: "Group By"
  selector_type: radio
  applies_to: x  # or: color, size
```

### Collapsible Exhibits

Wrap exhibits in collapsible sections.

```yaml
type: line_chart
title: "Detailed Price Analysis"
source: company.fact_prices
x: trade_date
y: close
color: ticker
collapsible: true
collapsible_title: "Price Details"
collapsible_expanded: false
nest_in_expander: true
```

### Exhibit Filters

Apply exhibit-specific filters (in addition to notebook-level filters).

```yaml
type: line_chart
title: "Top Tech Stocks"
source: company.fact_prices
x: trade_date
y: close
color: ticker
filters:
  ticker: ["AAPL", "MSFT", "GOOGL", "AMZN"]
  volume: {min: 1000000}
```

### Custom Components

Render custom Streamlit components.

```yaml
type: custom_component
title: "Custom Analysis"
component: my_custom_component
params:
  model: company
  table: fact_prices
  custom_param: value
options:
  height: 600
  scrolling: true
```

### Complete Exhibit Examples

**Example 1: Stock Dashboard**

```markdown
$exhibits${
type: metric_cards
title: "Market Summary"
source: company.fact_prices
metrics:
  - measure: close
    label: "Avg Close"
    aggregation: avg
  - measure: volume
    label: "Total Volume"
    aggregation: sum
  - measure: ticker
    label: "# Stocks"
    aggregation: count
}

$exhibits${
type: line_chart
title: "Stock Price Trends"
source: company.fact_prices
x: trade_date
y: close
color: ticker
legend: true
interactive: true
measure_selector:
  available_measures: [close, open, high, low]
  default_measures: [close]
  allow_multiple: true
}

$exhibits${
type: data_table
title: "Recent Prices"
source: company.fact_prices
columns: [trade_date, ticker, open, high, low, close, volume]
pagination: true
page_size: 20
sortable: true
download: true
sort: {by: trade_date, order: desc}
}
```

**Example 2: Economic Dashboard**

```markdown
$exhibits${
type: line_chart
title: "Unemployment Rate"
source: macro.fact_unemployment
x: date
y: value
color: series_id
collapsible: true
collapsible_title: "Unemployment Trends"
}

$exhibits${
type: bar_chart
title: "CPI Changes"
source: macro.fact_cpi
x: year
y: value
aggregation: avg
color: series_id
sort: {by: year, order: asc}
}
```

---

## Markdown Notebook Best Practices

### 1. **Organization**

```markdown
---
id: stock_analysis
title: "Stock Market Analysis"
models: [company, macro, core]
---

# Executive Summary

High-level findings...

$filters${
  # User controls here
}

# Market Overview

$exhibits${
  # Summary metrics
}

<details>
<summary>Deep Dive Analysis</summary>

Additional analysis...

$exhibits${
  # Detailed charts
}

</details>
```

### 2. **Filter Design**

- **Start with most important filters** (e.g., date range, primary dimension)
- **Use sensible defaults** that work for most users
- **Add help text** for complex filters
- **Enable fuzzy search** for large option lists
- **Set `required: true`** for critical filters

### 3. **Exhibit Design**

- **Start with summary metrics** (metric cards)
- **Follow with primary visualization** (line chart, bar chart)
- **Provide detailed views** in collapsible sections
- **Enable interactivity** for exploration (measure selectors, dimension selectors)
- **Include data tables** for export and detailed review
- **Use consistent color schemes** across exhibits

### 4. **Performance**

- **Limit date ranges** in defaults (e.g., `-90d` to `today`)
- **Add `limit` to filter sources** with many options
- **Use pagination** for large tables
- **Apply exhibit-level filters** to reduce data size
- **Leverage caching** via model build system

---

## Parsing Implementation

The markdown parser (`app/notebook/parsers/markdown_parser.py`) uses regex patterns to extract and parse:

1. **Front Matter**: `^---\s*\n(.*?)\n---\s*\n`
2. **Filters**: `\$filters?\$\{\s*\n(.*?)\n\}`
3. **Exhibits**: `\$exhibits?\$\{\s*\n(.*?)\n\}`
4. **Collapsible Sections**: `<details>\s*<summary>(.*?)</summary>\s*(.*?)</details>`

Each block is parsed into typed dataclass instances:
- **Filters** → `FilterConfig` objects in `FilterCollection`
- **Exhibits** → `Exhibit` objects with `ExhibitType` enum
- **Content** → Mixed list of markdown blocks, exhibits, and collapsible sections

The parser supports:
- **Streamlined syntax**: Shorthand properties (e.g., `x` instead of `x_axis`)
- **Auto-detection**: Infers types from operators and IDs
- **Error handling**: Continues parsing on errors, adds error blocks
- **Nesting**: Exhibits can be nested in `<details>` tags

---
