"""
UniversalSession - Model-agnostic session for cross-model queries.

Provides:
- Dynamic model loading from registry
- Cross-model queries and joins
- Auto-join support via graph traversal
- Aggregation with measure metadata

REFACTORED: This file now uses composition with:
- AutoJoinHandler: Automatic join operations
- AggregationHandler: Data aggregation

All auto-join and aggregation logic has been extracted to separate modules.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
else:
    SparkDataFrame = Any

# Import StorageRouter separately to avoid pyspark dependency
try:
    from models.api.dal import StorageRouter, BronzeTable
except ImportError:
    from dataclasses import dataclass
    from typing import Dict, Any as DictAny

    @dataclass(frozen=True)
    class StorageRouter:
        storage_cfg: Dict[DictAny, DictAny]

        def bronze_path(self, logical_table: str) -> str:
            root = self.storage_cfg["roots"]["bronze"].rstrip("/")
            rel = self.storage_cfg["tables"][logical_table]["rel"]
            return f"{root}/{rel}"

        def silver_path(self, logical_rel: str) -> str:
            root = self.storage_cfg["roots"]["silver"].rstrip("/")
            return f"{root}/{logical_rel}"

    BronzeTable = None

from core.session.filters import FilterEngine

try:
    import yaml
except Exception:
    yaml = None


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
        self._models: Dict[str, Any] = {}

        # Build model dependency graph
        from models.api.graph import ModelGraph
        self.model_graph = ModelGraph()
        try:
            self.model_graph.build_from_config_dir(models_dir)
        except Exception as e:
            print(f"Warning: Could not build model graph: {e}")

        # Composition helpers (lazy-loaded)
        self._auto_join_handler = None
        self._aggregation_handler = None

        # Pre-load specified models
        if models:
            for model_name in models:
                self.load_model(model_name)

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def backend(self) -> str:
        """Detect backend type from connection."""
        connection_type = str(type(self.connection))

        if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
            return 'spark'

        if 'duckdb' in connection_type.lower() or (
            hasattr(self.connection, '_conn') and 'duckdb' in str(type(self.connection._conn)).lower()
        ):
            return 'duckdb'

        raise ValueError(f"Unknown connection type: {connection_type}")

    def _get_auto_join_handler(self):
        """Get or create AutoJoinHandler instance."""
        if self._auto_join_handler is None:
            from models.api.auto_join import AutoJoinHandler
            self._auto_join_handler = AutoJoinHandler(self)
        return self._auto_join_handler

    def _get_aggregation_handler(self):
        """Get or create AggregationHandler instance."""
        if self._aggregation_handler is None:
            from models.api.aggregation import AggregationHandler
            self._aggregation_handler = AggregationHandler(self)
        return self._aggregation_handler

    # ============================================================
    # GRAPH ORCHESTRATION
    # ============================================================

    def should_apply_cross_model_filter(
        self,
        source_model: str,
        target_model: str
    ) -> bool:
        """
        Check if a filter from source_model should be applied to target_model.

        Returns True if:
        - Same model (always apply)
        - Models are related via graph (cross-model filter is valid)
        """
        if source_model == target_model:
            return True

        if hasattr(self, 'model_graph') and self.model_graph:
            return self.model_graph.are_related(target_model, source_model)

        return False

    # ============================================================
    # MODEL LOADING
    # ============================================================

    def load_model(self, model_name: str):
        """
        Dynamically load a model by name.

        Steps:
        1. Get model config from registry (YAML)
        2. Get model class from registry (Python class)
        3. Instantiate model
        4. Inject session for cross-model access
        5. Cache instance
        """
        if model_name in self._models:
            return self._models[model_name]

        model_config = self.registry.get_model_config(model_name)

        try:
            model_class = self.registry.get_model_class(model_name)
        except ValueError:
            from models.base.model import BaseModel
            model_class = BaseModel
            print(f"⚠ No custom class for {model_name}, using BaseModel")

        model = model_class(
            connection=self.connection,
            storage_cfg=self.storage_cfg,
            model_cfg=model_config,
            params={},
            repo_root=self.repo_root
        )

        if hasattr(model, 'set_session'):
            model.set_session(self)

        self._models[model_name] = model
        return model

    def get_model_instance(self, model_name: str):
        """Get the model instance directly."""
        return self.load_model(model_name)

    # ============================================================
    # TABLE ACCESS
    # ============================================================

    def _get_table_from_view_or_build(self, model, model_name: str, table_name: str) -> Any:
        """Try to get table from existing silver view, fall back to building."""
        if hasattr(self.connection, 'table'):
            view_name = f"{model_name}.{table_name}"
            try:
                return self.connection.table(view_name)
            except Exception:
                pass

        return model.get_table(table_name)

    def get_table(
        self,
        model_name: str,
        table_name: str,
        required_columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> Any:
        """
        Get a table from any model with transparent auto-join and aggregation support.

        If required_columns are specified and some don't exist in the base table,
        the system automatically uses the model graph to find join paths.

        If group_by is specified, the data is aggregated using measure metadata.

        Args:
            model_name: Name of the model
            table_name: Name of the base table
            required_columns: Optional list of columns needed
            filters: Optional filters to apply
            group_by: Optional list of columns to group by
            aggregations: Optional dict mapping measure columns to agg functions
            use_cache: Whether to use cached data (kept for backwards compatibility)

        Returns:
            DataFrame with requested columns (auto-joined and aggregated if needed)
        """
        model = self.load_model(model_name)
        auto_join = self._get_auto_join_handler()
        aggregation = self._get_aggregation_handler()

        # If no specific columns requested, return full table
        if not required_columns:
            df = self._get_table_from_view_or_build(model, model_name, table_name)
            if filters:
                df = FilterEngine.apply_from_session(df, filters, self)
            return df

        # Check which columns exist in base table
        try:
            schema = model.get_table_schema(table_name)
            base_columns = set(schema.keys())
        except Exception as e:
            print(f"Warning: Could not get schema for {model_name}.{table_name}: {e}")
            return self._get_table_from_view_or_build(model, model_name, table_name)

        # Find missing columns
        missing = [col for col in required_columns if col not in base_columns]

        # No missing columns - direct table access
        if not missing:
            df = self._get_table_from_view_or_build(model, model_name, table_name)

            if filters:
                df = FilterEngine.apply_from_session(df, filters, self)

            df = auto_join.select_columns(df, required_columns)

            if group_by:
                df = aggregation.aggregate_data(model_name, df, required_columns, group_by, aggregations)

            return df

        # Missing columns - try auto-join strategies
        print(f"🔗 Auto-join: {missing} not in {table_name}, searching for join path...")

        # Strategy 1: Check for materialized view
        materialized_table = auto_join.find_materialized_view(model_name, required_columns)
        if materialized_table:
            print(f"✓ Using materialized view: {materialized_table}")
            df = model.get_table(materialized_table)

            if filters:
                df = FilterEngine.apply_from_session(df, filters, self)

            df = auto_join.select_columns(df, required_columns)

            if group_by:
                df = aggregation.aggregate_data(model_name, df, required_columns, group_by, aggregations)

            return df

        # Strategy 2: Build joins from graph
        try:
            join_plan = auto_join.plan_auto_joins(model_name, table_name, missing)
            print(f"✓ Join plan: {' -> '.join(join_plan['table_sequence'])}")
            df = auto_join.execute_auto_joins(model_name, join_plan, required_columns, filters)
        except Exception as e:
            print(f"❌ Auto-join failed: {e}")
            print(f"   Falling back to base table {table_name}")
            df = model.get_table(table_name)

            if filters:
                df = FilterEngine.apply_from_session(df, filters, self)

        if group_by:
            df = aggregation.aggregate_data(model_name, df, required_columns, group_by, aggregations)

        return df

    def get_filter_column_mappings(self, model_name: str, table_name: str) -> Dict[str, str]:
        """
        Get automatic filter column mappings based on model graph edges.

        Examines graph edges to find joins to dim_calendar and extracts
        column mappings for filter translation.
        """
        mappings = {}

        try:
            model_config = self.registry.get_model_config(model_name)
        except Exception:
            return mappings

        if 'graph' not in model_config or 'edges' not in model_config['graph']:
            return mappings

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = model_config['graph']['edges']
        if isinstance(edges_config, dict):
            edges_list = list(edges_config.values())
        else:
            edges_list = edges_config

        for edge in edges_list:
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')

            if edge_from == table_name and 'dim_calendar' in edge_to:
                on_conditions = edge.get('on', edge.get(True, []))

                for condition in on_conditions:
                    if isinstance(condition, str):
                        parts = condition.split('=')
                        if len(parts) == 2:
                            table_col = parts[0].strip()
                            calendar_col = parts[1].strip()
                            mappings[calendar_col] = table_col

        return mappings

    def get_dimension_df(self, model_name: str, dim_id: str) -> Any:
        """Get a dimension table from a model."""
        model = self.load_model(model_name)
        return model.get_dimension_df(dim_id)

    def get_fact_df(self, model_name: str, fact_id: str) -> Any:
        """Get a fact table from a model."""
        model = self.load_model(model_name)
        return model.get_fact_df(fact_id)

    def list_models(self) -> list[str]:
        """List all available models."""
        return self.registry.list_models()

    def list_tables(self, model_name: str) -> Dict[str, list[str]]:
        """List all tables in a model."""
        model = self.load_model(model_name)
        return model.list_tables()

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """Get metadata for a model."""
        model = self.load_model(model_name)
        return model.get_metadata()
