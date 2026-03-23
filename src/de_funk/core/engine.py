"""
Engine — long-lived backend-agnostic data operations.

Wraps the existing QueryEngine (DuckDB) and DataConnection (Spark)
behind a unified interface. Handlers and sessions use Engine instead
of importing duckdb or pyspark directly.

Phase 2 implementation: wraps existing QueryEngine internally.
Future: replace QueryEngine internals with DataOps/SqlOps strategy.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class Engine:
    """Backend-agnostic data engine.

    Provides read/write/join/filter/aggregate operations that work
    with both DuckDB and Spark. Created by DeFunk.from_config().

    Current implementation wraps QueryEngine for DuckDB path.
    """

    def __init__(self, backend: str, conn=None, storage_config=None, **kwargs):
        self.backend = backend
        self._conn = conn
        self._storage_config = storage_config or {}
        self._query_engine = None  # Lazy — created when needed
        self._kwargs = kwargs

    @staticmethod
    def for_duckdb(storage_config: dict, **kwargs) -> Engine:
        """Create a DuckDB-backed engine."""
        engine = Engine(backend="duckdb", storage_config=storage_config, **kwargs)
        return engine

    @staticmethod
    def for_spark(spark_session, storage_config: dict, **kwargs) -> Engine:
        """Create a Spark-backed engine."""
        engine = Engine(backend="spark", conn=spark_session, storage_config=storage_config, **kwargs)
        return engine

    def _get_query_engine(self):
        """Lazy-create QueryEngine for DuckDB operations."""
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
            logger.info(f"Engine: DuckDB QueryEngine created (memory={memory_limit})")
        return self._query_engine

    # ── DataFrame operations ─────────────────────────────

    def read(self, path: str) -> Any:
        """Read a table from storage."""
        qe = self._get_query_engine()
        if qe:
            return qe._conn.execute(f"SELECT * FROM '{path}'").fetchdf()
        raise NotImplementedError(f"read() not implemented for backend={self.backend}")

    def write(self, df, path: str, format: str = "delta", mode: str = "overwrite") -> Any:
        """Write a DataFrame to storage."""
        raise NotImplementedError("write() — use ModelWriter for now")

    def execute_sql(self, sql: str) -> Any:
        """Execute raw SQL."""
        qe = self._get_query_engine()
        if qe:
            return qe._execute(sql)
        raise NotImplementedError(f"execute_sql() not implemented for backend={self.backend}")

    def count(self, df) -> int:
        """Count rows in a DataFrame."""
        if hasattr(df, '__len__'):
            return len(df)
        if hasattr(df, 'count'):
            return df.count()
        return 0

    def to_pandas(self, df):
        """Convert to pandas DataFrame."""
        if hasattr(df, 'toPandas'):
            return df.toPandas()
        return df

    def columns(self, df) -> list[str]:
        """Get column names."""
        if hasattr(df, 'columns'):
            return list(df.columns)
        return []

    # ── Query handler support ────────────────────────────

    def get_query_engine(self):
        """Get the underlying QueryEngine for handler compatibility.

        This is the bridge between old handler code and the new Engine.
        Handlers can call engine.get_query_engine() to get the QueryEngine
        they previously inherited via mixin.

        Will be removed when handlers are fully migrated.
        """
        return self._get_query_engine()

    def get_handler_registry(self, resolver=None, bronze_resolver=None):
        """Create a HandlerRegistry using this Engine's QueryEngine.

        This replaces the old build_registry() function in handlers/__init__.py
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
