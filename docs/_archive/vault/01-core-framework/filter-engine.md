# FilterEngine Reference

**Centralized filter application for all backends**

File: `core/session/filters.py`

---

## Overview

`FilterEngine` provides a **unified interface for filter application** that works with both Spark and DuckDB backends, eliminating code duplication across the codebase.

### Key Features

- **Backend abstraction**: Single API for Spark and DuckDB
- **Multiple filter types**: Exact match, IN clause, range filters
- **Pandas support**: Works with DuckDB relations and pandas DataFrames
- **SQL generation**: Build WHERE clauses from filter specs
- **Session integration**: Auto-detects backend from UniversalSession

### Design Patterns

- **Static Methods**: No instance needed, pure utility class
- **Strategy Pattern**: Different backends use different implementations
- **Filter Specification**: Declarative filter definition

### Consolidation Complete (v2.2)

**FilterEngine is now the single source of truth for filter application.**

Previously duplicated code has been removed:
- ~~`app/notebook/filters/engine.py`~~ - **DELETED** (was 346 lines of dead code)
- ~~`app/notebook/filters/types.py`~~ - **DELETED** (was 34 lines, only used by deleted engine)
- `app/notebook/filters/__init__.py` now re-exports from `core.session.filters`

All filter application now goes through `FilterEngine` in `core/session/filters.py`.

---

## Public Methods

### `apply_filters(df, filters, backend) -> Any`

Apply filters based on backend type.

**Parameters:**
- `df` - DataFrame (SparkDataFrame or DuckDB relation)
- `filters` - Filter specifications mapping column names to filter values
- `backend` - Backend type ('spark' or 'duckdb')

**Returns:** Filtered DataFrame

**Raises:** `ValueError` if backend is unknown

**Example:**
```python
# With Spark
filtered = FilterEngine.apply_filters(spark_df, filters, 'spark')

# With DuckDB
filtered = FilterEngine.apply_filters(duckdb_relation, filters, 'duckdb')
```

---

### `apply_from_session(df, filters, session) -> Any`

Apply filters using session's backend detection.

**Convenience method** that automatically detects backend from session.

**Parameters:**
- `df` - DataFrame
- `filters` - Filter specifications
- `session` - UniversalSession instance with `backend` property

**Returns:** Filtered DataFrame

**Example:**
```python
filtered = FilterEngine.apply_from_session(df, filters, session)
# Equivalent to:
# FilterEngine.apply_filters(df, filters, session.backend)
```

---

### `build_filter_sql(filters) -> str`

Build SQL WHERE clause from filter specifications.

Useful for generating SQL queries with filters.

**Parameters:**
- `filters` - Filter specifications

**Returns:** SQL WHERE clause (without 'WHERE' keyword)

**Example:**
```python
filters = {
    'ticker': ['AAPL', 'GOOGL'],
    'volume': {'min': 1000000}
}

sql = FilterEngine.build_filter_sql(filters)
# "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000"

query = f"SELECT * FROM prices WHERE {sql}"
```

---

## Filter Specification Format

Filters are specified as a dictionary mapping column names to filter values.

### Exact Match

```python
filters = {'ticker': 'AAPL'}
# SQL: ticker = 'AAPL'
```

### IN Clause

```python
filters = {'ticker': ['AAPL', 'GOOGL', 'MSFT']}
# SQL: ticker IN ('AAPL', 'GOOGL', 'MSFT')
```

### Range Filters

**Date Range (start/end):**
```python
filters = {
    'trade_date': {
        'start': '2024-01-01',
        'end': '2024-12-31'
    }
}
# SQL: trade_date >= '2024-01-01' AND trade_date <= '2024-12-31'
```

**Numeric Range (min/max):**
```python
filters = {
    'volume': {
        'min': 1000000,
        'max': 10000000
    }
}
# SQL: volume >= 1000000 AND volume <= 10000000
```

**Comparison Operators:**
```python
filters = {
    'close': {'gt': 100},       # close > 100
    'close': {'gte': 100},      # close >= 100
    'close': {'lt': 200},       # close < 200
    'close': {'lte': 200}       # close <= 200
}
```

### Combined Filters

```python
filters = {
    'ticker': ['AAPL', 'GOOGL'],
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'},
    'volume': {'min': 1000000}
}
# SQL: ticker IN ('AAPL', 'GOOGL')
#      AND trade_date >= '2024-01-01'
#      AND trade_date <= '2024-12-31'
#      AND volume >= 1000000
```

---

## Internal Methods

### `_apply_spark_filters(df, filters) -> SparkDataFrame`

Apply filters to Spark DataFrame.

**Implementation:**
- Uses `F.col()` for column references
- Uses `.filter()` method for each condition
- Supports all filter types: exact match, IN clause, range filters

**Example:**
```python
# Internal implementation:
for col_name, value in filters.items():
    if isinstance(value, dict):
        if 'min' in value:
            df = df.filter(F.col(col_name) >= value['min'])
        if 'max' in value:
            df = df.filter(F.col(col_name) <= value['max'])
    elif isinstance(value, list):
        if value:
            df = df.filter(F.col(col_name).isin(value))
    elif value is not None:
        df = df.filter(F.col(col_name) == value)
```

---

### `_apply_duckdb_filters(df, filters) -> Any`

Apply filters to DuckDB relation or pandas DataFrame.

**Handles Two Types:**
- **DuckDB relations**: Uses SQL WHERE clause via `.filter()`
- **Pandas DataFrames**: Uses boolean indexing

**Implementation:**

