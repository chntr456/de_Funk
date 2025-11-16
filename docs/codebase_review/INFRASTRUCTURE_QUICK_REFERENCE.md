# de_Funk Infrastructure - Quick Reference Guide

## Core Concepts at a Glance

| Concept | What | Where | Key Insight |
|---------|------|-------|------------|
| **BaseModel** | YAML-driven model framework | `models/base/model.py` | Generic graph construction - works for any domain |
| **UniversalSession** | Cross-model orchestrator | `models/api/session.py` | Auto-joins, lazy loading, backend abstraction |
| **ModelRegistry** | Model discovery & instantiation | `models/registry.py` | Finds YAML configs, auto-registers Python classes |
| **ModelGraph** | Dependency DAG | `models/api/graph.py` | Determines build order, enables cross-model joins |
| **FilterEngine** | Backend-agnostic filtering | `core/session/filters.py` | Same filter code on Spark and DuckDB |
| **MeasureExecutor** | Unified measure execution | `models/base/measures/executor.py` | Registry-based dispatch for all measure types |
| **GraphQueryPlanner** | Dynamic join builder | `models/api/query_planner.py` | Uses edges to build joins at runtime |
| **StorageRouter** | Path abstraction | `models/api/dal.py` | Logical table → Physical path mapping |
| **ConfigLoader** | Centralized configuration | `config/loader.py` | Env vars > params > files > defaults |

---

## The 4 Main Design Patterns

### 1. Graph-Based Planning
- **What**: Use directed graphs to plan queries and build order
- **Where**: ModelGraph (inter-model), GraphQueryPlanner (intra-model)
- **Example**: Join path from `fact_prices` → `dim_company` → `dim_exchange` automatically discovered

### 2. YAML as Source of Truth
- **What**: Declarative model definitions (no code changes needed)
- **Where**: `configs/models/*.yaml` for schema, edges, measures
- **Example**: Add new column without touching Python code

### 3. Backend Transparency
- **What**: Same code works on Spark and DuckDB
- **Where**: FilterEngine, Adapters abstract differences
- **Example**: `session.get_table()` works identically on both backends

### 4. Lazy Evaluation + Caching
- **What**: Compute on first access, cache results
- **Where**: BaseModel._is_built flag, UniversalSession._models cache
- **Example**: Models built on first query, not at initialization

---

## Common Operations

### Loading a Model
```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(ctx.connection, ctx.storage, ctx.repo)
model = session.load_model('equity')
```

### Getting a Table (Simple)
```python
df = session.get_table('equity', 'fact_equity_prices')
```

### Getting a Table (With Auto-Join)
```python
# Automatically joins to get company_name (not in fact_equity_prices)
df = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['ticker', 'close', 'company_name']
)
```

### Getting a Table (With Filter + Aggregation)
```python
df = session.get_table(
    'equity',
    'fact_equity_prices',
    required_columns=['trade_date', 'ticker', 'close', 'volume'],
    filters={'trade_date': {'min': '2024-01-01', 'max': '2024-12-31'}},
    group_by=['ticker', 'trade_date'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
```

### Calculating a Measure
```python
result = model.calculate_measure(
    'avg_close_price',
    entity_column='ticker',
    filters={'trade_date': '2024-01-01'},
    limit=10
)
print(result.data)  # Pandas or Spark DataFrame
```

### Building a Model
```python
model = session.load_model('equity')
model.ensure_built()  # Trigger build if needed
dims, facts = model._dims, model._facts
```

### Listing Available Models
```python
models = session.list_models()
for model_name in models:
    print(session.get_model_metadata(model_name))
```

---

## File Organization Reference

### 1. Model Framework (Core)
- `models/base/model.py` → BaseModel class
- `models/base/measures/` → Measure framework
- `models/api/session.py` → UniversalSession
- `models/api/graph.py` → ModelGraph
- `models/api/query_planner.py` → GraphQueryPlanner
- `models/api/dal.py` → StorageRouter

### 2. Execution Infrastructure
- `core/session/filters.py` → FilterEngine
- `core/connection.py` → Connection factory
- `core/context.py` → RepoContext

