# BaseModel Reference

**Complete documentation for the BaseModel class**

File: `models/base/model.py`
Line: 67-1230

---

## Overview

`BaseModel` is the **foundation class for all dimensional models** in de_Funk. It provides a complete YAML-driven framework for building, querying, and managing dimensional models with automatic graph building, cross-model references, and backend abstraction.

### Why BaseModel Has 40+ Methods

Instead of duplicating graph-building logic across 8+ models, BaseModel centralizes all functionality into a single, powerful base class. This provides:

- **Consistency**: All models work the same way
- **Maintainability**: Fix bugs once, all models benefit
- **Extensibility**: Override specific methods for custom behavior
- **Backend Agnostic**: Same code works with Spark or DuckDB

### Design Patterns

- **Template Method Pattern**: `build()` orchestrates standard workflow, subclasses override hooks
- **Lazy Loading**: Tables built on first access via `ensure_built()`
- **Backend Abstraction**: Methods automatically adapt to Spark or DuckDB
- **Graph-Based**: Uses NetworkX internally for dependency resolution

---

## Class Constructor

### `__init__(connection, storage_cfg, model_cfg, params=None)`

Initialize a model instance.

**Parameters:**
- `connection` - Database connection (SparkConnection or DuckDBConnection)
- `storage_cfg` - Storage configuration dict (from `storage.json`)
- `model_cfg` - Model YAML configuration dict
- `params` - Optional runtime parameters (filters, date ranges, etc.)

**Initializes:**
- Storage router for path management
- Backend detection (Spark or DuckDB)
- Lazy loading infrastructure
- Measure executor and query planner

**Example:**
```python
from core.context import RepoContext
from models.api.registry import get_model_registry

ctx = RepoContext.from_repo_root(connection_type="duckdb")
registry = get_model_registry()

equity_model = registry.create_model_instance(
    "equity",
    connection=ctx.connection,
    storage=ctx.storage,
    params={"ticker": "AAPL"}
)
```

---

## Properties

### `backend` (property)

Returns backend type: `"spark"` or `"duckdb"`

**Returns:** `str`

**Example:**
```python
print(model.backend)  # "duckdb"
```

### `measures` (property)

Get unified measure executor for calculating measures.

**Returns:** `MeasureExecutor` instance

**Example:**
```python
executor = model.measures
result = executor.calculate("avg_close_price", filters=[...])
```

### `query_planner` (property)

Get query planner for dynamic table joins.

**Returns:** `QueryPlanner` instance

**Example:**
```python
planner = model.query_planner
df = planner.join_tables(["dim_equity", "fact_equity_prices"])
```

---

## Graph Building Methods

These methods implement the YAML-driven graph building process.

### `build() -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]`

**Main orchestrator** for model building. Executes the complete build workflow.

**Process:**
1. Call `before_build()` hook
2. Build nodes from YAML graph.nodes
3. Validate edges between nodes
4. Materialize paths (joined views)
5. Separate dims and facts
6. Call `after_build()` hook

**Returns:** Tuple of (dimensions, facts) dictionaries

**Example:**
```python
dims, facts = model.build()
print(f"Built {len(dims)} dimensions, {len(facts)} facts")
```

**Called by:** `ensure_built()` on first access

---

### `_build_nodes() -> Dict[str, DataFrame]`

Build all nodes from `graph.nodes` YAML configuration.

**For each node:**
1. Check for custom loader via `custom_node_loading()`
2. Load from Bronze table or parent node
3. Apply `select` transformations (column selection/aliasing)
4. Apply `derive` transformations (computed columns)
5. Enforce `unique_key` constraints (deduplication)

**Returns:** Dict mapping node_id → DataFrame

**Node Configuration Example:**
```yaml
graph:
  nodes:
    - id: dim_equity
      from: bronze.ref_ticker
      select:
        ticker: ticker
        name: name
        exchange: primary_exchange
      derive:
        equity_key: sha1(ticker)
      unique_key: [ticker]
```

**Backend Support:**
- **Spark**: Uses PySpark DataFrame operations
- **DuckDB**: Uses DuckDB relation operations

---

### `_apply_edges(nodes: Dict[str, DataFrame]) -> None`

Validate edges between nodes with dry-run joins.

**Validation:**
- Both nodes exist (supports cross-model references)
- Join columns exist in both DataFrames
- Join is valid (executes limit(1) join)

