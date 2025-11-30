# CLAUDE.md - AI Assistant Guide for de_Funk

**Last Updated**: 2025-11-30
**Version**: 2.2

This document provides comprehensive guidance for AI assistants (like Claude) working with the de_Funk codebase. It covers project structure, architecture patterns, development workflows, and key conventions.

**Architecture Diagram**: See `docs/architecture-diagram.drawio` for visual representation of the system architecture.

**Recent Updates (v2.2)** - Backend Abstraction Rules:
- **⚠️ Backend Selection Guidelines**: When to use Spark vs DuckDB (ENFORCED)
- **Session Abstraction Required**: Never import `duckdb` or `pyspark` directly
- **Decision Tree**: Clear guidance for backend selection
- **Pre-Commit Checklist**: Added backend abstraction checks

**Previous Updates (v2.1)** - Code Quality & Architecture Guidelines:
- **⚠️ Code Quality Rules**: Mandatory rules for file size, error handling, logging
- **Architecture Boundaries**: Clear layer definitions with import rules
- **Anti-Pattern Documentation**: What NOT to do and why
- **Pre-Commit Checklist**: Verification steps before committing code
- **Proposals Reference**: Links to detailed architectural proposals in `docs/vault/13-proposals/`

**Previous Updates (v2.0)**:
- **Modular YAML Architecture**: Models now split into schema.yaml, graph.yaml, measures.yaml
- **Model Inheritance**: Base securities templates with `extends` and `inherits_from` keywords
- **Python Measures**: Hybrid measure system (YAML for simple, Python for complex)
- **Unified Bronze Layer**: Single tables with asset_type filtering (securities_reference, securities_prices_daily)
- **New Models**: company, stocks, options, etfs, futures (replaces equity, corporate)
- **ModelConfigLoader**: Centralized YAML loading with inheritance resolution
- **CIK Integration**: Company linkage via SEC identifiers
- Enhanced BaseModel with Python measures auto-loading

