"""
Unified configuration management for de_Funk.

This module provides a centralized, type-safe configuration system that:
- Loads all configuration from a single entry point
- Validates configuration values
- Supports clear precedence: env vars > explicit params > config files > defaults
- Eliminates hardcoded values scattered throughout the codebase
"""

from .loader import ConfigLoader
from .models import (
    AppConfig,
    ConnectionConfig,
    StorageConfig,
    APIConfig,
    SparkConfig,
    DuckDBConfig,
)

__all__ = [
    "ConfigLoader",
    "AppConfig",
    "ConnectionConfig",
    "StorageConfig",
    "APIConfig",
    "SparkConfig",
    "DuckDBConfig",
]
