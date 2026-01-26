# System Architecture

**Complete architectural overview of the de_Funk system**

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL DATA SOURCES                          │
├─────────────────┬─────────────────────┬─────────────────────────────────┤
│  Alpha Vantage  │  Bureau of Labor    │  Chicago Data Portal            │
│  (Securities)   │  Statistics (BLS)   │  (Municipal)                    │
│  - Stocks       │  - Unemployment     │  - Building Permits             │
│  - Options      │  - CPI              │  - Business Licenses            │
│  - ETFs         │  - Employment       │  - Local Unemployment           │
│  - Company Info │  - Wages            │  - Economic Indicators          │
└────────┬────────┴──────────┬──────────┴──────────────┬──────────────────┘
         │                   │                         │
         ▼                   ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Providers          │  Facets                │  Ingestors                │
│  - HTTP clients     │  - Schema normalization│  - Orchestration          │
│  - Rate limiting    │  - Type conversion     │  - Batch processing       │
│  - Key rotation     │  - Validation          │  - Error handling         │
└─────────────────────┴──────────────────────────────────┬────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BRONZE LAYER (Raw Data)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  storage/bronze/                                                         │
│  ├── securities_reference/      (v2.0 unified, partitioned by asset_type)│
│  ├── securities_prices_daily/   (v2.0 unified, OHLCV all securities)    │
│  ├── bls/                       (unemployment, cpi, employment, wages)   │
│  └── chicago/                   (permits, licenses, indicators)          │
│                                                                          │
│  Format: Partitioned Parquet files                                       │
│  Schema: Facet-normalized (provider-agnostic)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MODEL FRAMEWORK LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│  BaseModel (40+ methods)                                                 │
│  ├── YAML Configuration Loading (ModelConfigLoader)                      │
│  ├── Graph Building (_build_nodes, _apply_edges, _materialize_paths)     │
│  ├── Cross-Model Resolution (_resolve_node, set_session)                 │
│  ├── Backend Abstraction (_detect_backend, _select_columns)              │
│  └── Measure Execution (calculate_measure, Python measures)              │
│                                                                          │
│  Inheritance: _base/securities → stocks, options, etfs, futures          │
└─────────────────────────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SILVER LAYER (Dimensional)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  storage/silver/                                                         │
│  ├── core/          (dim_calendar - 23 columns)                          │
│  ├── company/       (dim_company - CIK-based entities)                   │
│  ├── stocks/        (dim_stock, fact_stock_prices, fact_stock_technicals)│
│  ├── macro/         (dim_economic_series, fact_unemployment, fact_cpi)   │
│  ├── city_finance/  (dim_community_area, fact_local_unemployment)        │
│  └── forecast/      (fact_forecasts, fact_forecast_metrics)              │
│                                                                          │
│  Format: Star/Snowflake schemas in Parquet                               │
│  Configuration: YAML-driven graph definitions                            │
└─────────────────────────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         QUERY LAYER                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  UniversalSession                                                        │
│  ├── Cross-model queries (stocks + company + calendar)                   │
│  ├── Backend-agnostic filters                                            │
│  ├── Measure calculations (simple, computed, weighted, Python)           │
│  └── Query planning with automatic joins                                 │
│                                                                          │
│  DuckDB Analytics                                                        │
│  ├── In-process SQL engine                                               │
│  ├── storage/duckdb/analytics.db (catalog/metadata only)                 │
│  └── Direct Parquet queries (no data duplication)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Streamlit UI (app/ui/)                                                  │
│  ├── Notebook System (Markdown with $filter${} and $exhibits${})         │
│  ├── Filter Engine (dynamic filtering with folder contexts)              │
│  ├── Exhibits (Plotly visualizations)                                    │
│  └── Session Management                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Interactions

### 1. Data Ingestion Flow

```
API Request → Provider → Raw JSON → Facet → Normalized DataFrame → Bronze Parquet
```

1. **Provider** handles HTTP requests, authentication, rate limiting
2. **Facet** normalizes API response to standard schema
3. **Ingestor** orchestrates batching and writes to Bronze

### 2. Model Building Flow

