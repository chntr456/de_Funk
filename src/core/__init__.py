"""
Core infrastructure for de_Funk.

Provides foundational abstractions for:
- Data connections (Spark, future: DuckDB, GraphDB)
- Model registry and configuration
- Validation
"""

from .connection import DataConnection, SparkConnection, ConnectionFactory, get_spark_connection
from .model_registry import ModelRegistry, ModelConfig, TableConfig, MeasureConfig
from .validation import NotebookValidator, ValidationError

__all__ = [
    'DataConnection',
    'SparkConnection',
    'ConnectionFactory',
    'get_spark_connection',
    'ModelRegistry',
    'ModelConfig',
    'TableConfig',
    'MeasureConfig',
    'NotebookValidator',
    'ValidationError',
]
