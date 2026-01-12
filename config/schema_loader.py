"""
SchemaLoader - Load Spark schemas from YAML configuration files.

DEPRECATED (v2.6): This module is superseded by markdown-driven schemas.
Facets should now use ENDPOINT_ID to load schemas from markdown endpoint files:

    class MyFacet(AlphaVantageFacet):
        ENDPOINT_ID = "income_statement"  # Loads from Documents/Data Sources/Endpoints/

The markdown approach provides:
- Field mappings (source -> output)
- Coercion rules (type conversion)
- Computed field expressions
- Transform specifications

This module is kept for backwards compatibility with any legacy code that
may still reference configs/schemas/*.yaml files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import yaml

from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, DoubleType,
    IntegerType, BooleanType, DateType, TimestampType
)

# Cache for loaded schemas
_schema_cache: Dict[str, Dict[str, StructType]] = {}


def _get_spark_type(type_str: str):
    """Convert string type name to Spark type."""
    type_map = {
        "string": StringType(),
        "long": LongType(),
        "double": DoubleType(),
        "int": IntegerType(),
        "integer": IntegerType(),
        "boolean": BooleanType(),
        "bool": BooleanType(),
        "date": DateType(),
        "timestamp": TimestampType(),
    }
    return type_map.get(type_str.lower(), StringType())


def _build_schema(fields: list) -> StructType:
    """Build a StructType from a list of field definitions."""
    struct_fields = []
    for field in fields:
        name = field.get("name")
        type_str = field.get("type", "string")
        nullable = field.get("nullable", True)

        spark_type = _get_spark_type(type_str)
        struct_fields.append(StructField(name, spark_type, nullable))

    return StructType(struct_fields)


class SchemaLoader:
    """
    Load and cache Spark schemas from YAML configuration files.

    Schema files are located in configs/schemas/{provider}.yaml
    """

    _configs_dir: Optional[Path] = None

    @classmethod
    def _get_configs_dir(cls) -> Path:
        """Get the configs directory path."""
        if cls._configs_dir is None:
            # Try to find configs dir relative to this file
            this_file = Path(__file__).resolve()
            # config/schema_loader.py -> project_root/configs
            project_root = this_file.parent.parent
            cls._configs_dir = project_root / "configs" / "schemas"
        return cls._configs_dir

    @classmethod
    def set_configs_dir(cls, path: Path):
        """Override the configs directory path."""
        cls._configs_dir = path
        _schema_cache.clear()

    @classmethod
    def load(cls, provider: str, schema_key: str) -> Optional[StructType]:
        """
        Load a schema by provider and key.

        Args:
            provider: Provider name (e.g., "alpha_vantage")
            schema_key: Schema key within the provider file (e.g., "overview")

        Returns:
            StructType schema, or None if not found
        """
        # Check cache first
        cache_key = f"{provider}.{schema_key}"
        if provider in _schema_cache and schema_key in _schema_cache[provider]:
            return _schema_cache[provider][schema_key]

        # Load provider config file
        if provider not in _schema_cache:
            cls._load_provider(provider)

        return _schema_cache.get(provider, {}).get(schema_key)

    @classmethod
    def _load_provider(cls, provider: str):
        """Load all schemas for a provider from YAML file."""
        config_file = cls._get_configs_dir() / f"{provider}.yaml"

        if not config_file.exists():
            _schema_cache[provider] = {}
            return

        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        if config is None:
            _schema_cache[provider] = {}
            return

        # Build schemas for each key
        schemas = {}
        for key, fields in config.items():
            if isinstance(fields, list):
                schemas[key] = _build_schema(fields)

        _schema_cache[provider] = schemas

    @classmethod
    def get_all_keys(cls, provider: str) -> list:
        """Get all available schema keys for a provider."""
        if provider not in _schema_cache:
            cls._load_provider(provider)
        return list(_schema_cache.get(provider, {}).keys())

    @classmethod
    def clear_cache(cls):
        """Clear the schema cache."""
        _schema_cache.clear()