**Supports:**
- Local edges: `dim_equity → fact_equity_prices`
- Cross-model edges: `dim_equity → core.dim_calendar`

**Edge Configuration Example:**
```yaml
graph:
  edges:
    - from: fact_equity_prices
      to: dim_equity
      on: [ticker = ticker]
    - from: fact_equity_prices
      to: core.dim_calendar
      on: [trade_date = date]
```

**Note:** Skipped for DuckDB backend (validation only in Spark)

---

### `_materialize_paths(nodes: Dict[str, DataFrame]) -> Dict[str, DataFrame]`

Create materialized views by joining nodes along paths.

**Paths** represent denormalized views optimized for analytics queries.

**Path Configuration Example:**
```yaml
graph:
  paths:
    - id: equity_prices_with_company
      hops: fact_equity_prices -> dim_equity -> corporate.dim_company
```

**Process:**
1. Parse hops into chain of nodes
2. Resolve each node (supports cross-model)
3. Join sequentially with deduplication
4. Return materialized DataFrame

**Returns:** Dict mapping path_id → joined DataFrame

**Note:** Skipped for DuckDB backend (paths not yet implemented)

---

### `_load_bronze_table(table_name: str) -> DataFrame`

Load a Bronze table using StorageRouter.

**Parameters:**
- `table_name` - Logical table name from storage config

**Backend Handling:**
- **Spark**: Uses `BronzeTable` class with schema merging
- **DuckDB**: Uses `connection.read_parquet()`

**Returns:** DataFrame with merged schema

**Example:**
```python
df = model._load_bronze_table("prices_daily")
```

---

### `_select_columns(df: DataFrame, select_config: Dict[str, str]) -> DataFrame`

Apply column selection and aliasing (backend-agnostic).

**Parameters:**
- `df` - Input DataFrame
- `select_config` - Dict mapping output_name → expression

**Example:**
```yaml
select:
  ticker: ticker
  company_name: name
  market: primary_exchange
```

**Backend Implementation:**
- **Spark**: Uses `F.col().alias()`
- **DuckDB**: Uses `project()` with AS clauses

**Returns:** DataFrame with selected/renamed columns

---

### `_apply_derive(df: DataFrame, col_name: str, expr: str, node_id: str) -> DataFrame`

Create computed columns from expressions.

**Supports:**
- Column references: `"ticker"` → `F.col("ticker")`
- SHA1 hashing: `"sha1(ticker)"` → `F.sha1(F.col("ticker"))`
- SQL expressions: Window functions, aggregations, etc.

**Parameters:**
- `df` - Input DataFrame
- `col_name` - Output column name
- `expr` - Derive expression
- `node_id` - Node ID (for error messages)

**Example:**
```yaml
derive:
  equity_key: sha1(ticker)
  price_range: high - low
  returns: (close - open) / open
```

**Backend Implementation:**
- **Spark**: Uses `withColumn()` with `F.expr()`
- **DuckDB**: Uses SQL SELECT with temp table registration

**Returns:** DataFrame with new column

**Error Handling:** Logs warning and skips unsupported expressions

---

### `_resolve_node(node_id: str, nodes: Dict[str, DataFrame]) -> DataFrame`

Resolve node DataFrame with cross-model reference support.

**Supports:**
- Local nodes: `"dim_equity"`
- Cross-model: `"core.dim_calendar"`, `"corporate.dim_company"`

**Parameters:**
- `node_id` - Node identifier
- `nodes` - Local nodes dictionary

**Cross-Model Process:**
1. Parse `model_name.table_name`
2. Get model instance from session
3. Ensure model is built
4. Fetch dimension or fact table

**Returns:** DataFrame

**Raises:** `ValueError` if node not found

**Example:**
```python
# Local node
equity_dim = model._resolve_node("dim_equity", nodes)

# Cross-model reference
calendar_dim = model._resolve_node("core.dim_calendar", nodes)
```

---

## Data Access Methods

### `ensure_built()`

Ensure model is built (lazy loading). Builds only on first call.

**Thread-safe with `_build_lock`**

**Example:**
```python
model.ensure_built()  # First call: builds model
model.ensure_built()  # Subsequent calls: no-op
```

---

### `get_table(table_name: str) -> DataFrame`

Retrieve table by name (dimension or fact).

**Parameters:**
- `table_name` - Table identifier (e.g., "dim_equity", "fact_equity_prices")

**Process:**
1. Call `ensure_built()` to lazy-load
2. Check dimensions first
3. Check facts second
4. Raise KeyError if not found

