"""
Core infrastructure for de_Funk.

Provides foundational abstractions for:
- Data connections (Spark, DuckDB, future: GraphDB)
- Repository context
- Validation
"""

from .connection import DataConnection

# DuckDB connection (lazy import - only if duckdb is installed)
try:
    from .duckdb_connection import DuckDBConnection
    _duckdb_available = True
except ImportError:
    DuckDBConnection = None
    _duckdb_available = False

from .validation import NotebookValidator, ValidationError
from .context import RepoContext

__all__ = [
    'DataConnection',
    'DuckDBConnection',
    'NotebookValidator',
    'ValidationError',
    'RepoContext',
]
