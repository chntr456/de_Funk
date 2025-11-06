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

    def get_table(self, model_name: str, table_name: str) -> DataFrame:
        """
        Get a table from any model.

        Args:
            model_name: Name of the model
            table_name: Name of the table

        Returns:
            DataFrame
        """
        model = self.load_model(model_name)
        return model.get_table(table_name)

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
