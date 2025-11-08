# Core Session - Connections

## Overview

The **Connection Layer** provides a backend-agnostic interface for data access. It abstracts the differences between Spark and DuckDB, allowing application code to work with both backends using the same API.

## Architecture

```
┌──────────────────────────────────────┐
│      DataConnection (Abstract)       │
├──────────────────────────────────────┤
│ + read_table(path)                   │
│ + apply_filters(df, filters)         │
│ + to_pandas(df)                      │
│ + count(df)                          │
│ + cache(df)                          │
│ + uncache(df)                        │
│ + stop()                             │
└──────────────┬───────────────────────┘
               │
     ┌─────────┴─────────┐
     │                   │
     ▼                   ▼
┌──────────────┐   ┌──────────────┐
│    Spark     │   │   DuckDB     │
│ Connection   │   │ Connection   │
└──────────────┘   └──────────────┘
```

## DataConnection Interface

```python
# File: core/connection.py:14-84

class DataConnection(ABC):
    """Abstract base class for data connections."""

    @abstractmethod
    def read_table(self, path: str, format: str = "parquet") -> Any:
        """Read a table from storage."""
        pass

    @abstractmethod
    def apply_filters(self, df: Any, filters: Dict[str, Any]) -> Any:
        """Apply filters to a dataframe."""
        pass

    @abstractmethod
    def to_pandas(self, df: Any) -> pd.DataFrame:
        """Convert to Pandas DataFrame."""
        pass

    @abstractmethod
    def count(self, df: Any) -> int:
        """Get row count."""
        pass

    @abstractmethod
    def cache(self, df: Any) -> Any:
        """Cache dataframe in memory."""
        pass

    @abstractmethod
    def uncache(self, df: Any):
        """Remove from cache."""
        pass

    @abstractmethod
    def stop(self):
        """Close connection and cleanup resources."""
        pass
```

## Spark Connection

```python
# File: core/connection.py:87-170

class SparkConnection(DataConnection):
    """Spark-based data connection."""

    def __init__(self, spark_session):
        self.spark = spark_session
        self._cached_dfs = []

    def read_table(self, path: str, format: str = "parquet"):
        """Read table using Spark."""
        return self.spark.read.format(format).load(path)

    def apply_filters(self, df, filters: Dict[str, Any]):
        """Apply filters using Spark SQL."""
        from pyspark.sql import functions as F

        for column, value in filters.items():
            if isinstance(value, dict):
                # Date range filter
                if 'start' in value and 'end' in value:
                    start, end = value['start'], value['end']
                    if hasattr(start, 'strftime'):
                        start = start.strftime('%Y-%m-%d')
                    if hasattr(end, 'strftime'):
                        end = end.strftime('%Y-%m-%d')
                    df = df.filter((F.col(column) >= start) & (F.col(column) <= end))

                # Numeric range filter
                if 'min' in value:
                    df = df.filter(F.col(column) >= value['min'])
                if 'max' in value:
                    df = df.filter(F.col(column) <= value['max'])

            elif isinstance(value, list):
                # IN clause
                if value:
                    df = df.filter(F.col(column).isin(value))

            else:
                # Exact match
                df = df.filter(F.col(column) == value)

        return df

    def to_pandas(self, df) -> pd.DataFrame:
        """Convert Spark DataFrame to Pandas."""
        return df.toPandas()

    def count(self, df) -> int:
        """Get row count."""
        return df.count()

    def cache(self, df):
        """Cache Spark DataFrame."""
        df.cache()
        self._cached_dfs.append(df)
        return df

    def uncache(self, df):
        """Uncache Spark DataFrame."""
        df.unpersist()
        if df in self._cached_dfs:
            self._cached_dfs.remove(df)

    def stop(self):
        """Stop Spark session."""
        # Uncache all dataframes
        for df in self._cached_dfs:
            df.unpersist()
        self._cached_dfs.clear()
        self.spark.stop()
```

## DuckDB Connection

