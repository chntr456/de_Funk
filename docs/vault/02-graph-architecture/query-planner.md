# GraphQueryPlanner Reference

**Intra-model query planning using graph edges**

File: `models/api/query_planner.py`

---

## Overview

**GraphQueryPlanner** uses a model's graph.edges configuration to plan and execute dynamic joins at runtime, making materialized views an **optional performance optimization** rather than a requirement.

### Key Features

- **Graph-Based Join Planning**: Uses NetworkX to find join paths between tables
- **Dynamic Joins**: Builds joins at runtime using edge metadata
- **Materialized View Fallback**: Uses pre-computed paths when available for performance
- **Backend Agnostic**: Supports both Spark and DuckDB
- **Auto-Enrichment Support**: Enables measure auto-enrichment with automatic table joins
- **Column Selection**: Optimizes queries by selecting only required columns

### Design Pattern

Each model instance gets its own query planner that understands the table-level relationships within that model.

```
┌─────────────────────┐
│ Model Config (YAML) │
│  graph.edges: [...]  │
└─────────┬───────────┘
          │
          ▼
  ┌──────────────┐
  │ Query Planner│
  │  (NetworkX)  │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────┐
  │ Strategy Selection│
  └──────┬───────────┘
         │
    ┌────┴────┐
    │         │
Fast Path   Slow Path
(Materialized (Dynamic Join)
  View)      via Graph
```

---

## Class Definition

**File:** `models/api/query_planner.py:17-725`

```python
class GraphQueryPlanner:
    """
    Query planner that uses graph edges for dynamic table joins.

    Each model instance has its own query planner. The planner reads
    the model's graph.edges configuration and builds a NetworkX graph
    of table relationships.
    """

    def __init__(self, model):
        self.model = model
        self.model_name = model.model_name
        self.backend = model.backend
        self.graph = self._build_table_graph()
```

---

## Constructor

### `__init__(model)`

Initialize query planner for a model.

**Parameters:**
- `model` - BaseModel instance

**Attributes Set:**
- `model` - Reference to BaseModel instance
- `model_name` - Model name (for error messages)
- `backend` - Backend type ('duckdb' or 'spark')
- `graph` - NetworkX DiGraph of table relationships

**Example:**
```python
from models.api.registry import get_model_registry

registry = get_model_registry()
equity_model = registry.get_model('equity')

# Query planner is automatically created by BaseModel
planner = equity_model.query_planner

# Or create manually
from models.api.query_planner import GraphQueryPlanner
planner = GraphQueryPlanner(equity_model)
```

---

## Public Methods

### `get_table_enriched(table_name, enrich_with=None, columns=None) -> Any`

Get table with optional enrichment via dynamic joins.

**Main entry point for auto-enrichment and dynamic joins.**

**Strategy:**
1. Check if materialized view exists that matches (fast path)
2. If not, build join dynamically using graph edges (slow path)
3. Select only requested columns (if specified)

**Parameters:**
- `table_name` - Base table name (e.g., `'fact_equity_prices'`)
- `enrich_with` - List of tables to join (e.g., `['dim_equity', 'dim_exchange']`)
- `columns` - Columns to select (default: all columns)

**Returns:** DataFrame with enrichment applied

**Examples:**

**No Enrichment:**
```python
# Just get base table
df = planner.get_table_enriched('fact_equity_prices')
# Returns fact_equity_prices DataFrame
```

**Single Table Enrichment:**
```python
# Get prices with company info
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity'],
    columns=['ticker', 'trade_date', 'close', 'company_name']
)

# Query planner:
# 1. Checks for materialized view matching this pattern
# 2. If not found, builds join: fact_equity_prices -> dim_equity
# 3. Selects only specified columns
```

**Multi-Table Enrichment:**
```python
# Get prices with company and exchange info
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity', 'dim_exchange'],
    columns=['ticker', 'trade_date', 'close', 'company_name', 'exchange_name']
)

# Query planner:
# 1. Checks for materialized view: equity_prices_with_company_and_exchange
# 2. If not found, builds join chain:
#    fact_equity_prices -> dim_equity -> dim_exchange
# 3. Returns enriched DataFrame
```

**Auto-Enrichment Example:**
```python
# Used by MeasureExecutor for auto-enrichment
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity', 'dim_exchange'],
    columns=['ticker', 'close', 'exchange_name']  # exchange_name from dim_exchange!
)
```

