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
└──────┬───────────────────────────────────┬──────────────────────────────────┘
       │                                   │
       │                                   │
       ↓                                   ↓
┌──────────────────────┐      ┌────────────────────────────────────────┐
│   MODEL REGISTRY     │      │       FILTER ENGINE                    │
│  ┌──────────────┐    │      │  ┌──────────────────────────────────┐ │
│  │ Discovers &  │    │      │  │ Backend-agnostic filters         │ │
│  │ Loads Models │    │      │  │                                  │ │
│  │              │    │      │  │ Methods:                         │ │
│  │ Sources:     │    │      │  │  • apply_filters(df, filters,   │ │
│  │  - YAML      │    │      │  │      backend) → Filtered DF     │ │
│  │    configs   │    │      │  │  • apply_from_session(...)      │ │
│  │  - Python    │    │      │  │  • build_filter_sql(...)        │ │
│  │    classes   │    │      │  │                                  │ │
│  │              │    │      │  │ Supports:                        │ │
│  │ Returns:     │    │      │  │  - Exact match                   │ │
│  │  - ModelCfg  │    │      │  │  - IN clause                     │ │
│  │  - ModelCls  │    │      │  │  - Range filters                 │ │
│  └──────────────┘    │      │  │  - Spark & DuckDB backends       │ │
└──────────────────────┘      │  └──────────────────────────────────┘ │
                              └────────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MODEL LAYER: BaseModel                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ BaseModel(connection, storage_cfg, model_cfg, params)              │   │
│  │                                                                      │   │
│  │  Properties:                                                         │   │
│  │   • connection: Database connection                                 │   │
│  │   • model_cfg: YAML configuration                                   │   │
│  │   • storage_router: StorageRouter instance                          │   │
│  │   • backend: 'spark' or 'duckdb'                                    │   │
│  │   • _dims: Cached dimensions                                        │   │
│  │   • _facts: Cached facts                                            │   │
│  │                                                                      │   │
│  │  Lifecycle:                                                          │   │
│  │   1. build() → Builds graph from YAML                               │   │
│  │      • _build_nodes() - Read Bronze, transform                      │   │
│  │      • _apply_edges() - Validate relationships                      │   │
│  │      • _materialize_paths() - Create joined views                   │   │
│  │   2. get_table(name) → Returns DataFrame                            │   │
│  │   3. get_dimension_df(id) → Returns dimension                       │   │
│  │   4. get_fact_df(id) → Returns fact                                 │   │
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
```

---

## Call Flow Example: Querying Stock Prices

```
1. User Code:
   ┌────────────────────────────────────────────────────────────┐
   │ from core.context import RepoContext                       │
   │ from models.api.session import UniversalSession            │
   │                                                             │
   │ ctx = RepoContext.from_repo_root()                         │
   │ session = UniversalSession(ctx.connection, ctx.storage,    │
   │                            ctx.repo)                        │
   │                                                             │
   │ # Query with filters                                       │
   │ prices = session.get_fact_df('company', 'fact_prices')     │
   │ filters = {'ticker': ['AAPL', 'MSFT'],                     │
   │            'trade_date': {'min': '2024-01-01'}}            │
   │                                                             │
   │ from core.session.filters import FilterEngine              │
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
   │ • If not built, calls build()                             │
   │   ├─ _build_nodes() - Read from Bronze                    │
   │   │   ├─ StorageRouter.bronze_path('prices_daily')        │
   │   │   ├─ BronzeTable.read() → Spark/DuckDB DataFrame      │
   │   │   └─ Apply transformations from YAML graph.nodes      │
   │   │                                                        │
   │   ├─ _apply_edges() - Validate relationships              │
   │   │   └─ Check foreign keys between tables                │
   │   │                                                        │
   │   └─ _materialize_paths() - Create joined views           │
   │       └─ Build prices_with_company (price + dims)         │
   │                                                            │
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

### **FilterEngine** (Query Optimization)
- **Purpose**: Backend-agnostic filtering
- **Responsibilities**:
  - Detect backend type from session
  - Apply filters (exact, range, IN clause)
  - Translate filters to Spark or DuckDB syntax
  - Build SQL WHERE clauses
- **Benefits**: Eliminates code duplication across codebase

### **BaseModel** (Model Foundation)
- **Purpose**: Generic model implementation
- **Responsibilities**:
  - YAML-driven graph building
  - Node loading from Bronze
  - Edge validation (foreign keys)
  - Path materialization (joins)
  - Table caching
  - Backend abstraction
- **Pattern**: All models inherit from BaseModel

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
         ↓                  ↓
    FilterEngine      Cached DataFrames
```

---

## Key Design Principles

1. **Lazy Loading**: Models built only when first accessed
2. **Caching**: Loaded models and DataFrames cached in memory
3. **Backend Agnostic**: Works with Spark or DuckDB transparently
4. **YAML-Driven**: Model structure defined in configs, not code
5. **Cross-Model Access**: Models can query other models via session injection
6. **Filter Centralization**: Single FilterEngine for all filtering logic
7. **Convention Over Configuration**: Auto-discovery of models by naming convention

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

### Custom Filtering

```python
# Extend FilterEngine for complex filters
filters = {
    'ticker': ['AAPL', 'MSFT'],
    'volume': {'min': 1000000},
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
}

filtered_df = FilterEngine.apply_filters(df, filters, backend='spark')
```

---

This architecture provides a clean separation of concerns, enables code reuse, and supports both Spark and DuckDB backends transparently.