```
Bronze Parquet → YAML Config → Graph Builder → Dimensions + Facts → Silver Parquet
```

1. **ModelConfigLoader** loads YAML with inheritance resolution
2. **BaseModel.build()** orchestrates graph construction
3. **Nodes** are built from Bronze tables with transformations
4. **Edges** validate relationships between nodes
5. **Tables** are written to Silver layer

### 3. Query Flow

```
User Query → UniversalSession → Model Resolution → Filter Application → Result
```

1. **UniversalSession** provides unified query interface
2. **Query Planner** resolves cross-model joins
3. **Filter Engine** applies filters (backend-agnostic)
4. **Measure Executor** calculates metrics

---

## Key Design Patterns

### 1. Graph-Based Modeling

Models use a **directed acyclic graph (DAG)** for dimensional schemas:

- **Nodes**: Tables (dimensions and facts)
- **Edges**: Relationships (foreign keys)
- **Paths**: Materialized joins (denormalized views)

```yaml
graph:
  nodes:
    - id: dim_stock
      from: bronze.securities_reference
      filters: ["asset_type = 'stocks'"]
    - id: fact_stock_prices
      from: bronze.securities_prices_daily
      filters: ["asset_type = 'stocks'"]
  edges:
    - from: fact_stock_prices
      to: dim_stock
      on: [ticker = ticker]
```

### 2. YAML Inheritance

Models can inherit from base templates:

```yaml
# stocks/model.yaml
inherits_from: _base.securities

# stocks/schema.yaml
extends: _base.securities.schema
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
    columns:
      company_id: string  # Additional field
```

### 3. Backend Abstraction

Same code works with both backends:

```python
# BaseModel automatically detects backend
if self.backend == "duckdb":
    return connection.sql(query).df()
else:  # spark
    return connection.sql(query).toPandas()
```

### 4. Lazy Loading

Tables are built on first access:

```python
model.ensure_built()  # First call: builds model
model.ensure_built()  # Subsequent calls: no-op
```

---

## Storage Architecture

### Bronze Layer

```
storage/bronze/
├── securities_reference/
│   └── snapshot_dt=2024-01-15/
│       └── asset_type=stocks/
│           └── part-00000.parquet
├── securities_prices_daily/
│   └── asset_type=stocks/
│       └── year=2024/
│           └── month=01/
│               └── part-00000.parquet
├── bls/
│   ├── unemployment/
│   │   └── year=2024/
│   └── cpi/
└── chicago/
    ├── unemployment/
    └── building_permits/
```

### Silver Layer

```
storage/silver/
├── core/
│   └── dim_calendar/
├── company/
│   └── dim_company/
├── stocks/
│   ├── dim_stock/
│   ├── fact_stock_prices/
│   └── fact_stock_technicals/
├── macro/
│   ├── dim_economic_series/
│   ├── fact_unemployment/
│   └── fact_cpi/
└── forecast/
    ├── fact_forecasts/
    └── fact_forecast_metrics/
```

### DuckDB Catalog

```
storage/duckdb/
└── analytics.db     # Catalog metadata only (no data duplication)
```

---

## Configuration System

### Precedence (Highest to Lowest)

1. **Explicit parameters** - Passed to `loader.load(connection_type="duckdb")`
2. **Environment variables** - From `.env` file
3. **Configuration files** - JSON in `configs/`
4. **Default values** - Defined in `config/constants.py`

### Key Configuration Files

| File | Purpose |
|------|---------|
| `configs/storage.json` | Storage paths and table mappings |
| `configs/alpha_vantage_endpoints.json` | Alpha Vantage API configuration |
| `configs/bls_endpoints.json` | BLS API configuration |
| `configs/chicago_endpoints.json` | Chicago API configuration |
| `configs/models/{model}/` | Model YAML configurations |

---

## Related Documentation

- [Data Flow](data-flow.md) - Detailed data flow explanation
- [Technology Stack](technology-stack.md) - Tools and frameworks
- [Core Framework](../01-core-framework/README.md) - BaseModel and sessions
- [Graph Architecture](../02-graph-architecture/README.md) - Graph system details