**Returns:** DataFrame

**Example:**
```python
equity_dim = model.get_table("dim_equity")
prices_fact = model.get_table("fact_equity_prices")
```

---

### `get_table_enriched(table_name: str, join_path: Optional[List[str]] = None) -> DataFrame`

Fetch table with optional joins along a path.

**Parameters:**
- `table_name` - Base table name
- `join_path` - List of tables to join (e.g., `["dim_equity", "corporate.dim_company"]`)

**Uses query planner** for dynamic joins.

**Returns:** Enriched DataFrame

**Example:**
```python
# Get prices with company information
enriched = model.get_table_enriched(
    "fact_equity_prices",
    join_path=["dim_equity", "corporate.dim_company"]
)
```

---

### `get_dimension_df(dim_id: str) -> DataFrame`

Get dimension DataFrame by ID.

**Parameters:**
- `dim_id` - Dimension identifier (e.g., "dim_equity")

**Returns:** Dimension DataFrame

**Raises:** `KeyError` if dimension not found

---

### `get_fact_df(fact_id: str) -> DataFrame`

Get fact DataFrame by ID.

**Parameters:**
- `fact_id` - Fact identifier (e.g., "fact_equity_prices")

**Returns:** Fact DataFrame

**Raises:** `KeyError` if fact not found

---

### `has_table(table_name: str) -> bool`

Check if table exists in model.

**Parameters:**
- `table_name` - Table identifier

**Returns:** `True` if table exists, `False` otherwise

**Example:**
```python
if model.has_table("fact_equity_prices"):
    df = model.get_table("fact_equity_prices")
```

---

### `list_tables() -> Dict[str, List[str]]`

Get inventory of all tables.

**Returns:** Dict with keys `"dimensions"` and `"facts"`

**Example:**
```python
tables = model.list_tables()
print(f"Dimensions: {tables['dimensions']}")
print(f"Facts: {tables['facts']}")
```

---

### `get_table_schema(table_name: str) -> Dict[str, str]`

Get schema for a table (column names and types).

**Parameters:**
- `table_name` - Table identifier

**Returns:** Dict mapping column_name → data_type

**Backend Support:**
- **Spark**: Uses `df.dtypes`
- **DuckDB**: Uses `df.types`

**Example:**
```python
schema = model.get_table_schema("dim_equity")
for col, dtype in schema.items():
    print(f"{col}: {dtype}")
```

---

## Measure Execution Methods

### `calculate_measure(measure_id: str, filters: List[Dict] = None, group_by: List[str] = None) -> DataFrame`

Execute a measure calculation.

**Parameters:**
- `measure_id` - Measure identifier from YAML
- `filters` - List of filter dicts
- `group_by` - Columns to group by

**Delegates to:** `self.measures.calculate()`

**Returns:** DataFrame with measure results

**Example:**
```python
result = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}],
    group_by=["trade_date"]
)
```

---

### `calculate_measure_by_entity(measure_id: str, entity_col: str, entities: List[str], filters: List[Dict] = None) -> Dict[str, Any]`

Calculate measure grouped by entity values.

**Parameters:**
- `measure_id` - Measure identifier
- `entity_col` - Column to group by (e.g., "ticker")
- `entities` - List of entity values (e.g., ["AAPL", "MSFT"])
- `filters` - Additional filters

**Returns:** Dict mapping entity_value → measure_result

**Example:**
```python
results = model.calculate_measure_by_entity(
    "avg_close_price",
    entity_col="ticker",
    entities=["AAPL", "MSFT", "GOOGL"]
)

for ticker, avg_price in results.items():
    print(f"{ticker}: ${avg_price:.2f}")
```

---

## Cross-Model Support Methods

### `set_session(session)`

Inject UniversalSession reference for cross-model access.

**Called by:** `UniversalSession` after model instantiation

**Parameters:**
- `session` - UniversalSession instance

**Enables:**
- Cross-model table loading via `session.load_model()`
- Cross-model edge validation
- Cross-model path materialization

**Example:**
```python
# Typically called automatically
model.set_session(session)

# Now cross-model references work
df = model._resolve_node("core.dim_calendar", nodes)
```

---

## Metadata & Introspection Methods

### `get_relations() -> Dict[str, List[str]]`

Get relationship map showing which tables connect to which.

**Returns:** Dict mapping from_table → list of to_tables