### 3. Registry & Discovery
- `models/registry.py` → ModelRegistry
- `models/base/measures/registry.py` → MeasureRegistry
- `config/loader.py` → ConfigLoader

### 4. Storage & Builders
- `models/base/parquet_loader.py` → Optimized Parquet writer
- `models/builders/weighted_aggregate_builder.py` → Weighted index builder

### 5. Domain Models
- `models/implemented/{model_name}/` → Model implementations

### 6. Configuration
- `configs/models/*.yaml` → Model definitions
- `configs/storage.json` → Storage paths
- `configs/*_endpoints.json` → API configurations

---

## Key Methods Explained

### BaseModel

#### `build()` → (dims, facts)
- Constructs model from YAML config
- Order: load_nodes → validate_edges → materialize_paths → post_process
- Lazy-triggered by `ensure_built()`

#### `get_table(name)` → DataFrame
- Get dims/facts by name (searches both)
- Triggers build if not yet built

#### `get_table_enriched(table, enrich_with, columns)` → DataFrame
- Get table with dynamic joins
- Uses `query_planner` to find join paths

#### `calculate_measure(measure_name, entity_column, filters)` → QueryResult
- Execute measure from YAML config
- Uses `MeasureExecutor`

### UniversalSession

#### `load_model(model_name)` → BaseModel
- Dynamically load model
- Caches instance
- Injects session for cross-model access

#### `get_table(model_name, table_name, required_columns, filters, group_by)` → DataFrame
- Get table with optional enrichment/aggregation
- Tries: materialized view → dynamic joins
- Applies: filters → selection → aggregation

#### `get_model_instance(model_name)` → BaseModel
- Get underlying model object
- Useful for advanced operations

### MeasureExecutor

#### `execute_measure(measure_name, entity_column, filters, limit)` → QueryResult
- Main entry point for measure calculation
- Registry-based dispatch (Simple, Computed, Weighted, etc.)
- Backend-agnostic

### FilterEngine

#### `apply_filters(df, filters, backend)` → DataFrame
- Apply filters (exact, IN, range)
- Backend-specific logic (Spark vs DuckDB)

### ModelGraph

#### `get_build_order()` → [model_names]
- Topological sort of models
- Use to build in dependency order

#### `get_dependencies(model_name, transitive)` → Set[model_names]
- Direct or transitive dependencies

#### `get_join_path(model_a, model_b)` → [model_names]
- Find shortest path between models

---

## Common Data Patterns

### Filter Specification
```python
filters = {
    'ticker': 'AAPL',                              # Exact match
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],          # IN clause
    'trade_date': {
        'min': '2024-01-01',                       # Range (date)
        'max': '2024-12-31'
    },
    'volume': {
        'min': 1000000,                            # Range (numeric)
        'max': 10000000
    }
}
```

### Measure Definition (YAML)
```yaml
measures:
  avg_close_price:
    type: simple
    source: fact_prices.close
    aggregation: avg
    data_type: double
    
  volume_weighted_index:
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: volume
    group_by: [trade_date]
    
  revenue:
    type: computed
    source: fact_prices  # Just reference
    expression: close * volume
    aggregation: sum
```

### Edge Definition (YAML)
```yaml
edges:
  - from: fact_equity_prices
    to: dim_equity
    on: [ticker = ticker]          # Join condition
    type: left                      # Join type
    
  - from: fact_equity_prices
    to: core.dim_calendar           # Cross-model
    on: [trade_date = trade_date]
```

---

## Backend Differences

| Aspect | Spark | DuckDB |
|--------|-------|--------|
| **Connection Type** | SparkSession | duckdb.DuckDBPyConnection |
| **DataFrame Type** | pyspark.sql.DataFrame | duckdb.DuckDBPyRelation |
| **Filter Method** | .filter(F.col(...)==val) | .filter(SQL_string) |
| **Select Method** | .select(*cols) | .project(col_list) |
| **Join Method** | .join(other, condition) | SQL LEFT JOIN |
| **Aggregation** | .groupBy().agg() | SQL GROUP BY |
| **Execution** | Lazy until .collect()/.show() | Immediate with .execute() |

