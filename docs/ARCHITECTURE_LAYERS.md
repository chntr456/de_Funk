# de_Funk Architecture Layers - Visual Reference

## Layer Stack (Top to Bottom)

```
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATIONS LAYER                        │
│  (Notebooks, UI, Reports, Scripts)                         │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│            ORCHESTRATION LAYER (UniversalSession)          │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ ModelRegistry│ │ ModelGraph   │ │ FilterEngine       │  │
│  │ (Discovery)  │ │ (Dependencies)│ │ (Filter Pushdown)  │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│                                                              │
│  Model Lifecycle:                                           │
│  1. Load model config from registry                        │
│  2. Instantiate model class                                │
│  3. Inject session for cross-model access                  │
│  4. Cache model instance                                   │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│         MODEL FRAMEWORK LAYER (BaseModel + Subclasses)     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ BaseModel                                           │   │
│  │                                                     │   │
│  │ Graph-Based Construction:                         │   │
│  │ 1. _build_nodes()    → Load from Bronze           │   │
│  │ 2. _apply_edges()    → Validate joins             │   │
│  │ 3. _materialize_paths() → Create views           │   │
│  │ 4. after_build()     → Post-processing            │   │
│  │                                                     │   │
│  │ Properties:                                        │   │
│  │ - measures (MeasureExecutor)                       │   │
│  │ - query_planner (GraphQueryPlanner)               │   │
│  │ - storage_router (StorageRouter)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Domain-Specific Models (CompanyModel, etc.)        │    │
│  │ - Inherit from BaseModel                           │    │
│  │ - Override: custom_node_loading()                  │    │
│  │ - Override: after_build()                          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│            COMPUTE LAYER (Measures & Queries)              │
│                                                              │
│  ┌──────────────────┐ ┌──────────────────────────────────┐  │
│  │ MeasureExecutor  │ │ GraphQueryPlanner                │  │
│  │                  │ │                                  │  │
│  │ Registry-based   │ │ Dynamic join planning:           │  │
│  │ measure dispatch │ │ 1. Find join paths (NetworkX)   │  │
│  │                  │ │ 2. Check materialized views     │  │
│  │ Types:           │ │ 3. Build dynamic joins          │  │
│  │ - Simple         │ │ 4. Apply filters (pushdown)    │  │
│  │ - Computed       │ └──────────────────────────────────┘  │
│  │ - Weighted       │                                       │
│  │ - Window         │ ┌──────────────────────────────────┐  │
│  │ - Ratio          │ │ FilterEngine                      │  │
│  │ - Custom         │ │                                  │  │
│  └──────────────────┘ │ Spark: DataFrame API            │  │
│                       │ DuckDB: SQL strings              │  │
│                       └──────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│            BACKEND ADAPTER LAYER                           │
│                                                              │
│  ┌─────────────────────┐ ┌─────────────────────────────┐   │
│  │ SparkAdapter        │ │ DuckDBAdapter               │   │
│  │                     │ │                             │   │
│  │ - DataFrame API     │ │ - SQL Execution             │   │
│  │ - PySpark F.col()   │ │ - Connection.execute()      │   │
│  │ - F.join(), F.agg() │ │ - Relation-based API        │   │
│  └─────────────────────┘ └─────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────┐
│              STORAGE LAYER                                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Storage Router                                       │  │
│  │ - Logical table → Physical path mapping             │  │
│  │ - Bronze paths: {root}/bronze/{provider}/{table}   │  │
│  │ - Silver paths: {root}/silver/{model}/{table}      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────┐ ┌───────────────────────────────┐   │
│  │ Bronze Layer     │ │ Silver Layer                  │   │
│  │                  │ │                               │   │
│  │ Raw Data:        │ │ Dimensional Models:           │   │
│  │ - Polygon APIs   │ │ - Dims (star schema)         │   │
│  │ - BLS APIs       │ │ - Facts (fact tables)        │   │
│  │ - Chicago APIs   │ │ - Paths (materialized views) │   │
│  │                  │ │                               │   │
│  │ Format: Parquet  │ │ Format: Parquet (optimized)  │   │
│  │ Schema: Raw      │ │ Schema: Dimensional          │   │
│  └──────────────────┘ └───────────────────────────────┘   │
│                                                              │
│  Parquet Optimizations (DuckDB-tuned):                     │
│  - Few large files (1-5) vs 200+ tiny files               │
│  - Sorted by query columns (zone maps)                    │
│  - Snappy compression (fast)                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Query
    │
    ▼
UniversalSession.get_table()
    │
    ├─→ Load model from registry (if needed)
    ├─→ Inject session into model
    ├─→ Check if columns exist in base table
    │
    ├─ (Column exists) ──→ Get table, apply filters, select columns
    │
    ├─ (Column missing) ──→ Check for materialized view
    │                          │
    │                          ├─ (Found) ──→ Use cached view
    │                          │
    │                          └─ (Not found) ──→ Plan joins
    │                                                │
    │                                                ├─ Build column index
    │                                                ├─ Find target tables
    │                                                ├─ Traverse edges
    │                                                └─ Execute joins
    │
    ├─→ Apply aggregation (if group_by specified)
    │
    ▼
Return DataFrame/Relation
```

## Measure Execution Flow