**Example:**
```python
relations = model.get_relations()
# {
#   "fact_equity_prices": ["dim_equity", "core.dim_calendar"],
#   "dim_equity": ["corporate.dim_company"]
# }
```

---

### `get_metadata() -> Dict[str, Any]`

Get comprehensive model metadata.

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
metadata = model.get_metadata()
print(f"Model: {metadata['model_name']} v{metadata['version']}")
print(f"Backend: {metadata['backend']}")
print(f"Tables: {metadata['table_count']}")
```

---

## Storage Operations Methods

### `write_tables(dims: Dict[str, DataFrame], facts: Dict[str, DataFrame], mode: str = "overwrite")`

Persist built tables to Silver layer storage.

**Parameters:**
- `dims` - Dictionary of dimension DataFrames
- `facts` - Dictionary of fact DataFrames
- `mode` - Write mode: `"overwrite"` or `"append"`

**Process:**
1. Get storage path from router
2. Write DataFrames as Parquet
3. Handle partitioning if configured
4. Log progress

**Backend Support:**
- **Spark**: Uses `write.parquet()` with partitioning
- **DuckDB**: Converts to pandas, writes via PyArrow

**Example:**
```python
dims, facts = model.build()
model.write_tables(dims, facts, mode="overwrite")
```

---

## Extension Points (Hooks)

### `before_build()`

Hook called **before** graph building starts.

**Override to:**
- Validate preconditions
- Load external data
- Set runtime parameters

**Example:**
```python
class CustomModel(BaseModel):
    def before_build(self):
        print("Starting build...")
        self.start_time = time.time()
```

---

### `after_build(dims: Dict[str, DataFrame], facts: Dict[str, DataFrame]) -> Tuple[Dict, Dict]`

Hook called **after** graph building completes.

**Parameters:**
- `dims` - Built dimensions
- `facts` - Built facts

**Returns:** Modified (dims, facts) tuple

**Override to:**
- Add custom tables
- Apply global transformations
- Validate output

**Example:**
```python
class CustomModel(BaseModel):
    def after_build(self, dims, facts):
        # Add custom metric table
        facts["custom_metrics"] = self._build_custom_metrics()
        return dims, facts
```

---

### `custom_node_loading(node_id: str, node_config: Dict) -> Optional[DataFrame]`

Hook for custom node loading logic.

**Parameters:**
- `node_id` - Node identifier
- `node_config` - Node YAML configuration

**Returns:**
- DataFrame if custom loading applied
- `None` to use default loading

**Override to:**
- Load from external sources
- Apply custom transformations
- Implement caching

**Example:**
```python
class CustomModel(BaseModel):
    def custom_node_loading(self, node_id, node_config):
        if node_id == "dim_custom":
            # Load from custom source
            return self._load_custom_dimension()
        return None  # Use default loading
```

---

## Backend Detection Methods

### `_detect_backend() -> str`

Detect backend type from connection object.

**Detection Logic:**
1. Check for 'spark' in type name or `.sql()` method → Spark
2. Check for 'duckdb' in type name or `._conn` attribute → DuckDB
3. Raise error if unknown

**Returns:** `"spark"` or `"duckdb"`

**Example:**
```python
backend = model._detect_backend()
print(f"Using {backend} backend")
```

---

## Join Helper Methods

### `_join_pairs_from_strings(specs: List[str]) -> List[Tuple[str, str]]`

Parse join specifications into column pairs.

**Parameters:**
- `specs` - List of join specs (e.g., `["ticker = ticker", "date = trade_date"]`)

**Returns:** List of (left_col, right_col) tuples

**Example:**
```python
pairs = model._join_pairs_from_strings(["ticker = ticker", "date = trade_date"])
# [("ticker", "ticker"), ("date", "trade_date")]
```

---

### `_infer_join_pairs(left: DataFrame, right: DataFrame) -> List[Tuple[str, str]]`

Infer join columns from common column names.

**Parameters:**
- `left` - Left DataFrame
- `right` - Right DataFrame

**Logic:**
- Find columns with same name in both DataFrames
- Use as join keys

**Returns:** List of (left_col, right_col) tuples

**Raises:** `ValueError` if no common columns found

---

### `_join_with_dedupe(left: DataFrame, right: DataFrame, pairs: List[Tuple], how: str = "left") -> DataFrame`

Join two DataFrames with automatic column deduplication.

**Parameters:**
- `left` - Left DataFrame
- `right` - Right DataFrame
- `pairs` - Join key pairs
- `how` - Join type (`"left"`, `"inner"`, `"outer"`)

**Deduplication:**
- Removes duplicate columns from right side
- Keeps join key columns from left side only

**Returns:** Joined DataFrame

**Backend Support:** Spark and DuckDB

---

### `_find_edge(from_id: str, to_id: str) -> Optional[Dict]`

Find edge configuration between two nodes.

**Parameters:**
- `from_id` - Source node
- `to_id` - Target node

**Returns:** Edge config dict or `None` if not found

**Example:**
```python
edge = model._find_edge("fact_equity_prices", "dim_equity")
if edge:
    print(f"Join on: {edge['on']}")