```python
# File: core/duckdb_connection.py:15-120

class DuckDBConnection(DataConnection):
    """DuckDB-based data connection."""

    def __init__(self, db_path: Optional[str] = None):
        import duckdb
        self._conn = duckdb.connect(database=db_path or ':memory:')
        self._table_counter = 0

    def read_table(self, path: str, format: str = "parquet"):
        """Read table using DuckDB."""
        if format == "parquet":
            # DuckDB can query parquet directly
            return self._conn.from_parquet(path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def apply_filters(self, df, filters: Dict[str, Any]):
        """Apply filters using DuckDB SQL."""
        conditions = []

        for column, value in filters.items():
            if isinstance(value, dict):
                # Date range
                if 'start' in value and 'end' in value:
                    start, end = value['start'], value['end']
                    conditions.append(f"{column} >= '{start}' AND {column} <= '{end}'")

                # Numeric range
                if 'min' in value:
                    conditions.append(f"{column} >= {value['min']}")
                if 'max' in value:
                    conditions.append(f"{column} <= {value['max']}")

            elif isinstance(value, list):
                # IN clause
                if value:
                    values_str = ', '.join([f"'{v}'" for v in value])
                    conditions.append(f"{column} IN ({values_str})")

            else:
                # Exact match
                conditions.append(f"{column} = '{value}'")

        # Apply WHERE clause
        if conditions:
            where_clause = " AND ".join(conditions)
            return df.filter(where_clause)

        return df

    def to_pandas(self, df) -> pd.DataFrame:
        """Convert DuckDB relation to Pandas."""
        return df.df()

    def count(self, df) -> int:
        """Get row count."""
        result = df.aggregate("COUNT(*) as cnt").fetchone()
        return result[0]

    def cache(self, df):
        """
        Cache DuckDB relation as temp table.

        DuckDB doesn't have explicit caching like Spark,
        but we can materialize as a temp table.
        """
        table_name = f"_cached_{self._table_counter}"
        self._table_counter += 1

        self._conn.register(table_name, df.df())
        return self._conn.table(table_name)

    def uncache(self, df):
        """Drop temp table (no-op for now)."""
        pass

    def stop(self):
        """Close DuckDB connection."""
        self._conn.close()
```

## Connection Factory

```python
# File: core/connection.py:200-230

class ConnectionFactory:
    """Factory for creating data connections."""

    @staticmethod
    def create(backend: str, **kwargs) -> DataConnection:
        """
        Create a data connection.

        Args:
            backend: 'spark' or 'duckdb'
            **kwargs: Backend-specific arguments
                - spark_session (for Spark)
                - db_path (for DuckDB)

        Returns:
            DataConnection instance

        Raises:
            ValueError: If backend is unsupported
        """
        if backend == "spark":
            if "spark_session" not in kwargs:
                raise ValueError("SparkConnection requires 'spark_session'")
            return SparkConnection(kwargs["spark_session"])

        elif backend == "duckdb":
            return DuckDBConnection(kwargs.get("db_path"))

        else:
            raise ValueError(f"Unsupported backend: {backend}")
```

## Usage Examples

### Example 1: Read and Filter

```python
from core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type='duckdb')

# Read table
df = ctx.connection.read_table("storage/silver/fact_prices")

# Apply filters
filters = {
    'ticker': 'AAPL',
    'date': {'start': '2024-01-01', 'end': '2024-12-31'}
}
filtered = ctx.connection.apply_filters(df, filters)

# Convert to Pandas
pdf = ctx.connection.to_pandas(filtered)
print(pdf.head())
```

### Example 2: Caching

```python
# Cache expensive query
df = ctx.connection.read_table("storage/silver/fact_prices")
df = ctx.connection.cache(df)

# Use multiple times without re-reading
for ticker in ['AAPL', 'GOOGL', 'MSFT']:
    filtered = ctx.connection.apply_filters(df, {'ticker': ticker})
    print(f"{ticker}: {ctx.connection.count(filtered)} rows")

# Clean up
ctx.connection.uncache(df)
```

### Example 3: Backend Switching

```python
def analyze_data(backend='duckdb'):
    """Run analysis on specified backend."""
    ctx = RepoContext.from_repo_root(connection_type=backend)

    df = ctx.connection.read_table("storage/silver/fact_prices")
    filtered = ctx.connection.apply_filters(df, {'ticker': 'AAPL'})

    return ctx.connection.to_pandas(filtered)

# Fast for OLAP
pdf = analyze_data('duckdb')

# Scalable for large datasets
pdf = analyze_data('spark')
```

---

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/core-session/connections.md`
