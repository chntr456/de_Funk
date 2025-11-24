# UniversalSession Reference

**Complete documentation for the UniversalSession class**

File: `models/api/session.py`
Line: 47-1063

---

## Overview

`UniversalSession` is the **unified query interface** for all models in de_Funk. It provides model-agnostic access to tables, automatic cross-model joins, dynamic filtering, and intelligent aggregation.

### Key Features

- **Dynamic model loading**: Load any model on demand from YAML configs
- **Cross-model queries**: Access tables from multiple models seamlessly
- **Auto-join capability**: Automatically joins tables based on graph relationships
- **Filter pushdown**: Applies filters before joins for optimal performance
- **Smart aggregation**: Changes data grain based on group_by specifications
- **Backend abstraction**: Works with both Spark and DuckDB
- **Session injection**: Models can reference each other via injected session

### Design Patterns

- **Lazy Loading**: Models loaded on first access, cached thereafter
- **Dependency Injection**: Session injected into models for cross-model access
- **Graph Traversal**: Uses model dependency graph for join planning
- **Strategy Pattern**: Different backends (Spark/DuckDB) use different execution strategies

---

## Class Constructor

### `__init__(connection, storage_cfg, repo_root, models=None)`

Initialize a UniversalSession.

**Parameters:**
- `connection` - Database connection (SparkConnection or DuckDBConnection)
- `storage_cfg` - Storage configuration dict (from `storage.json`)
- `repo_root` - Repository root path
- `models` - Optional list of model names to pre-load

**Initializes:**
- Model registry for dynamic loading
- Model dependency graph (NetworkX-based)
- Empty model cache (`_models`)
- Filter engine

**Example:**
```python
from pathlib import Path
from core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type="duckdb")

session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=Path.cwd(),
    models=['equity', 'corporate']  # Pre-load these models
)
```

---

## Properties

### `backend` (property)

Detect backend type from connection.

**Returns:** `"spark"` or `"duckdb"`

**Raises:** `ValueError` if connection type unknown

**Detection Logic:**
- Checks for 'spark' in type name or `.sql()` method → Spark
- Checks for 'duckdb' in type name or `._conn` attribute → DuckDB

**Example:**
```python
print(session.backend)  # "duckdb"
```

---

## Model Management Methods

### `load_model(model_name: str)`

Dynamically load a model by name.

**Process:**
1. Check cache - return if already loaded
2. Get model config from registry (YAML)
3. Get model class from registry (Python class)
4. Instantiate model with connection and storage
5. Inject session via `set_session()` for cross-model access
6. Cache instance
7. Return model

**Parameters:**
- `model_name` - Model identifier (e.g., "equity", "corporate")

**Returns:** BaseModel instance

**Caching:** Model instances cached in `_models` dict

**Example:**
```python
equity_model = session.load_model("equity")
corporate_model = session.load_model("corporate")

# Second call returns cached instance
equity_model_cached = session.load_model("equity")
assert equity_model is equity_model_cached
```

---

### `get_model_instance(model_name: str)`

Get model instance directly (alias for `load_model`).

Useful for accessing model-specific methods not available through session.

**Parameters:**
- `model_name` - Model identifier

**Returns:** BaseModel instance

**Example:**
```python
equity_model = session.get_model_instance("equity")

# Access model-specific methods
metadata = equity_model.get_metadata()
relations = equity_model.get_relations()
```

---

### `list_models() -> list[str]`

List all available models.

**Returns:** List of model names

**Source:** Model registry (scans `configs/models/*.yaml`)

**Example:**
```python
models = session.list_models()
# ['core', 'corporate', 'equity', 'macro', 'forecast', 'etf', 'city_finance']
```

---

### `get_model_metadata(model_name: str) -> Dict[str, Any]`

Get comprehensive metadata for a model.

**Parameters:**
- `model_name` - Model identifier

**Returns:** Dict containing:
- `model_name` - Model identifier
- `version` - Model version
- `backend` - Backend type
- `table_count` - Number of tables
- `dimensions` - List of dimension names
- `facts` - List of fact names
- `measures` - Available measures
- `dependencies` - Model dependencies

**Example:**
```python
metadata = session.get_model_metadata("equity")
print(f"Model: {metadata['model_name']}")
print(f"Tables: {metadata['table_count']}")
print(f"Depends on: {metadata['dependencies']}")
```

