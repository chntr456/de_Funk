from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any
from pyspark.sql import DataFrame

from models.api.dal import StorageRouter, BronzeTable

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


# ============================================================
# UNIVERSAL SESSION (Model-Agnostic)
# ============================================================

class UniversalSession:
    """
    Model-agnostic session that works with any BaseModel.

    Key features:
    - Dynamic model loading from registry
    - Works with any model (company, forecast, etc.)
    - Cross-model queries and joins
    - Session injection for model dependencies

    Usage:
        session = UniversalSession(
            connection=spark,
            storage_cfg=storage_cfg,
            repo_root=Path.cwd(),
            models=['company', 'forecast']
        )

        # Get table from any model
        prices = session.get_table('company', 'fact_prices')
        forecasts = session.get_table('forecast', 'fact_forecasts')

        # Models can access each other via session injection
    """

    def __init__(
        self,
        connection,
        storage_cfg: Dict[str, Any],
        repo_root: Path,
        models: list[str] | None = None
    ):
        """
        Initialize universal session.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration
            repo_root: Repository root path
            models: List of model names to pre-load (optional)
        """
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.repo_root = repo_root

        # Model registry for dynamic loading
        from models.registry import ModelRegistry
        models_dir = repo_root / "configs" / "models"
        self.registry = ModelRegistry(models_dir)

        # Cache loaded models
        self._models: Dict[str, Any] = {}  # model_name -> BaseModel instance

        # Pre-load specified models
        if models:
            for model_name in models:
                self.load_model(model_name)

    @property
    def backend(self) -> str:
        """
        Detect backend type from connection.

        Returns:
            'spark' or 'duckdb'

        Raises:
            ValueError: If connection type is unknown
        """
        connection_type = str(type(self.connection))

        # Check for Spark
        if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
            return 'spark'

        # Check for DuckDB
        if 'duckdb' in connection_type.lower() or (
            hasattr(self.connection, '_conn') and 'duckdb' in str(type(self.connection._conn)).lower()
        ):
            return 'duckdb'

        # Unknown connection type
        raise ValueError(f"Unknown connection type: {connection_type}")

    def load_model(self, model_name: str):
        """
        Dynamically load a model by name.

        Steps:
        1. Get model config from registry (YAML)
        2. Get model class from registry (Python class)
        3. Instantiate model
        4. Inject session for cross-model access
        5. Cache instance

        Args:
            model_name: Name of model to load

        Returns:
            BaseModel instance
        """
        # Return cached if already loaded
        if model_name in self._models:
            return self._models[model_name]

        # Get config and class from registry
        model_config = self.registry.get_model_config(model_name)
        model_class = self.registry.get_model_class(model_name)

        # Instantiate model
        model = model_class(
            connection=self.connection,
            storage_cfg=self.storage_cfg,
            model_cfg=model_config,
            params={}
        )

        # Inject session for cross-model access
        if hasattr(model, 'set_session'):
            model.set_session(self)

        # Cache
        self._models[model_name] = model

        return model

    def get_table(self, model_name: str, table_name: str, use_cache: bool = True) -> DataFrame:
        """
        Get a table from any model.

        Args:
            model_name: Name of the model
            table_name: Name of the table
            use_cache: Whether to use cached data (ignored, kept for backwards compatibility)

        Returns:
            DataFrame

        Note:
            The use_cache parameter is kept for backwards compatibility with old
            SilverStorageService API but is not used. Model caching is handled
            automatically via the _models cache in UniversalSession.
        """
        model = self.load_model(model_name)
        return model.get_table(table_name)

    def get_filter_column_mappings(self, model_name: str, table_name: str) -> Dict[str, str]:
        """
        Get automatic filter column mappings based on model graph edges.

        Examines graph edges to find joins to dim_calendar and extracts
        column mappings. This allows filters like 'trade_date' to be
        automatically mapped to table-specific columns like 'metric_date'.

        Args:
            model_name: Name of the model
            table_name: Name of the table

        Returns:
            Dictionary mapping standard filter columns to table columns
            Example: {'trade_date': 'metric_date'}

        Example:
            If forecast model has this edge:
                from: fact_forecast_metrics
                to: core.dim_calendar
                on: [metric_date = trade_date]

            Then get_filter_column_mappings('forecast', 'fact_forecast_metrics')
            returns: {'trade_date': 'metric_date'}
        """
        mappings = {}

        # Get model config
        try:
            model_config = self.registry.get_model_config(model_name)
        except Exception as e:
            print(f"DEBUG: Failed to get model config for {model_name}: {e}")
            return mappings  # No model config, no mappings

        # DEBUG
        print(f"\nDEBUG get_filter_column_mappings: model_name={model_name}, table_name={table_name}")
        print(f"DEBUG: Has 'graph' in config: {'graph' in model_config}")
        if 'graph' in model_config:
            print(f"DEBUG: Has 'edges' in graph: {'edges' in model_config['graph']}")
            if 'edges' in model_config['graph']:
                print(f"DEBUG: Number of edges: {len(model_config['graph']['edges'])}")
                for i, e in enumerate(model_config['graph']['edges']):
                    print(f"DEBUG: Edge {i}: {e}")

        # Check if model has graph metadata
        if 'graph' not in model_config or 'edges' not in model_config['graph']:
            print(f"DEBUG: No graph or edges found")
            return mappings

        # Look for edges from this table to dim_calendar
        for edge in model_config['graph']['edges']:
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')

            print(f"DEBUG: Checking edge: from='{edge_from}', to='{edge_to}' (looking for table_name='{table_name}')")

            # Check if this edge is from our table to dim_calendar
            if edge_from == table_name and 'dim_calendar' in edge_to:
                print(f"DEBUG: FOUND MATCHING EDGE!")
                # Extract column mapping from 'on' condition
                # Note: YAML parser converts 'on:' to boolean True (reserved word)
                # So we need to check both 'on' and True keys
                on_conditions = edge.get('on', edge.get(True, []))
                print(f"DEBUG: on_conditions={on_conditions}, type={type(on_conditions)}")

                for condition in on_conditions:
                    print(f"DEBUG: Processing condition={condition}, type={type(condition)}")
                    if isinstance(condition, str):
                        # Format: "metric_date = trade_date"
                        parts = condition.split('=')
                        if len(parts) == 2:
                            table_col = parts[0].strip()
                            calendar_col = parts[1].strip()
                            # Map calendar column to table column
                            # e.g., trade_date → metric_date
                            mappings[calendar_col] = table_col
                            print(f"DEBUG: Added mapping: {calendar_col} -> {table_col}")

        print(f"DEBUG: Final mappings: {mappings}\n")
        return mappings

    def get_dimension_df(self, model_name: str, dim_id: str) -> DataFrame:
        """Get a dimension table from a model"""
        model = self.load_model(model_name)
        return model.get_dimension_df(dim_id)

    def get_fact_df(self, model_name: str, fact_id: str) -> DataFrame:
        """Get a fact table from a model"""
        model = self.load_model(model_name)
        return model.get_fact_df(fact_id)

    def list_models(self) -> list[str]:
        """List all available models"""
        return self.registry.list_models()

    def list_tables(self, model_name: str) -> Dict[str, list[str]]:
        """
        List all tables in a model.

        Returns:
            Dictionary with 'dimensions' and 'facts' keys
        """
        model = self.load_model(model_name)
        return model.list_tables()

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """Get metadata for a model"""
        model = self.load_model(model_name)
        return model.get_metadata()

    def get_model_instance(self, model_name: str):
        """
        Get the model instance directly.

        Useful for accessing model-specific methods.

        Args:
            model_name: Name of the model

        Returns:
            BaseModel instance
        """
        return self.load_model(model_name)
