# Connection System Reference

**Complete documentation for backend connection adapters**

Files:
- `core/connection.py` - Abstract base and SparkConnection
- `core/duckdb_connection.py` - DuckDBConnection

---

## Overview

The Connection System provides **backend abstraction** for de_Funk, allowing the same models and queries to work with both Spark and DuckDB. It implements the Strategy pattern with pluggable connection adapters.

### Key Features

- **Backend abstraction**: Unified interface for Spark and DuckDB
- **Delta Lake support**: ACID transactions, time travel, merge operations
- **Format flexibility**: Parquet and Delta Lake formats
- **Filter optimization**: Backend-specific filter implementations
- **Caching**: Memory caching for performance
- **Resource management**: Proper connection cleanup

### Design Patterns

- **Abstract Base Class**: `DataConnection` defines interface contract
- **Strategy Pattern**: Different backends implement same interface
- **Factory Pattern**: `ConnectionFactory` creates appropriate connection
- **Adapter Pattern**: Wraps native Spark/DuckDB APIs with unified interface

---

## DataConnection (Abstract Base Class)

**File:** `core/connection.py:17-88`

Abstract base class defining the connection interface that all backends must implement.

### Abstract Methods

All backend implementations must provide these methods:

#### `read_table(path: str, format: str = "parquet") -> Any`

Read a table from storage.

**Parameters:**
- `path` - Path to table
- `format` - Format (parquet, delta, csv, etc.)

**Returns:** DataFrame-like object (specific to connection type)

---

#### `apply_filters(df: Any, filters: Dict[str, Any]) -> Any`

Apply filters to a dataframe.

**Parameters:**
- `df` - DataFrame-like object
- `filters` - Dict of column → value/condition

**Returns:** Filtered dataframe

---

#### `to_pandas(df: Any) -> pd.DataFrame`

Convert to Pandas DataFrame.

**Parameters:**
- `df` - DataFrame-like object

**Returns:** Pandas DataFrame

---

#### `count(df: Any) -> int`

Get row count.

**Parameters:**
- `df` - DataFrame-like object

**Returns:** Number of rows

---

#### `cache(df: Any) -> Any`

Cache dataframe in memory.

**Parameters:**
- `df` - DataFrame-like object

**Returns:** Cached dataframe

---

#### `uncache(df: Any)`

Remove from cache.

**Parameters:**
- `df` - DataFrame-like object

---

#### `stop()`

Close connection and cleanup resources.

---

## SparkConnection

**File:** `core/connection.py:90-443`

Spark-based data connection with Delta Lake support.

### Class Constructor

#### `__init__(spark_session)`

Initialize Spark connection.

**Parameters:**
- `spark_session` - PySpark SparkSession
  - For Delta support, configure with:
    - `spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`
    - `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`

**Initializes:**
- Spark session reference
- Cached DataFrames list
- Delta availability check

**Example:**
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

conn = SparkConnection(spark)
```

---

### Read Methods

#### `read_table(path, format="parquet", version=None, timestamp=None)`

Read table using Spark with optional Delta Lake time travel.

**Parameters:**
- `path` - Path to table or catalog table name
- `format` - Format ('parquet', 'delta', or any Spark-supported format)
- `version` - For Delta tables, specific version to read (time travel)
- `timestamp` - For Delta tables, timestamp to read (time travel)

**Returns:** Spark DataFrame

**Example:**
```python
# Read Parquet
df = conn.read_table('/path/to/parquet', format='parquet')

# Read Delta table
df = conn.read_table('/path/to/delta', format='delta')

# Time travel - specific version
df = conn.read_table('/path/to/delta', format='delta', version=5)

# Time travel - timestamp
df = conn.read_table('/path/to/delta', format='delta',
                     timestamp='2024-01-15 10:00:00')
```

---

### Delta Lake Write Methods

#### `write_delta_table(df, path, mode="overwrite", partition_by=None, **options)`

Write Spark DataFrame to Delta Lake table.

**Parameters:**
- `df` - Spark DataFrame to write
- `path` - Path to Delta table
- `mode` - Write mode ('overwrite', 'append')
- `partition_by` - Columns to partition by
- `**options` - Additional write options

**Note:** For merge operations, use `merge_delta_table()` instead.

**Example:**
```python
# Overwrite
conn.write_delta_table(df, '/path/to/delta', mode='overwrite')

# Append with partitioning
conn.write_delta_table(df, '/path/to/delta', mode='append',
                       partition_by=['year', 'month'])
