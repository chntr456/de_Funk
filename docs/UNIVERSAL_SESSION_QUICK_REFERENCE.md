# Universal Session - Quick Reference Guide

## Basic Usage

### Initialize Session

```python
from models.api.session import UniversalSession
from pathlib import Path

# Create session
session = UniversalSession(
    connection=spark_or_duckdb_connection,
    storage_cfg=storage_configuration,
    repo_root=Path.cwd(),
    models=['stocks', 'company']  # Optional: pre-load models
)

# Detect backend
print(f"Using {session.backend} backend")  # 'spark' or 'duckdb'
```

## Common Operations

### 1. Get a Table

```python
# Simple access
df = session.get_table('stocks', 'fact_prices')

# With filtering
df = session.get_table(
    'stocks', 'fact_prices',
    filters={'ticker': 'AAPL'}
)

# With auto-join (missing columns from related tables)
df = session.get_table(
    'stocks', 'fact_prices',
    required_columns=['ticker', 'close', 'exchange_name'],  # exchange_name auto-joined
)

# With aggregation to new grain
df = session.get_table(
    'stocks', 'fact_prices',
    required_columns=['trade_date', 'ticker', 'volume'],
    group_by=['trade_date'],  # Aggregate by date
    aggregations={'volume': 'sum'}
)
```

### 2. List Available Models and Tables

```python
# List all models
models = session.list_models()
print(f"Available: {models}")

# List tables in a model
tables = session.list_tables('stocks')
print(f"Dimensions: {tables['dimensions']}")
print(f"Facts: {tables['facts']}")

# Get model metadata
metadata = session.get_model_metadata('stocks')
```

### 3. Apply Filters

```python
# Different filter types
filters = {
    # Exact match
    'ticker': 'AAPL',
    
    # IN clause (multiple values)
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],
    
    # Range filter
    'volume': {'min': 1000000, 'max': 5000000},
    'trade_date': {'min': '2024-01-01', 'max': '2024-12-31'},
    
    # Comparison operators
    'price': {'gt': 100, 'lt': 200},
    'volume': {'gte': 1000000}
}

df = session.get_table('stocks', 'fact_prices', filters=filters)
```

### 4. Access Model Directly

```python
# Get the model instance
model = session.load_model('stocks')

# Use model-specific methods
prices = model.get_table('fact_prices')
schema = model.get_table_schema('fact_prices')
metadata = model.get_metadata()
```

## Filter Specifications

### Format Reference

```python
# Type: Exact Match
filters = {'column': value}
# Example
filters = {'ticker': 'AAPL'}

# Type: IN Clause  
filters = {'column': [val1, val2, val3]}
# Example
filters = {'ticker': ['AAPL', 'GOOGL', 'MSFT']}

# Type: Range Filter
filters = {
    'column': {
        'min': min_value,
        'max': max_value,
        # OR
        'start': start_date,    # For dates
        'end': end_date,        # For dates
        # Comparison operators
        'gt': value,            # >
        'gte': value,           # >=
        'lt': value,            # <
        'lte': value            # <=
    }
}
# Examples
filters = {'volume': {'min': 1000000}}
filters = {'price': {'gt': 100, 'lt': 200}}
filters = {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}
```

## Auto-Join Examples

### When to Use Auto-Join

Auto-join activates when:
- You request `required_columns` parameter
- Some columns don't exist in the base table
- Model graph has edges connecting the tables

### Example: Exchange Information

```
Scenario: You want stock prices with exchange information
- Table: fact_prices (has: ticker, close, volume)
- Need: exchange_name (not in fact_prices)
- Graph: fact_prices → dim_stock → dim_exchange

Code:
df = session.get_table(
    'stocks', 'fact_prices',
    required_columns=['ticker', 'close', 'exchange_name']
)
# Automatically:
# 1. Finds exchange_name in dim_exchange
# 2. Plans joins: fact_prices → dim_stock → dim_exchange  
# 3. Executes joins
# 4. Returns all requested columns
```

## Aggregation Examples

### Grain Changes

```python
# Original grain: ticker-level daily prices
df = session.get_table('stocks', 'fact_prices')
# Shape: 1,000+ tickers × 250+ trading days = 250K+ rows

# Change grain: daily prices by exchange
df = session.get_table(
    'stocks', 'fact_prices',
    required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
    group_by=['trade_date', 'exchange_name'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
# Shape: 5-10 exchanges × 250 trading days = 1-2.5K rows
```

### Aggregation Inference

If you don't specify aggregations, system infers from:
1. Model measure definitions (from YAML config)
2. Column name patterns:
   - `volume`, `count`, `total` → `sum`
   - `high`, `max` → `max`
   - `low`, `min` → `min`
   - `close`, `price`, other numeric → `avg` (default)

```python
# Explicit aggregations (recommended)
df = session.get_table(
    'stocks', 'fact_prices',
    group_by=['ticker'],
    aggregations={'volume': 'sum', 'close': 'avg'}
)

# Inferred aggregations (uses defaults)
df = session.get_table(
    'stocks', 'fact_prices',
    group_by=['ticker']
    # System automatically infers: volume→sum, close→avg
)
```

## Backend Differences

### DuckDB Features

```
✓ Direct Parquet/Delta reading (no memory load)
✓ QUALIFY clause (filter after window functions)
✓ Very fast for analytics queries
✓ Single-machine in-process
```

