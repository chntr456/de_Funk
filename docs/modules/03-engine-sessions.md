---
title: "Engine & Sessions"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/engine.py
  - src/de_funk/core/ops.py
  - src/de_funk/core/sql.py
  - src/de_funk/core/sessions.py
  - src/de_funk/core/session/filters.py
  - src/de_funk/core/storage.py
  - src/de_funk/core/connection.py
  - src/de_funk/core/duckdb_connection.py
---

# Engine & Sessions

> Backend-agnostic Engine (read/write/transform), scoped Sessions (Build/Query/Ingest), and connection wrappers.

## Purpose & Design Decisions

### What Problem This Solves

<!-- TODO: Explain the problem this group addresses. -->

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| <!-- TODO --> | | |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| <!-- TODO --> | | |

## Architecture

### Where This Fits

```
[Upstream] --> [THIS GROUP] --> [Downstream]
```

<!-- TODO: Brief explanation of data/control flow. -->

### Dependencies

| Depends On | What For |
|------------|----------|
| <!-- TODO --> | |

| Depended On By | What For |
|----------------|----------|
| <!-- TODO --> | |

## Key Classes

### Engine

**File**: `src/de_funk/core/engine.py:20`

**Purpose**: Backend-agnostic data engine.

| Method | Description |
|--------|-------------|
| `for_duckdb(memory_limit: str, max_sql_rows: int, max_dimension_values: int) -> Engine` | Create a DuckDB-backed engine with DataOps + SqlOps. |
| `for_spark(storage_config: dict) -> Engine` | Create a Spark-backed engine with DataOps + SqlOps. |
| `read(path: str, format: str) -> Any` | <!-- TODO --> |
| `write(df: Any, path: str, format: str, mode: str) -> None` | <!-- TODO --> |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | <!-- TODO --> |
| `select(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `drop(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `derive(df: Any, col: str, expr: str) -> Any` | <!-- TODO --> |
| `filter(df: Any, conditions: list[str]) -> Any` | <!-- TODO --> |
| `dedup(df: Any, subset: list[str]) -> Any` | <!-- TODO --> |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | <!-- TODO --> |
| `union(dfs: list[Any]) -> Any` | <!-- TODO --> |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | <!-- TODO --> |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | <!-- TODO --> |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | <!-- TODO --> |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | <!-- TODO --> |
| `count(df: Any) -> int` | <!-- TODO --> |
| `to_pandas(df: Any) -> Any` | <!-- TODO --> |
| `columns(df: Any) -> list[str]` | <!-- TODO --> |
| `execute_sql(sql_str: str, max_rows: int) -> list` | <!-- TODO --> |
| `scan(path: str) -> str` | <!-- TODO --> |
| `build_from(tables: dict[str, str], resolver, allowed_domains: set[str] | None) -> str` | <!-- TODO --> |
| `build_where(filters: list, resolver, from_tables: set[str] | None) -> list[str]` | <!-- TODO --> |
| `distinct_values(resolved, extra_filters, resolver, max_values: int) -> list` | <!-- TODO --> |
| `distinct_values_by_measure(resolved, order_by, order_dir, extra_filters, resolver) -> list` | Return distinct values ordered by aggregated measure. |
| `get_query_engine()` | Deprecated: handlers now use Engine directly. |
| `get_handler_registry(resolver, bronze_resolver, max_response_mb: float, storage_root)` | Create a HandlerRegistry using this Engine directly. |

### DataOps

**File**: `src/de_funk/core/ops.py:19`

**Purpose**: Abstract interface for backend-agnostic DataFrame operations.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | Read a table from storage. |
| `write(df: Any, path: str, format: str, mode: str) -> None` | Write a DataFrame to storage. |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | Create a DataFrame from rows and schema. |
| `select(df: Any, columns: list[str]) -> Any` | Select columns from a DataFrame. |
| `drop(df: Any, columns: list[str]) -> Any` | Drop columns from a DataFrame. |
| `derive(df: Any, col: str, expr: str) -> Any` | Add a computed column via SQL expression. |
| `filter(df: Any, conditions: list[str]) -> Any` | Filter rows by SQL conditions. |
| `dedup(df: Any, subset: list[str]) -> Any` | Deduplicate rows by column subset. |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | Join two DataFrames. |
| `union(dfs: list[Any]) -> Any` | Vertically stack multiple DataFrames. |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | Melt wide columns into long format. |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | Add a window function column. |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | Pivot rows to columns with aggregation. |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | Group and aggregate. |
| `count(df: Any) -> int` | Count rows. |
| `to_pandas(df: Any) -> Any` | Convert to pandas DataFrame. |
| `columns(df: Any) -> list[str]` | Get column names. |

### DuckDBOps (DataOps)

**File**: `src/de_funk/core/ops.py:111`

**Purpose**: DuckDB implementation of DataOps using in-process SQL.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | <!-- TODO --> |
| `write(df: Any, path: str, format: str, mode: str) -> None` | <!-- TODO --> |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | <!-- TODO --> |
| `select(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `drop(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `derive(df: Any, col: str, expr: str) -> Any` | <!-- TODO --> |
| `filter(df: Any, conditions: list[str]) -> Any` | <!-- TODO --> |
| `dedup(df: Any, subset: list[str]) -> Any` | <!-- TODO --> |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | <!-- TODO --> |
| `union(dfs: list[Any]) -> Any` | <!-- TODO --> |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | <!-- TODO --> |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | <!-- TODO --> |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | <!-- TODO --> |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | <!-- TODO --> |
| `count(df: Any) -> int` | <!-- TODO --> |
| `to_pandas(df: Any) -> Any` | <!-- TODO --> |
| `columns(df: Any) -> list[str]` | <!-- TODO --> |

### SparkOps (DataOps)

**File**: `src/de_funk/core/ops.py:247`

**Purpose**: Spark implementation of DataOps.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | <!-- TODO --> |
| `write(df: Any, path: str, format: str, mode: str) -> None` | <!-- TODO --> |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | <!-- TODO --> |
| `select(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `drop(df: Any, columns: list[str]) -> Any` | <!-- TODO --> |
| `derive(df: Any, col: str, expr: str) -> Any` | <!-- TODO --> |
| `filter(df: Any, conditions: list[str]) -> Any` | <!-- TODO --> |
| `dedup(df: Any, subset: list[str]) -> Any` | <!-- TODO --> |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | <!-- TODO --> |
| `union(dfs: list[Any]) -> Any` | <!-- TODO --> |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | <!-- TODO --> |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | <!-- TODO --> |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | <!-- TODO --> |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | <!-- TODO --> |
| `count(df: Any) -> int` | <!-- TODO --> |
| `to_pandas(df: Any) -> Any` | <!-- TODO --> |
| `columns(df: Any) -> list[str]` | <!-- TODO --> |

### SqlOps

**File**: `src/de_funk/core/sql.py:40`

**Purpose**: Abstract interface for SQL operations.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | Execute raw SQL and return rows. |
| `scan(path: str) -> str` | Return a backend-specific scan expression for a storage path. |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | Build a FROM clause with automatic join resolution. |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | Build WHERE clause fragments from filter specs. |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | Return sorted distinct values for a dimension field. |

### DuckDBSql (SqlOps)

**File**: `src/de_funk/core/sql.py:74`

**Purpose**: DuckDB implementation of SqlOps.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | <!-- TODO --> |
| `scan(path: str) -> str` | <!-- TODO --> |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | <!-- TODO --> |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | <!-- TODO --> |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | <!-- TODO --> |

### SparkSql (SqlOps)

**File**: `src/de_funk/core/sql.py:234`

**Purpose**: Spark implementation of SqlOps.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | <!-- TODO --> |
| `scan(path: str) -> str` | <!-- TODO --> |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | <!-- TODO --> |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | <!-- TODO --> |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | <!-- TODO --> |

### Session

**File**: `src/de_funk/core/sessions.py:22`

**Purpose**: Abstract base for all sessions.

| Method | Description |
|--------|-------------|
| `raw_path(provider: str, endpoint: str) -> str` | Resolve raw storage path. |
| `bronze_path(provider: str, endpoint: str) -> str` | Resolve bronze storage path. |
| `silver_path(domain: str, table: str) -> str` | Resolve silver storage path. |
| `model_path(model_name: str, version: str) -> str` | Resolve ML model artifact path. |
| `close()` | Clean up session resources. |

### BuildSession (Session)

**File**: `src/de_funk/core/sessions.py:54`

**Purpose**: Session for building Silver tables from Bronze + Silver dependencies.

| Method | Description |
|--------|-------------|
| `get_model(model_name: str) -> dict` | Get a domain model config by name. |
| `get_dependencies(model_name: str) -> list[str]` | Get dependency list for a model. |
| `build(model_name: str) -> Any` | Build a single model — passes this session directly to the builder. |
| `build_all() -> list` | Build all models in dependency order. |
| `close()` | <!-- TODO --> |

### QuerySession (Session)

**File**: `src/de_funk/core/sessions.py:153`

**Purpose**: Session for querying Silver tables (read-only).

| Method | Description |
|--------|-------------|
| `resolve(ref_str: str)` | Resolve a domain.field reference to a ResolvedField. |
| `find_join_path(src: str, dst: str) -> list` | Find join path between two tables. |
| `distinct_values(resolved, extra_filters, resolver) -> list` | Return distinct values for a dimension field. |
| `build_from(tables: dict[str, str], allowed_domains: set[str] | None) -> str` | Build FROM clause with automatic join resolution. |
| `build_where(filters: list, from_tables: set[str] | None) -> list[str]` | Build WHERE clause fragments from filter specs. |
| `close()` | <!-- TODO --> |

### IngestSession (Session)

**File**: `src/de_funk/core/sessions.py:194`

**Purpose**: Session for ingesting data from external APIs.

| Method | Description |
|--------|-------------|
| `get_provider(provider_id: str) -> dict` | Get provider config by ID. |
| `get_endpoint(provider_id: str, endpoint_id: str) -> dict` | Get endpoint config by provider + endpoint ID. |
| `close()` | <!-- TODO --> |

### FilterEngine

**File**: `src/de_funk/core/session/filters.py:24`

**Purpose**: Centralized filter application for all backends.

| Method | Description |
|--------|-------------|
| `apply_filters(filters: Dict[str, Any], backend: str) -> Any` | Apply filters based on backend type. |
| `apply_from_session(filters: Dict[str, Any], session) -> Any` | Apply filters using session's backend detection. |
| `build_filter_sql() -> str` | Build SQL WHERE clause from filter specifications. |

### StorageRouter

**File**: `src/de_funk/core/storage.py:22`

**Purpose**: Resolves storage paths from config.

| Method | Description |
|--------|-------------|
| `raw_path(provider: str, endpoint: str) -> str` | Resolve raw storage path: raw_root/provider/endpoint. |
| `bronze_path(provider: str, endpoint: str) -> str` | Resolve bronze storage path: bronze_root/provider/endpoint. |
| `silver_path(domain: str, table: str) -> str` | Resolve silver storage path with domain_roots overrides. |
| `model_path(model_name: str, version: str) -> str` | Resolve ML model artifact path. |
| `resolve(table_ref: str) -> str` | Resolve a config-style table reference to a path. |
| `silver_root() -> str` | <!-- TODO --> |
| `bronze_root() -> str` | <!-- TODO --> |
| `raw_root() -> str` | <!-- TODO --> |
| `models_root() -> str` | <!-- TODO --> |

### DataConnection

**File**: `src/de_funk/core/connection.py:20`

**Purpose**: Abstract base class for data connections.

| Method | Description |
|--------|-------------|
| `read_table(path: str, format: str) -> Any` | Read a table from storage. |
| `apply_filters(df: Any, filters: Dict[str, Any]) -> Any` | Apply filters to a dataframe. |
| `to_pandas(df: Any) -> pd.DataFrame` | Convert to Pandas DataFrame. |
| `count(df: Any) -> int` | Get row count. |
| `cache(df: Any) -> Any` | Cache dataframe in memory. |
| `uncache(df: Any)` | Remove from cache. |
| `stop()` | Close connection and cleanup resources. |

### SparkConnection (DataConnection)

**File**: `src/de_funk/core/connection.py:93`

**Purpose**: Spark-based data connection with Delta Lake support.

| Method | Description |
|--------|-------------|
| `read_table(path: str, format: str, version: Optional[int], timestamp: Optional[str])` | Read table using Spark with optional Delta Lake time travel. |
| `write_delta_table(df, path: str, mode: str, partition_by: Optional[List[str]])` | Write Spark DataFrame to Delta Lake table. |
| `merge_delta_table(source_df, target_path: str, merge_condition: str, update_set: Optional[Dict[str, str]], insert_values: Optional[Dict[str, str]])` | Merge (upsert) data into Delta table using Spark's Delta Lake API. |
| `optimize_delta_table(path: str, zorder_by: Optional[List[str]])` | Optimize Delta table (compact files, optionally z-order). |
| `vacuum_delta_table(path: str, retention_hours: int)` | Vacuum Delta table (remove old files). |
| `get_delta_table_history(path: str, limit: Optional[int]) -> pd.DataFrame` | Get version history of Delta table. |
| `apply_filters(df, filters: Dict[str, Any])` | Apply filters using Spark SQL. |
| `to_pandas(df) -> pd.DataFrame` | Convert Spark DataFrame to pandas. |
| `count(df) -> int` | Get row count. |
| `cache(df)` | Cache Spark DataFrame. |
| `uncache(df)` | Uncache Spark DataFrame. |
| `stop()` | Stop Spark session and cleanup. |

### ConnectionFactory

**File**: `src/de_funk/core/connection.py:468`

**Purpose**: Factory for creating data connections.

| Method | Description |
|--------|-------------|
| `create() -> DataConnection` | Create a data connection. |

### DuckDBConnection (DataConnection)

**File**: `src/de_funk/core/duckdb_connection.py:37`

**Purpose**: DuckDB connection for analytics queries with Delta Lake support.

| Method | Description |
|--------|-------------|
| `table(view_name: str) -> Any` | Get a table or view by name from the DuckDB catalog. |
| `has_view(view_name: str) -> bool` | Check if a view exists in the database. |
| `read_table(path: str, format: str, version: Optional[int], timestamp: Optional[str]) -> Any` | Read a table from storage (Parquet or Delta Lake). |
| `write_delta_table(df: pd.DataFrame, path: str, mode: str, partition_by: Optional[List[str]])` | Write DataFrame to Delta Lake table. |
| `get_delta_table_history(path: str) -> pd.DataFrame` | Get the version history of a Delta table. |
| `optimize_delta_table(path: str, zorder_by: Optional[List[str]])` | Optimize Delta table (compact small files, optionally z-order). |
| `vacuum_delta_table(path: str, retention_hours: int, enforce_retention: bool)` | Vacuum Delta table (remove old files no longer needed). |
| `read_parquet(path: str) -> Any` | Read parquet file(s) from path. |
| `createDataFrame(data: list, schema) -> Any` | Create a DuckDB relation from data and schema. |
| `apply_filters(df: Any, filters: Dict[str, Any]) -> Any` | Apply filters to a DuckDB relation. |
| `to_pandas(df: Any) -> pd.DataFrame` | Convert DuckDB relation to pandas DataFrame. |
| `count(df: Any) -> int` | Get row count from DuckDB relation. |
| `cache(df: Any, name: Optional[str]) -> Any` | Cache a DuckDB relation. |
| `uncache(df: Any)` | Remove cached table. |
| `stop()` | Close the DuckDB connection. |
| `execute_sql(query: str) -> Any` | Execute raw SQL query. |
| `execute(query: str) -> Any` | Execute raw SQL query (alias for execute_sql). |

## How to Use

### Common Operations

<!-- TODO: Runnable code examples with expected output -->

### Integration Examples

<!-- TODO: Show cross-group usage -->

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| <!-- TODO --> | | |

### Debug Checklist

- [ ] <!-- TODO -->

### Common Pitfalls

1. <!-- TODO -->

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/core/engine.py` | Engine — long-lived backend-agnostic data operations. | `Engine` |
| `src/de_funk/core/ops.py` | DataOps — backend-agnostic DataFrame operation interfaces. | `DataOps`, `DuckDBOps`, `SparkOps` |
| `src/de_funk/core/sql.py` | SqlOps — backend-agnostic SQL operation interfaces. | `SqlOps`, `DuckDBSql`, `SparkSql` |
| `src/de_funk/core/sessions.py` | Session abstractions — scoped contexts for each pipeline path. | `Session`, `BuildSession`, `QuerySession`, `IngestSession` |
| `src/de_funk/core/session/filters.py` | Centralized filter engine for applying filters across different backends. | `FilterEngine` |
| `src/de_funk/core/storage.py` | StorageRouter — resolves storage paths for all 4 data tiers. | `StorageRouter` |
| `src/de_funk/core/connection.py` | Connection layer abstraction for data access. | `DataConnection`, `SparkConnection`, `ConnectionFactory` |
| `src/de_funk/core/duckdb_connection.py` | DuckDB connection implementation with Delta Lake support. | `DuckDBConnection` |