```

---

#### `merge_delta_table(source_df, target_path, merge_condition, update_set=None, insert_values=None)`

Merge (upsert) data into Delta table using Spark's Delta Lake API.

**Parameters:**
- `source_df` - Spark DataFrame with source data
- `target_path` - Path to target Delta table
- `merge_condition` - SQL condition for matching (e.g., "target.id = source.id")
- `update_set` - Dict of column updates for matched rows (default: update all)
- `insert_values` - Dict of column values for not matched rows (default: insert all)

**Example:**
```python
# Basic merge (update all, insert all)
conn.merge_delta_table(
    source_df,
    '/path/to/delta',
    merge_condition="target.ticker = source.ticker AND target.trade_date = source.trade_date"
)

# Custom update/insert logic
conn.merge_delta_table(
    source_df,
    '/path/to/delta',
    merge_condition="target.id = source.id",
    update_set={"value": "source.value", "updated_at": "source.updated_at"},
    insert_values={"*": "*"}  # Insert all columns
)
```

---

### Delta Lake Optimization Methods

#### `optimize_delta_table(path, zorder_by=None)`

Optimize Delta table (compact files, optionally z-order).

**Parameters:**
- `path` - Path to Delta table
- `zorder_by` - Columns to z-order by (for better data skipping)

**Benefits:**
- Compacts small files into larger ones
- Z-ordering improves query performance via data skipping

**Example:**
```python
# Basic optimization
conn.optimize_delta_table('/path/to/delta')

# With z-ordering
conn.optimize_delta_table('/path/to/delta', zorder_by=['ticker', 'trade_date'])
```

---

#### `vacuum_delta_table(path, retention_hours=168)`

Vacuum Delta table (remove old files).

**Parameters:**
- `path` - Path to Delta table
- `retention_hours` - Retention period in hours (default: 168 = 7 days)

**Warning:** Vacuuming permanently deletes old data files and disables time travel to versions older than retention period!

**Example:**
```python
# Vacuum with default 7-day retention
conn.vacuum_delta_table('/path/to/delta')

# Custom retention
conn.vacuum_delta_table('/path/to/delta', retention_hours=24)
```

---

#### `get_delta_table_history(path, limit=None) -> pd.DataFrame`

Get version history of Delta table.

**Parameters:**
- `path` - Path to Delta table
- `limit` - Optional limit on number of versions to return

**Returns:** Pandas DataFrame with history (version, timestamp, operation, etc.)

**Example:**
```python
history = conn.get_delta_table_history('/path/to/delta')
print(history[['version', 'timestamp', 'operation']])
```

---

### Filter Methods

#### `apply_filters(df, filters: Dict[str, Any])`

Apply filters using Spark SQL.

**Parameters:**
- `df` - Spark DataFrame
- `filters` - Dict of column → value/condition

**Filter Types:**
- **Date range**: `{'start': '2024-01-01', 'end': '2024-12-31'}`
- **List (IN)**: `['AAPL', 'MSFT', 'GOOGL']`
- **Single value**: `'AAPL'`

**Example:**
```python
filters = {
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'},
    'ticker': ['AAPL', 'MSFT', 'GOOGL']
}
filtered_df = conn.apply_filters(df, filters)
```

---

### Utility Methods

#### `to_pandas(df) -> pd.DataFrame`

Convert Spark DataFrame to Pandas.

**Parameters:**
- `df` - Spark DataFrame

**Returns:** Pandas DataFrame

---

#### `count(df) -> int`

Get row count.

**Parameters:**
- `df` - Spark DataFrame

**Returns:** Number of rows

---

#### `cache(df)`

Cache Spark DataFrame in memory.

**Parameters:**
- `df` - Spark DataFrame

**Returns:** Cached DataFrame

**Side Effect:** Adds to internal `_cached_dfs` list for cleanup

---

#### `uncache(df)`

Uncache Spark DataFrame.

**Parameters:**
- `df` - Spark DataFrame

**Side Effect:** Removes from `_cached_dfs` list

---

#### `stop()`

Stop Spark session and cleanup.

**Process:**
1. Unpersist all cached DataFrames
2. Clear cache list
3. Stop Spark session

---

### Internal Methods

#### `_is_delta_table(path: str) -> bool`

Check if path points to a Delta Lake table.

**Parameters:**
- `path` - Path to check

**Returns:** `True` if Delta table (has `_delta_log` directory), `False` otherwise

---

## DuckDBConnection

**File:** `core/duckdb_connection.py:36-625`

DuckDB connection for analytics queries with Delta Lake support.

### Benefits

- **Fast startup**: No Spark overhead
- **Native Parquet/Delta support**: Reads files directly
- **SQL-based queries**: Familiar SQL interface
- **ACID transactions**: With Delta Lake
- **Time travel**: Delta version history
- **Interactive workloads**: Great for notebooks

### Class Constructor

#### `__init__(db_path=":memory:", read_only=False, enable_delta=True)`

Initialize DuckDB connection with optional Delta Lake support.

**Parameters:**
- `db_path` - Path to DuckDB database file (":memory:" for in-memory)
- `read_only` - Whether to open in read-only mode
- `enable_delta` - Whether to enable Delta Lake extension (default: True)

**Initializes:**
- DuckDB connection
- Cached tables dict
- Delta extension (if enabled)

**Example:**
```python
# In-memory database
conn = DuckDBConnection()

