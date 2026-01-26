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

# Import StorageRouter and Table from canonical location (models/api/dal.py)
# Fallback only exists for DuckDB-only environments without pyspark
try:
    from de_funk.models.api.dal import StorageRouter, Table
except ImportError:
    from dataclasses import dataclass
    from typing import Dict, Any as DictAny

    @dataclass(frozen=True)
    class StorageRouter:
        """Fallback StorageRouter for DuckDB-only environments."""
        storage_cfg: Dict[DictAny, DictAny]
        repo_root: Optional[Path] = None

        def resolve(self, table_ref: str) -> str:
            """Resolve config-style table reference to path."""
            if table_ref.startswith("bronze."):
                layer, rel = "bronze", table_ref[7:].replace(".", "/")
            elif table_ref.startswith("silver."):
                layer, rel = "silver", table_ref[7:]
            else:
                layer, rel = "silver", table_ref

            root = self.storage_cfg["roots"][layer].rstrip("/")
            path = f"{root}/{rel}"
            if self.repo_root and not Path(path).is_absolute():
                return str(self.repo_root / path)
            return path

        # Legacy compatibility
        def bronze_path(self, logical_table: str) -> str:
            return self.resolve(f"bronze.{logical_table}")

        def silver_path(self, logical_rel: str) -> str:
            return self.resolve(f"silver.{logical_rel}")

    Table = None

from de_funk.core.session.filters import FilterEngine

try:
    import yaml
except Exception:
    yaml = None

