from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from pyspark.sql import DataFrame, SparkSession, functions as F

from models.company.model import CompanyModel
from models.api.dal import StorageRouter, BronzeTable, SilverPath

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

class ModelSession:
    """
    Thin wrapper around your CompanyModel with convenience to access bronze and silver.
    - builds the graph lazily
    - lets services get at named silver 'paths' without re-implementing joins
    """
    def __init__(self, spark: SparkSession, repo_root: Path, storage_cfg: Dict[str, Any]):
        self.spark = spark
        self.repo_root = repo_root
        self.storage_cfg = storage_cfg
        self.router = StorageRouter(storage_cfg)
        self._dims: Dict[str, DataFrame] | None = None
        self._facts: Dict[str, DataFrame] | None = None

    # ------------- bronze -------------
    def bronze(self, logical_table: str) -> BronzeTable:
        return BronzeTable(self.spark, self.router, logical_table)

    # ------------- silver -------------
    def _load_model_yaml(self) -> Dict[str, Any]:
        p = self.repo_root / "configs" / "models" / "company.yaml"
        txt = p.read_text()
        if yaml is not None:
            return yaml.safe_load(txt)
        return json.loads(txt)

    def ensure_built(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        if self._facts is None or self._dims is None:
            model_cfg = self._load_model_yaml()
            model = CompanyModel(
                self.spark, model_cfg=model_cfg, storage_cfg=self.storage_cfg, params={}
            )
            self._dims, self._facts = model.build()
        return self._dims, self._facts

    def silver_path_df(self, path_id: str) -> DataFrame:
        _, facts = self.ensure_built()
        if path_id not in facts:
            raise KeyError(f"Silver path '{path_id}' not built.")
        return facts[path_id]

    def get_dimension_df(self, model_name: str, node_name: str) -> DataFrame:
        """
        Get a dimension dataframe.

        Args:
            model_name: Model name (e.g., 'company')
            node_name: Node name (e.g., 'dim_company')

        Returns:
            Dimension dataframe
        """
        dims, _ = self.ensure_built()
        if node_name not in dims:
            raise KeyError(f"Dimension '{node_name}' not found in model '{model_name}'. Available dims: {list(dims.keys())}")
        return dims[node_name]

    def get_fact_df(self, model_name: str, node_name: str) -> DataFrame:
        """
        Get a fact dataframe.

        Args:
            model_name: Model name (e.g., 'company')
            node_name: Node name (e.g., 'fact_prices')

        Returns:
            Fact dataframe
        """
        _, facts = self.ensure_built()
        if node_name not in facts:
            raise KeyError(f"Fact '{node_name}' not found in model '{model_name}'. Available facts: {list(facts.keys())}")
        return facts[node_name]

    # Optional: writer if you decide to persist silver later
    def persist_silver(self, outputs: Dict[str, str]):
        """
        outputs: mapping of path_id -> silver relative path (e.g. 'company/paths/news_with_company')
        """
        _, facts = self.ensure_built()
        for pid, rel in outputs.items():
            if pid not in facts:
                raise KeyError(f"Path '{pid}' not found.")
            facts[pid].write.mode("overwrite").parquet(self.router.silver_path(rel))


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

    # Backward compatibility with ModelSession
    def bronze(self, logical_table: str) -> BronzeTable:
        """Access Bronze tables (backward compatibility)"""
        if not hasattr(self.connection, 'read'):
            raise ValueError("Bronze access requires Spark connection")
        router = StorageRouter(self.storage_cfg)
        return BronzeTable(self.connection, router, logical_table)
