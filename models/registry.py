"""
Model Registry for discovering and managing data models.

Provides central registry of available models with their schemas, storage, and measures.
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import yaml


@dataclass
class TableConfig:
    """Configuration for a table (dimension or fact)."""
    name: str
    path: str
    description: str
    columns: Dict[str, str]
    primary_key: Optional[List[str]] = None
    partitions: Optional[List[str]] = None
    tags: Optional[List[str]] = None


@dataclass
class MeasureConfig:
    """Configuration for a measure."""
    name: str
    description: str
    source: str  # e.g., "fact_prices.close"
    data_type: str
    aggregation: Optional[str] = None  # avg, sum, min, max, count, etc. (for simple measures)
    type: Optional[str] = None  # simple, weighted_aggregate, etc.
    weighting_method: Optional[str] = None  # For weighted_aggregate type
    group_by: Optional[List[str]] = None  # For weighted_aggregate type
    format: Optional[str] = None
    tags: Optional[List[str]] = None


class ModelConfig:
    """
    Configuration for a data model.

    Contains:
    - Storage configuration (where data lives)
    - Schema definitions (dimensions, facts, columns)
    - Available measures (pre-defined aggregations)
    - Graph structure (for visualization, future graph DB)
    """

    def __init__(self, config_dict: Dict):
        """
        Initialize model config from dictionary.

        Args:
            config_dict: Parsed YAML configuration
        """
        self.name = config_dict['model']
        self.version = config_dict.get('version', 1)
        self.tags = config_dict.get('tags', [])

        # Storage configuration
        self.storage = config_dict.get('storage', {})

        # Schema
        self._dimensions = {}
        self._facts = {}
        self._load_schema(config_dict.get('schema', {}))

        # Measures
        self._measures = {}
        self._load_measures(config_dict.get('measures', {}))

        # Graph structure (for visualization)
        self.graph = config_dict.get('graph', {})

    def _load_schema(self, schema: Dict):
        """Load schema definitions."""
        # Load dimensions
        for dim_name, dim_config in schema.get('dimensions', {}).items():
            self._dimensions[dim_name] = TableConfig(
                name=dim_name,
                path=dim_config['path'],
                description=dim_config.get('description', ''),
                columns=dim_config.get('columns', {}),
                primary_key=dim_config.get('primary_key'),
                tags=dim_config.get('tags', [])
            )

        # Load facts
        for fact_name, fact_config in schema.get('facts', {}).items():
            self._facts[fact_name] = TableConfig(
                name=fact_name,
                path=fact_config['path'],
                description=fact_config.get('description', ''),
                columns=fact_config.get('columns', {}),
                partitions=fact_config.get('partitions'),
                tags=fact_config.get('tags', [])
            )

    def _load_measures(self, measures: Dict):
        """Load measure definitions."""
        for measure_name, measure_config in measures.items():
            self._measures[measure_name] = MeasureConfig(
                name=measure_name,
                description=measure_config.get('description', ''),
                source=measure_config['source'],
                data_type=measure_config.get('data_type', 'double'),
                aggregation=measure_config.get('aggregation'),  # Optional for weighted aggregates
                type=measure_config.get('type'),  # Type of measure
                weighting_method=measure_config.get('weighting_method'),  # For weighted aggregates
                group_by=measure_config.get('group_by'),  # For weighted aggregates
                format=measure_config.get('format'),
                tags=measure_config.get('tags', [])
            )

    @property
    def storage_root(self) -> str:
        """Get storage root path."""
        return self.storage.get('root', '')

    @property
    def storage_format(self) -> str:
        """Get storage format (parquet, delta, etc.)."""
        return self.storage.get('format', 'parquet')

    def list_tables(self) -> List[str]:
        """List all table names (dimensions + facts)."""
        return list(self._dimensions.keys()) + list(self._facts.keys())

    def list_dimensions(self) -> List[str]:
        """List dimension table names."""
        return list(self._dimensions.keys())

    def list_facts(self) -> List[str]:
        """List fact table names."""
        return list(self._facts.keys())

    def get_table(self, table_name: str) -> TableConfig:
        """
        Get table configuration.

        Args:
            table_name: Name of table

        Returns:
            TableConfig

        Raises:
            ValueError: If table not found
        """
        if table_name in self._dimensions:
            return self._dimensions[table_name]
        if table_name in self._facts:
            return self._facts[table_name]

        raise ValueError(
            f"Table '{table_name}' not found in model '{self.name}'. "
            f"Available tables: {self.list_tables()}"
        )

    def has_table(self, table_name: str) -> bool:
        """Check if table exists."""
        return table_name in self._dimensions or table_name in self._facts

    def get_table_path(self, table_name: str) -> str:
        """Get full path to table data."""
        table = self.get_table(table_name)
        return f"{self.storage_root}/{table.path}"

    def get_table_columns(self, table_name: str) -> Dict[str, str]:
        """Get columns for a table."""
        table = self.get_table(table_name)
        return table.columns

    def list_measures(self) -> List[str]:
        """List available measure names."""
        return list(self._measures.keys())

    def get_measure(self, measure_name: str) -> MeasureConfig:
        """
        Get measure configuration.

        Args:
            measure_name: Name of measure

        Returns:
            MeasureConfig

        Raises:
            ValueError: If measure not found
        """
        if measure_name not in self._measures:
            raise ValueError(
                f"Measure '{measure_name}' not found in model '{self.name}'. "
                f"Available measures: {self.list_measures()}"
            )
        return self._measures[measure_name]

    def has_measure(self, measure_name: str) -> bool:
        """Check if measure exists."""
        return measure_name in self._measures

    def get_edges(self) -> List[Dict]:
        """Get graph edges (for visualization)."""
        return self.graph.get('edges', [])

    def get_nodes(self) -> List[Dict]:
        """Get graph nodes (for visualization)."""
        return self.graph.get('nodes', [])


class ModelRegistry:
    """
    Registry of available data models.

    Discovers models from configs/models/ directory.
    Provides model metadata, validation, and querying.
    """

    def __init__(self, models_dir: Path):
        """
        Initialize model registry.

        Args:
            models_dir: Directory containing model YAML files
        """
        self.models_dir = Path(models_dir)
        self.models: Dict[str, ModelConfig] = {}
        self._load_models()

    def _load_models(self):
        """Discover and load all model configurations."""
        if not self.models_dir.exists():
            raise ValueError(f"Models directory not found: {self.models_dir}")

        for yaml_file in self.models_dir.glob("*.yaml"):
            try:
                config_dict = yaml.safe_load(yaml_file.read_text())
                model = ModelConfig(config_dict)
                self.models[model.name] = model
            except Exception as e:
                print(f"Warning: Failed to load model from {yaml_file}: {e}")

    def list_models(self) -> List[str]:
        """List all available model names."""
        return list(self.models.keys())

    def get_model(self, model_name: str) -> ModelConfig:
        """
        Get model configuration.

        Args:
            model_name: Name of model

        Returns:
            ModelConfig

        Raises:
            ValueError: If model not found
        """
        if model_name not in self.models:
            raise ValueError(
                f"Model '{model_name}' not found. "
                f"Available models: {self.list_models()}"
            )
        return self.models[model_name]

    def has_model(self, model_name: str) -> bool:
        """Check if model exists."""
        return model_name in self.models

    def list_tables(self, model_name: str) -> List[str]:
        """List all tables in a model."""
        model = self.get_model(model_name)
        return model.list_tables()

    def list_measures(self, model_name: str) -> List[str]:
        """List all measures in a model."""
        model = self.get_model(model_name)
        return model.list_measures()

    def get_table_schema(self, model_name: str, table_name: str) -> Dict[str, str]:
        """Get schema (columns) for a table."""
        model = self.get_model(model_name)
        return model.get_table_columns(table_name)

    def reload(self):
        """Reload all model configurations."""
        self.models.clear()
        self._load_models()