import logging
logger = logging.getLogger(__name__)


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
        from de_funk.models.registry import ModelRegistry
        # Models are in domains/ directory (v2.0+ architecture)
        models_dir = repo_root / "domains"
        self.registry = ModelRegistry(models_dir)

        # Cache loaded models
        self._models: Dict[str, Any] = {}

        # Build model dependency graph from registry (handles modular YAML)
        from de_funk.models.api.graph import ModelGraph
        self.model_graph = ModelGraph()
        try:
            # Use registry to handle modular YAML configs (v2.0+)
            self.model_graph.build_from_registry(self.registry)
        except Exception as e:
            logger.warning(f"Could not build model graph: {e}")

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
            from de_funk.models.api.auto_join import AutoJoinHandler
            self._auto_join_handler = AutoJoinHandler(self)
        return self._auto_join_handler

    def _get_aggregation_handler(self):
        """Get or create AggregationHandler instance."""
        if self._aggregation_handler is None:
            from de_funk.models.api.aggregation import AggregationHandler
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
        import logging
        logger = logging.getLogger(__name__)

        if source_model == target_model:
            return True

        if hasattr(self, 'model_graph') and self.model_graph:
            result = self.model_graph.are_related(target_model, source_model)
            logger.debug(
                f"Cross-model filter check: {source_model} -> {target_model} = {result}"
            )
            return result

        logger.warning("Model graph not available for cross-model filter check")
        return False

    def column_exists_in_table(
        self,
        model_name: str,
        table_name: str,
        column_name: str
    ) -> bool:
        """
        Check if a column exists in a table.

        This is used to determine if a filter can be applied to a table
        regardless of model relationships. If the column exists, the filter
        can be applied directly.

        Args:
            model_name: Name of the model (e.g., 'stocks')
            table_name: Name of the table (e.g., 'fact_stock_prices')
            column_name: Name of the column to check (e.g., 'ticker')

        Returns:
            True if the column exists in the table, False otherwise
        """
        try:
            model = self.load_model(model_name)
            schema = model.get_table_schema(table_name)
            if schema:
                return column_name in schema
        except Exception:
            pass
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
            from de_funk.models.base.model import BaseModel
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

    def _get_table_from_view_or_build(self, model, model_name: str, table_name: str, allow_build: bool = True) -> Any:
        """
        Try to get table from existing silver view, fall back to reading Silver parquet directly,
        then finally fall back to building from Bronze.

        Args:
            model: Model instance
            model_name: Name of the model
            table_name: Name of the table
            allow_build: If False, raise error instead of building from Bronze.
                         Use this to prevent expensive builds when using DuckDB views.

        Returns:
            DataFrame (DuckDB relation or Spark DataFrame)

        Raises:
            ValueError: If view not found and allow_build=False
        """
        import logging
        from pathlib import Path
        import glob
        logger = logging.getLogger(__name__)

        # Strategy 1: Try DuckDB view
        if hasattr(self.connection, 'table'):
            view_name = f"{model_name}.{table_name}"
            try:
                result = self.connection.table(view_name)
                logger.debug(f"Using DuckDB view: {view_name}")
                return result
            except Exception as e:
                logger.debug(f"View {view_name} not available ({e})")

        # Strategy 2: Try reading Silver files directly
        # First check if the model config specifies its own silver root (from domain markdown)
        model_cfg = model.model_cfg if hasattr(model, 'model_cfg') else {}
        model_silver_root = model_cfg.get('storage', {}).get('silver', {}).get('root')

        if model_silver_root:
            # Domain config specifies explicit path like 'storage/silver/securities/stocks'
            base_silver_path = Path(model_silver_root)
            if not base_silver_path.is_absolute():
                base_silver_path = self.repo_root / base_silver_path if self.repo_root else base_silver_path
            logger.debug(f"Using model-specific silver root: {base_silver_path}")
        else:
            # Fallback: Use global silver root + model_name
            silver_base = self.storage_cfg.get('roots', {}).get('silver', 'storage/silver')
            if not Path(silver_base).is_absolute():
                silver_base = self.repo_root / silver_base if self.repo_root else Path(silver_base)
            else:
                silver_base = Path(silver_base)
            base_silver_path = silver_base / model_name
            logger.debug(f"Using global silver root + model_name: {base_silver_path}")

        # Get the table path from config
        # Support both v2.x (schema.facts/dimensions) and v3.0 (tables) formats
        table_path = None

        # v3.0 format: tables: {table_name: {path: ...}}
        tables_cfg = model_cfg.get('tables', {})
        if table_name in tables_cfg:
            table_path = tables_cfg[table_name].get('path', table_name)
            logger.debug(f"Found table path in v3.0 'tables' config: {table_path}")

        # v2.x format: schema.facts/dimensions.{table_name}.path
        if not table_path:
            schema_cfg = model_cfg.get('schema', {})
            for table_type in ['facts', 'dimensions']:
                tables = schema_cfg.get(table_type, {})
                if table_name in tables:
                    table_path = tables[table_name].get('path', table_name)
                    logger.debug(f"Found table path in v2.x 'schema' config: {table_path}")
                    break

        # If not in any config, use the table name directly
        if not table_path:
            table_path = table_name
            logger.debug(f"No config path found, using table name: {table_path}")

        # Try multiple possible paths
        # Model writer creates: facts/fact_xxx or dims/dim_xxx
        # Also check shared NFS storage which may have data from cluster builds
        possible_paths = [
            base_silver_path / table_path,
            base_silver_path / f"facts/{table_name}",  # facts/fact_stock_prices
            base_silver_path / f"dims/{table_name}",   # dims/dim_stock
        ]

        # Also try shared NFS storage paths (cluster builds write here)
        shared_silver_base = Path('/shared/storage/silver') / model_name
        if shared_silver_base != base_silver_path:
            possible_paths.extend([
                shared_silver_base / table_path,
                shared_silver_base / f"facts/{table_name}",
                shared_silver_base / f"dims/{table_name}",
            ])

        logger.debug(f"Looking for {model_name}.{table_name} in paths: {[str(p) for p in possible_paths]}")

        for silver_table_path in possible_paths:
            exists = silver_table_path.exists()
            logger.debug(f"  Checking {silver_table_path}: exists={exists}")
            # Check if Silver table exists (Delta or Parquet)
            delta_log_path = silver_table_path / "_delta_log"
            is_delta = delta_log_path.exists()
            parquet_pattern = str(silver_table_path / "**/*.parquet")
            parquet_files = glob.glob(parquet_pattern, recursive=True)

            if not silver_table_path.exists():
                continue

            # Strategy 2a: DuckDB direct read
            if hasattr(self.connection, 'conn'):
                logger.debug(f"Reading Silver {'Delta' if is_delta else 'Parquet'} with DuckDB from {silver_table_path}")
                try:
                    if is_delta:
                        sql = f"SELECT * FROM delta_scan('{silver_table_path}')"
                    else:
                        sql = f"SELECT * FROM read_parquet('{parquet_pattern}', hive_partitioning=true)"
                    # Return lazy DuckDB relation - DO NOT use fetchdf() which loads all data
                    # DuckDB's lazy evaluation handles large tables efficiently
                    return self.connection.conn.sql(sql)
                except Exception as e:
                    logger.debug(f"Failed to read from {silver_table_path}: {e}")
                    continue

            # Strategy 2b: Spark direct read from Silver
            if hasattr(self.connection, 'spark') or hasattr(self.connection, '_spark'):
                spark = getattr(self.connection, 'spark', None) or getattr(self.connection, '_spark', None)
                if spark:
                    logger.debug(f"Reading Silver {'Delta' if is_delta else 'Parquet'} with Spark from {silver_table_path}")
                    try:
                        if is_delta:
                            return spark.read.format("delta").load(str(silver_table_path))
                        else:
                            return spark.read.parquet(str(silver_table_path))
                    except Exception as e:
                        logger.debug(f"Failed to read from {silver_table_path}: {e}")
                        continue

        # Strategy 3: None of the paths worked - log detailed info
        paths_checked = [str(p) for p in possible_paths]
        logger.warning(
            f"Table '{model_name}.{table_name}' not found in any of these paths: {paths_checked}. "
            f"Model silver root: {model_silver_root if model_silver_root else 'not specified (using global)'}"
        )

        if not allow_build:
            raise ValueError(
                f"Table '{model_name}.{table_name}' not available as view and building is disabled. "
                f"Paths checked: {paths_checked}"
            )

        if not base_silver_path.exists():
            raise ValueError(
                f"Silver storage for '{model_name}' not found at {base_silver_path}. "
                f"Run: python -m scripts.build.build_models --models {model_name}"
            )

        # Strategy 4: REMOVED - Never fall back to Bronze for queries
        # Building from Bronze would load 22M+ rows into memory and crash.
        # If we get here, Silver doesn't exist - raise clear error.
        raise ValueError(
            f"Table '{model_name}.{table_name}' not available. "
            f"Paths checked: {paths_checked}. "
            f"Run: python -m scripts.build.build_models --models {model_name}"
        )

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
                # Translate universal date filters before applying
                translated_filters = self._translate_date_filters_for_table(
                    model_name, table_name, filters, df
                )
                df = FilterEngine.apply_from_session(df, translated_filters, self)
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
                # Translate universal date filters before applying
                translated_filters = self._translate_date_filters_for_table(
                    model_name, table_name, filters, df
                )
                df = FilterEngine.apply_from_session(df, translated_filters, self)

            df = auto_join.select_columns(df, required_columns)

            if group_by:
                df = aggregation.aggregate_data(model_name, df, required_columns, group_by, aggregations)

            return df

        # Missing columns - use auto-join to get them from related tables
        # Auto-join uses the model graph to find join paths
        import time

        logger.debug(f"AUTO-JOIN START: {missing} not in {table_name}, searching for join path...")
        start_time = time.time()

        # Strategy 1: Check for materialized view
        t0 = time.time()
        materialized_table = auto_join.find_materialized_view(model_name, required_columns)
        logger.debug(f"AUTO-JOIN: find_materialized_view took {time.time() - t0:.2f}s")

        if materialized_table:
            logger.debug(f"AUTO-JOIN: Using materialized view: {materialized_table}")
            # Use session method to get from Silver - don't call model.get_table() directly
            df = self._get_table_from_view_or_build(model, model_name, materialized_table, allow_build=False)

            if filters:
                df = FilterEngine.apply_from_session(df, filters, self)

            df = auto_join.select_columns(df, required_columns)

            if group_by:
                df = aggregation.aggregate_data(model_name, df, required_columns, group_by, aggregations)

            logger.debug(f"AUTO-JOIN COMPLETE: Total time {time.time() - start_time:.2f}s (materialized view)")
            return df

        # Strategy 2: Build joins from graph
        t0 = time.time()
        join_plan = auto_join.plan_auto_joins(model_name, table_name, missing)
        logger.debug(f"AUTO-JOIN: plan_auto_joins took {time.time() - t0:.2f}s")
        logger.debug(f"AUTO-JOIN: Join plan: {' -> '.join(join_plan['table_sequence'])}")

        t0 = time.time()
        # Pass group_by and aggregations to SQL level for efficient aggregation
        df = auto_join.execute_auto_joins(
            model_name, join_plan, required_columns, filters,
            group_by=group_by, aggregations=aggregations
        )
        logger.debug(f"AUTO-JOIN: execute_auto_joins took {time.time() - t0:.2f}s")

        # Log result row count for debugging
        try:
            if hasattr(df, 'count'):
                # DuckDB relation - use count() which is efficient
                row_count = df.count('*').fetchone()[0]
            elif hasattr(df, 'shape'):
                # Pandas DataFrame
                row_count = df.shape[0]
            else:
                row_count = 'unknown'
            logger.info(f"AUTO-JOIN RESULT: {row_count} rows returned")
            if row_count == 0:
                logger.warning(f"AUTO-JOIN RESULT: No data! Check filters: {filters}")
        except Exception as e:
            logger.debug(f"AUTO-JOIN RESULT: Could not get row count: {e}")

        # NOTE: Removed try/except fallback to model.get_table()
        # If auto-join fails, let the error propagate - don't silently read from Bronze

        # NOTE: Aggregation is now pushed to SQL level in execute_auto_joins
        # No need to call aggregate_data here

        logger.debug(f"AUTO-JOIN COMPLETE: Total time {time.time() - start_time:.2f}s")
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

    def _translate_date_filters_for_table(
        self,
        model_name: str,
        table_name: str,
        filters: Dict[str, Any],
        df: Any
    ) -> Dict[str, Any]:
        """
        Translate universal date filters for a table using its calendar edge mapping.

        If a filter uses 'forecast_date' but the table has 'trade_date',
        this method translates it via the dim_calendar relationship.

        Also translates filter parameters like start_date/end_date to date range filters.

        Args:
            model_name: Model being queried
            table_name: Table being queried
            filters: Original filter dict
            df: DataFrame to get available columns from

        Returns:
            Translated filter dict
        """
        if not filters:
            return filters

        # Get available columns from the dataframe
        try:
            import pandas as pd
            if isinstance(df, pd.DataFrame):
                available_cols = set(df.columns)
            else:
                # DuckDB relation
                available_cols = set(df.columns)
        except Exception:
            return filters

        # Use auto-join handler's translation logic
        auto_join = self._get_auto_join_handler()

        # Step 1: Translate filter parameters (start_date/end_date -> date range)
        # This must happen BEFORE translate_date_filters to ensure date filters work
        param_translated = auto_join.translate_filter_parameters(filters, available_cols)

        # Step 2: Translate universal date filters via dim_calendar mapping
        return auto_join.translate_date_filters(model_name, table_name, param_translated, available_cols)

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

    # ============================================================
    # BACKEND-AGNOSTIC QUERY HELPERS
    # ============================================================
    # These methods encapsulate backend differences so models
    # can remain backend-agnostic. Models should use these
    # instead of writing backend-specific code.

    def filter_by_value(self, df: Any, column: str, value: Any) -> Any:
        """
        Filter DataFrame where column equals value (exact match).

        Args:
            df: DataFrame (Spark or DuckDB/pandas)
            column: Column name to filter on
            value: Value to match

        Returns:
            Filtered DataFrame
        """
        if self.backend == 'spark':
            return df.filter(df[column] == value)
        else:
            # DuckDB relation or pandas
            if hasattr(df, 'filter'):
                return df.filter(f"{column} = {self._sql_value(value)}")
            else:
                return df[df[column] == value]

    def filter_by_values(self, df: Any, column: str, values: List[Any]) -> Any:
        """
        Filter DataFrame where column is in values list.

        Handles Spark semi-join vs DuckDB isin() transparently.

        Args:
            df: DataFrame (Spark or DuckDB/pandas)
            column: Column name to filter on
            values: List of values to match

        Returns:
            Filtered DataFrame
        """
        if not values:
            return df

        if self.backend == 'spark':
            # Spark: Use semi-join for efficient large list filtering
            values_df = self.connection.createDataFrame([(v,) for v in values], [column])
            return df.join(values_df, column, 'left_semi')
        else:
            # DuckDB/pandas: Use isin
            if hasattr(df, 'filter'):
                # DuckDB relation
                values_str = ', '.join(self._sql_value(v) for v in values)
                return df.filter(f"{column} IN ({values_str})")
            else:
                # pandas
                return df[df[column].isin(values)]

    def filter_by_range(
        self,
        df: Any,
        column: str,
        min_val: Any = None,
        max_val: Any = None
    ) -> Any:
        """
        Filter DataFrame by range (dates, numbers).

        Args:
            df: DataFrame (Spark or DuckDB/pandas)
            column: Column name to filter on
            min_val: Minimum value (inclusive), None to skip
            max_val: Maximum value (inclusive), None to skip

        Returns:
            Filtered DataFrame
        """
        if min_val is None and max_val is None:
            return df

        if self.backend == 'spark':
            if min_val is not None:
                df = df.filter(df[column] >= min_val)
            if max_val is not None:
                df = df.filter(df[column] <= max_val)
        else:
            if hasattr(df, 'filter'):
                # DuckDB relation
                if min_val is not None:
                    df = df.filter(f"{column} >= {self._sql_value(min_val)}")
                if max_val is not None:
                    df = df.filter(f"{column} <= {self._sql_value(max_val)}")
            else:
                # pandas
                if min_val is not None:
                    df = df[df[column] >= min_val]
                if max_val is not None:
                    df = df[df[column] <= max_val]

        return df

    def semi_join(self, df: Any, filter_df: Any, on: str) -> Any:
        """
        Efficient filtering via semi-join.

        Keeps rows from df where the join column exists in filter_df.
        Useful for filtering a large table to a subset of keys.

        Args:
            df: Main DataFrame to filter
            filter_df: DataFrame with values to keep
            on: Column name to join on

        Returns:
            Filtered DataFrame (rows from df where on-column exists in filter_df)
        """
        if self.backend == 'spark':
            # Spark: native left_semi join
            return df.join(filter_df.select(on).distinct(), on, 'left_semi')
        else:
            # DuckDB/pandas: use isin
            import pandas as pd

            # Get filter values
            if hasattr(filter_df, 'df'):
                filter_values = set(filter_df.df()[on].unique())
            elif isinstance(filter_df, pd.DataFrame):
                filter_values = set(filter_df[on].unique())
            else:
                filter_values = set(filter_df[on].unique())

            # Apply filter
            if hasattr(df, 'filter'):
                values_str = ', '.join(self._sql_value(v) for v in filter_values)
                return df.filter(f"{on} IN ({values_str})")
            elif hasattr(df, 'df'):
                pdf = df.df()
                filtered = pdf[pdf[on].isin(filter_values)]
                return self.connection.conn.from_df(filtered)
            else:
                return df[df[on].isin(filter_values)]

    def join(
        self,
        left_df: Any,
        right_df: Any,
        on: List[str],
        how: str = 'inner'
    ) -> Any:
        """
        Join two DataFrames.

        Args:
            left_df: Left DataFrame
            right_df: Right DataFrame
            on: List of column names to join on
            how: Join type ('inner', 'left', 'right', 'outer')

        Returns:
            Joined DataFrame
        """
        if self.backend == 'spark':
            return left_df.join(right_df, on, how)
        else:
            import pandas as pd

            # Convert to pandas if needed
            left_pdf = left_df.df() if hasattr(left_df, 'df') else left_df
            right_pdf = right_df.df() if hasattr(right_df, 'df') else right_df

            result = left_pdf.merge(right_pdf, on=on, how=how)

            # Convert back to DuckDB if needed
            if hasattr(self.connection, 'conn'):
                return self.connection.conn.from_df(result)
            return result

    def distinct_values(self, df: Any, column: str) -> List[Any]:
        """
        Get distinct values from a column as a list.

        Args:
            df: DataFrame
            column: Column name

        Returns:
            List of unique values
        """
        if self.backend == 'spark':
            return [row[column] for row in df.select(column).distinct().collect()]
        else:
            if hasattr(df, 'df'):
                return df.df()[column].unique().tolist()
            else:
                return df[column].unique().tolist()

    def order_by(self, df: Any, column: str, ascending: bool = True) -> Any:
        """
        Order DataFrame by column.

        Args:
            df: DataFrame
            column: Column to order by
            ascending: True for ascending, False for descending

        Returns:
            Ordered DataFrame
        """
        if self.backend == 'spark':
            if ascending:
                return df.orderBy(df[column].asc())
            else:
                return df.orderBy(df[column].desc())
        else:
            if hasattr(df, 'order'):
                direction = 'ASC' if ascending else 'DESC'
                return df.order(f"{column} {direction}")
            else:
                return df.sort_values(column, ascending=ascending)

    def limit(self, df: Any, n: int) -> Any:
        """
        Limit DataFrame to first n rows.

        Args:
            df: DataFrame
            n: Number of rows to return

        Returns:
            DataFrame with at most n rows
        """
        if self.backend == 'spark':
            return df.limit(n)
        else:
            if hasattr(df, 'limit'):
                return df.limit(n)
            else:
                return df.head(n)

    def top_n_by(self, df: Any, n: int, column: str, ascending: bool = False) -> Any:
        """
        Get top N rows by a column value.

        Args:
            df: DataFrame
            n: Number of rows
            column: Column to rank by
            ascending: True for smallest, False for largest (default)

        Returns:
            DataFrame with top N rows
        """
        if self.backend == 'spark':
            if ascending:
                return df.orderBy(df[column].asc()).limit(n)
            else:
                return df.orderBy(df[column].desc()).limit(n)
        else:
            if hasattr(df, 'df'):
                pdf = df.df()
            else:
                pdf = df

            if ascending:
                result = pdf.nsmallest(n, column)
            else:
                result = pdf.nlargest(n, column)

            if hasattr(self.connection, 'conn'):
                return self.connection.conn.from_df(result)
            return result

    def row_count(self, df: Any) -> int:
        """
        Get row count of DataFrame.

        Args:
            df: DataFrame

        Returns:
            Number of rows
        """
        if self.backend == 'spark':
            return df.count()
        else:
            if hasattr(df, 'count'):
                # DuckDB relation
                result = df.count('*').fetchone()
                return result[0] if result else 0
            elif hasattr(df, 'df'):
                return len(df.df())
            else:
                return len(df)

    def to_pandas(self, df: Any) -> 'pd.DataFrame':
        """
        Convert DataFrame to pandas.

        Args:
            df: DataFrame (Spark or DuckDB)

        Returns:
            pandas DataFrame
        """
        import pandas as pd

        if self.backend == 'spark':
            return df.toPandas()
        else:
            if hasattr(df, 'df'):
                return df.df()
            elif isinstance(df, pd.DataFrame):
                return df
            else:
                return df.fetchdf()

    def select_columns(self, df: Any, columns: List[str]) -> Any:
        """
        Select specific columns from DataFrame.

        Args:
            df: DataFrame
            columns: List of column names to select

        Returns:
            DataFrame with only specified columns
        """
        if self.backend == 'spark':
            return df.select(columns)
        else:
            if hasattr(df, 'select'):
                return df.select(', '.join(columns))
            else:
                return df[columns]

    def add_column(self, df: Any, name: str, expression: Any) -> Any:
        """
        Add a computed column to DataFrame.

        Args:
            df: DataFrame
            name: New column name
            expression: Column expression (Spark Column or SQL string for DuckDB)

        Returns:
            DataFrame with new column
        """
        if self.backend == 'spark':
            return df.withColumn(name, expression)
        else:
            if hasattr(df, 'project'):
                # DuckDB: add column via SQL expression
                return df.project(f"*, {expression} AS {name}")
            else:
                # pandas: evaluate expression
                df = df.copy()
                df[name] = expression
                return df

    def _sql_value(self, value: Any) -> str:
        """Format value for SQL (internal helper)."""
        if value is None:
            return 'NULL'
        elif isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"