---

### `get_join_path(from_table: str, to_table: str) -> Optional[List[str]]`

Find join path between two tables.

Useful for debugging and understanding table relationships.

**Parameters:**
- `from_table` - Source table
- `to_table` - Target table

**Returns:** List of table names forming the path, or `None` if no path exists

**Example:**
```python
# Find path from prices to exchange
path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
# ['fact_equity_prices', 'dim_equity', 'dim_exchange']

# Direct path
path = planner.get_join_path('fact_equity_prices', 'dim_equity')
# ['fact_equity_prices', 'dim_equity']

# No path
path = planner.get_join_path('dim_equity', 'fact_macro_unemployment')
# None (tables not connected)
```

**Use Cases:**
- Debugging join failures
- Understanding model structure
- Planning query optimization
- Validating edge configuration

---

### `get_table_relationships(table_name: str) -> Dict[str, Any]`

Get all relationships for a table.

**Parameters:**
- `table_name` - Table to analyze

**Returns:** Dictionary with relationship information

**Example:**
```python
rels = planner.get_table_relationships('fact_equity_prices')
# {
#     'can_join_to': ['dim_equity'],
#     'can_be_joined_from': [],
#     'graph_depth': 0
# }

rels = planner.get_table_relationships('dim_equity')
# {
#     'can_join_to': ['dim_exchange'],
#     'can_be_joined_from': ['fact_equity_prices'],
#     'graph_depth': 1
# }
```

**Use Cases:**
- Model documentation
- Debugging join issues
- Understanding table connectivity

---

### `find_tables_with_column(column_name: str) -> List[str]`

Find all tables that contain a specific column.

Searches the model's schema to find tables that have the specified column. **Used for auto-enrichment** to find which tables to join.

**Parameters:**
- `column_name` - Column to search for

**Returns:** List of table names that contain the column

**Example:**
```python
# Find tables with 'exchange_name' column
tables = planner.find_tables_with_column('exchange_name')
# ['dim_exchange']

# Find tables with 'ticker' column
tables = planner.find_tables_with_column('ticker')
# ['dim_equity', 'fact_equity_prices', 'fact_equity_news']

# Column not in any table
tables = planner.find_tables_with_column('nonexistent_column')
# []
```

**Use Cases:**
- Auto-enrichment column lookup
- Schema discovery
- Validation

---

## Protected Methods

### `_build_table_graph() -> nx.DiGraph`

Build NetworkX graph from model's graph.edges configuration.

Creates a directed graph where:
- **Nodes**: Table names (dims and facts)
- **Edges**: Join relationships with metadata (join_on, join_type)

**Returns:** `nx.DiGraph` with table nodes and join edges

**Graph Structure:**
```python
# Nodes
g.add_node('fact_equity_prices', type='fact')
g.add_node('dim_equity', type='dimension')

# Edges
g.add_edge(
    'fact_equity_prices',
    'dim_equity',
    join_on=['ticker=ticker'],
    join_type='left',
    description='Equity dimension'
)
```

**Note:** Cross-model edges (containing dot notation like `"core.dim_calendar"`) are skipped. Cross-model joins are handled by UniversalSession, not QueryPlanner.

---

### `_find_materialized_view(base_table: str, join_tables: List[str]) -> Optional[str]`

Find materialized view (path) that matches the join pattern.

Searches through model's paths configuration to find a pre-computed view that joins the same tables.

**Parameters:**
- `base_table` - Starting table
- `join_tables` - Tables to join

**Returns:** Path ID if matching materialized view exists, `None` otherwise

**Example:**

**Model Config:**
```yaml
graph:
  paths:
    - id: equity_prices_with_company
      hops: fact_equity_prices -> dim_equity
```

**Lookup:**
```python
# Find materialized view
path_id = planner._find_materialized_view(
    'fact_equity_prices',
    ['dim_equity']
)
# 'equity_prices_with_company'

# No matching view
path_id = planner._find_materialized_view(
    'fact_equity_prices',
    ['dim_equity', 'dim_exchange']
)
# None
```

**Matching Logic:**
- First table in path must match `base_table`
- All `join_tables` must be present in the path
- Order doesn't matter (path can have additional tables)

---

### `_build_dynamic_join(base_table: str, join_tables: List[str], columns=None) -> Any`

