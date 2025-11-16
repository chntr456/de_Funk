# CLAUDE.md - AI Assistant Guide for de_Funk

**Last Updated**: 2025-11-16
**Version**: 1.1

This document provides comprehensive guidance for AI assistants (like Claude) working with the de_Funk codebase. It covers project structure, architecture patterns, development workflows, and key conventions.

**Recent Updates (v1.1)**:
- Added comprehensive Configuration Management System documentation
- Documented new `config/` module with ConfigLoader and typed models
- Added `utils/repo.py` centralized repository discovery
- Updated script execution patterns to use `python -m` module syntax
- Documented configuration precedence rules and environment variable usage

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

---

## Project Overview

**de_Funk** is a modern financial analytics platform that provides:

- **Multi-source data ingestion**: Automated pipelines for financial, economic, and municipal data
- **Dimensional data modeling**: YAML-driven graph-based models using a two-layer architecture (Bronze/Silver)
- **Interactive analytics**: Markdown-based notebooks with dynamic filtering and visualization
- **Time series forecasting**: Multiple ML models (ARIMA, Prophet, Random Forest)
- **High-performance analytics**: DuckDB backend for 10-100x faster queries vs Spark
- **Cross-model analysis**: Unified query interface across multiple domain models

### Data Sources
- **Polygon.io**: Stock prices, company data, news, technical indicators
- **Bureau of Labor Statistics (BLS)**: Economic indicators (unemployment, CPI, GDP)
- **Chicago Data Portal**: Municipal finance data (Socrata API)

### Core Capabilities
- Real-time and historical stock data analysis
- Economic indicator tracking and correlation
- Municipal finance analysis
- ETF holdings and performance tracking
- Multi-model time series forecasting
- Interactive notebook-based analytics

---

## Repository Structure

```
de_Funk/
├── app/                      # Streamlit UI application
│   ├── notebook/            # Notebook system (parsers, managers, filters)
│   ├── services/            # Business logic services
│   └── ui/                  # Streamlit components & main app
├── config/                   # Centralized configuration system (NEW)
│   ├── __init__.py          # ConfigLoader and typed models
│   ├── loader.py            # Configuration loading with precedence
│   ├── models.py            # Type-safe config dataclasses
│   └── constants.py         # Default configuration values
├── configs/
│   ├── models/              # YAML model configurations (8 models)
│   ├── notebooks/           # Markdown notebook definitions
│   ├── storage.json         # Storage paths and table mappings
│   ├── polygon_endpoints.json  # Polygon API configuration
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
│       ├── polygon/         # Stock market data (Polygon.io)
│       ├── chicago/         # Municipal data (Chicago Data Portal)
│       └── bls/             # Economic data (Bureau of Labor Statistics)
├── models/
│   ├── api/                 # Model sessions & registry
│   ├── base/                # BaseModel class framework
│   ├── builders/            # Model building utilities
│   ├── measures/            # Measure framework (simple, computed, weighted)
│   └── implemented/         # Domain models (equity, corporate, macro, etc.)
│       ├── core/            # Calendar dimension (foundation)
│       ├── equity/          # Tradable securities and prices
│       ├── corporate/       # Company entities and fundamentals
│       ├── macro/           # Economic indicators
│       ├── city_finance/    # Municipal finance
│       ├── etf/             # ETF data
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
│   ├── silver/              # Dimensional models (Parquet)
│   └── duckdb/              # DuckDB catalog (analytics.db)
├── docs/
│   └── guide/               # Comprehensive documentation
├── examples/                # Runnable code examples
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
- **Organization**: By data provider (polygon, bls, chicago)
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

All models follow a YAML-driven configuration pattern:

```yaml
model: equity
version: 1
depends_on: [core, corporate]  # Model dependencies
storage:
  root: storage/silver/equity
  format: parquet
schema:
  dimensions:
    dim_equity: {...}
  facts:
    fact_equity_prices: {...}
