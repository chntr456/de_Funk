# Core Session - Filter Engine

## Overview

The **FilterEngine** provides centralized filter application logic that works across both Spark and DuckDB backends. It eliminates code duplication and ensures consistent filter semantics throughout the application.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FilterEngine                         │
├─────────────────────────────────────────────────────────┤
│ + apply_filters(df, filters, backend)                   │
│ + apply_from_session(df, filters, session)              │
│ - _apply_spark_filters(df, filters)                     │
│ - _apply_duckdb_filters(df, filters)                    │
└─────────────────────────────────────────────────────────┘
```

## Filter Specification Format

```python
{
    # Exact match
    'column_name': value,

    # IN clause
    'column_name': [val1, val2, val3],

    # Range filter
    'column_name': {
        'min': value,     # >= 
        'max': value,     # <=
        'operator': 'gte' | 'lte' | 'gt' | 'lt'
    },

    # Date range
    'date_column': {
        'start': '2024-01-01',
        'end': '2024-12-31'
    }
}
```

## Core Implementation

```python
# File: core/session/filters.py:13-90

class FilterEngine:
    """Centralized filter application for all backends."""

    @staticmethod
    def apply_filters(df: Any, filters: Dict[str, Any], backend: str) -> Any:
        """
        Apply filters based on backend type.

        Args:
            df: DataFrame (Spark or DuckDB)
            filters: Filter specifications
            backend: Backend type ('spark' or 'duckdb')

        Returns:
            Filtered DataFrame
        """
        if backend == 'spark':
            return FilterEngine._apply_spark_filters(df, filters)
        elif backend == 'duckdb':
            return FilterEngine._apply_duckdb_filters(df, filters)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    @staticmethod
    def apply_from_session(df: Any, filters: Dict[str, Any], session) -> Any:
        """
        Apply filters using session's backend detection.

        Convenience method that automatically detects backend.
        """
        backend = session.backend
        return FilterEngine.apply_filters(df, filters, backend)
```

## Spark Filter Implementation

```python
# File: core/session/filters.py:92-150

@staticmethod
def _apply_spark_filters(df: SparkDataFrame, filters: Dict[str, Any]) -> SparkDataFrame:
    """Apply filters for Spark backend."""
    from pyspark.sql import functions as F

    for column, value in filters.items():
        # Skip if column doesn't exist
        if column not in df.columns:
            continue

        if isinstance(value, dict):
            # Date range: {start: 'YYYY-MM-DD', end: 'YYYY-MM-DD'}
            if 'start' in value and 'end' in value:
                start, end = value['start'], value['end']
                
                # Convert datetime objects to strings
                if hasattr(start, 'strftime'):
                    start = start.strftime('%Y-%m-%d')
                if hasattr(end, 'strftime'):
                    end = end.strftime('%Y-%m-%d')

                df = df.filter((F.col(column) >= start) & (F.col(column) <= end))

            # Numeric range: {min: value, max: value}
            if 'min' in value:
                df = df.filter(F.col(column) >= value['min'])
            if 'max' in value:
                df = df.filter(F.col(column) <= value['max'])

            # Custom operator: {value: 100, operator: 'gt'}
            if 'operator' in value:
                op = value['operator']
                val = value.get('value', value.get('min', value.get('max')))

                if op == 'gt':
                    df = df.filter(F.col(column) > val)
                elif op == 'gte':
                    df = df.filter(F.col(column) >= val)
                elif op == 'lt':
                    df = df.filter(F.col(column) < val)
                elif op == 'lte':
                    df = df.filter(F.col(column) <= val)
                elif op == 'eq':
                    df = df.filter(F.col(column) == val)
                elif op == 'ne':
                    df = df.filter(F.col(column) != val)

        elif isinstance(value, list):
            # IN clause
            if value:  # Only filter if list is not empty
                df = df.filter(F.col(column).isin(value))

        else:
            # Exact match
            df = df.filter(F.col(column) == value)

    return df
```

## DuckDB Filter Implementation

```python
# File: core/session/filters.py:152-210

@staticmethod
def _apply_duckdb_filters(df, filters: Dict[str, Any]):
    """Apply filters for DuckDB backend."""
    conditions = []

    for column, value in filters.items():
        if isinstance(value, dict):
            # Date range
            if 'start' in value and 'end' in value:
                start, end = value['start'], value['end']

                # Convert datetime to string
                if hasattr(start, 'strftime'):
                    start = start.strftime('%Y-%m-%d')
                if hasattr(end, 'strftime'):
                    end = end.strftime('%Y-%m-%d')

                conditions.append(f"{column} >= '{start}' AND {column} <= '{end}'")

            # Numeric range
            if 'min' in value:
                conditions.append(f"{column} >= {value['min']}")
            if 'max' in value:
                conditions.append(f"{column} <= {value['max']}")

            # Custom operator
            if 'operator' in value:
                op = value['operator']
                val = value.get('value', value.get('min', value.get('max')))

                op_map = {
                    'gt': '>',
                    'gte': '>=',
                    'lt': '<',
                    'lte': '<=',
                    'eq': '=',
                    'ne': '!='
                }

                if op in op_map:
                    conditions.append(f"{column} {op_map[op]} {val}")

        elif isinstance(value, list):
            # IN clause
            if value:
                # Quote string values
                if isinstance(value[0], str):
                    values_str = ', '.join([f"'{v}'" for v in value])
                else:
                    values_str = ', '.join([str(v) for v in value])

                conditions.append(f"{column} IN ({values_str})")

        else:
            # Exact match
            if isinstance(value, str):
                conditions.append(f"{column} = '{value}'")
            else:
                conditions.append(f"{column} = {value}")

    # Apply WHERE clause
    if conditions:
        where_clause = " AND ".join(conditions)
        return df.filter(where_clause)

    return df
```

## Usage Examples

### Example 1: Basic Filtering

```python
from core.session.filters import FilterEngine

# Apply filters with explicit backend
filters = {'ticker': 'AAPL', 'date': {'start': '2024-01-01'}}
filtered_df = FilterEngine.apply_filters(df, filters, backend='duckdb')
```

### Example 2: Session-Based Filtering

```python
# Let session detect backend
from models.api.session import UniversalSession

session = UniversalSession(connection, storage_cfg, repo_root)
df = session.get_table('company', 'fact_prices')

filters = {'ticker': ['AAPL', 'GOOGL'], 'volume': {'min': 1000000}}
filtered_df = FilterEngine.apply_from_session(df, filters, session)
```

### Example 3: Complex Filters

```python
filters = {
    # Multi-value IN clause
    'ticker': ['AAPL', 'GOOGL', 'MSFT'],

    # Date range
    'date': {
        'start': '2024-01-01',
        'end': '2024-12-31'
    },

    # Numeric range
    'volume': {
        'min': 1000000,
        'max': 10000000
    },

    # Custom operator
    'close': {
        'value': 150.0,
        'operator': 'gte'
    },

    # Exact match
    'exchange': 'NASDAQ'
}

filtered_df = FilterEngine.apply_filters(df, filters, backend='spark')
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/core-session/filter-engine.md`