Build join dynamically using graph edges.

Uses NetworkX to find join paths, then executes joins using backend-specific join operations (Spark or DuckDB).

**Parameters:**
- `base_table` - Starting table
- `join_tables` - Tables to join
- `columns` - Columns to select

**Returns:** Joined DataFrame

**Raises:** `ValueError` if no join path exists in graph

**Backend Dispatch:**
- **DuckDB**: Calls `_build_duckdb_join_sql()` (SQL-based, more efficient)
- **Spark**: Uses DataFrame API with Spark joins

---

### `_build_duckdb_join_sql(base_table, join_tables, columns=None) -> Any`

Build SQL join query for DuckDB.

Constructs a SQL query with JOINs based on graph edges, then executes it via DuckDB connection.

**Parameters:**
- `base_table` - Starting table
- `join_tables` - Tables to join
- `columns` - Columns to select (if None, selects all from base table + joined cols)

**Returns:** Pandas DataFrame with joined data

**Raises:** `ValueError` if no join path exists

**Generated SQL Structure:**
```sql
SELECT t0.ticker, t0.close, t1.company_name, t2.exchange_name
FROM read_parquet('/path/to/fact_equity_prices/*.parquet') AS t0
LEFT JOIN read_parquet('/path/to/dim_equity/*.parquet') AS t1
  ON t0.ticker = t1.ticker
LEFT JOIN read_parquet('/path/to/dim_exchange/*.parquet') AS t2
  ON t1.exchange_id = t2.exchange_id
```

**Optimizations:**
- Uses table aliases (`t0`, `t1`, `t2`)
- Selects only requested columns
- Builds efficient ON clauses from edge metadata

---

### `_get_duckdb_table_reference(table_name: str) -> str`

Get DuckDB table reference (parquet path).

Uses the model's schema to resolve table paths, ensuring tables are looked up within the correct model's storage.

**Parameters:**
- `table_name` - Table name

**Returns:** DuckDB-compatible table reference (e.g., `read_parquet('path/*.parquet')`)

**Raises:** `ValueError` if table not found in model schema

**Example:**
```python
ref = planner._get_duckdb_table_reference('fact_equity_prices')
# "read_parquet('storage/silver/equity/facts/fact_equity_prices/*.parquet')"
```

---

### `_join_dataframes(left_df, right_df, join_on, join_type='left') -> Any`

Join two DataFrames using backend-specific operations.

**Parameters:**
- `left_df` - Left DataFrame
- `right_df` - Right DataFrame
- `join_on` - Join conditions (e.g., `["ticker=ticker", "date=date"]`)
- `join_type` - Join type (`'left'`, `'inner'`, `'outer'`)

**Returns:** Joined DataFrame

**Delegates To:**
- `_spark_join()` for Spark backend
- `_duckdb_join()` for DuckDB backend

---

### `_parse_join_conditions(join_on: List[str]) -> List[Tuple[str, str]]`

Parse join conditions into (left_col, right_col) pairs.

**Parameters:**
- `join_on` - List of join conditions (e.g., `["ticker=ticker", "date=trade_date"]`)

**Returns:** List of `(left_col, right_col)` tuples

**Raises:** `ValueError` if join condition format is invalid

**Examples:**
```python
# Explicit mapping
pairs = planner._parse_join_conditions(['ticker=ticker', 'date=trade_date'])
# [('ticker', 'ticker'), ('date', 'trade_date')]

# Same column name (no '=')
pairs = planner._parse_join_conditions(['ticker', 'date'])
# [('ticker', 'ticker'), ('date', 'date')]
```

---

### `_spark_join(left_df, right_df, join_pairs, join_type) -> Any`

Execute join using Spark DataFrame API.

**Parameters:**
- `left_df` - Left Spark DataFrame
- `right_df` - Right Spark DataFrame
- `join_pairs` - List of `(left_col, right_col)` tuples
- `join_type` - Join type (`'left'`, `'inner'`, `'outer'`, etc.)

**Returns:** Joined Spark DataFrame

**Special Handling:**
- Builds join condition from multiple column pairs
- Automatically drops duplicate columns from right side to avoid `AMBIGUOUS_REFERENCE` errors
- Preserves left-side columns when column names match