**For DuckDB Relations:**
```python
# Build SQL WHERE conditions
conditions = []
for col_name, value in filters.items():
    if isinstance(value, list):
        conditions.append(f"{col_name} IN ('val1', 'val2')")
    elif isinstance(value, dict):
        if 'min' in value:
            conditions.append(f"{col_name} >= {value['min']}")

# Apply WHERE clause
where_clause = " AND ".join(conditions)
df = df.filter(where_clause)
```

**For Pandas DataFrames:**
```python
# Use boolean indexing
for col_name, value in filters.items():
    if isinstance(value, list):
        df = df[df[col_name].isin(value)]
    elif isinstance(value, dict):
        if 'min' in value:
            df = df[df[col_name] >= value['min']]
```

---

## Usage Patterns

### Basic Usage

```python
from core.session.filters import FilterEngine

# Define filters
filters = {
    'ticker': ['AAPL', 'MSFT', 'GOOGL'],
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
}

# Apply to Spark DataFrame
filtered_spark = FilterEngine.apply_filters(spark_df, filters, 'spark')

# Apply to DuckDB relation
filtered_duckdb = FilterEngine.apply_filters(duckdb_rel, filters, 'duckdb')
```

### With UniversalSession

```python
from core.session.filters import FilterEngine
from models.api.session import UniversalSession

# Create session
session = UniversalSession(connection, storage_cfg, repo_root)

# Get table
df = session.get_table('equity', 'fact_equity_prices')

# Apply filters (backend auto-detected)
filters = {'ticker': 'AAPL', 'trade_date': {'start': '2024-01-01'}}
filtered = FilterEngine.apply_from_session(df, filters, session)
```

### Building SQL Queries

```python
# Define filters
filters = {
    'ticker': ['AAPL', 'GOOGL'],
    'volume': {'min': 1000000},
    'close': {'gt': 100}
}

# Generate WHERE clause
where_clause = FilterEngine.build_filter_sql(filters)

# Build complete query
query = f"""
SELECT ticker, trade_date, close, volume
FROM fact_equity_prices
WHERE {where_clause}
"""

# Execute query
result = connection.execute(query)
```

### Filter in BaseModel

```python
class CustomModel(BaseModel):
    def get_filtered_data(self, table_name, filters):
        """Get filtered data using FilterEngine."""
        # Get table
        df = self.get_table(table_name)

        # Apply filters
        filtered = FilterEngine.apply_filters(df, filters, self.backend)

        return filtered
```

---

## Filter Types Summary

| Filter Type | Specification | SQL Output |
|-------------|---------------|------------|
| **Exact Match** | `{'col': 'value'}` | `col = 'value'` |
| **IN Clause** | `{'col': ['v1', 'v2']}` | `col IN ('v1', 'v2')` |
| **Date Range** | `{'col': {'start': 'date1', 'end': 'date2'}}` | `col >= 'date1' AND col <= 'date2'` |
| **Numeric Range** | `{'col': {'min': 10, 'max': 20}}` | `col >= 10 AND col <= 20'` |
| **Greater Than** | `{'col': {'gt': 100}}` | `col > 100` |
| **Greater or Equal** | `{'col': {'gte': 100}}` | `col >= 100` |
| **Less Than** | `{'col': {'lt': 100}}` | `col < 100` |
| **Less or Equal** | `{'col': {'lte': 100}}` | `col <= 100` |

---

## Backend Implementations

### Spark Backend

**Method:** `F.filter()` with PySpark functions

**Features:**
- Uses `F.col()` for column references
- Uses `.isin()` for IN clauses
- Comparison operators: `>=`, `<=`, `>`, `<`, `==`

**Example:**
```python
df.filter(F.col('ticker').isin(['AAPL', 'MSFT']))
df.filter((F.col('close') >= 100) & (F.col('close') <= 200))
```

### DuckDB Backend

**Method:** SQL WHERE clause via `.filter()`

**Features:**
- Builds SQL WHERE clause as string
- Uses SQL IN syntax
- Standard SQL comparison operators

**Example:**
```python
df.filter("ticker IN ('AAPL', 'MSFT')")
df.filter("close >= 100 AND close <= 200")
```

### Pandas Backend

**Method:** Boolean indexing

**Features:**
- Uses `.isin()` for IN clauses
- Standard Python comparison operators
- Chained boolean indexing

**Example:**
```python
df[df['ticker'].isin(['AAPL', 'MSFT'])]
df[(df['close'] >= 100) & (df['close'] <= 200)]
```

---

## Special Handling

### None Values

None values in filters are **ignored** (no filter applied for that column).

```python
filters = {
    'ticker': 'AAPL',
    'exchange': None  # Ignored - no filter applied
}
# Only filters by ticker
```

### Empty Lists

Empty lists are **ignored** (no filter applied).

```python
filters = {
    'ticker': [],  # Ignored - no filter applied
    'volume': {'min': 1000000}
}
# Only filters by volume
```

### Date Format Flexibility

Supports both `start/end` (dates) and `min/max` (numbers) for range filters.

```python
# Date range
filters = {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}

# Numeric range
filters = {'volume': {'min': 1000000, 'max': 10000000}}
```

---

## Best Practices

1. **Use apply_from_session()**: Let session detect backend automatically
2. **Consistent filter format**: Use dictionaries for all filter specs
3. **Null safety**: FilterEngine ignores None values gracefully
4. **Date ranges**: Use ISO format strings ('YYYY-MM-DD')
5. **Performance**: Apply filters early for pushdown optimization
6. **SQL generation**: Use `build_filter_sql()` for custom queries

---

## Related Documentation

- [UniversalSession](universal-session.md) - Uses FilterEngine internally
- [Connection System](connection-system.md) - Backend-specific filter methods
- [BaseModel](base-model.md) - Filter application in models
