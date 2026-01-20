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
        self._measures = {}  # Initialize early - _load_tables may add measures

        # Load from v1.x/v2.x 'schema:' structure
        self._load_schema(config_dict.get('schema', {}))

        # Load from v3.0 'tables:' structure (markdown front matter)
        if 'tables' in config_dict:
            self._load_tables(config_dict.get('tables', {}))

        # Load top-level measures (v1.x/v2.x format)
        self._load_measures(config_dict.get('measures', {}))

        # Graph structure (for visualization)
        self.graph = config_dict.get('graph', {})

    def _load_schema(self, schema: Dict):
        """Load schema definitions."""
        # Load dimensions from v1.x/v2.x structure
        for dim_name, dim_config in schema.get('dimensions', {}).items():
            # Skip base templates (names starting with _)
            if dim_name.startswith('_'):
                continue

            # Auto-generate path if not provided (v2.0 compatibility)
            path = dim_config.get('path', f'dims/{dim_name}')

            self._dimensions[dim_name] = TableConfig(
                name=dim_name,
                path=path,
                description=dim_config.get('description', ''),
                columns=dim_config.get('columns', {}),
                primary_key=dim_config.get('primary_key'),
                tags=dim_config.get('tags', [])
            )

        # Load facts from v1.x/v2.x structure
        for fact_name, fact_config in schema.get('facts', {}).items():
            # Skip base templates (names starting with _)
            if fact_name.startswith('_'):
                continue

            # Auto-generate path if not provided (v2.0 compatibility)
            path = fact_config.get('path', f'facts/{fact_name}')

            self._facts[fact_name] = TableConfig(
                name=fact_name,
                path=path,
                description=fact_config.get('description', ''),
                columns=fact_config.get('columns', {}),
                partitions=fact_config.get('partitions'),
                tags=fact_config.get('tags', [])
            )

    def _load_tables(self, tables: Dict):
        """
        Load table definitions from v3.0 'tables:' structure.

        v3.0 uses:
            tables:
              dim_company:
                type: dimension
                ...
              fact_income_statement:
                type: fact
                ...
        """
        for table_name, table_config in tables.items():
            # Skip base templates (names starting with _)
            if table_name.startswith('_'):
                continue

            # Determine table type
            table_type = table_config.get('type', '')

            # Auto-generate path if not provided
            if table_type == 'dimension':
                path = table_config.get('path', f'dims/{table_name}')
                self._dimensions[table_name] = TableConfig(
                    name=table_name,
                    path=path,
                    description=table_config.get('description', ''),
                    columns=self._extract_columns(table_config.get('schema', [])),
                    primary_key=table_config.get('primary_key'),
                    tags=table_config.get('tags', [])
                )
            elif table_type == 'fact':
                path = table_config.get('path', f'facts/{table_name}')
                self._facts[table_name] = TableConfig(
                    name=table_name,
                    path=path,
                    description=table_config.get('description', ''),
                    columns=self._extract_columns(table_config.get('schema', [])),
                    partitions=table_config.get('partition_by'),
                    tags=table_config.get('tags', [])
                )

            # Load measures defined on the table (v3.0 format)
            self._load_table_measures(table_name, table_config.get('measures', []))

    def _load_table_measures(self, table_name: str, measures_list: list):
        """
        Load measures from v3.0 table-level measures list.

        v3.0 measure format: [name, aggregation_type, source_column, description, {options}]
        Example: [company_count, count_distinct, company_id, "Number of companies", {format: "#,##0"}]
        """
        if not isinstance(measures_list, list):
            return

        for measure_def in measures_list:
            if not isinstance(measure_def, list) or len(measure_def) < 3:
                continue

            measure_name = measure_def[0]
            aggregation = measure_def[1]
            source_column = measure_def[2]
            description = measure_def[3] if len(measure_def) > 3 else ''
            options = measure_def[4] if len(measure_def) > 4 else {}

            # Build source reference: table_name.column
            source = f"{table_name}.{source_column}"

            # Handle expression-type measures
            if aggregation == 'expression':
                # source_column is actually the expression
                source = source_column
                aggregation = None

            self._measures[measure_name] = MeasureConfig(
                name=measure_name,
                description=description,
                source=source,
                data_type='double',
                aggregation=aggregation,
                type='simple' if aggregation else 'expression',
                format=options.get('format') if isinstance(options, dict) else None,
                tags=[]
            )

    def _extract_columns(self, schema_list: list) -> Dict[str, str]:
        """
        Extract columns from v3.0 schema list format.

        v3.0 schema format: [[column_name, type, nullable, description, options], ...]
        """
        columns = {}
        if isinstance(schema_list, list):
            for item in schema_list:
                if isinstance(item, list) and len(item) >= 2:
                    col_name = item[0]
                    col_type = item[1]
                    columns[col_name] = col_type
        return columns

    def _load_measures(self, measures: Dict):
        """
        Load measure definitions.

        Supports both v1.x flat structure and v2.0 nested structure:
        - v1.x: measures = {measure_name: {source, aggregation, ...}}
        - v2.0: measures = {simple_measures: {...}, computed_measures: {...}, python_measures: {...}}
        """
        # Check if this is v2.0 nested structure
        if 'simple_measures' in measures or 'computed_measures' in measures or 'python_measures' in measures:
            # v2.0 nested structure - flatten all measure types
            all_measures = {}

            # Merge simple, computed, and python measures
            for measure_type in ['simple_measures', 'computed_measures', 'python_measures']:
                if measure_type in measures and isinstance(measures[measure_type], dict):
                    all_measures.update(measures[measure_type])

            # Load flattened measures
            for measure_name, measure_config in all_measures.items():
                self._measures[measure_name] = MeasureConfig(
                    name=measure_name,
                    description=measure_config.get('description', ''),
                    source=measure_config.get('source', ''),  # Python measures may not have source
                    data_type=measure_config.get('data_type', 'double'),
                    aggregation=measure_config.get('aggregation'),
                    type=measure_config.get('type'),
                    weighting_method=measure_config.get('weighting_method'),
                    group_by=measure_config.get('group_by'),
                    format=measure_config.get('format'),
                    tags=measure_config.get('tags', [])
                )
        else:
            # v1.x flat structure - load directly
            for measure_name, measure_config in measures.items():
                # Skip internal keys
                if measure_name.startswith('_'):
                    continue

                self._measures[measure_name] = MeasureConfig(
                    name=measure_name,
                    description=measure_config.get('description', ''),
                    source=measure_config.get('source', ''),
                    data_type=measure_config.get('data_type', 'double'),
                    aggregation=measure_config.get('aggregation'),
                    type=measure_config.get('type'),
                    weighting_method=measure_config.get('weighting_method'),
                    group_by=measure_config.get('group_by'),
                    format=measure_config.get('format'),
                    tags=measure_config.get('tags', [])
                )

    @property
    def storage_root(self) -> str:
        """Get storage root path.

        Supports both flat and nested storage config:
        - Flat (v1.x): storage.root = 'storage/silver/stocks'
        - Nested (v3.0): storage.silver.root = 'storage/silver/stocks'
        """
        # Try nested format first (v3.0): storage.silver.root
        silver_config = self.storage.get('silver', {})
        if isinstance(silver_config, dict) and 'root' in silver_config:
            return silver_config.get('root', '')
        # Fall back to flat format (v1.x): storage.root
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

    Discovers models from domains/ directory (markdown with YAML front matter).
    Provides model metadata, validation, and querying.
    Also maintains a registry of model classes for dynamic instantiation.
    """

    def __init__(self, models_dir: Path):
        """
        Initialize model registry.

        Args:
            models_dir: Directory containing model definitions (domains/ directory)
        """
        self.models_dir = Path(models_dir)
        self.models: Dict[str, ModelConfig] = {}
        self._model_classes: Dict[str, type] = {}
        self._domain_loader = None  # Cached loader for performance
        self._load_models()
        self._register_default_model_classes()

    def _load_models(self):
        """Discover and load all model configurations from domains/ directory."""
        if not self.models_dir.exists():
            raise ValueError(f"Models directory not found: {self.models_dir}")

        # Use domain_loader for markdown-based configs
        try:
            from config.domain_loader import ModelConfigLoader
            # Cache the loader for reuse in get_model_config()
            self._domain_loader = ModelConfigLoader(self.models_dir)

            # Load all discovered domain models
            for model_name in self._domain_loader.list_models():
                try:
                    config_dict = self._domain_loader.load_model_config(model_name)
                    model = ModelConfig(config_dict)
                    self.models[model.name] = model
                except Exception as e:
                    print(f"Warning: Failed to load model '{model_name}': {e}")

        except ImportError as e:
            print(f"Warning: Could not import domain_loader: {e}")

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

    def resolve_cross_model(self, cross_model_ref: str) -> str:
        """
        Resolve a cross_model reference to an actual model name.

        This uses domain configuration to map category/base names to concrete models:
        - 'temporal' -> 'temporal' (foundation model)
        - 'foundation' -> 'temporal' (alias)
        - 'corporate' -> 'company' (domain folder -> model name)
        - 'securities' -> 'stocks' (base template -> concrete model)
        - 'geospatial' -> 'geospatial' (foundation model)

        Args:
            cross_model_ref: Reference from graph edge cross_model value

        Returns:
            Actual model name that exists in registry
        """
        # Direct model match
        if cross_model_ref in self.models:
            return cross_model_ref

        # Build dynamic mapping from model configs
        # Check if any model extends a base matching this ref
        for model_name, model_config in self.models.items():
            # Check if model extends this base
            if hasattr(model_config, '_raw_config'):
                extends = model_config._raw_config.get('extends', '')
            else:
                # Try to get from domain loader
                try:
                    raw_config = self._domain_loader.load_model_config(model_name)
                    extends = raw_config.get('extends', '')
                except Exception:
                    extends = ''

            # Match on extends path like '_base.finance.securities'
            if extends:
                # Extract the base category name
                # '_base.finance.securities' -> 'securities'
                # '_base.geospatial.geospatial' -> 'geospatial'
                parts = extends.split('.')
                if parts:
                    base_category = parts[-1]
                    if base_category == cross_model_ref:
                        return model_name

        # Known aliases (foundation aliases)
        aliases = {
            'foundation': 'temporal',
            'foundation_temporal': 'temporal',
        }
        if cross_model_ref in aliases:
            alias_target = aliases[cross_model_ref]
            if alias_target in self.models:
                return alias_target

        # Domain folder to model name mappings (when folder != model name)
        domain_mappings = {
            'corporate': 'company',  # domains/corporate/ -> company model
        }
        if cross_model_ref in domain_mappings:
            mapped = domain_mappings[cross_model_ref]
            if mapped in self.models:
                return mapped

        # If nothing matched, return as-is (will fail later with helpful error)
        return cross_model_ref

    # ============================================================
    # MODEL CLASS REGISTRY (for dynamic instantiation)
    # ============================================================

    def _register_default_model_classes(self):
        """
        Register default model classes.

        This allows the registry to dynamically instantiate models.
        Models are lazy-imported to avoid circular dependencies.
        """
        # Try to register known models
        # Imports are delayed and failures are silently ignored

        # Foundation models
        try:
            from models.domains.foundation.temporal.model import TemporalModel
            self.register_model_class('temporal', TemporalModel)
        except Exception:
            pass  # Will use auto-registration on first access

        # Domain models (v2.6 architecture - organized by domain)
        # Corporate domain
        try:
            from models.domains.corporate.company import CompanyModel
            self.register_model_class('company', CompanyModel)
        except Exception:
            pass  # Will use auto-registration on first access

        # Securities domain
        try:
            from models.domains.securities.stocks import StocksModel
            self.register_model_class('stocks', StocksModel)
        except Exception:
            pass  # Will use auto-registration on first access

        # Municipal domain
        try:
            from models.domains.municipal.city_finance import CityFinanceModel
            self.register_model_class('city_finance', CityFinanceModel)
        except Exception:
            pass  # Will use auto-registration on first access

    def register_model_class(self, model_name: str, model_class: type):
        """
        Register a model class for dynamic instantiation.

        Args:
            model_name: Name of the model (matches YAML config name)
            model_class: Python class (must inherit from BaseModel)
        """
        self._model_classes[model_name] = model_class

    def get_model_class(self, model_name: str) -> type:
        """
        Get the Python class for a model.

        Args:
            model_name: Name of the model

        Returns:
            Model class

        Raises:
            ValueError: If model class not registered
        """
        # Lazy registration - try to import if not already registered
        if model_name not in self._model_classes:
            self._try_auto_register(model_name)

        if model_name not in self._model_classes:
            raise ValueError(
                f"Model class for '{model_name}' not registered. "
                f"Available: {list(self._model_classes.keys())}"
            )

        return self._model_classes[model_name]

    def _try_auto_register(self, model_name: str):
        """
        Try to auto-register a model class by convention.

        Convention (tries in order):
        1. Foundation package: models.foundation.{model_name}
        2. Domain package: models.domain.{model_name}
        3. Foundation module: models.foundation.{model_name}.model
        4. Domain module: models.domain.{model_name}.model

        Args:
            model_name: Name of the model
        """
        import importlib

        # Convert model name to class name (e.g., 'stocks' -> 'StocksModel')
        class_name = ''.join(word.capitalize() for word in model_name.split('_')) + 'Model'

        # Try paths in order of preference
        paths_to_try = [
            f"models.foundation.{model_name}",
            f"models.domain.{model_name}",
            f"models.foundation.{model_name}.model",
            f"models.domain.{model_name}.model",
        ]

        for path in paths_to_try:
            try:
                module = importlib.import_module(path)
                if hasattr(module, class_name):
                    model_class = getattr(module, class_name)
                    self.register_model_class(model_name, model_class)
                    return
            except (ImportError, AttributeError):
                continue

        # Auto-registration failed - model needs manual registration

    def get_model_config(self, model_name: str) -> Dict:
        """
        Get raw model configuration dictionary (for model instantiation).

        Uses cached domain_loader for performance - avoids re-parsing
        markdown files on every call.

        Args:
            model_name: Name of the model

        Returns:
            Dictionary with model configuration
        """
        # Verify model exists in registry
        self.get_model(model_name)

        # Use cached loader (has internal cache for parsed configs)
        if self._domain_loader is not None:
            return self._domain_loader.load_model_config(model_name)

        # Fallback: create loader if not cached (shouldn't happen normally)
        from config.domain_loader import ModelConfigLoader
        self._domain_loader = ModelConfigLoader(self.models_dir)
        return self._domain_loader.load_model_config(model_name)