### Spark Features

```
✓ Distributed processing
✓ In-memory caching
✓ Catalog/metastore integration
✓ Scaling to multiple machines
```

### Same Code Works on Both!

```python
# This code works on BOTH backends
df = session.get_table(
    'stocks', 'fact_prices',
    filters={'ticker': ['AAPL', 'GOOGL']},
    required_columns=['ticker', 'close', 'exchange_name'],
    group_by=['exchange_name'],
    aggregations={'close': 'avg'}
)
# UniversalSession handles backend differences internally
```

## Session Injection (Cross-Model Access)

Models can access each other through the session:

```python
# Inside StocksModel
def some_method(self):
    # Access other models
    company_model = self.session.load_model('company')
    company_df = company_model.get_table('dim_company')
    
    # Can join with self's tables
    merged = self.get_table('fact_prices').join(company_df, on='cik')
```

## Error Handling

### Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ValueError: Unknown connection type` | Wrong connection type | Use Spark session or DuckDB connection |
| `ValueError: Model 'xyz' not found` | Model not in registry | Check configs/models/ directory |
| `ValueError: Table 'xyz' not found` | Table not in schema | Verify table in model YAML |
| `ValueError: Cannot find join path` | No graph edges | Add edges to model graph YAML |
| `ValueError: graph contains cycles` | Circular dependencies | Fix model depends_on declarations |

## Configuration

### Storage Configuration Format

```python
storage_cfg = {
    "roots": {
        "bronze": "storage/bronze",      # Raw data location
        "silver": "storage/silver"       # Dimensional models location
    },
    "tables": {
        "securities_reference": {
            "rel": "alpha_vantage/securities_reference"
        },
        "securities_prices_daily": {
            "rel": "alpha_vantage/securities_prices_daily"
        }
        # ... more table mappings
    }
}
```

## Performance Tips

### Do's ✓

```python
# Pre-load frequently used models
session = UniversalSession(..., models=['stocks', 'company'])

# Specify required_columns explicitly
df = session.get_table('stocks', 'fact_prices',
                       required_columns=['ticker', 'close'])

# Use filters to reduce data early
df = session.get_table('stocks', 'fact_prices',
                       filters={'trade_date': {'min': '2024-01-01'}})

# Aggregate to smaller grain when possible
df = session.get_table('stocks', 'fact_prices',
                       group_by=['ticker'],
                       aggregations={'volume': 'sum'})

# Check if materialized view exists first
view = session._find_materialized_view('stocks', 
                                       ['ticker', 'close', 'exchange'])
```

### Don'ts ✗

```python
# DON'T: Load all models at startup
session = UniversalSession(..., models=[all_100_models])

# DON'T: Request all columns (let system optimize)
df = session.get_table('stocks', 'fact_prices')  # Gets all
# INSTEAD specify what you need

# DON'T: Complex joins across many tables
df = session.get_table(..., required_columns=[50 columns from 10 tables])
# INSTEAD: Use materialized views or break into smaller queries

# DON'T: Assume specific backend behavior
df = df.collect()  # Fails on DuckDB
# INSTEAD: Use backend-agnostic operations
```

## File Locations

| Component | Location |
|-----------|----------|
| UniversalSession | `/models/api/session.py` |
| FilterEngine | `/core/session/filters.py` |
| Backend Adapters | `/models/base/backend/` |
| - DuckDB | `/models/base/backend/duckdb_adapter.py` |
| - Spark | `/models/base/backend/spark_adapter.py` |
| Model Registry | `/models/registry.py` |
| Model Graph | `/models/api/graph.py` |
| Storage Router | `/models/api/dal.py` |

## Advanced: Direct Filter Engine Usage

```python
from core.session.filters import FilterEngine

# Apply filters without UniversalSession
df = some_dataframe
filters = {'ticker': ['AAPL', 'GOOGL'], 'volume': {'min': 1000000}}

# Spark backend
filtered_df = FilterEngine.apply_filters(df, filters, 'spark')

# DuckDB backend  
filtered_df = FilterEngine.apply_filters(df, filters, 'duckdb')

# Generate SQL WHERE clause
where_clause = FilterEngine.build_filter_sql(filters)
# Result: "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000"
```

## Advanced: Direct Graph Access

```python
from models.api.graph import ModelGraph
from pathlib import Path

graph = ModelGraph()
graph.build_from_config_dir(Path('configs/models'))

# Check relationships
related = graph.are_related('stocks', 'company')  # True?
dependencies = graph.get_dependencies('forecast')
path = graph.get_join_path('stocks', 'company')

# Get metrics
metrics = graph.get_metrics()
print(f"Models: {metrics['num_models']}")
print(f"Relationships: {metrics['num_relationships']}")

# Validate DAG
try:
    graph.validate_no_cycles()
    print("✓ Graph is a valid DAG")
except ValueError as e:
    print(f"✗ Cycles found: {e}")
```

## Summary

UniversalSession provides:

1. **Unified API** - Same code for Spark & DuckDB
2. **Dynamic Loading** - Models loaded on demand
3. **Transparent Joins** - Auto-joins via graph traversal
4. **Filter Engine** - Centralized filter application
5. **Aggregation** - Intelligent grain changes
6. **Session Injection** - Cross-model access
7. **Metadata Access** - Inspection capabilities

For more details, see `/docs/UNIVERSAL_SESSION_ARCHITECTURE.md`
