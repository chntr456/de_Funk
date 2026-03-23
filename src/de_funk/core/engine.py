"""
Engine — long-lived backend-agnostic data operations.

Delegates all operations to DataOps (DataFrame ops) and SqlOps (SQL ops).
Created via Engine.for_duckdb() or Engine.for_spark().

Backward compatibility: get_query_engine() and get_handler_registry()
bridge to the existing handler code during migration.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class Engine:
    """Backend-agnostic data engine.

    Provides read/write/join/filter/aggregate operations that work
    with both DuckDB and Spark via DataOps/SqlOps strategy pattern.
    """

    def __init__(self, backend: str, ops=None, sql=None,
                 conn=None, storage_config=None, **kwargs):
        self.backend = backend
        self._ops = ops
        self._sql = sql
        self._conn = conn
        self._storage_config = storage_config or {}
        self._query_engine = None  # Lazy — backward compat bridge
        self._kwargs = kwargs

    @staticmethod
    def for_duckdb(storage_config: dict = None, memory_limit: str = "3GB",
                   max_sql_rows: int = 30000, max_dimension_values: int = 10000,
                   **kwargs) -> Engine:
        """Create a DuckDB-backed engine with DataOps + SqlOps."""
        import duckdb
        conn = duckdb.connect()
        conn.execute(f"SET memory_limit='{memory_limit}'")

        from de_funk.core.ops import DuckDBOps
        from de_funk.core.sql import DuckDBSql

        ops = DuckDBOps(conn=conn, memory_limit=memory_limit)
        sql = DuckDBSql(conn, max_sql_rows=max_sql_rows,
                        max_dimension_values=max_dimension_values)

        engine = Engine(backend="duckdb", ops=ops, sql=sql, conn=conn,
                        storage_config=storage_config or {}, **kwargs)
        logger.info(f"Engine: DuckDB ready (memory={memory_limit})")
        return engine

    @staticmethod
    def for_spark(spark_session, storage_config: dict = None, **kwargs) -> Engine:
        """Create a Spark-backed engine with DataOps + SqlOps."""
        from de_funk.core.ops import SparkOps
        from de_funk.core.sql import SparkSql

        ops = SparkOps(spark_session)
        sql = SparkSql(spark_session)

        engine = Engine(backend="spark", ops=ops, sql=sql, conn=spark_session,
                        storage_config=storage_config or {}, **kwargs)
        logger.info("Engine: Spark ready")
        return engine

    # ── DataFrame operations (delegate to DataOps) ────────

    def read(self, path: str, format: str = "delta") -> Any:
        return self._ops.read(path, format)

    def write(self, df: Any, path: str, format: str = "delta",
              mode: str = "overwrite") -> None:
        self._ops.write(df, path, format, mode)

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        return self._ops.create_df(rows, schema)

    def select(self, df: Any, columns: list[str]) -> Any:
        return self._ops.select(df, columns)

    def drop(self, df: Any, columns: list[str]) -> Any:
        return self._ops.drop(df, columns)

    def derive(self, df: Any, col: str, expr: str) -> Any:
        return self._ops.derive(df, col, expr)

    def filter(self, df: Any, conditions: list[str]) -> Any:
        return self._ops.filter(df, conditions)

    def dedup(self, df: Any, subset: list[str]) -> Any:
        return self._ops.dedup(df, subset)

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        return self._ops.join(left, right, on, how)

    def union(self, dfs: list[Any]) -> Any:
        return self._ops.union(dfs)

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        return self._ops.unpivot(df, id_cols, value_cols, var_name, val_name)

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        return self._ops.window(df, partition, order, expr, alias)

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        return self._ops.pivot(df, rows, cols, measures)

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        return self._ops.aggregate(df, group_by, aggs)

    def count(self, df: Any) -> int:
        return self._ops.count(df)

    def to_pandas(self, df: Any) -> Any:
        return self._ops.to_pandas(df)

    def columns(self, df: Any) -> list[str]:
        return self._ops.columns(df)

    # ── SQL operations (delegate to SqlOps) ───────────────

    def execute_sql(self, sql_str: str, max_rows: int = 0) -> list:
        return self._sql.execute_sql(sql_str, max_rows)

    def scan(self, path: str) -> str:
        return self._sql.scan(path)

    def build_from(self, tables: dict[str, str], resolver=None,
                   allowed_domains: set[str] | None = None) -> str:
        return self._sql.build_from(tables, resolver, allowed_domains)

    def build_where(self, filters: list, resolver=None,
                    from_tables: set[str] | None = None) -> list[str]:
        return self._sql.build_where(filters, resolver, from_tables)

    def distinct_values(self, resolved, extra_filters=None,
                        resolver=None, max_values: int = 0) -> list:
        return self._sql.distinct_values(resolved, extra_filters, resolver, max_values)

    # ── Backward compatibility bridges ────────────────────
    # These will be removed after handler migration (Phase 7+10).

    def _get_query_engine(self):
        """Lazy-create QueryEngine for legacy handler compatibility."""
        if self._query_engine is None and self.backend == "duckdb":
            from de_funk.api.executor import QueryEngine

            roots = self._storage_config.get("roots", {}) if isinstance(self._storage_config, dict) else {}
            api_cfg = self._storage_config.get("api", {}) if isinstance(self._storage_config, dict) else {}

            storage_root = Path(roots.get("silver", "storage/silver"))
            memory_limit = api_cfg.get("duckdb_memory_limit", "3GB")
            max_sql_rows = api_cfg.get("max_sql_rows", 30000)
            max_dimension_values = api_cfg.get("max_dimension_values", 10000)
            max_response_mb = api_cfg.get("max_response_mb", 4.0)

            self._query_engine = QueryEngine(
                storage_root=storage_root,
                memory_limit=memory_limit,
                max_sql_rows=max_sql_rows,
                max_dimension_values=max_dimension_values,
                max_response_mb=max_response_mb,
            )
        return self._query_engine

    def get_query_engine(self):
        """Get the underlying QueryEngine for handler compatibility.

        Bridge for old handler code. Will be removed after Phase 7.
        """
        return self._get_query_engine()

    def get_handler_registry(self, resolver=None, bronze_resolver=None):
        """Create a HandlerRegistry using this Engine's QueryEngine.

        Bridge for old API setup. Will be removed after Phase 10.
        """
        from de_funk.api.handlers import HandlerRegistry, _HANDLER_CLASSES

        qe = self._get_query_engine()
        if qe is None:
            raise RuntimeError("Cannot create handler registry without DuckDB QueryEngine")

        registry = HandlerRegistry()
        registry.shared_engine = qe

        for cls in _HANDLER_CLASSES:
            handler = cls.__new__(cls)
            handler._conn = qe._conn
            handler._delta_available = qe._delta_available
            handler._scan_cache = qe._scan_cache
            handler._max_sql_rows = qe._max_sql_rows
            handler._max_dimension_values = qe._max_dimension_values
            handler.max_response_mb = qe.max_response_mb
            handler.storage_root = qe.storage_root
            registry.register(handler)

        return registry

    def __repr__(self):
        return f"Engine(backend={self.backend})"
