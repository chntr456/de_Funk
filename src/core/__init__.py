"""
Core infrastructure for de_Funk.

Provides foundational abstractions for:
- Data connections (Spark, DuckDB, future: GraphDB)
- Model registry and configuration
- Validation
"""

from .connection import DataConnection, SparkConnection, ConnectionFactory, get_spark_connection
from .model_registry import ModelRegistry, ModelConfig, TableConfig, MeasureConfig
from .validation import NotebookValidator, ValidationError

# DuckDB connection (lazy import - only if duckdb is installed)
try:
    from .duckdb_connection import DuckDBConnection
    _duckdb_available = True
except ImportError:
    DuckDBConnection = None
    _duckdb_available = False

__all__ = [
    'DataConnection',
    'SparkConnection',
    'DuckDBConnection',
    'ConnectionFactory',
    'get_spark_connection',
    'ModelRegistry',
    'ModelConfig',
    'TableConfig',
    'MeasureConfig',
    'NotebookValidator',
    'ValidationError',
]