```

---

## Method Summary by Category

### Graph Building (8 methods)
- `build()` - Main orchestrator
- `_build_nodes()` - Create nodes
- `_apply_edges()` - Validate edges
- `_materialize_paths()` - Create paths
- `_load_bronze_table()` - Load source data
- `_select_columns()` - Column operations
- `_apply_derive()` - Computed columns
- `_resolve_node()` - Cross-model resolution

### Data Access (7 methods)
- `ensure_built()` - Lazy loading
- `get_table()` - Retrieve table
- `get_table_enriched()` - Enriched retrieval
- `get_dimension_df()` - Get dimension
- `get_fact_df()` - Get fact
- `has_table()` - Check existence
- `list_tables()` - Inventory

### Measure Execution (2 methods)
- `calculate_measure()` - Execute measure
- `calculate_measure_by_entity()` - Grouped calculation

### Cross-Model Support (1 method)
- `set_session()` - Inject session

### Metadata (2 methods)
- `get_relations()` - Relationship map
- `get_metadata()` - Model metadata

### Storage (1 method)
- `write_tables()` - Persist tables

### Extension Hooks (3 methods)
- `before_build()` - Pre-build hook
- `after_build()` - Post-build hook
- `custom_node_loading()` - Custom loader

### Backend Detection (1 method)
- `_detect_backend()` - Identify backend

### Join Helpers (4 methods)
- `_join_pairs_from_strings()` - Parse join specs
- `_infer_join_pairs()` - Auto-detect keys
- `_join_with_dedupe()` - Join with dedup
- `_find_edge()` - Find edge config

### Schema Introspection (1 method)
- `get_table_schema()` - Get schema

---

## Usage Patterns

### Basic Model Usage

```python
from core.context import RepoContext
from models.api.registry import get_model_registry

# Setup
ctx = RepoContext.from_repo_root(connection_type="duckdb")
registry = get_model_registry()

# Get model instance
equity_model = registry.create_model_instance(
    "equity",
    connection=ctx.connection,
    storage=ctx.storage
)

# Access tables (lazy builds on first access)
equity_dim = equity_model.get_table("dim_equity")
prices_fact = equity_model.get_table("fact_equity_prices")

# Calculate measures
avg_price = equity_model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}]
)
```

### Custom Model Implementation

```python
from models.base.model import BaseModel

class MyCustomModel(BaseModel):
    """Custom model with specialized logic."""

    def before_build(self):
        """Validate preconditions."""
        print(f"Building {self.model_cfg['model']} model...")

    def custom_node_loading(self, node_id, node_config):
        """Custom loading for specific nodes."""
        if node_id == "dim_custom":
            return self._load_from_api()
        return None  # Use default loading

    def after_build(self, dims, facts):
        """Add custom tables."""
        facts["custom_metrics"] = self._compute_metrics(dims, facts)
        return dims, facts

    def _load_from_api(self):
        """Custom data loading logic."""
        # Implementation here
        pass
```

---

## Best Practices

1. **Always use lazy loading**: Call `ensure_built()` or access via `get_table()`
2. **Leverage hooks**: Override `before_build()`, `after_build()`, `custom_node_loading()` for custom logic
3. **Backend agnostic**: Use BaseModel methods instead of direct Spark/DuckDB APIs
4. **Cross-model references**: Use session injection for cross-model access
5. **YAML-driven**: Define schema in YAML, not in code
6. **Validate edges**: Let BaseModel validate joins automatically
7. **Use measures**: Pre-define calculations in YAML measures

---

## Related Documentation

- [Graph Architecture Overview](../02-graph-architecture/graph-overview.md)
- [Model Lifecycle](../03-model-framework/model-lifecycle.md)
- [YAML Configuration](../03-model-framework/yaml-configuration.md)
- [UniversalSession](universal-session.md)