# Persistent database
conn = DuckDBConnection(db_path='analytics.db')

# Read-only mode
conn = DuckDBConnection(db_path='analytics.db', read_only=True)
```

---

### Read Methods

#### `read_table(path, format="parquet", version=None, timestamp=None)`

Read a table from storage (Parquet or Delta Lake).

DuckDB can query files **directly** without loading into memory!

**Parameters:**
- `path` - Path to the table (file or directory)
- `format` - Format of the data ('parquet' or 'delta')
- `version` - For Delta tables, specific version to read (time travel)
- `timestamp` - For Delta tables, timestamp to read (time travel)

**Returns:** DuckDB relation (lazy query result)

**Auto-Detection:** Automatically detects Delta tables and switches format

**Example:**
```python
# Read current version
df = conn.read_table('/path/to/delta', format='delta')

# Read specific version (time travel)
df = conn.read_table('/path/to/delta', format='delta', version=5)

# Auto-detect Delta table
df = conn.read_table('/path/to/delta', format='parquet')  # Auto-switches to delta
```

---

#### `read_parquet(path: str)`

Read parquet file(s) from path.

Alias for `read_table()` for compatibility.

**Parameters:**
- `path` - Path to parquet file or directory

**Returns:** DuckDB relation

---

#### `_read_delta_table(path, version=None, timestamp=None)`

Read a Delta Lake table using DuckDB's `delta_scan` function.

**Internal method** for Delta table reading.

**Parameters:**
- `path` - Path to Delta table
- `version` - Specific version to read (time travel)
- `timestamp` - Timestamp to read (time travel)

**Returns:** DuckDB relation

**Implementation:**
- For current version: Uses `delta_scan()` (fast)
- For time travel: Uses delta-rs library + arrow conversion

---

### Delta Lake Write Methods

#### `write_delta_table(df: pd.DataFrame, path, mode="overwrite", partition_by=None, **kwargs)`

Write DataFrame to Delta Lake table.

**Parameters:**
- `df` - Pandas DataFrame to write
- `path` - Path to Delta table
- `mode` - Write mode ('overwrite', 'append', 'merge')
- `partition_by` - Columns to partition by
- `**kwargs` - Additional arguments passed to write_deltalake

**Example:**
```python
# Overwrite table
conn.write_delta_table(df, '/path/to/delta', mode='overwrite')

# Append to table
conn.write_delta_table(df, '/path/to/delta', mode='append')

# Partition by column
conn.write_delta_table(df, '/path/to/delta', partition_by=['year', 'month'])

# Merge (requires merge_keys)
conn.write_delta_table(df, '/path/to/delta', mode='merge',
                       merge_keys=['ticker', 'trade_date'])
```

---

#### `_merge_delta_table(df: pd.DataFrame, path, merge_keys: List[str])`

Merge (upsert) DataFrame into Delta table.

**Internal method** for merge operations.

**Parameters:**
- `df` - DataFrame with new/updated data
- `path` - Path to Delta table
- `merge_keys` - Columns to match on (e.g., ['ticker', 'trade_date'])

**Process:**
1. Build predicate for merge
2. Perform merge with `when_matched_update_all()` and `when_not_matched_insert_all()`

---

### Delta Lake Optimization Methods

#### `optimize_delta_table(path, zorder_by=None)`

Optimize Delta table (compact small files, optionally z-order).

**Parameters:**
- `path` - Path to Delta table
- `zorder_by` - Columns to z-order by (for better data skipping)

**Example:**
```python
# Basic compaction
conn.optimize_delta_table('/path/to/delta')

