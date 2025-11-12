"""
Backend abstraction layer for unified measure execution.

Provides backend-agnostic interface for executing measures across
DuckDB, Spark, and other data processing engines.
"""

from .adapter import BackendAdapter, QueryResult
from .duckdb_adapter import DuckDBAdapter
from .spark_adapter import SparkAdapter
from .sql_builder import SQLBuilder

__all__ = [
    'BackendAdapter',
    'QueryResult',
    'DuckDBAdapter',
    'SparkAdapter',
    'SQLBuilder',
]