**Previous Updates (v1.1)**:
- Configuration Management System with ConfigLoader
- Centralized repository discovery (utils/repo.py)
- Script execution with `python -m` module syntax
- Configuration precedence rules

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Repository Structure](#repository-structure)
3. [Technology Stack](#technology-stack)
4. [Architecture & Design Patterns](#architecture--design-patterns)
5. [Development Workflows](#development-workflows)
6. [Testing Strategy](#testing-strategy)
7. [Key Conventions](#key-conventions)
8. [Common Operations](#common-operations)
9. [Troubleshooting](#troubleshooting)
10. [Important Files Reference](#important-files-reference)
11. [Best Practices for AI Assistants](#best-practices-for-ai-assistants)
12. [⚠️ Code Quality Rules (MUST FOLLOW)](#️-code-quality-rules-must-follow) ← **READ THIS BEFORE WRITING CODE**
    - [File Size Limits](#file-size-limits-enforced)
    - [Error Handling Rules](#error-handling-rules-enforced)
    - [Logging Rules](#logging-rules-enforced)
    - [Documentation Rules](#documentation-rules)
    - [Testing Rules](#testing-rules)
    - [Script Conventions](#script-conventions)
    - [Commit Message Conventions](#commit-message-conventions)
    - [When to Ask for Clarification](#when-to-ask-for-clarification)
    - [Session Handoff Notes](#session-handoff-notes)

---

## Project Overview

**de_Funk** is a graphical overlay to a unified relational model enabling low-code interactions with data warehouses. It provides:

- **YAML-driven graph-based modeling**: Declarative dimensional models using nodes, edges, and paths
- **Two-layer architecture**: Bronze (raw data) → Silver (dimensional models)
- **Backend abstraction**: Unified interface supporting both Spark and DuckDB
- **Multi-source data ingestion**: Pluggable pipeline architecture for any data provider
- **Cross-model analysis**: Unified query interface with automatic dependency resolution
- **Interactive analytics**: Markdown-based notebooks with dynamic filtering and visualization
- **Low-code development**: Define models, measures, and transformations in YAML, not code

### Current Implementation (Example Domain)

The current implementation demonstrates the framework with financial and economic data:

**Data Sources:**
- **Alpha Vantage**: Stock prices, company fundamentals, technical indicators (v2.0 - sole securities provider)
- **Bureau of Labor Statistics (BLS)**: Economic indicators (unemployment, CPI, GDP)
- **Chicago Data Portal**: Municipal finance data (Socrata API)

**v2.0 Models (Modular Architecture):**
- **Core** (calendar dimension) - Foundation for all date-based analysis
- **Company** (corporate entities) - CIK-based, SEC identifiers, fundamentals
- **Stocks** (stock securities) - Inherits from base securities, prices + technicals
- **Options** (options contracts) - Inherits from base securities, Greeks + Black-Scholes
- **ETFs** (exchange-traded funds) - Holdings and NAV tracking
- **Futures** (futures contracts) - Roll-adjusted, margin tracking

**v1.x Legacy Models (Being Deprecated):**
- Macro (economic indicators), City Finance (municipal data), Forecast (predictions)
- Equity → migrated to Stocks, Corporate → migrated to Company

**Note:** The framework is domain-agnostic. The modular YAML architecture with inheritance makes it easy to model any domain (healthcare, retail, logistics, etc.).

---

## Repository Structure

```
de_Funk/
├── app/                      # Streamlit UI application
│   ├── notebook/            # Notebook system (parsers, managers, filters)
│   ├── services/            # Business logic services
│   └── ui/                  # Streamlit components & main app
├── config/                   # Centralized configuration system
│   ├── __init__.py          # ConfigLoader and typed models
│   ├── loader.py            # Configuration loading with precedence
│   ├── model_loader.py      # ModelConfigLoader with YAML inheritance (v2.0)
│   ├── models.py            # Type-safe config dataclasses
│   └── constants.py         # Default configuration values
├── configs/
│   ├── models/              # YAML model configurations
│   │   ├── _base/           # Base templates for inheritance (v2.0)
│   │   │   └── securities/  # Base securities schema/graph/measures
│   │   ├── company/         # Company model (modular: model/schema/graph/measures)
│   │   ├── stocks/          # Stocks model (modular + Python measures)
│   │   ├── options/         # Options model (partial implementation)
│   │   ├── etfs/            # ETFs model (skeleton)
│   │   ├── futures/         # Futures model (skeleton)
│   │   └── [legacy models]  # equity.yaml, corporate.yaml (deprecated)
│   ├── notebooks/           # Markdown notebook definitions
│   ├── storage.json         # Storage paths and table mappings (v2.0 updated)
│   ├── alpha_vantage_endpoints.json  # Alpha Vantage API configuration (v2.0)
│   ├── bls_endpoints.json   # BLS API configuration
│   └── chicago_endpoints.json  # Chicago API configuration
├── core/
│   ├── context.py           # RepoContext (now uses ConfigLoader)
│   └── session/             # Core session & connection management
├── datapipelines/
│   ├── base/                # Base classes for pipeline components
│   ├── facets/              # Data transformation facets
│   ├── ingestors/           # Data ingestion orchestration
│   └── providers/           # Provider-specific implementations
│       ├── alpha_vantage/   # Stock market data (Alpha Vantage - v2.0)
│       ├── chicago/         # Municipal data (Chicago Data Portal)
│       └── bls/             # Economic data (Bureau of Labor Statistics)
├── models/
│   ├── api/                 # Model sessions & registry
│   ├── base/                # BaseModel class framework (v2.0: Python measures support)
│   ├── builders/            # Model building utilities
│   ├── measures/            # Measure framework (simple, computed, weighted, Python)
│   └── implemented/         # Domain models
│       ├── core/            # Calendar dimension (foundation)
│       │
│       ├── _v2.0 Models:_
│       ├── company/         # Corporate entities (model.py, measures.py)
│       ├── stocks/          # Stock securities (model.py, measures.py with 6 Python measures)
│       ├── options/         # Options contracts [PARTIAL - needs model.py]
│       ├── etfs/            # Exchange-traded funds [SKELETON]
│       ├── futures/         # Futures contracts [SKELETON]
│       │
│       ├── _v1.x Legacy:_
│       ├── equity/          # [DEPRECATED] → use stocks
│       ├── corporate/       # [DEPRECATED] → use company
│       ├── macro/           # Economic indicators
│       ├── city_finance/    # Municipal finance
│       └── forecast/        # Time series predictions
├── orchestration/
│   ├── common/              # Shared orchestration utilities
│   ├── pipelines/           # Pipeline definitions
│   └── tasks/               # Individual task definitions
├── tests/
│   ├── fixtures/            # Test data generators
│   ├── integration/         # Integration tests
│   └── unit/                # Unit tests
├── scripts/                 # Operational scripts (27 scripts)
├── storage/
│   ├── bronze/              # Raw ingested data (Parquet)
│   │   ├── _v2.0:_
│   │   ├── securities_reference/  # Unified reference data with CIK (partitioned by snapshot_dt, asset_type)
│   │   ├── securities_prices_daily/  # Unified OHLCV for all securities (partitioned by trade_date, asset_type)
│   │   ├── _v1.x (deprecated):_
│   │   ├── ref_ticker/      # → use securities_reference
│   │   ├── prices_daily/    # → use securities_prices_daily
│   │   └── [other providers]  # bls/, chicago/, etc.
│   ├── silver/              # Dimensional models (Parquet)
│   │   ├── company/         # Company dimension & facts (v2.0)
│   │   ├── stocks/          # Stock securities with prices/technicals (v2.0)
│   │   ├── options/         # Options contracts [planned]
│   │   ├── etfs/            # ETFs [planned]
│   │   ├── futures/         # Futures [planned]
│   │   └── [legacy]/        # equity/, corporate/ (deprecated)
│   └── duckdb/              # DuckDB catalog (analytics.db)
├── docs/
│   └── guide/               # Comprehensive documentation
└── utils/                   # Utility functions
    ├── repo.py              # Centralized repo discovery (NEW)
    └── env_loader.py        # Environment variable loading
```

### Key Statistics
- **244 Python files**: Core application code
- **136 Markdown files**: Documentation and notebooks
- **10 YAML files**: Configuration files
- **27 operational scripts**: Pipeline and model management

---

## Technology Stack

### Core Technologies
- **Python 3.x**: Primary programming language
- **DuckDB**: High-performance analytics engine (10-100x faster than Spark)
- **PySpark** (Optional): ETL pipelines and transformations
- **Streamlit**: Web-based UI framework

### Data Processing
- **Pandas**: Data manipulation and analysis
- **PyArrow**: Parquet file support and columnar data
- **NetworkX**: Model dependency graph management

### Visualization
- **Plotly**: Interactive charts and visualizations

### Machine Learning / Forecasting
- **Statsmodels**: ARIMA models
- **Prophet**: Facebook's time series forecasting
- **Scikit-learn**: ML models for forecasting

### Configuration & Parsing
- **PyYAML**: YAML configuration parsing
- **Markdown**: Notebook rendering and documentation

---

## Architecture & Design Patterns

### Two-Layer Architecture (Bronze → Silver)

**Note**: de_Funk uses a simplified two-layer architecture (Bronze and Silver) rather than the full three-layer medallion pattern. Analytics are performed directly on the Silver layer using DuckDB, which serves the role of a "Gold" layer without creating a separate persisted layer.

#### Bronze Layer (Raw Data)
- **Purpose**: Store raw, unprocessed data from APIs
- **Format**: Partitioned Parquet files
- **Path**: `storage/bronze/{provider}/{table}/`
- **Organization**: By data provider (alpha_vantage, bls, chicago)
- **Schema**: Facet-normalized schemas

#### Silver Layer (Dimensional Models)
- **Purpose**: Clean, transformed dimensional models ready for analytics
- **Format**: Star/snowflake schemas with facts and dimensions
- **Path**: `storage/silver/{model}/{table}/`
- **Configuration**: YAML-driven graph transformations
- **Models**: 8 domain models with cross-model relationships

#### Analytics Layer (DuckDB Catalog)
- **Purpose**: Business-ready analytics and insights
- **Interface**: Notebooks and dashboards query Silver directly
- **Query Engine**: DuckDB (10-100x faster than Spark)
- **Database File**: `storage/duckdb/analytics.db` (persistent catalog/metadata)
- **Features**: Dynamic filtering and visualization
- **Note**: No separate "Gold" layer - queries run directly against Silver Parquet files. The DuckDB file stores catalog metadata, views, and query workspace but does NOT duplicate the data.

### Model Architecture Pattern

**v2.0 Modular YAML Pattern** (Recommended):

Models split across multiple files for clarity and inheritance:

```
configs/models/stocks/
├── model.yaml          # Metadata & composition
├── schema.yaml         # Table definitions (extends base)
├── graph.yaml          # Graph structure (extends base)
└── measures.yaml       # Measure definitions (YAML + Python)
```

**model.yaml**:
```yaml
model: stocks
version: 2.0
description: "Stock securities with technical indicators"
inherits_from: _base.securities  # Inherit from base templates

components:
  schema: stocks/schema.yaml
  graph: stocks/graph.yaml
  measures:
    yaml: stocks/measures.yaml
    python: stocks/measures.py  # Python measures for complex calculations

depends_on: [core, company]
storage:
  root: storage/silver/stocks
  format: parquet
```

**schema.yaml** (with inheritance):
```yaml
extends: _base.securities.schema  # Inherit base schema

dimensions:
  dim_stock:
    extends: _base.securities._dim_security  # Extend base dimension
    columns:
      # Inherited: ticker, asset_type, exchange_code, etc.
      company_id: string  # Added field
      cik: string
      shares_outstanding: long
```

**measures.yaml** (hybrid YAML + Python):
```yaml
extends: _base.securities.measures  # Inherit base measures

simple_measures:
  avg_market_cap:  # YAML for simple aggregations
    type: simple
    source: dim_stock.market_cap
    aggregation: avg

python_measures:  # Python for complex calculations
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
```

**v1.x Single YAML Pattern** (Legacy):

```yaml
model: equity
version: 1
depends_on: [core, corporate]
schema:
  dimensions:
    dim_equity: {...}
measures:
  avg_close_price: {...}
```

### Model Dependency Graph

**v2.0 Model Dependencies:**

```
Tier 0 (Foundation):
  └── core (calendar dimension)

Tier 1 (Independent):
  └── company (corporate entities, CIK-based)

Tier 2 (Securities - inherit from _base.securities):
  ├── stocks (depends on: core, company)
  ├── options (depends on: core, stocks)  [PARTIAL]
  ├── etfs (depends on: core, stocks)     [SKELETON]
  └── futures (depends on: core)          [SKELETON]

_base/ (Templates - not instantiated):
  └── securities (schema, graph, measures templates)
```

**v1.x Legacy Dependencies** (being deprecated):

```
Tier 1: macro, corporate
Tier 2: equity (→ stocks), city_finance
Tier 3: etf (→ etfs), forecast
```

### Cross-Model Relationships

**v2.0 Relationships:**
- **stocks → company**: Stock dimension links to company via company_id (derived from CIK)
- **options → stocks**: Options reference underlying stocks via ticker
- **etfs → stocks**: ETF holdings reference constituent stocks
- **All → core**: All models link to calendar dimension for time-series analysis

**Key Design:**
- **Company is standalone** (not a security) - tracks legal entities
- **Securities inherit from _base.securities** - shared OHLCV schema
- **CIK as bridge** - SEC identifier connects stocks to companies

### Key Architectural Patterns

1. **Modular YAML Architecture** (v2.0): Models split into schema/graph/measures files for clarity
2. **YAML Inheritance** (v2.0): `extends` and `inherits_from` keywords for reusable templates
3. **Hybrid Measure System** (v2.0): YAML for simple aggregations, Python for complex calculations
4. **Python Measures Auto-Loading** (v2.0): BaseModel discovers and loads Python measure modules
5. **Unified Bronze Tables** (v2.0): Single tables with asset_type filtering (securities_reference, securities_prices_daily)
6. **Centralized Configuration**: ConfigLoader for type-safe, validated configuration
7. **BaseModel Inheritance**: All models extend `models/base/model.py::BaseModel`
8. **Storage Router**: Abstracts Bronze/Silver path resolution
9. **Backend Agnostic**: Adapters for both Spark and DuckDB
10. **Measure Framework**: Unified calculation engine (simple, computed, weighted, Python)
11. **Universal Session**: Cross-model query interface
12. **Filter Engine**: Backend-agnostic filter application
13. **Lazy Loading**: Models and tables loaded on demand
14. **Graph-Based Dependencies**: NetworkX for dependency resolution

---

## v2.0 Model Architecture (November 2025)

### Modular YAML Structure

**Philosophy**: Split large monolithic YAMLs into logical components for maintainability.

**Structure**:
```
configs/models/{model}/
├── model.yaml      # Metadata, dependencies, composition
├── schema.yaml     # Dimensions, facts, columns
├── graph.yaml      # Nodes, edges, paths
└── measures.yaml   # Simple + Python measures
```

**Loading**: `ModelConfigLoader` (`config/model_loader.py`) handles:
- Discovering modular YAML files
- Resolving `extends` and `inherits_from` keywords
- Deep merging configurations with override semantics
- Auto-discovering Python measure modules

**Example Usage**:
```python
from config.model_loader import ModelConfigLoader
from pathlib import Path

loader = ModelConfigLoader(Path("configs/models"))
config = loader.load_model_config("stocks")
# Returns fully merged config with inherited schemas/measures
```

### YAML Inheritance System

**Two Keywords**:
- `inherits_from`: Model-level inheritance (e.g., `stocks` inherits from `_base.securities`)
- `extends`: Component-level inheritance (e.g., `schema.yaml` extends base schema)

**Inheritance Resolution**:
1. Load base template (e.g., `_base/securities/schema.yaml`)
2. Load child config (e.g., `stocks/schema.yaml`)
3. Deep merge: child overrides parent, preserving structure
4. Result: Child has all base fields + additions/overrides

**Example**:
```yaml
# _base/securities/schema.yaml
dimensions:
  _dim_security:
    columns:
      ticker: string
      asset_type: string
      exchange_code: string

# stocks/schema.yaml
extends: _base.securities.schema
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
    columns:
      # ticker, asset_type, exchange_code inherited automatically
      company_id: string  # Added field
      shares_outstanding: long
```

**Result**: `dim_stock` has ALL base fields + new fields (100% inheritance verified).

### Hybrid Measure System

**Problem**: YAML can't express complex calculations (rolling windows, correlations, ML).

**Solution**: Hybrid approach with clear boundary:

**YAML Measures** - Simple aggregations:
```yaml
simple_measures:
  avg_close_price:
    type: simple
    source: fact_prices.close
    aggregation: avg
    format: "#,##0.00"
```

**Python Measures** - Complex calculations:
```yaml
python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
      window_days: 252
```

**Python Implementation** (`models/implemented/stocks/measures.py`):
```python
class StocksMeasures:
    def __init__(self, model):
        self.model = model

    def calculate_sharpe_ratio(self, ticker=None, risk_free_rate=0.045, window_days=252, **kwargs):
        """Calculate rolling Sharpe ratio."""
        # Get price data from model
        df = self.model.get_prices(ticker=ticker)

        # Calculate returns
        df['returns'] = df['close'].pct_change()

        # Rolling Sharpe
        df['sharpe'] = (
            (df['returns'].rolling(window_days).mean() - risk_free_rate / 252) /
            df['returns'].rolling(window_days).std() * np.sqrt(252)
        )

        return df[['ticker', 'trade_date', 'sharpe']]
```

**Usage** (seamless for both types):
```python
model = registry.get_model("stocks")

# YAML measure
avg_price = model.calculate_measure("avg_close_price", ticker="AAPL")

# Python measure (YAML params + runtime override)
sharpe = model.calculate_measure("sharpe_ratio", ticker="AAPL", window_days=60)
```

**Benefits**:
- ✅ Simple aggregations stay declarative (easy to define)
- ✅ Complex logic uses full Python power (pandas, numpy, scipy)
- ✅ Unified interface (users don't care which type)
- ✅ YAML params provide defaults, runtime kwargs override

### Unified Bronze Layer

**v1.x Problem**: Separate bronze tables per model (ref_ticker, prices_daily, etc.)

**v2.0 Solution**: Unified tables with asset_type filtering:

**Bronze Tables**:
- `securities_reference` - All ticker reference data with CIK
  - Partitions: `snapshot_dt`, `asset_type` (stocks, options, etfs, futures)
  - Schema: ticker, name, asset_type, cik, exchange_code, shares_outstanding, market_cap

- `securities_prices_daily` - All daily OHLCV data
  - Partitions: `trade_date`, `asset_type`
  - Schema: ticker, trade_date, asset_type, open, high, low, close, volume, volume_weighted

**Silver Filtering**:
```yaml
# stocks/graph.yaml
nodes:
  fact_stock_prices:
    from: bronze.securities_prices_daily
    filters:
      - "asset_type = 'stocks'"  # KEY FILTER
```

**Benefits**:
- ✅ Bronze mirrors API structure (Alpha Vantage returns all types from same endpoint)
- ✅ No data duplication at ingestion
- ✅ Easy to add new asset types (just filter differently)
- ✅ Single ingestion pipeline for all securities

### CIK Integration

**CIK** (Central Index Key) - SEC's permanent 10-digit identifier for companies.

**Why CIK**:
- Tickers change (GOOGL/GOOG, FB→META)
- CIK is permanent and unique per legal entity
- Links to SEC filings (10-K, 10-Q, 8-K)

**Architecture**:
```
company.dim_company (primary key: cik)
  ↑
  | company_id = CONCAT('COMPANY_', cik)
  |
stocks.dim_stock (foreign key: company_id)
```

**Extraction** (`SecuritiesReferenceFacet`):
```python
cik_expr = (
    when(col("cik").isNotNull(),
         lpad(regexp_extract(col("cik"), r"(\d+)", 1), 10, "0"))
    .cast("string")
)
```

**Usage**:
```python
# Get stock with company info
df = session.query("""
    SELECT
        s.ticker,
        s.close_price,
        c.company_name,
        c.sector
    FROM stocks.dim_stock s
    JOIN company.dim_company c ON s.company_id = c.company_id
    WHERE s.ticker = 'AAPL'
""")
```

---

## Configuration Management System

### Overview

de_Funk uses a **centralized, type-safe configuration system** introduced in November 2025 that eliminates scattered configuration loading and provides clear precedence rules.

**Key Features:**
- **Single entry point**: `ConfigLoader` class loads all configuration
- **Type safety**: Dataclass models for all config (no raw dicts)
- **Clear precedence**: env vars > explicit params > config files > defaults
- **Auto-discovery**: Automatically finds and loads API configs
- **Validation**: Configuration values validated at load time
- **No hardcoded values**: All config externalized to files/env vars

### Configuration Precedence

Configuration sources in order of priority (highest to lowest):

1. **Explicit parameters** - Passed directly to `loader.load(connection_type="duckdb")`
2. **Environment variables** - From `.env` file or system env
3. **Configuration files** - JSON files in `configs/` directory
4. **Default values** - Defined in `config/constants.py`

### ConfigLoader Usage

```python
from config import ConfigLoader

# Basic usage - auto-discover repo root
loader = ConfigLoader()
config = loader.load()

# Access typed configuration
print(f"Connection type: {config.connection.type}")
print(f"Repo root: {config.repo_root}")
print(f"Models dir: {config.models_dir}")

# Override connection type
config = loader.load(connection_type="duckdb")

# Access API configs (auto-discovered from configs/*.json)
alpha_vantage_cfg = config.apis.get("alpha_vantage", {})
bls_cfg = config.apis.get("bls", {})
```

### Typed Configuration Models

All configuration uses dataclasses for type safety:

**`AppConfig`** - Top-level configuration
- `repo_root: Path` - Repository root directory
- `connection: ConnectionConfig` - Database connection config
- `storage: Dict` - Storage configuration (from storage.json)
- `apis: Dict` - API configurations (auto-discovered)
- `log_level: str` - Logging level

**`ConnectionConfig`** - Connection settings
- `type: str` - "spark" or "duckdb"
- `spark: SparkConfig` - Spark-specific settings (if using Spark)
- `duckdb: DuckDBConfig` - DuckDB-specific settings (if using DuckDB)

**`SparkConfig`** - Spark configuration
- `driver_memory: str` - Driver memory (e.g., "4g")
- `executor_memory: str` - Executor memory (e.g., "4g")
- `shuffle_partitions: int` - Number of shuffle partitions
- `timezone: str` - Session timezone

**`DuckDBConfig`** - DuckDB configuration
- `database_path: Path` - Path to DuckDB file
- `memory_limit: str` - Memory limit (e.g., "4GB")
- `threads: int` - Number of threads
- `read_only: bool` - Read-only mode

### RepoContext Integration

`RepoContext` now uses `ConfigLoader` internally:

```python
from core.context import RepoContext

# RepoContext uses ConfigLoader behind the scenes
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Access typed config (new)
if ctx.config:
    print(f"Models directory: {ctx.config.models_dir}")
    print(f"Connection type: {ctx.config.connection.type}")

# Access API configurations for any provider
alpha_vantage_cfg = ctx.get_api_config("alpha_vantage")
bls_cfg = ctx.get_api_config("bls")
chicago_cfg = ctx.get_api_config("chicago")
```

### Environment Variables

Set in `.env` file (copy from `.env.example`):

```bash
# API Keys (required for data ingestion)
ALPHA_VANTAGE_API_KEYS=your_key_here
BLS_API_KEYS=your_key_here
CHICAGO_API_KEYS=your_key_here

# Connection type override (optional)
CONNECTION_TYPE=duckdb

# Logging level (optional)
LOG_LEVEL=DEBUG

# Spark configuration (when using Spark)
SPARK_DRIVER_MEMORY=8g
SPARK_EXECUTOR_MEMORY=8g
SPARK_SHUFFLE_PARTITIONS=400

# DuckDB configuration (when using DuckDB)
DUCKDB_DATABASE_PATH=storage/duckdb/analytics.db
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=8
```

### Repository Discovery

The `utils/repo.py` module provides centralized repo root discovery:

```python
from utils.repo import get_repo_root, setup_repo_imports

# Option 1: Just get repo root (no sys.path modification)
repo_root = get_repo_root()
print(repo_root)  # /home/user/de_Funk

# Option 2: Setup imports (recommended for scripts)
repo_root = setup_repo_imports()
# Now you can import from anywhere in the repo!
from core.context import RepoContext
from models.api.session import UniversalSession

# Option 3: Context manager (auto-cleanup)
from utils.repo import repo_imports
with repo_imports() as repo_root:
    from core.context import RepoContext
    # ... use imports ...
# sys.path cleaned up after exiting context
```

**Repo Discovery Algorithm:**
- Walks up directory tree from start point
- Looks for directories containing: `configs/`, `core/`, `.git/`
- Returns first parent directory containing all markers

---

## Development Workflows

### Model Development Workflow

When creating a new model or modifying an existing one:

1. **Create/Update YAML Configuration**
   - Location: `/configs/models/{model_name}.yaml`
   - Define schema (dimensions, facts, columns)
   - Define graph (nodes, edges, paths)
   - Define measures (simple, computed, weighted)
   - Specify dependencies

2. **Implement Model Class**
   - Location: `/models/implemented/{model_name}/`
   - Extend `BaseModel`
   - Implement any custom logic
   - Add to model registry

3. **Test the Model**
   ```bash
   python scripts/test_all_models.py
   python scripts/test_domain_model_integration_duckdb.py
   ```

4. **Build the Model**
   ```bash
   python scripts/build_silver_layer.py
   # or for specific model
   python scripts/rebuild_model.py --model {model_name}
   ```

5. **Verify Data**
   - Check storage path: `storage/silver/{model_name}/`
   - Verify Parquet files exist
   - Test queries via Universal Session

### Data Pipeline Development Workflow

When adding a new data source:

1. **Create Facet Class**
   - Location: `/datapipelines/facets/`
   - Normalize API response to DataFrame
   - Define schema transformation

2. **Create Provider/Ingestor**
   - Location: `/datapipelines/providers/{provider_name}/`
   - Implement API client
   - Implement data fetching logic

3. **Configure API Endpoints**
   - Update configuration files (e.g., `alpha_vantage_endpoints.json`, `bls_endpoints.json`)
   - Add API keys to `.env`

4. **Run Ingestion**
   ```bash
   python run_full_pipeline.py --top-n 100
   ```

5. **Verify Bronze Data**
   - Check: `storage/bronze/{provider}/{table}/`
   - Verify Parquet files exist and are readable

### Notebook Development Workflow

When creating analytics notebooks:

1. **Create Markdown File**
   - Location: `/configs/notebooks/{category}/{notebook_name}.md`
   - Add YAML front matter (metadata)

2. **Define Filters**
   ```markdown
   $filter${
     "type": "date_range",
     "label": "Date Range",
     "column": "date"
   }
   ```

3. **Define Exhibits**
   ```markdown
   $exhibits${
     "type": "line_chart",
     "data": "query_result",
     "x": "date",
     "y": "close_price"
   }
   ```

4. **Test in Streamlit UI**
   ```bash
   python run_app.py
   ```

5. **Optional: Add Folder Context**
   - Create `.filter_context.yaml` for folder-level filters

### Testing Workflow

Before committing changes:

1. **Run Unit Tests**
   ```bash
   pytest tests/unit/
   ```

2. **Run Integration Tests**
   ```bash
   pytest tests/integration/
   ```

3. **Run Backend Tests**
   ```bash
   bash scripts/run_backend_tests.sh
   ```

4. **Run E2E Pipeline Test**
   ```bash
   python scripts/test_pipeline_e2e.py
   ```

5. **Test UI Integration**
   ```bash
   python scripts/test_ui_integration.py
   ```

### Git Workflow

Recent commits show clear conventions:

```bash
# Commit message patterns
git commit -m "refactor: Improve measures showcase notebook for better clarity"
git commit -m "docs: Add comprehensive session summary"
git commit -m "fix: Use public API for measure registry test"

# Common prefixes
refactor:  # Code improvements
docs:      # Documentation updates
fix:       # Bug fixes
feat:      # New features
test:      # Test additions/changes
```

Branch naming convention:
```
claude/claude-md-{identifier}
```

---

## Testing Strategy

### Test Organization

```
tests/
├── conftest.py              # Pytest configuration & shared fixtures
├── fixtures/                # Test data generators
│   └── sample_data_generator.py
├── unit/                    # Unit tests
│   ├── test_measure_framework.py
│   ├── test_backend_adapters.py
│   └── test_weighting_strategies.py
└── integration/             # Integration tests
    └── test_measure_pipeline.py
```

### Testing Tools

- **pytest**: Primary testing framework
- **DuckDB in-memory**: Fast test database
- **Fixtures**: Provide sample data (price data, company data, ETF holdings)

### Test Scripts

Located in `/scripts/`:

- `run_backend_tests.sh`: Run backend compatibility tests
- `test_all_models.py`: Test all model implementations
- `test_domain_model_integration_duckdb.py`: DuckDB integration tests
- `test_domain_model_integration_spark.py`: Spark integration tests
- `test_pipeline_e2e.py`: End-to-end pipeline tests
- `test_ui_integration.py`: UI integration tests
- `test_filter_system.py`: Filter system tests
- `test_ui_state.py`: UI state management tests

### Testing Best Practices

1. **Always test both backends**: DuckDB and Spark when applicable
2. **Use fixtures**: Leverage existing fixtures in `tests/fixtures/`
3. **Test measure calculations**: Verify simple, computed, and weighted measures
4. **Test cross-model queries**: Verify model dependencies work correctly
5. **Test filter application**: Ensure filters work across all backends
6. **Use in-memory databases**: Faster tests with DuckDB in-memory mode

---

## Key Conventions

### Code Organization

- **No leading underscores for public APIs**: Clean public interfaces
- **Type hints throughout**: Improved code clarity and IDE support
- **Comprehensive docstrings**: All public functions and classes documented
- **Dataclasses for configuration**: Structured configuration objects

### File Naming

- **Python modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **YAML configs**: `lowercase.yaml`
- **Markdown docs**: `UPPERCASE.md` or `Title_Case.md`

### Model Conventions

- **YAML as source of truth**: Models defined declaratively
- **Lazy loading**: Models and tables loaded on demand
- **Explicit dependencies**: Declare all model dependencies in YAML
- **Measure-driven analytics**: Pre-define calculations in YAML
- **Backend abstraction**: Support both Spark and DuckDB

### Notebook Conventions

- **Markdown for content**: Analysis as documents
- **YAML front matter**: Metadata at top of file
- **Filter-driven UX**: Folder-based filter contexts
- **Exhibit syntax**: `$exhibits${...}` for visualizations
- **Filter syntax**: `$filter${...}` for dynamic filters

### Storage Conventions

- **Parquet format**: All persistent data storage (Bronze/Silver)
- **Partitioned data**: Efficient querying and updates
- **Bronze**: `storage/bronze/{provider}/{table}/` - Raw ingested data
- **Silver**: `storage/silver/{model}/{table}/` - Dimensional models
- **DuckDB**: `storage/duckdb/analytics.db` - Query catalog and metadata (does NOT duplicate data)
- **Versioning**: Track schema versions in YAML

### API Conventions

- **Environment variables**: Store API keys in `.env` (not committed)
- **Rate limiting**: Respect API rate limits
- **Error handling**: Graceful degradation on API failures
- **Caching**: Cache API responses when appropriate

---

## Common Operations

### Starting the Application

```bash
# DuckDB-powered UI (recommended - fast)
python run_app.py
# or
./run_app.sh

# Direct Streamlit launch
streamlit run app/ui/notebook_app_duckdb.py
```

### Running Full Pipeline

```bash
# Ingest data and build all models
python run_full_pipeline.py --top-n 100

# Build only silver layer models
python scripts/build_all_models.py

# Build specific silver layer
python scripts/build_silver_layer.py
```

### Model Operations

**Note**: Scripts now use the `python -m` pattern for better import handling:

```bash
# Rebuild specific model
python -m scripts.rebuild_model --model equity

# Reset model state
python -m scripts.reset_model --model equity

# Test all models
python -m scripts.test_all_models
```

### Data Operations

```bash
# Clear cache and refresh
python scripts/clear_and_refresh.py

# Migrate to Delta format (if needed)
python scripts/migrate_to_delta.py

# Verify ticker count
python scripts/verify_ticker_count.py
```

### Forecasting

```bash
# Run all forecasts
python scripts/run_forecasts.py

# Run specific forecast model
python scripts/run_forecast_model.py --model arima
```

### Testing

```bash
# Run all unit tests
pytest tests/unit/

# Run all integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_measure_framework.py

# Run backend compatibility tests
bash scripts/run_backend_tests.sh

# Run E2E pipeline test
python -m scripts.test_pipeline_e2e
```

### Querying Data

```python
# Using Universal Session (recommended)
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")
df = session.query("""
    SELECT ticker, date, close_price
    FROM equity.fact_equity_prices
    WHERE date >= '2024-01-01'
""")

# Apply filters
filters = [{"column": "ticker", "operator": "in", "value": ["AAPL", "MSFT"]}]
filtered_df = session.apply_filters(df, filters)
```

### Using Measures

```python
# Get measure registry
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("equity")

# Calculate measure
result = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}]
)
```

---

## Troubleshooting

### Common Issues

#### 1. API Key Errors

**Symptom**: `401 Unauthorized` or missing API key errors

**Solution**:
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
# POLYGON_API_KEY=your_key_here
# BLS_API_KEY=your_key_here
# CHICAGO_DATA_TOKEN=your_token_here
```

#### 2. Model Build Failures

**Symptom**: Model fails to build or shows dependency errors

**Solution**:
```bash
# Check model dependencies
python scripts/analyze_model_dependencies.py

# Build models in dependency order
# 1. Core first
python scripts/rebuild_model.py --model core

# 2. Then dependent models
python scripts/rebuild_model.py --model equity
```

#### 3. Missing Data in Bronze Layer

**Symptom**: No data in `storage/bronze/`

**Solution**:
```bash
# Run full pipeline to ingest data
python run_full_pipeline.py --top-n 100

# Verify data exists
ls -R storage/bronze/
```

#### 4. DuckDB vs Spark Discrepancies

**Symptom**: Different results between backends

**Solution**:
```bash
# Run backend comparison tests
bash scripts/run_backend_tests.sh

# Check for backend-specific issues in filter application
python scripts/test_filter_system.py
```

#### 5. Notebook Rendering Issues

**Symptom**: Filters or exhibits not showing in UI

**Solution**:
- Check YAML front matter syntax
- Verify `$filter${}` and `$exhibits${}` syntax
- Check `.filter_context.yaml` if using folder contexts
- Review `TESTING_GUIDE.md` for filter system details

### Debug Resources

- **`scripts/examples/measure_calculations/01_basic_measures.py`**: Usage examples
- **`scripts/examples/measure_calculations/02_troubleshooting.py`**: Debug guide
- **`scripts/examples/README.md`**: Examples overview and guide
- **`tests/pipeline_tester.py`**: Validate entire setup
- **`TESTING_GUIDE.md`**: Comprehensive testing guide
- **`MODEL_DEPENDENCY_ANALYSIS.md`**: Model dependency issues

### Performance Issues

If queries are slow:

1. **Use DuckDB instead of Spark**: 10-100x faster
2. **Check partitioning**: Ensure data is properly partitioned
3. **Verify indexes**: Check if indexes exist on join columns
4. **Optimize filters**: Push filters down to storage layer
5. **Review `FILTER_PUSHDOWN_FIX.md`**: Filter optimization guide

---

## Important Files Reference

### Essential Configuration Files

| File | Purpose |
|------|---------|
| `.env` | API keys and environment configuration |
| `configs/storage.json` | Storage paths and table mappings |
| `configs/alpha_vantage_endpoints.json` | Alpha Vantage API endpoint configuration (v2.0) |
| `configs/bls_endpoints.json` | BLS API endpoint configuration (auto-discovered) |
| `configs/chicago_endpoints.json` | Chicago API endpoint configuration (auto-discovered) |
| `configs/models/*.yaml` | Model definitions (v2.0 modular architecture) |
| `configs/notebooks/*.md` | Notebook definitions |

**Note**: With the new ConfigLoader system, API configs are auto-discovered from `configs/*_endpoints.json` files. No manual registration needed!

### Critical Documentation Files

| File | Purpose |
|------|---------|
| `QUICKSTART.md` | Getting started guide |
| `RUNNING.md` | How to run the application |
| `TESTING_GUIDE.md` | Comprehensive testing guide |
| `PIPELINE_GUIDE.md` | Data pipeline documentation |
| `docs/configuration.md` | **Configuration system documentation (NEW)** |
| `docs/IMPORT-PATTERNS.md` | **Import pattern standardization (NEW)** |
| `docs/path-management-migration.md` | **Path management guide (NEW)** |
| `CALENDAR_DIMENSION_GUIDE.md` | Calendar dimension details |
| `MODEL_DEPENDENCY_ANALYSIS.md` | Model dependency issues |
| `MODEL_EDGES_REFERENCE.md` | Cross-model relationships |
| `FORECAST_README.md` | Forecasting documentation |
| `FILTER_PUSHDOWN_FIX.md` | Filter optimization guide |

### Key Python Modules

| Module | Purpose |
|--------|---------|
| `config/loader.py` | **ConfigLoader** - Centralized configuration loading (NEW) |
| `config/models.py` | Type-safe configuration dataclasses (NEW) |
| `utils/repo.py` | **Repo discovery** - Find repo root and setup imports (NEW) |
| `core/context.py` | **RepoContext** - Now uses ConfigLoader internally |
| `models/base/model.py` | BaseModel class - foundation for all models |
| `models/api/registry.py` | Model registry - discover and manage models |
| `core/session/universal_session.py` | Unified query interface |
| `core/session/filters.py` | Backend-agnostic filter application |
| `models/measures/framework.py` | Measure calculation framework |
| `datapipelines/base/facet.py` | Base facet transformation class |
| `app/notebook/parser.py` | Markdown notebook parser |
| `app/notebook/manager.py` | Notebook management |

### Key Scripts

| Script | Purpose |
|--------|---------|
| `run_app.py` / `run_app.sh` | Launch Streamlit UI |
| `run_full_pipeline.py` | Run complete ETL pipeline |
| `scripts/build_all_models.py` | Build all models |
| `scripts/rebuild_model.py` | Rebuild specific model |
| `scripts/test_all_models.py` | Test all models |
| `scripts/run_forecasts.py` | Generate forecasts |
| `scripts/clear_and_refresh.py` | Clear cache and refresh |

---

## Current State & Known Issues

### Recent Migrations (November 2025)

**✅ Configuration System Migration - COMPLETE**
- New centralized `config/` module with ConfigLoader
- All scripts updated to use `python -m` module syntax
- Repository discovery centralized in `utils/repo.py`
- Type-safe configuration with dataclass models
- Auto-discovery of API configurations

**✅ v2.0 Model Architecture - COMPLETE**
- Modular YAML structure (schema/graph/measures split)
- YAML inheritance with `extends` and `inherits_from`
- Hybrid measure system (YAML + Python)
- Unified bronze layer with asset_type filtering
- Legacy models removed (equity, corporate)
- Polygon.io completely removed, Alpha Vantage is sole securities provider
- New models: company, stocks, options (partial), etfs (skeleton), futures (skeleton)

### Backend Support

- **DuckDB**: Primary backend, fully supported (10-100x faster)
- **Spark**: Optional backend, maintained for compatibility
- Most operations tested on both backends

### Data Sources Status

- **Alpha Vantage**: Active, v2.0 sole securities provider (Free: 5 calls/min, Premium: 75 calls/min)
- **BLS**: Active, economic indicators working
- **Chicago Data Portal**: Active, municipal finance data

**Note**: Polygon.io has been completely removed in v2.0. Alpha Vantage is now the exclusive provider for securities data (stocks, options, ETFs, futures).

---

## Best Practices for AI Assistants

### When Making Changes

1. **Read before editing**: Always use Read tool before Edit tool
2. **Understand dependencies**: Check model dependency graph
3. **Test both backends**: Verify changes work with DuckDB and Spark
4. **Update documentation**: Keep markdown files in sync with code
5. **Follow conventions**: Match existing code style and patterns
6. **Run tests**: Execute relevant test scripts before committing

### When Exploring Code

1. **Start with YAML configs**: Models defined in `/configs/models/`
2. **Check documentation**: Review relevant `.md` files first
3. **Use examples**: Look at `/scripts/examples/` for usage patterns
4. **Follow imports**: Trace from high-level to implementation
5. **Check tests**: Unit tests show expected behavior

### When Debugging

1. **Check recent commits**: See `git log` for recent changes
2. **Review documentation**: Check `MODEL_DEPENDENCY_ANALYSIS.md`, etc.
3. **Run debug scripts**: Use `tests/pipeline_tester.py`
4. **Test incrementally**: Isolate issues with unit tests
5. **Compare backends**: Check if issue is backend-specific

### When Adding Features

1. **Search for similar code**: Don't reinvent the wheel
2. **Follow existing patterns**: Match architectural patterns
3. **Add tests first**: TDD approach preferred
4. **Update YAML configs**: Keep configuration in sync
5. **Document thoroughly**: Update relevant `.md` files

---

## ⚠️ Code Quality Rules (MUST FOLLOW)

**Reference**: See `docs/vault/13-proposals/draft/` for detailed proposals on architecture and code quality.

### File Size Limits (ENFORCED)

| Threshold | Action Required |
|-----------|-----------------|
| **<300 lines** | ✅ Target size - proceed normally |
| **300-500 lines** | ⚠️ Warning - consider splitting before adding more |
| **500-800 lines** | 🟠 Must justify why not splitting |
| **>800 lines** | 🔴 **STOP** - Must refactor before adding ANY new code |

**Before adding code to a file >300 lines**:
1. Check if function belongs in this file's responsibility
2. If file is approaching limit, extract to new module FIRST
3. Never add "just one more function" to a large file

### Error Handling Rules (ENFORCED)

```python
# ❌ NEVER DO THIS - Bare except catches everything including Ctrl+C
try:
    do_something()
except:
    pass

# ❌ NEVER DO THIS - Silent failure masks bugs
except Exception:
    pass

# ❌ NEVER DO THIS - Catching too broadly
except Exception as e:
    print(f"Error: {e}")  # No logging, continues silently

# ✅ CORRECT - Specific exceptions with proper handling
try:
    do_something()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    raise
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    raise ConfigurationError(f"Missing file: {e}") from e
```

**Rules**:
1. **Never use bare `except:`** - always specify exception types
2. **Never silently pass** - at minimum log the error
3. **Use `from e`** for exception chaining
4. **Reraise unexpected exceptions** - don't swallow bugs

### Logging Rules (ENFORCED)

```python
# ❌ NEVER DO THIS in production code
print(f"Processing {item}...")
print(f"Done!")
print(f"Error: {e}")

# ✅ CORRECT - Use logger
from config.logging import get_logger
logger = get_logger(__name__)

logger.info(f"Processing {item}")
logger.debug(f"Details: {details}")
logger.error(f"Failed to process", exc_info=True)
```

**Rules**:
1. **No print statements** except in CLI scripts for user output
2. **Use `get_logger(__name__)`** for module-specific loggers
3. **Use appropriate levels**: DEBUG for details, INFO for progress, WARNING for issues, ERROR for failures
4. **Include `exc_info=True`** when logging exceptions

### Code Duplication Rules

**Before implementing ANY new functionality**:
1. **Search the codebase** for similar code: `grep -r "function_name" .`
2. If similar code exists:
   - **Extend existing** if it's close to what you need
   - **Refactor to shared location** if duplicating
3. **Never create a "similar but different" version**

**Known Duplications to Avoid**:
- FilterEngine - USE `core/session/filters.py` ONLY (extend if needed)
- Configuration loading - USE `config/loader.py` ONLY
- Backend detection - USE existing patterns, don't recreate

### Architecture Boundaries

**Layer Rules** - Code must stay in its layer:

| Layer | Location | Responsibilities | Does NOT Do |
|-------|----------|------------------|-------------|
| **Config** | `config/`, `configs/` | Load/validate configuration | Query data, HTTP requests |
| **Core** | `core/` | DB connections, filters, infrastructure | Business logic, UI |
| **Pipelines** | `datapipelines/` | Fetch external APIs, write Bronze | Query data, build models |
| **Models** | `models/` | Domain models, measures, Silver layer | Fetch APIs, handle UI |
| **App** | `app/` | Streamlit UI, notebooks | Direct DB queries, API calls |

**Import Rules**:
```python
# ❌ WRONG - UI importing from pipeline layer
# app/ui/notebook_app.py
from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

# ✅ CORRECT - UI calls service, service calls pipeline
# app/ui/notebook_app.py
from app.services import DataService
```

### Where Does New Code Go? (Decision Tree)

```
Q1: Fetching external data?          → datapipelines/providers/{provider}/
Q2: Transforming raw data?           → datapipelines/facets/
Q3: Loading/validating config?       → config/ (Python) or configs/ (YAML)
Q4: Reusable infrastructure?         → core/
Q5: Specific domain model?           → models/implemented/{domain}/
Q6: Measure framework itself?        → models/measures/
Q7: Model discovery/cross-model?     → models/api/
Q8: UI rendering?                    → app/ui/components/
Q9: Application state?               → app/ui/state/
Q10: Notebook parsing?               → app/notebook/
Q11: Operational script?             → scripts/{category}/
```

### Anti-Patterns to Avoid

| Anti-Pattern | Example | Correct Approach |
|--------------|---------|------------------|
| **God File** | 1,885 line markdown_renderer.py | Split into focused modules |
| **Bare Except** | `except: pass` | Specific exceptions with logging |
| **Print Debugging** | `print(f"here: {x}")` | `logger.debug(f"value: {x}")` |
| **Duplicate Implementation** | 3 FilterEngines | One implementation, extend if needed |
| **Cross-Layer Import** | UI imports from pipelines | Add service layer between |
| **Magic Numbers** | `cols = st.columns([0.88, 0.06, 0.06])` | Named constants |
| **Silent Failure** | `except Exception: pass` | Log error, handle or reraise |
| **Direct Backend Import** | `import duckdb` in services | Use `UniversalSession(backend=...)` |

### Pre-Commit Checklist

Before committing ANY code change:

- [ ] Target file is <300 lines (or I'm extracting, not adding)
- [ ] No bare `except:` clauses added
- [ ] No `print()` statements added (use logger)
- [ ] Searched for existing similar code first
- [ ] Imports don't cross layer boundaries
- [ ] No direct `import duckdb` or `import pyspark` (use session abstraction)
- [ ] Correct backend selected (Spark for batch, DuckDB for interactive)
- [ ] Added/updated tests if behavior changed
- [ ] Updated CLAUDE.md if new patterns introduced

### Proposals Reference

For detailed architectural guidance, see these proposals in `docs/vault/13-proposals/draft/`:

| Proposal | Topic |
|----------|-------|
| `008-large-file-refactoring.md` | Specific plans to split large files |
| `009-architecture-guidelines.md` | Layer boundaries and module responsibilities |
| `005-logging-error-handling.md` | Logging framework and exception hierarchy |
| `007-codebase-review-ratings.md` | Current quality ratings and issues |

### Documentation Rules

**When to Update Documentation**:

| Change Type | Documentation Required |
|-------------|----------------------|
| New module/file | Docstring at top explaining purpose |
| New class | Class docstring with usage example |
| New public function | Docstring with Args, Returns, Raises |
| New model | Update CLAUDE.md model list |
| New pattern | Add to CLAUDE.md or create proposal |
| Bug fix | Update related docs if behavior changed |
| Config change | Update relevant section in CLAUDE.md |

**Docstring Standards**:
```python
def calculate_measure(
    self,
    measure_name: str,
    filters: Optional[Dict] = None,
    **kwargs
) -> Any:
    """
    Calculate a measure by name.

    Args:
        measure_name: Name of the measure from YAML config
        filters: Optional filters to apply before calculation
        **kwargs: Additional parameters passed to measure function

    Returns:
        Calculated measure value (type depends on measure definition)

    Raises:
        MeasureNotFoundError: If measure_name not in config
        MeasureError: If calculation fails

    Example:
        >>> model.calculate_measure("avg_close_price", filters={"ticker": "AAPL"})
        185.50
    """
```

**Module Docstrings** (required at top of every new file):
```python
"""
Module Name - Brief description.

Purpose:
    What this module does and why it exists.

Key Classes/Functions:
    - ClassName: What it does
    - function_name: What it does

Usage:
    from module import ClassName
    obj = ClassName(...)

Note:
    Any important caveats or dependencies.
"""
```

### Testing Rules

**When Tests Are Required**:

| Change Type | Test Required? | Test Type |
|-------------|---------------|-----------|
| New function with logic | ✅ Yes | Unit test |
| Bug fix | ✅ Yes | Regression test |
| New model | ✅ Yes | Integration test |
| New API endpoint | ✅ Yes | Integration test |
| Config change only | ⚠️ Maybe | If affects behavior |
| Documentation only | ❌ No | - |
| Refactoring (no behavior change) | ✅ Yes | Verify existing tests pass |

**Test File Location**:
```
scripts/test/
├── unit/                    # Pure function tests, no I/O
│   └── test_{module}.py
├── integration/             # Tests with database/files
│   └── test_{feature}.py
├── validation/              # Data validation tests
│   └── test_{model}_data.py
└── performance/             # Timing/load tests
    └── test_{operation}_perf.py
```

**Test Naming Convention**:
```python
# File: test_{module_name}.py

def test_{function_name}_{scenario}_{expected_result}():
    """Test that {function} does {expected} when {scenario}."""

# Examples:
def test_calculate_measure_with_filters_returns_filtered_result():
def test_apply_filters_empty_list_returns_unchanged():
def test_load_config_missing_file_raises_config_error():
```

**Test Structure (AAA Pattern)**:
```python
def test_calculate_measure_returns_correct_value():
    """Test measure calculation with known data."""
    # Arrange - Set up test data and dependencies
    model = create_test_model()
    expected = 100.0

    # Act - Execute the code under test
    result = model.calculate_measure("test_measure")

    # Assert - Verify the result
    assert result == expected
```

**Always Run Before Committing**:
```bash
# Run relevant tests
pytest scripts/test/unit/test_{module}.py -v

# Run full test suite if touching core modules
pytest scripts/test/ -v --ignore=scripts/test/performance/
```

### Script Conventions

**Script Location by Purpose**:
```
scripts/
├── build/           # Model building scripts
├── ingest/          # Data ingestion scripts
├── forecast/        # Forecasting scripts
├── test/            # Test scripts (see Testing Rules)
├── examples/        # Usage examples (READ-ONLY, don't modify)
└── maintenance/     # Cleanup, migration scripts
```

**Script Template**:
```python
#!/usr/bin/env python
"""
Script Name - Brief description.

Purpose:
    What this script does.

Usage:
    python -m scripts.category.script_name [--options]

Examples:
    python -m scripts.build.rebuild_model --model stocks
    python -m scripts.ingest.run_pipeline --provider alpha_vantage
"""
from __future__ import annotations  # MUST BE FIRST IMPORT

import argparse
import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """Main entry point."""
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    # Add arguments...
    args = parser.parse_args()

    try:
        # Script logic here
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Script Rules**:
1. Always use `python -m scripts.category.name` syntax
2. Always call `setup_repo_imports()` before other imports
3. Always use argparse for CLI arguments
4. Always use logger, not print (except for user-facing output)
5. Always exit with non-zero code on failure

### Commit Message Conventions

**Format**:
```
type: Short description (imperative mood, <50 chars)

Longer description if needed. Explain WHY not just WHAT.
Wrap at 72 characters.

Refs: #issue-number (if applicable)
```

**Types**:
| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that doesn't fix bug or add feature |
| `test` | Adding or updating tests |
| `chore` | Maintenance (deps, config, etc.) |
| `perf` | Performance improvement |

**Examples**:
```bash
# Good
feat: Add Black-Scholes option pricing to options model
fix: Resolve syntax error in forecast scripts
docs: Add code quality rules to CLAUDE.md
refactor: Extract TableAccessor from BaseModel
test: Add unit tests for measure calculation

# Bad
update code  # Too vague
Fixed stuff  # Not imperative, not descriptive
WIP          # Don't commit WIP
```

### When to Ask for Clarification

**STOP and ask the user when**:

1. **Ambiguous requirements**
   - "Make it better" → Better how? Performance? Readability?
   - "Add error handling" → What errors? How to handle?

2. **Multiple valid approaches**
   - Should this be a new module or extend existing?
   - Sync or async implementation?
   - Which design pattern fits best?

3. **Breaking changes**
   - Changing function signatures
   - Modifying config file structure
   - Removing deprecated code

4. **Large scope**
   - Task would touch >5 files
   - Estimated >500 lines of changes
   - Requires new dependencies

5. **Unclear priority**
   - Multiple tasks requested, unclear order
   - Conflict between requirements

**How to ask**:
```
Before I proceed, I have a question:

[Specific question]

Option A: [Description]
- Pros: ...
- Cons: ...

Option B: [Description]
- Pros: ...
- Cons: ...

Which approach would you prefer?
```

### Session Handoff Notes

**When ending a session with incomplete work**:

1. **Update TODO comments** in code:
   ```python
   # TODO(session-date): Description of what's incomplete
   # - What's done
   # - What's remaining
   # - Any blockers
   ```

2. **Create/update proposal** if architectural decision needed

3. **Commit with WIP prefix** (only if user requests):
   ```bash
   git commit -m "WIP: Partial implementation of X

   Completed:
   - Item 1
   - Item 2

   Remaining:
   - Item 3
   - Item 4

   Next steps: [description]"
   ```

4. **Leave breadcrumbs** - Add comments that help the next session:
   ```python
   # NOTE: This implementation is incomplete. See proposal 010 for full design.
   # The next step is to implement the _calculate_metrics method.
   ```

### Configuration Management

**When adding new configuration**:

1. **Add to appropriate location**:
   - Environment secret → `.env` (never commit)
   - API endpoint → `configs/{provider}_endpoints.json`
   - Model config → `configs/models/{model}/*.yaml`
   - App setting → `config/constants.py`

2. **Add type-safe access**:
   ```python
   # In config/models.py, add to appropriate dataclass
   @dataclass
   class NewConfig:
       setting_name: str = "default_value"
   ```

3. **Document in CLAUDE.md** if it's a new pattern

4. **Add validation** in `config/loader.py` if required

---

## Quick Reference

### Directory Purpose Quick Lookup

- `/app/` → Streamlit UI and notebook system
- `/config/` → **Centralized configuration system (NEW)** - ConfigLoader, typed models
- `/configs/` → Configuration files (storage.json, API endpoints, model YAMLs)
- `/core/` → Session management and filters
- `/datapipelines/` → Data ingestion and Bronze layer
- `/models/` → Silver layer models and measure framework
- `/orchestration/` → Pipeline orchestration
- `/tests/` → Unit and integration tests
- `/scripts/` → Operational scripts (use `python -m scripts.script_name`)
  - `/scripts/examples/` → Runnable code examples (queries, measures, extending)
- `/storage/` → Data storage (Bronze/Silver Parquet files, DuckDB catalog)
- `/docs/` → Documentation
- `/utils/` → **Utility functions** - repo.py for centralized repo discovery

### Backend Selection (ENFORCED)

**CRITICAL**: Always use session abstraction. NEVER import `duckdb` or `pyspark` directly in application code.

```python
# ❌ NEVER DO THIS - Direct backend import
import duckdb
conn = duckdb.connect()
result = conn.execute("SELECT ...").fetchdf()

# ❌ NEVER DO THIS - Direct Spark import in models/services
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()

# ✅ CORRECT - Always use session abstraction
from core.session.universal_session import UniversalSession
session = UniversalSession(backend="duckdb")  # or "spark"
result = session.query("SELECT ...")
```

**Backend Selection Rules**:

| Use Case | Backend | Rationale |
|----------|---------|-----------|
| **Model building** | **Spark** | ETL, full table transformations |
| **Bronze → Silver transforms** | **Spark** | Batch processing, scheduled |
| **Pre-calculation tasks** | **Spark** | Metadata collection, aggregations |
| **Column profiling** | **Spark** | Full table scans |
| **Interactive queries** | **DuckDB** | Fast response for UI (10-100x faster) |
| **Notebook execution** | **DuckDB** | User-facing, needs speed |
| **Dashboard rendering** | **DuckDB** | Point queries, small result sets |
| **Ad-hoc analysis** | **DuckDB** | Exploratory queries |
| **Unit tests** | **DuckDB** | In-memory, fast isolation |

**Decision Tree**:
```
Is this a scheduled/batch operation?
  └── YES → Use Spark
  └── NO → Is this user-facing (UI/notebook)?
              └── YES → Use DuckDB
              └── NO → Is it a full table scan or heavy aggregation?
                        └── YES → Use Spark
                        └── NO → Use DuckDB (default for queries)
```

### Model Lifecycle

```
1. Define in YAML → 2. Implement class → 3. Test → 4. Build → 5. Query
```

### Data Flow

```
API → Facet → Bronze → Model → Silver → Query → UI/Notebook
```

---

## Additional Resources

- **GitHub Issues**: Report bugs and request features
- **Code Examples**: `/scripts/examples/` directory (queries, measures, extending)
- **Documentation**: `/docs/guide/` directory
- **Test Examples**: `/tests/` directory
- **Notebook Examples**: `/configs/notebooks/` directory

---

**For more detailed information on specific topics, refer to the specialized markdown files in the repository root and `/docs/guide/` directory.**