# With z-ordering
conn.optimize_delta_table('/path/to/delta', zorder_by=['ticker', 'trade_date'])
```

---

#### `vacuum_delta_table(path, retention_hours=168, enforce_retention=True)`

Vacuum Delta table (remove old files no longer needed).

**Parameters:**
- `path` - Path to Delta table
- `retention_hours` - Retention period in hours (default: 168 = 7 days, minimum: 168)
- `enforce_retention` - Whether to enforce minimum retention period (default: True)

**Warning:** Vacuuming removes old files and disables time travel!

**Example:**
```python
# Vacuum files older than 7 days
conn.vacuum_delta_table('/path/to/delta')

# Custom retention (risky for production!)
conn.vacuum_delta_table('/path/to/delta', retention_hours=24,
                       enforce_retention=False)
```

---

#### `get_delta_table_history(path) -> pd.DataFrame`

Get the version history of a Delta table.

**Parameters:**
- `path` - Path to Delta table

**Returns:** DataFrame with version history (version, timestamp, operation, etc.)

**Example:**
```python
history = conn.get_delta_table_history('/path/to/delta')
print(history[['version', 'timestamp', 'operation']])
```

---

### Filter Methods

#### `apply_filters(df, filters: Dict[str, Any])`

Apply filters to a DuckDB relation.

**Parameters:**
- `df` - DuckDB relation
- `filters` - Dictionary of column → filter value

**Returns:** Filtered DuckDB relation

**Filter Types:**
- **Date range**: `{'start': '2024-01-01', 'end': '2024-12-31'}`
- **Numeric range**: `{'min': 100, 'max': 200}`
- **List (IN)**: `['AAPL', 'MSFT', 'GOOGL']`
- **Single value**: `'AAPL'`

**Implementation:** Builds SQL WHERE clause

**Example:**
```python
filters = {
    'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'},
    'close': {'min': 100, 'max': 200},
    'ticker': ['AAPL', 'MSFT', 'GOOGL']
}
filtered = conn.apply_filters(df, filters)
```

---

### Utility Methods

#### `to_pandas(df) -> pd.DataFrame`

Convert DuckDB relation to pandas DataFrame.

**Parameters:**
- `df` - DuckDB relation or pandas DataFrame

**Returns:** Pandas DataFrame

**Auto-detection:** Returns as-is if already pandas

---

#### `count(df) -> int`

Get row count from DuckDB relation.

**Parameters:**
- `df` - DuckDB relation

**Returns:** Number of rows

---

#### `cache(df, name=None)`

Cache a DuckDB relation as a temporary table.

**Parameters:**
- `df` - DuckDB relation to cache
- `name` - Optional name for the cached table (auto-generated if not provided)

**Returns:** Cached relation

**Implementation:** Creates temporary table in DuckDB

---

#### `uncache(df)`

Remove cached table.

**Parameters:**
- `df` - DuckDB relation to uncache

**Implementation:** Drops temporary table from DuckDB

---

#### `stop()`

Close the DuckDB connection and cleanup.

**Process:**
1. Clear all cached tables
2. Close connection

---

### SQL Methods

#### `execute_sql(query: str)`

Execute raw SQL query.

**Parameters:**
- `query` - SQL query string

**Returns:** DuckDB relation with results

---

#### `execute(query: str)`

Execute raw SQL query (alias for `execute_sql`).

Provided for compatibility.

**Parameters:**
- `query` - SQL query string

**Returns:** DuckDB relation with results

---

#### `table(table_name: str)`

Get a table/view by name.

**Parameters:**
- `table_name` - Name of table or view (can include schema: schema.table)

**Returns:** DuckDB relation

---

### Compatibility Methods

#### `createDataFrame(data: list, schema=None)`

Create a DuckDB relation from data and schema.

**Compatibility method** for Spark's createDataFrame API.

**Parameters:**
- `data` - List of rows (typically empty [])
- `schema` - PySpark StructType schema (optional)

**Returns:** DuckDB relation

**Use Case:** Primarily used for creating empty tables when no data exists

---

### Internal Methods

#### `_enable_delta_extension()`

Enable DuckDB Delta extension.

Installs and loads the Delta extension for reading/writing Delta Lake tables.

---

#### `_is_delta_table(path: str) -> bool`

Check if a path points to a Delta Lake table.

**Parameters:**
- `path` - Path to check

**Returns:** `True` if path has `_delta_log` directory, `False` otherwise

---

## ConnectionFactory

**File:** `core/connection.py:445-489`

Factory for creating data connections.

### Static Methods

#### `create(connection_type="spark", **kwargs) -> DataConnection`

Create a data connection.

**Parameters:**
- `connection_type` - Type of connection ('spark', 'duckdb')
- `**kwargs` - Connection-specific arguments

**Returns:** DataConnection instance

**Raises:** `ValueError` if connection type is not supported

**Example:**
```python
# Create Spark connection
spark_conn = ConnectionFactory.create("spark", spark_session=spark)