---

## Table Access Methods

### `get_table(model_name, table_name, required_columns=None, filters=None, group_by=None, aggregations=None, use_cache=True)`

Get a table from any model with **automatic joins and aggregation**.

This is the **main query method** - it transparently handles:
- Cross-table joins based on graph relationships
- Filter pushdown for performance
- Data aggregation to change grain

**Parameters:**
- `model_name` - Model identifier
- `table_name` - Base table name
- `required_columns` - Optional list of columns needed (auto-joins if missing)
- `filters` - Optional filters dict (pushed down before joins)
- `group_by` - Optional list of columns to group by (dimensions at new grain)
- `aggregations` - Optional dict mapping column → agg function
- `use_cache` - Whether to use cached data (kept for backwards compatibility)

**Returns:** DataFrame with requested columns (auto-joined and aggregated if needed)

**Auto-Join Logic:**
1. Check if all `required_columns` exist in `table_name`
2. If missing columns → find materialized view with all columns
3. If no materialized view → use graph to plan joins
4. Execute joins and return enriched DataFrame

**Filter Pushdown:**
- Filters applied to base table BEFORE joins
- Reduces data volume early for better performance

**Aggregation:**
- If `group_by` specified, data aggregated to new grain
- Aggregation functions inferred from measure metadata or provided explicitly

**Example - Simple:**
```python
# Get full table
prices = session.get_table('equity', 'fact_equity_prices')
```

**Example - Auto-Join:**
```python
# company_name not in fact_equity_prices
# System auto-joins: fact_equity_prices → dim_equity → corporate.dim_company
enriched = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'trade_date', 'close', 'company_name']
)
```

**Example - With Filters:**
```python
# Filter BEFORE join (pushdown)
filtered = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'close', 'exchange_name'],
    filters={'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}
)
```

**Example - Aggregation:**
```python
# Change grain from ticker-level to exchange-level
exchange_summary = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
    group_by=['trade_date', 'exchange_name'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
```

---

### `get_dimension_df(model_name: str, dim_id: str)`

Get a dimension table.

**Parameters:**
- `model_name` - Model identifier
- `dim_id` - Dimension identifier (e.g., "dim_equity")

**Returns:** Dimension DataFrame

**Example:**
```python
equity_dim = session.get_dimension_df('equity', 'dim_equity')
```

---

### `get_fact_df(model_name: str, fact_id: str)`

Get a fact table.

**Parameters:**
- `model_name` - Model identifier
- `fact_id` - Fact identifier (e.g., "fact_equity_prices")

**Returns:** Fact DataFrame

**Example:**
```python
prices = session.get_fact_df('equity', 'fact_equity_prices')
```

---

### `list_tables(model_name: str) -> Dict[str, list[str]]`

List all tables in a model.

**Parameters:**
- `model_name` - Model identifier

**Returns:** Dict with `'dimensions'` and `'facts'` keys

**Example:**
```python
tables = session.list_tables('equity')
print(f"Dimensions: {tables['dimensions']}")
# ['dim_equity']
print(f"Facts: {tables['facts']}")
# ['fact_equity_prices', 'fact_equity_news']
```

---

## Filter Methods

### `get_filter_column_mappings(model_name: str, table_name: str) -> Dict[str, str]`

Get automatic filter column mappings based on graph edges.

Examines edges to `dim_calendar` and extracts column mappings, allowing filters like 'trade_date' to be automatically mapped to table-specific columns like 'metric_date'.

**Parameters:**
- `model_name` - Model identifier
- `table_name` - Table name

**Returns:** Dict mapping standard filter columns to table columns

**Example:**
```yaml
# forecast model edge:
edges:
  - from: fact_forecast_metrics
    to: core.dim_calendar
    on: [metric_date = trade_date]
```

```python
mappings = session.get_filter_column_mappings('forecast', 'fact_forecast_metrics')
# {'trade_date': 'metric_date'}

# Now filter with standard 'trade_date' column name
# System automatically maps to 'metric_date' for this table
```

---

## Auto-Join Methods (Internal)

These methods implement the transparent auto-join capability.

### `_find_materialized_view(model_name, required_columns) -> Optional[str]`

Find a materialized view containing all required columns.