**Example:**
```python
# Join DataFrames on ticker
join_pairs = [('ticker', 'ticker')]
result = planner._spark_join(
    prices_df,
    equity_df,
    join_pairs,
    'left'
)
```

---

### `_duckdb_join(left_df, right_df, join_pairs, join_type) -> Any`

Execute join using DuckDB pandas DataFrames.

**Note:** This method is now **deprecated** in favor of `_build_duckdb_join_sql()` which builds SQL queries directly. Kept for backwards compatibility.

**Parameters:**
- `left_df` - Left pandas DataFrame
- `right_df` - Right pandas DataFrame
- `join_pairs` - List of `(left_col, right_col)` tuples
- `join_type` - Join type

**Returns:** Joined pandas DataFrame

**Implementation:** Uses `pd.merge()`

---

### `_select_columns(df, columns: List[str]) -> Any`

Select specific columns from DataFrame (backend agnostic).

**Parameters:**
- `df` - DataFrame (Spark or pandas)
- `columns` - List of column names to select

**Returns:** DataFrame with only specified columns

**Backend Handling:**
- **Spark**: Uses `.select(*columns)`
- **DuckDB/Pandas**: Uses `df[columns]`

**Safety:** Filters to only columns that exist in DataFrame

---

### `_table_has_column(table_name: str, column_name: str) -> bool`

Check if a table has a specific column.

**Parameters:**
- `table_name` - Table to check
- `column_name` - Column to look for

**Returns:** `True` if table has the column, `False` otherwise

**Use Cases:**
- Column resolution during join construction
- Auto-enrichment column lookup
- Validation

---

## Usage Patterns

### Basic Dynamic Join

```python
from models.api.registry import get_model_registry

# Get model
registry = get_model_registry()
equity_model = registry.get_model('equity')
planner = equity_model.query_planner

# Get enriched table
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity'],
    columns=['ticker', 'trade_date', 'close', 'company_name']
)

# Result: DataFrame with prices + company names
```

---

### Multi-Hop Join

```python
# Join across 3 tables
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity', 'dim_exchange'],
    columns=['ticker', 'close', 'company_name', 'exchange_name', 'exchange_country']
)

# Query planner:
# 1. Finds path: fact_equity_prices -> dim_equity -> dim_exchange
# 2. Builds join chain
# 3. Returns enriched DataFrame
```

---

### Debugging Join Paths

```python
# Check if join path exists
path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
if path:
    print(f"Join path: {' -> '.join(path)}")
    # Join path: fact_equity_prices -> dim_equity -> dim_exchange
else:
    print("No join path available")

# Get table relationships
rels = planner.get_table_relationships('fact_equity_prices')
print(f"Can join to: {rels['can_join_to']}")
# Can join to: ['dim_equity']

# Find tables with specific column
tables = planner.find_tables_with_column('exchange_name')
print(f"Tables with exchange_name: {tables}")
# Tables with exchange_name: ['dim_exchange']
```

---

### Measure Auto-Enrichment

**Model Config:**
```yaml
# equity.yaml
measures:
  avg_close_by_exchange:
    type: simple
    source: fact_equity_prices.close
    aggregation: avg
    auto_enrich: true
```

**Execution:**
```python
# MeasureExecutor uses QueryPlanner for auto-enrichment
executor = MeasureExecutor(equity_model, backend='duckdb')

result = executor.execute_measure(
    'avg_close_by_exchange',
    entity_column='exchange_name'  # Not in fact_equity_prices!
)

# Behind the scenes:
# 1. MeasureExecutor detects exchange_name missing
# 2. Calls planner.find_tables_with_column('exchange_name')
#    → ['dim_exchange']
# 3. Calls planner.get_join_path('fact_equity_prices', 'dim_exchange')
#    → ['fact_equity_prices', 'dim_equity', 'dim_exchange']
# 4. Calls planner.get_table_enriched(
#       'fact_equity_prices',
#       enrich_with=['dim_equity', 'dim_exchange']
#    )
# 5. Executes measure on enriched table
```

---

### Materialized View Optimization

**Model Config:**
```yaml
# equity.yaml
graph:
  paths:
    - id: equity_prices_with_company
      hops: fact_equity_prices -> dim_equity
```

**Usage:**
```python
# Request enrichment
df = planner.get_table_enriched(
    'fact_equity_prices',
    enrich_with=['dim_equity']
)

# Query planner:
# 1. Finds materialized view: equity_prices_with_company
# 2. Uses pre-computed view (fast!)
# 3. Returns materialized DataFrame

# Output:
# "Using materialized view: equity_prices_with_company"
```

