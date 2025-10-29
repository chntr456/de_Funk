"""
Core infrastructure for de_Funk.

Provides foundational abstractions for:
- Data connections (Spark, future: DuckDB, GraphDB)
- Model registry and configuration
"""

from .connection import DataConnection, SparkConnection, ConnectionFactory, get_spark_connection
from .model_registry import ModelRegistry, ModelConfig, TableConfig, MeasureConfig

__all__ = [
    'DataConnection',
    'SparkConnection',
    'ConnectionFactory',
    'get_spark_connection',
    'ModelRegistry',
    'ModelConfig',
    'TableConfig',
    'MeasureConfig',
]