**Strategy 1** in auto-join: Check if pre-computed join (materialized path) has all columns.

**Parameters:**
- `model_name` - Model to search
- `required_columns` - Columns needed

**Returns:** Table name of materialized view, or `None`

**Logic:**
1. Get all facts (where paths are stored)
2. For each fact, get schema
3. Check if all `required_columns` in schema
4. Return first match

**Example:**
```python
# Internally called by get_table()
view = session._find_materialized_view(
    'equity',
    ['ticker', 'close', 'company_name']
)
# Returns: 'equity_prices_with_company' (if exists)
```

---

### `_plan_auto_joins(model_name, base_table, missing_columns) -> Dict[str, Any]`

Plan join sequence to get missing columns using model graph.

**Strategy 2** in auto-join: Build joins dynamically from graph edges.

**Parameters:**
- `model_name` - Model name
- `base_table` - Starting table
- `missing_columns` - Columns to find

**Returns:** Join plan dict:
- `table_sequence` - List of tables to join
- `join_keys` - List of (left_col, right_col) pairs
- `target_columns` - Which columns come from which table

**Algorithm:**
1. Build column-to-table index
2. Find which tables have missing columns
3. Greedy graph traversal from base_table
4. Add tables until all targets reached
5. Extract join keys from edges

**Raises:** `ValueError` if no join path found

**Example:**
```python
# Internally called
plan = session._plan_auto_joins(
    'equity',
    'fact_equity_prices',
    ['company_name', 'exchange_name']
)
# {
#   'table_sequence': ['fact_equity_prices', 'dim_equity', 'dim_company'],
#   'join_keys': [('ticker', 'ticker'), ('company_id', 'id')],
#   'target_columns': {'company_name': 'dim_company', 'exchange_name': 'dim_company'}
# }
```

---

### `_execute_auto_joins(model_name, join_plan, required_columns, filters=None)`

Execute the join plan to get required columns.

**Parameters:**
- `model_name` - Model name
- `join_plan` - Join plan from `_plan_auto_joins()`
- `required_columns` - Columns to return
- `filters` - Optional filters to apply

**Returns:** DataFrame with required columns

**Backend Implementation:**

**Spark:**
- Uses DataFrame API
- Applies filters to base table first (pushdown)
- Chains `.join()` operations
- Selects required columns

**DuckDB:**
- Uses SQL for joins (more efficient)
- Registers temp tables
- Builds `LEFT JOIN` SQL with qualified column names
- Adds `WHERE` clause for filter pushdown
- Executes query and returns pandas DataFrame

**Example SQL (DuckDB):**
```sql
SELECT _autojoin_fact_equity_prices.ticker,
       _autojoin_fact_equity_prices.close,
       _autojoin_dim_company.company_name
FROM _autojoin_fact_equity_prices
LEFT JOIN _autojoin_dim_equity
  ON _autojoin_fact_equity_prices.ticker = _autojoin_dim_equity.ticker
LEFT JOIN _autojoin_dim_company
  ON _autojoin_dim_equity.company_id = _autojoin_dim_company.id
WHERE _autojoin_fact_equity_prices.trade_date BETWEEN '2024-01-01' AND '2024-12-31'
```

---

### `_build_column_index(model_name: str) -> Dict[str, List[str]]`

Build reverse index: column_name → [table_names].

**Parameters:**
- `model_name` - Model to index

**Returns:** Dict mapping column names to tables that have that column

**Used by:** `_plan_auto_joins()` to find which tables contain missing columns

**Example:**
```python
index = session._build_column_index('equity')
# {
#   'ticker': ['dim_equity', 'fact_equity_prices'],
#   'company_name': ['dim_company'],
#   'close': ['fact_equity_prices'],
#   ...
# }
```

---

### `_parse_join_condition(condition: str) -> Tuple[str, str]`

Parse join condition like `"ticker=ticker"`.

**Parameters:**
- `condition` - Join condition string

**Returns:** Tuple of (left_column, right_column)

**Example:**
```python
left, right = session._parse_join_condition("ticker=ticker")
# ('ticker', 'ticker')

left, right = session._parse_join_condition("exchange_code=exchange_code")
# ('exchange_code', 'exchange_code')
```

---

## Aggregation Methods (Internal)

### `_aggregate_data(model_name, df, required_columns, group_by, aggregations=None)`