```
model.calculate_measure('avg_close_price', entity_column='ticker')
    │
    ▼
MeasureExecutor.execute_measure()
    │
    ├─→ Get measure config from model.model_cfg
    ├─→ MeasureRegistry.create_measure()
    │       │
    │       ├─ Determine measure type
    │       ├─ Look up in registry
    │       └─ Instantiate measure class
    │
    ├─→ Check auto_enrich flag
    │   (Automatic column enrichment if needed)
    │
    ├─→ measure.to_sql(adapter)
    │   (Generate SQL for the measure)
    │
    ├─→ adapter.execute_sql()
    │   │
    │   ├─ Spark: Build DataFrame operations
    │   └─ DuckDB: Execute SQL string
    │
    ▼
QueryResult(data, query_time_ms, rows)
```

## Cross-Model Query Flow

```
session.get_table('forecast', 'fact_forecast_metrics',
                 required_columns=['metric_date', 'trade_date', 'indicator_name'])
    │
    ▼
Load forecast model
    │
    ├─→ fact_forecast_metrics has: [metric_date]
    ├─→ Missing: [trade_date, indicator_name]
    │
    ├─→ Check edges for joins:
    │       fact_forecast_metrics → core.dim_calendar (metric_date=trade_date)
    │       (Cross-model reference to another model!)
    │
    ├─→ Auto-load core model
    │
    ├─→ Build join chain:
    │   fact_forecast_metrics (forecast)
    │       ↓ (join on metric_date=trade_date)
    │   dim_calendar (core model)
    │       ↓ (contains trade_date)
    │
    ├─→ Execute join
    │
    ├─→ Select requested columns
    │
    ▼
Return enriched DataFrame
```

## Model Graph Visualization

```
Tier 0 (Foundation):
    core (dim_calendar)
        ↑
        ├─ depends_on: none

Tier 1 (Independent):
    ├─ macro (economic indicators)
    │       ↑
    │       └─ depends_on: core
    │
    └─ corporate (companies)
            ↑
            └─ depends_on: core

Tier 2 (Dependent):
    ├─ equity (securities)
    │       ↑
    │       ├─ depends_on: [core, corporate]
    │       │
    │       └─ edges: equity.fact_prices → corporate.fact_companies
    │
    └─ city_finance
            ↑
            └─ depends_on: core

Tier 3 (Advanced):
    ├─ etf (fund holdings)
    │       ↑
    │       ├─ depends_on: equity
    │       │
    │       └─ edges: etf.fact_holdings → equity.fact_equities
    │
    └─ forecast (predictions)
            ↑
            ├─ depends_on: equity
            │
            └─ edges: forecast.fact_metrics → equity.fact_prices
```

## Session Lifecycle

```
┌─────────────────────────────────────────────┐
│ UniversalSession.__init__()                 │
│                                             │
│ 1. Create connection (Spark or DuckDB)     │
│ 2. Create ModelRegistry (loads all YAMLs)  │
│ 3. Create ModelGraph (builds dependencies) │
│ 4. Pre-load specified models (optional)    │
└──────────────┬──────────────────────────────┘
               │
               ▼
      (Models ready, not built yet)
               │
               ▼
┌─────────────────────────────────────────────┐
│ On First Access (session.get_table())       │
│                                             │
│ 1. Check _models cache                     │
│ 2. If not cached:                          │
│    - Load config from registry             │
│    - Get model class (with fallback)       │
│    - Instantiate model                     │
│    - Inject session (set_session())        │
│    - Cache instance                        │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ On First Model Table Access                 │
│                                             │
│ 1. Check _is_built flag                    │
│ 2. If not built:                           │
│    - _build_nodes() [load from Bronze]     │
│    - _apply_edges() [validate joins]       │
│    - _materialize_paths() [create views]   │
│    - after_build() [post-processing]       │
│    - Set _is_built = True                  │
│    - Cache _dims and _facts                │
└──────────────┬──────────────────────────────┘
               │
               ▼
         (Subsequent accesses use cache)
```

## Configuration Precedence

```
Explicit Parameter
    (highest priority)
    ↓
Environment Variable
    (from .env or system)
    ↓
Configuration File
    (JSON/YAML in configs/)
    ↓
Default Value
    (in constants.py)
    (lowest priority)
```

## Key Abstractions

### 1. **Graph as Query Planner**
- Model dependency graph → Build order
- Table edge graph → Join paths
- Automatic join planning without manual JOIN specifications

### 2. **YAML as Source of Truth**
- No configuration scattered across code
- Schema definitions declarative
- Measures pre-defined
- Models can be modified without code changes

### 3. **Adapters for Backend Transparency**
- Same code runs on Spark and DuckDB
- Adapter decides: SQL generation vs DataFrame API
- Filter pushing handled transparently

### 4. **Lazy Evaluation**
- Models not built until first access
- Materialized views optional performance optimization
- Measures computed on demand

### 5. **Dependency Injection**
- Session injected into models
- Enables cross-model access
- Models don't directly import other models

---

## Summary

The architecture is **graph-centric, configuration-driven, and backend-transparent**:

- **Graph-Centric**: Dependencies, joins, and build order derived from directed acyclic graphs
- **Configuration-Driven**: YAML defines models, measures, schemas; Python implements framework
- **Backend-Transparent**: Single codebase works on Spark (distributed) and DuckDB (single-machine)
- **Lazy-Evaluated**: Components computed/loaded on first access
- **Extensible**: Decorator-based registration for new measure types

This enables domain scientists to define complex dimensional models in YAML while the framework handles orchestration, optimization, and execution.