**Performance:**
- **Materialized view**: ~10ms (read from disk)
- **Dynamic join**: ~100ms (join at runtime)

---

## Join Type Mapping

Graph edges support multiple join type specifications that are mapped to standard SQL join types:

| Graph Edge Type | SQL Join Type |
|----------------|---------------|
| `many_to_one` | LEFT |
| `one_to_many` | LEFT |
| `left` | LEFT |
| `right` | RIGHT |
| `inner` | INNER |
| `full` | FULL OUTER |
| `outer` | FULL OUTER |

**Example:**
```yaml
# Model config
graph:
  edges:
    - from: fact_equity_prices
      to: dim_equity
      on: [ticker = ticker]
      type: many_to_one  # Mapped to LEFT join
```

---

## Backend Comparison

| Feature | DuckDB | Spark |
|---------|--------|-------|
| **Join Strategy** | SQL-based | DataFrame API |
| **Execution** | Single SQL query | Chained DataFrame joins |
| **Table Reference** | `read_parquet('path/*.parquet')` | DataFrame objects |
| **Column Selection** | SQL SELECT | `.select()` method |
| **Duplicate Handling** | SQL USING clause | Manual `.drop()` |
| **Performance** | 10-100x faster | Slower but scalable |
| **Recommended Use** | Small to medium data | Large-scale data |

---

## Graph Visualization

Example NetworkX graph structure:

```
Nodes (Tables):
  - fact_equity_prices (type: fact)
  - dim_equity (type: dimension)
  - dim_exchange (type: dimension)

Edges (Joins):
  fact_equity_prices -> dim_equity
    join_on: ['ticker = ticker']
    join_type: 'left'

  dim_equity -> dim_exchange
    join_on: ['exchange_id = exchange_id']
    join_type: 'left'

Join Paths:
  fact_equity_prices -> dim_exchange:
    ['fact_equity_prices', 'dim_equity', 'dim_exchange']
```

---

## Error Handling

### No Join Path

**Error:** `ValueError: No join path from fact_equity_prices to dim_exchange in equity model`

**Cause:** Tables are not connected via edges in graph

**Solution:** Add missing edge to model config:
```yaml
graph:
  edges:
    - from: dim_equity
      to: dim_exchange
      on: [exchange_id = exchange_id]
```

---

### Table Not Found

**Error:** `ValueError: Table 'fact_prices' not found in model 'equity' schema`

**Cause:** Table doesn't exist in model's schema configuration

**Solution:** Add table to schema:
```yaml
schema:
  facts:
    fact_equity_prices:
      path: facts/fact_equity_prices
      columns: {...}
```

---

### Column Not in Any Table

**Error:** Column `'unknown_column'` not found during join

**Cause:** Requested column doesn't exist in any joined table

**Solution:**
1. Check column name spelling
2. Verify column exists in table schema
3. Add missing enrichment table if column is in another table

---

### Cross-Model Join Attempted

**Note:** Cross-model joins are skipped by QueryPlanner (logged but not executed).

**Solution:** Use UniversalSession for cross-model joins:
```python
# Use UniversalSession instead of QueryPlanner
from models.api.session import UniversalSession

session = UniversalSession(backend='duckdb')
df = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'close', 'calendar_date']  # calendar_date from core.dim_calendar
)
```

---

## Best Practices

1. **Define edges in YAML**: Keep graph structure in model configuration
2. **Use materialized views**: Pre-compute common join patterns for performance
3. **Request only needed columns**: Optimize memory and query performance
4. **Check join paths**: Use `get_join_path()` to debug join issues
5. **Enable auto-enrichment**: Let measures use query planner automatically
6. **Monitor performance**: Compare materialized vs dynamic join times

---

## Related Documentation

- [BaseModel](../01-core-components/base-model.md) - Model framework using query planner
- [Graph Overview](graph-overview.md) - Understanding graph architecture
- [Nodes, Edges, Paths](nodes-edges-paths.md) - Graph configuration
- [Measure Framework](../03-model-framework/measure-framework.md) - Uses query planner for auto-enrichment
- [UniversalSession](../01-core-components/universal-session.md) - Cross-model joins