Aggregate data to a new grain using group_by and measure aggregations.

**Parameters:**
- `model_name` - Model name (for measure metadata lookup)
- `df` - DataFrame to aggregate
- `required_columns` - All columns in result
- `group_by` - Columns to group by (dimensions)
- `aggregations` - Optional dict mapping column → agg function

**Returns:** Aggregated DataFrame

**Aggregation Functions:**
- `avg` - Average
- `sum` - Sum
- `max` - Maximum
- `min` - Minimum
- `count` - Count
- `first` - First value

**Example:**
```python
# Input: ticker-level prices (10M rows)
# Output: exchange-level prices (1,825 rows for 5 exchanges * 365 days)
aggregated = session._aggregate_data(
    'equity',
    prices_df,
    required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
    group_by=['trade_date', 'exchange_name'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
```

---

### `_infer_aggregations(model_name: str, measure_cols: List[str]) -> Dict[str, str]`

Infer aggregation functions from model metadata.

**Parameters:**
- `model_name` - Model to look up metadata
- `measure_cols` - Measure columns to infer aggregations for

**Returns:** Dict mapping measure column → aggregation function

**Logic:**
1. Check model config for measure definitions
2. Use configured aggregation if available
3. Fall back to defaults based on column name

**Example:**
```yaml
# Model config
measures:
  close:
    aggregation: avg
  volume:
    aggregation: sum
```

```python
aggs = session._infer_aggregations('equity', ['close', 'volume'])
# {'close': 'avg', 'volume': 'sum'}
```

---

### `_default_aggregation(column_name: str) -> str`

Determine default aggregation based on column name heuristics.

**Parameters:**
- `column_name` - Name of the measure column

**Returns:** Aggregation function

**Heuristics:**
- Contains `volume`, `count`, `total`, `quantity` → `sum`
- Contains `high`, `max`, `peak` → `max`
- Contains `low`, `min` → `min`
- Default → `avg`

**Example:**
```python
session._default_aggregation('close_price')  # 'avg'
session._default_aggregation('volume')       # 'sum'
session._default_aggregation('high_price')   # 'max'
session._default_aggregation('low_price')    # 'min'
```

---

### `_aggregate_spark(df, group_by, aggregations)`

Aggregate Spark DataFrame using `groupBy` and `agg`.

**Parameters:**
- `df` - Spark DataFrame
- `group_by` - Columns to group by
- `aggregations` - Dict of column → agg function

**Returns:** Aggregated Spark DataFrame

**Implementation:**
```python
from pyspark.sql import functions as F

# Build aggregation expressions
agg_exprs = [F.avg('close').alias('close'), F.sum('volume').alias('volume')]

# Group and aggregate
result = df.groupBy('trade_date', 'exchange_name').agg(*agg_exprs)
```

---

### `_aggregate_duckdb(df, group_by, aggregations)`

Aggregate DuckDB relation using SQL `GROUP BY`.

**Parameters:**
- `df` - DuckDB relation or pandas DataFrame
- `group_by` - Columns to group by
- `aggregations` - Dict of column → agg function

**Returns:** Aggregated pandas DataFrame

**Implementation:**
```python
# Build SQL
sql = """
SELECT trade_date, exchange_name,
       AVG(close) as close,
       SUM(volume) as volume
FROM df
GROUP BY trade_date, exchange_name
"""

# Execute
result = connection.conn.execute(sql).df()
```

---

## Helper Methods

### `_select_columns(df, columns: List[str])`

Select specific columns from DataFrame (backend agnostic).

**Parameters:**
- `df` - DataFrame (Spark or DuckDB)
- `columns` - List of column names

**Returns:** DataFrame with only specified columns

**Backend Implementation:**
- **Spark**: Uses `select(*columns)`
- **DuckDB**: Uses `project(cols)` for relations or direct indexing for pandas

**Example:**
```python
# Internally called
subset = session._select_columns(df, ['ticker', 'close', 'volume'])
```

---

## Method Summary by Category

### Model Management (5 methods)
- `load_model()` - Dynamic model loading with caching
- `get_model_instance()` - Get model instance directly
- `list_models()` - List available models
- `get_model_metadata()` - Get model metadata
- `list_tables()` - List tables in model