# Create DuckDB connection
duckdb_conn = ConnectionFactory.create("duckdb", db_path="analytics.db")
```

---

### Convenience Functions

#### `get_spark_connection(spark_session) -> SparkConnection`

Get a Spark connection (convenience wrapper).

**Parameters:**
- `spark_session` - PySpark SparkSession

**Returns:** SparkConnection instance

**Example:**
```python
from core.connection import get_spark_connection

conn = get_spark_connection(spark)
```

---

## Usage Patterns

### Basic Usage - Spark

```python
from pyspark.sql import SparkSession
from core.connection import SparkConnection

# Create Spark session
spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Create connection
conn = SparkConnection(spark)

# Read data
df = conn.read_table('/path/to/parquet')

# Apply filters
filters = {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}
filtered = conn.apply_filters(df, filters)

# Convert to pandas
pandas_df = conn.to_pandas(filtered)
```

### Basic Usage - DuckDB

```python
from core.duckdb_connection import DuckDBConnection

# Create connection
conn = DuckDBConnection(db_path='analytics.db')

# Read data (lazy - no data loaded yet!)
df = conn.read_table('/path/to/parquet')

# Apply filters (still lazy)
filters = {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}
filtered = conn.apply_filters(df, filters)

# Materialize to pandas
pandas_df = conn.to_pandas(filtered)
```

### Delta Lake Operations

```python
# Write Delta table
conn.write_delta_table(df, '/path/to/delta', mode='overwrite')

# Time travel
old_version = conn.read_table('/path/to/delta', format='delta', version=5)

# Merge data
conn.merge_delta_table(
    new_data,
    '/path/to/delta',
    merge_condition="target.ticker = source.ticker AND target.date = source.date"
)

# Optimize
conn.optimize_delta_table('/path/to/delta', zorder_by=['ticker', 'date'])

# Vacuum
conn.vacuum_delta_table('/path/to/delta', retention_hours=168)

# View history
history = conn.get_delta_table_history('/path/to/delta')
```

### Using ConnectionFactory

```python
from core.connection import ConnectionFactory

# Configuration-driven connection creation
config = {'connection_type': 'duckdb', 'db_path': 'analytics.db'}

conn = ConnectionFactory.create(
    connection_type=config['connection_type'],
    db_path=config.get('db_path', ':memory:')
)

# Now use conn - works regardless of backend
df = conn.read_table('/path/to/data')
```

---

## Backend Comparison

| Feature | SparkConnection | DuckDBConnection |
|---------|----------------|------------------|
| **Startup** | Slow (JVM initialization) | Fast (native) |
| **Data Loading** | Loads into memory | Lazy (queries files directly) |
| **Best For** | Large distributed datasets | Single-node analytics |
| **Memory** | High overhead | Low overhead |
| **Parquet** | ✅ Full support | ✅ Full support |
| **Delta Lake** | ✅ Full support | ✅ Full support |
| **Time Travel** | ✅ Via version/timestamp | ✅ Via delta-rs |
| **Merge** | ✅ Native API | ✅ Via delta-rs |
| **SQL** | ✅ Spark SQL | ✅ DuckDB SQL |
| **Pandas** | ✅ `.toPandas()` | ✅ `.df()` |

---

## Best Practices

1. **Use DuckDB for analytics**: 10-100x faster startup for interactive queries
2. **Use Spark for ETL**: Better for large-scale distributed data processing
3. **Enable Delta Lake**: Provides ACID, time travel, and better reliability
4. **Use Z-ordering**: Significantly improves query performance on Delta tables
5. **Vacuum periodically**: But be careful with retention period
6. **Apply filters early**: Both backends optimize filter pushdown
7. **Cache judiciously**: Use for frequently accessed datasets
8. **Clean up connections**: Always call `stop()` when done

---

## Related Documentation

- [UniversalSession](universal-session.md) - Uses connections for data access
- [BaseModel](base-model.md) - Models use connections for reading/writing
- [Configuration System](../06-configuration/config-loader.md) - Connection configuration