---

## Performance Optimization Tips

### 1. Use Materialized Views
```python
# Instead of dynamic joins every time:
df = session.get_table('equity', 'fact_prices_with_company')  # Pre-computed view
```

### 2. Filter Early (Push-Down)
```python
# Filters applied BEFORE joins when possible
df = session.get_table('equity', 'fact_prices',
                      filters={'trade_date': '2024-01-01'})
```

### 3. Select Only Needed Columns
```python
# Project early to reduce data volume
df = session.get_table('equity', 'fact_prices',
                      required_columns=['ticker', 'close'])
```

### 4. Pre-Materialize Expensive Joins
```python
# In model YAML, define materialized paths:
paths:
  - id: fact_prices_with_company
    hops: [fact_prices, dim_equity, dim_company]
```

### 5. Use Pre-Aggregated Measures
```python
# Instead of computing on-demand
result = model.calculate_measure('volume_weighted_index')
# (Pre-materialized in Silver layer)
```

---

## Debugging Tips

### 1. Check Model Metadata
```python
metadata = session.get_model_metadata('equity')
print(metadata)  # Shows nodes, paths, measures, dependencies
```

### 2. List Available Tables
```python
tables = session.list_tables('equity')
print(f"Dims: {tables['dimensions']}")
print(f"Facts: {tables['facts']}")
```

### 3. Check Table Schema
```python
schema = model.get_table_schema('fact_equity_prices')
for col, dtype in schema.items():
    print(f"{col}: {dtype}")
```

### 4. Verify Model Dependencies
```python
deps = session.model_graph.get_dependencies('equity', transitive=True)
print(f"Equity depends on: {deps}")
```

### 5. Check Join Path
```python
path = session.model_graph.get_join_path('equity', 'corporate')
print(f"Join path: {' -> '.join(path)}")
```

---

## Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `Model 'xyz' not found` | YAML doesn't exist in `configs/models/` | Create `configs/models/xyz.yaml` |
| `Table 'xyz' not found` | Node not in model graph | Check YAML graph.nodes definition |
| `Column 'xyz' not found` | Not in base table or join path | Check schema, verify join edges |
| `Cannot find join path` | Tables not connected in graph | Add edge definition to YAML |
| `Measure 'xyz' not found` | Not in model measures | Add to YAML measures section |
| `UnsupportedOperationError` | Spark-only operation on DuckDB | Use FilterEngine instead of direct API |

---

## Architecture Decision Records

### Why Graphs?
- **Join planning**: Edges define join relationships automatically
- **Build order**: Topological sort ensures dependencies build first
- **Dependency injection**: Can find transitive dependencies for cross-model access

### Why YAML?
- **Configuration**: No code changes needed to modify models
- **Clarity**: Schema, edges, measures all visible in one place
- **Reusability**: Same YAML works with BaseModel for any domain

### Why Lazy Loading?
- **Performance**: Don't build unused models
- **Memory**: Only load tables when accessed
- **Scalability**: Multiple models don't all compete for resources

### Why Adapters?
- **Backend neutrality**: Same code on Spark and DuckDB
- **Testing**: Mock adapters for unit tests
- **Evolution**: Add new backends without changing business logic

---

## Quick Links

- **CLAUDE.md**: Project overview and conventions
- **INFRASTRUCTURE_ANALYSIS.md**: Detailed architecture breakdown
- **ARCHITECTURE_LAYERS.md**: Visual layer diagrams
- **TESTING_GUIDE.md**: Testing strategies
- **MODEL_DEPENDENCY_ANALYSIS.md**: Model relationships

---

## Key Takeaways

1. **Models are described in YAML**, not code
2. **BaseModel handles 90% of logic** generically
3. **Graphs drive joins and build order** automatically
4. **UniversalSession orchestrates everything** and manages caching
5. **Adapters make it backend-transparent** (Spark/DuckDB)
6. **Lazy loading and caching** optimize performance
7. **Filters push down** before joins
8. **Measures are registry-based** for extensibility