### Table Access (3 methods)
- `get_table()` - Main query method with auto-join/aggregation
- `get_dimension_df()` - Get dimension table
- `get_fact_df()` - Get fact table

### Filter Support (1 method)
- `get_filter_column_mappings()` - Auto filter mapping

### Auto-Join (5 methods)
- `_find_materialized_view()` - Find pre-computed joins
- `_plan_auto_joins()` - Plan join sequence
- `_execute_auto_joins()` - Execute joins
- `_build_column_index()` - Index columns to tables
- `_parse_join_condition()` - Parse join specs

### Aggregation (4 methods)
- `_aggregate_data()` - Main aggregation orchestrator
- `_infer_aggregations()` - Infer from metadata
- `_default_aggregation()` - Default heuristics
- `_aggregate_spark()` - Spark implementation
- `_aggregate_duckdb()` - DuckDB implementation

### Helper (1 method)
- `_select_columns()` - Column selection

---

## Usage Patterns

### Basic Usage

```python
from pathlib import Path
from core.context import RepoContext

# Setup
ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=Path.cwd()
)

# Get table
prices = session.get_table('equity', 'fact_equity_prices')
print(f"Loaded {len(prices)} rows")
```

### Cross-Model Query

```python
# Access tables from multiple models
equity_dim = session.get_table('equity', 'dim_equity')
calendar_dim = session.get_table('core', 'dim_calendar')
company_dim = session.get_table('corporate', 'dim_company')

# Models can access each other via injected session
# equity model can reference corporate.dim_company in edges/paths
```

### Auto-Join Query

```python
# Request columns that don't exist in base table
# System automatically finds and executes join path
enriched_prices = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=[
        'ticker',           # In fact_equity_prices
        'trade_date',       # In fact_equity_prices
        'close',            # In fact_equity_prices
        'company_name',     # In corporate.dim_company (auto-joined)
        'exchange_name'     # In dim_exchange (auto-joined)
    ]
)

# System executed:
# fact_equity_prices → dim_equity → corporate.dim_company
```

### Filtered Query with Aggregation

```python
# Complex query: filter, join, aggregate
exchange_summary = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
    filters={
        'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'},
        'ticker': ['AAPL', 'MSFT', 'GOOGL']
    },
    group_by=['trade_date', 'exchange_name'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)

# Process:
# 1. Filter fact_equity_prices (pushdown)
# 2. Auto-join to get exchange_name
# 3. Aggregate to exchange-level grain
```

### Model Discovery

```python
# Discover available models and tables
models = session.list_models()
print(f"Available models: {models}")

for model_name in models:
    tables = session.list_tables(model_name)
    print(f"\n{model_name}:")
    print(f"  Dimensions: {tables['dimensions']}")
    print(f"  Facts: {tables['facts']}")

    metadata = session.get_model_metadata(model_name)
    print(f"  Depends on: {metadata.get('dependencies', [])}")
```

---

## Best Practices

1. **Use get_table() as primary interface**: Leverages auto-join and aggregation
2. **Specify required_columns**: Enables auto-join optimization
3. **Apply filters early**: Filter pushdown improves performance
4. **Let system infer aggregations**: Uses measure metadata when available
5. **Pre-load frequently used models**: Pass `models` list to constructor
6. **Use backend property**: Write backend-agnostic code
7. **Leverage model graph**: Define edges in YAML for auto-join support

---

## Architecture Diagram Integration

UniversalSession sits at the center of the system:

```
┌─────────────────┐
│  User/Notebook  │
└────────┬────────┘
         │
         v
┌─────────────────────────┐
│  UniversalSession       │
│  • Model registry       │
│  • Model cache          │
│  • Dependency graph     │
└───┬─────────────────┬───┘
    │                 │
    v                 v
┌──────────┐    ┌──────────┐
│ Model A  │    │ Model B  │
│ (equity) │    │(corporate)│
└────┬─────┘    └─────┬────┘
     │                │
     v                v
┌─────────────────────────┐
│  Storage (Parquet)      │
└─────────────────────────┘
```

---

## Related Documentation

- [BaseModel Reference](base-model.md) - Models accessed by session
- [Graph Architecture](../02-graph-architecture/graph-overview.md) - Auto-join foundation
- [FilterEngine](filter-engine.md) - Filter application
- [Connection System](connection-system.md) - Backend adapters