graph:
  nodes: {...}
  edges: {...}
  paths: {...}
measures:
  avg_close_price: {...}
```

### Model Dependency Graph

Models are organized in tiers based on dependencies:

```
Tier 0 (Foundation):
  └── core (calendar dimension)

Tier 1 (Independent):
  ├── macro (economic indicators)
  └── corporate (company entities)

Tier 2 (Dependent):
  ├── equity (depends on: core, corporate)
  └── city_finance (depends on: core)

Tier 3 (Advanced):
  ├── etf (depends on: equity)
  └── forecast (depends on: equity)
```

### Cross-Model Relationships

- **equity ↔ corporate**: Equity instruments belong to corporate entities
- **forecast → equity**: Predictions reference equity prices
- **etf → equity**: ETF holdings reference equities
- **All → core**: All models link to calendar dimension

### Key Architectural Patterns

1. **Centralized Configuration**: ConfigLoader for type-safe, validated configuration
2. **BaseModel Inheritance**: All models extend `models/base/model.py::BaseModel`
3. **Storage Router**: Abstracts Bronze/Silver path resolution
4. **Backend Agnostic**: Adapters for both Spark and DuckDB
5. **Measure Framework**: Unified calculation engine (simple, computed, weighted)
6. **Universal Session**: Cross-model query interface
7. **Filter Engine**: Backend-agnostic filter application
8. **Lazy Loading**: Models and tables loaded on demand
9. **Graph-Based Dependencies**: NetworkX for dependency resolution

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
polygon_cfg = config.apis.get("polygon", {})
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

# Backward compatible properties still work
polygon_cfg = ctx.polygon_cfg  # Still works!

# New method for any API provider
bls_cfg = ctx.get_api_config("bls")
```

### Environment Variables

Set in `.env` file (copy from `.env.example`):

```bash
# API Keys (required for data ingestion)
POLYGON_API_KEYS=your_key_here
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
   - Update configuration files (e.g., `polygon_endpoints.json`)
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

- **`examples/measure_framework/01_basic_usage.py`**: Usage examples
- **`examples/measure_framework/02_troubleshooting.py`**: Debug guide
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
| `configs/polygon_endpoints.json` | Polygon API endpoint configuration (auto-discovered) |
| `configs/bls_endpoints.json` | BLS API endpoint configuration (auto-discovered) |
| `configs/chicago_endpoints.json` | Chicago API endpoint configuration (auto-discovered) |
| `configs/models/*.yaml` | Model definitions (8 models) |
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

**In Progress: `company` model migration** → Splitting into `equity` and `corporate`
- Several cross-model edges need updating
- Documented in `MODEL_DEPENDENCY_ANALYSIS.md`
- Some notebooks may reference old `company` model

### Backend Support

- **DuckDB**: Primary backend, fully supported (10-100x faster)
- **Spark**: Optional backend, maintained for compatibility
- Most operations tested on both backends

### Data Sources Status

- **Polygon.io**: Active, fully integrated (API limit: 1000/request)
- **BLS**: Active, economic indicators working
- **Chicago Data Portal**: Active, municipal finance data

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
3. **Use examples**: Look at `/examples/` for usage patterns
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
- `/storage/` → Data storage (Bronze/Silver Parquet files, DuckDB catalog)
- `/docs/` → Documentation
- `/examples/` → Code examples
- `/utils/` → **Utility functions** - repo.py for centralized repo discovery

### Backend Selection

```python
# Use DuckDB (recommended - fast)
from core.session.universal_session import UniversalSession
session = UniversalSession(backend="duckdb")

# Use Spark (optional - for large datasets)
session = UniversalSession(backend="spark")
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
- **Code Examples**: `/examples/` directory
- **Documentation**: `/docs/guide/` directory
- **Test Examples**: `/tests/` directory
- **Notebook Examples**: `/configs/notebooks/` directory

---

**For more detailed information on specific topics, refer to the specialized markdown files in the repository root and `/docs/guide/` directory.**
