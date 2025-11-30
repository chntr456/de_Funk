"""
BaseModel - Generic model class with YAML-driven graph building.

All domain models inherit from BaseModel, which provides:
- Generic node loading from Bronze
- Graph edge validation
- Path materialization (joins)
- Table access methods
- Metadata extraction

The YAML config is the source of truth for the model structure.

REFACTORED: This file now uses composition with:
- GraphBuilder: Graph building and node loading
- TableAccessor: Table access and schema inspection
- MeasureCalculator: Measure calculations
- ModelWriter: Persistence to storage
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import PySpark (may not be available when using DuckDB)
try:
    from pyspark.sql import DataFrame as SparkDataFrame, functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkDataFrame = None
    F = None

# Import StorageRouter (with fallback if pyspark not available)
try:
    from models.api.dal import StorageRouter, BronzeTable
except ImportError:
    # Fallback for DuckDB-only environments
    @dataclass(frozen=True)
    class StorageRouter:
        storage_cfg: Dict[str, Any]
        repo_root: Optional[Path] = None

        def bronze_path(self, logical_table: str) -> str:
            root = self.storage_cfg["roots"]["bronze"].rstrip("/")
            rel = self.storage_cfg["tables"][logical_table]["rel"]
            path = f"{root}/{rel}"
            if self.repo_root:
                return str(self.repo_root / path)
            return path

        def silver_path(self, logical_rel: str) -> str:
            root = self.storage_cfg["roots"]["silver"].rstrip("/")
            path = f"{root}/{logical_rel}"
            if self.repo_root:
                return str(self.repo_root / path)
            return path

    BronzeTable = None  # Not needed for DuckDB

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class BaseModel:
    """
    Smart base model that reads YAML config and implements all generic logic.

    Expected YAML structure:
      graph:
        nodes:        # Table definitions (dims and facts from Bronze)
        edges:        # Relationships between tables
        paths:        # Materialized views (joined tables)
      measures:       # Computed metrics (optional)
      schema:         # Table metadata (optional)
    """

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict, params: Dict = None, repo_root: Optional[Path] = None):
        """
        Initialize a model.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration (roots, table mappings)
            model_cfg: Model configuration from YAML
            params: Runtime parameters for customization
            repo_root: Repository root for absolute path resolution (optional)
        """
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.model_cfg = model_cfg
        self.params = params or {}
        self.model_name = model_cfg.get('model', 'unknown')
        self.repo_root = repo_root

        # Session reference for cross-model access (injected by UniversalSession)
        self.session = None

        # Lazy-loaded caches
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Storage router for path resolution (with repo_root for absolute paths)
        self.storage_router = StorageRouter(self.storage_cfg, repo_root=repo_root)

        # Detect backend type
        self._backend = self._detect_backend()

        # Unified measure executor (lazy-loaded)
        self._measure_executor = None

        # Query planner for dynamic joins (lazy-loaded)
        self._query_planner = None

        # Python measures module (lazy-loaded)
        self._python_measures = None

        # Composition helpers (lazy-loaded)
        self._graph_builder = None
        self._table_accessor = None
        self._measure_calculator = None
        self._model_writer = None

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def backend(self) -> str:
        """Get backend type (spark or duckdb)."""
        return self._backend

    @property
    def measures(self):
        """
        Get unified measure executor.

        Provides access to the new measure framework for calculating
        all types of measures (simple, computed, weighted, etc.).
        """
        if self._measure_executor is None:
            from models.base.measures.executor import MeasureExecutor
            self._measure_executor = MeasureExecutor(self, backend=self.backend)
        return self._measure_executor

    @property
    def query_planner(self):
        """
        Get query planner for dynamic table joins.

        Uses the model's graph edges to plan and execute joins at runtime.
        """
        if self._query_planner is None:
            from models.api.query_planner import GraphQueryPlanner
            self._query_planner = GraphQueryPlanner(self)
        return self._query_planner

    @property
    def python_measures(self):
        """
        Get Python measures module for complex calculations.

        Loads Python measure modules dynamically based on model configuration.
        """
        if self._python_measures is None:
            self._python_measures = self._load_python_measures()
        return self._python_measures

    def _load_python_measures(self):
        """Load Python measures module for this model."""
        try:
            from config.model_loader import ModelConfigLoader
            from pathlib import Path

            models_dir = self.storage_cfg.get('models_dir', 'configs/models')
            loader = ModelConfigLoader(Path(models_dir))
            measures_instance = loader.load_python_measures(self.model_name, model_instance=self)

            if measures_instance:
                logger.info(f"Loaded Python measures for model '{self.model_name}'")
                return measures_instance
            else:
                logger.debug(f"No Python measures found for model '{self.model_name}'")
                return None

        except Exception as e:
            logger.warning(f"Failed to load Python measures for '{self.model_name}': {e}")
            return None

    def _detect_backend(self) -> str:
        """Detect backend type from connection."""
        connection_type = str(type(self.connection))

        if 'spark' in connection_type.lower() or hasattr(self.connection, 'sql'):
            return 'spark'

        if 'duckdb' in connection_type.lower() or (
            hasattr(self.connection, '_conn') and 'duckdb' in str(type(self.connection._conn)).lower()
        ):
            return 'duckdb'

        raise ValueError(f"Unknown connection type: {connection_type}")

    def set_session(self, session):
        """
        Inject session reference for cross-model access.

        Called by UniversalSession after model instantiation.
        """
        self.session = session

    # ============================================================
    # BACKEND-AGNOSTIC HELPERS
    # ============================================================

    def _select_columns(self, df: DataFrame, select_config: Dict[str, str]) -> DataFrame:
        """Backend-agnostic column selection."""
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")
            cols = [
                F.col(expr).alias(out_name)
                for out_name, expr in select_config.items()
            ]
            return df.select(*cols)
        else:
            # DuckDB - use project() method
            col_expressions = []
            for out_name, expr in select_config.items():
                if out_name == expr:
                    col_expressions.append(expr)
                else:
                    col_expressions.append(f"{expr} AS {out_name}")
            return df.project(','.join(col_expressions))

    def _apply_filters(self, df: DataFrame, filters: list) -> DataFrame:
        """Backend-agnostic filter application."""
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")
            for filter_expr in filters:
                df = df.filter(F.expr(filter_expr))
            return df
        else:
            for filter_expr in filters:
                df = df.filter(filter_expr)
            return df

    # ============================================================
    # GRAPH BUILDING (delegated to GraphBuilder)
    # ============================================================

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Build model tables from Bronze layer."""
        if self._graph_builder is None:
            from models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)
        return self._graph_builder.build()

    def ensure_built(self):
        """Lazy build pattern - only build when needed."""
        if not self._is_built:
            if self._graph_builder is None:
                from models.base.graph_builder import GraphBuilder
                self._graph_builder = GraphBuilder(self)
            self._dims, self._facts = self._graph_builder.build()
            self._is_built = True

    # ============================================================
    # TABLE ACCESS (delegated to TableAccessor)
    # ============================================================

    def _get_table_accessor(self):
        """Get or create TableAccessor instance."""
        if self._table_accessor is None:
            from models.base.table_accessor import TableAccessor
            self._table_accessor = TableAccessor(self)
        return self._table_accessor

    def get_table(self, table_name: str) -> DataFrame:
        """Get a table by name (searches dims and facts)."""
        return self._get_table_accessor().get_table(table_name)

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> DataFrame:
        """Get table with optional enrichment via dynamic joins."""
        return self._get_table_accessor().get_table_enriched(table_name, enrich_with, columns)

    def get_dimension_df(self, dim_id: str) -> DataFrame:
        """Get a dimension table by ID."""
        return self._get_table_accessor().get_dimension_df(dim_id)

    def get_fact_df(self, fact_id: str) -> DataFrame:
        """Get a fact table by ID."""
        return self._get_table_accessor().get_fact_df(fact_id)

    def has_table(self, table_name: str) -> bool:
        """Check if a table exists in this model."""
        return self._get_table_accessor().has_table(table_name)

    def list_tables(self) -> Dict[str, List[str]]:
        """List all available tables."""
        return self._get_table_accessor().list_tables()

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get schema (column definitions) for a table."""
        return self._get_table_accessor().get_table_schema(table_name)

    def get_relations(self) -> Dict[str, List[str]]:
        """Return relationship graph from edges config."""
        return self._get_table_accessor().get_relations()

    def get_metadata(self) -> Dict[str, Any]:
        """Return model metadata."""
        return self._get_table_accessor().get_metadata()

    # ============================================================
    # MEASURE CALCULATIONS (delegated to MeasureCalculator)
    # ============================================================

    def _get_measure_calculator(self):
        """Get or create MeasureCalculator instance."""
        if self._measure_calculator is None:
            from models.base.measure_calculator import MeasureCalculator
            self._measure_calculator = MeasureCalculator(self)
        return self._measure_calculator

    def calculate_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """Calculate any measure defined in model config (UNIFIED METHOD)."""
        return self._get_measure_calculator().calculate_measure(
            measure_name, entity_column, filters, limit, **kwargs
        )

    def calculate_measure_by_entity(
        self,
        measure_name: str,
        entity_column: str,
        limit: Optional[int] = None
    ) -> DataFrame:
        """Calculate a measure aggregated by entity."""
        return self._get_measure_calculator().calculate_measure_by_entity(
            measure_name, entity_column, limit
        )

    # ============================================================
    # PERSISTENCE (delegated to ModelWriter)
    # ============================================================

    def write_tables(
        self,
        output_root: Optional[str] = None,
        format: str = "parquet",
        mode: str = "overwrite",
        use_optimized_writer: bool = True,
        partition_by: Optional[Dict[str, List[str]]] = None
    ):
        """Write all model tables to storage."""
        if self._model_writer is None:
            from models.base.model_writer import ModelWriter
            self._model_writer = ModelWriter(self)
        return self._model_writer.write_tables(
            output_root, format, mode, use_optimized_writer, partition_by
        )

    # ============================================================
    # EXTENSION POINTS (override in subclasses)
    # ============================================================

    def before_build(self):
        """Hook called before build(). Override for custom pre-processing."""
        pass

    def after_build(
        self,
        dims: Dict[str, DataFrame],
        facts: Dict[str, DataFrame]
    ) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Hook called after build(). Override for custom post-processing."""
        return dims, facts

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """Override to customize how specific nodes are loaded."""
        return None
