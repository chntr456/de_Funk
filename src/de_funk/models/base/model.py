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

# Import StorageRouter and Table (with fallback if pyspark not available)
try:
    from de_funk.models.api.dal import StorageRouter, Table
except ImportError:
    # Fallback for DuckDB-only environments
    @dataclass(frozen=True)
    class StorageRouter:
        storage_cfg: Dict[str, Any]
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
            if self.repo_root:
                return str(self.repo_root / path)
            return path

        # Legacy compatibility
        def bronze_path(self, logical_table: str) -> str:
            return self.resolve(f"bronze.{logical_table}")

        def silver_path(self, logical_rel: str) -> str:
            return self.resolve(f"silver.{logical_rel}")

    Table = None  # Not needed for DuckDB

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
            from de_funk.models.measures.executor import MeasureExecutor
            self._measure_executor = MeasureExecutor(self, backend=self.backend)
        return self._measure_executor

    @property
    def query_planner(self):
        """
        Get query planner for dynamic table joins.

        Uses the model's graph edges to plan and execute joins at runtime.
        """
        if self._query_planner is None:
            from de_funk.models.api.query_planner import GraphQueryPlanner
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
        """Load Python measures module for this model.

        Uses convention-based module discovery: looks for a measures.py
        file alongside the model's Python class.
        """
        try:
            import importlib

            # Convention: measures module lives next to the model class
            model_module = type(self).__module__
            package = model_module.rsplit('.', 1)[0]
            measures_module_name = f"{package}.measures"

            try:
                module = importlib.import_module(measures_module_name)
            except ImportError:
                logger.debug(f"No Python measures module at {measures_module_name}")
                return None

            # Look for {ModelName}Measures class
            class_name = ''.join(
                word.title() for word in self.model_name.replace('.', '_').split('_')
            ) + 'Measures'

            if hasattr(module, class_name):
                measures_class = getattr(module, class_name)
                instance = measures_class(self)
                logger.info(f"Loaded Python measures for model '{self.model_name}'")
                return instance

            logger.debug(f"Measures class '{class_name}' not found in {measures_module_name}")
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

    def _ensure_active_spark_session(self) -> bool:
        """
        Ensure Spark session is registered as active for Delta Lake 4.x.

        Delta Lake 4.x internally calls SparkSession.active() which requires
        the session to be registered in thread-local storage. This can become
        unregistered between operations.

        Returns:
            True if session is active after registration, False otherwise
        """
        if self.backend != 'spark':
            return True

        try:
            # Get the actual SparkSession from the connection wrapper
            spark = getattr(self.connection, 'spark', None) or self.connection

            if spark is None:
                logger.error("SPARK SESSION IS NONE - cannot register")
                return False

            # Check if spark has required attributes
            if not hasattr(spark, '_jvm') or not hasattr(spark, '_jsparkSession'):
                logger.error(f"Invalid SparkSession object: {type(spark)}")
                return False

            jvm = spark._jvm
            jss = spark._jsparkSession

            # Check state BEFORE registration
            before_active = jvm.org.apache.spark.sql.SparkSession.getActiveSession()
            before_state = "PRESENT" if before_active.isDefined() else "EMPTY"

            # Re-register with JVM thread-local storage
            jvm.org.apache.spark.sql.SparkSession.setActiveSession(jss)
            jvm.org.apache.spark.sql.SparkSession.setDefaultSession(jss)

            # Verify state AFTER registration
            after_active = jvm.org.apache.spark.sql.SparkSession.getActiveSession()
            after_state = "PRESENT" if after_active.isDefined() else "EMPTY"

            if after_state == "EMPTY":
                logger.error(f"Session registration FAILED: before={before_state}, after={after_state}")
                return False

            logger.debug(f"Session state: before={before_state}, after={after_state}")
            return True

        except Exception as e:
            logger.error(f"Failed to register Spark session: {e}", exc_info=True)
            return False

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
        """Backend-agnostic column selection with fallback for mismatched names.

        Handles the case where v4 source aliases reference raw API column names
        (e.g., 'Symbol') but Bronze already has normalized names (e.g., 'ticker').

        Strategy:
        1. Build a raw->clean column name map from aliases where the source
           doesn't exist in Bronze but the output name does.
        2. For simple column refs: fall back to the output name.
        3. For expressions: replace raw column refs with clean names.
        """
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")
            existing_cols = set(df.columns)

            # Build raw-to-clean column name map for expression rewriting.
            # If alias says [ticker, Symbol] and Bronze has 'ticker' not 'Symbol',
            # then 'Symbol' -> 'ticker' is a replacement we can apply in expressions.
            col_remap = {}
            for out_name, expr in select_config.items():
                if expr not in existing_cols and out_name in existing_cols:
                    col_remap[expr] = out_name

            cols = []
            for out_name, expr in select_config.items():
                if expr in existing_cols:
                    # Direct column reference matches a Bronze column
                    cols.append(F.col(expr).alias(out_name))
                elif out_name in existing_cols and expr not in col_remap:
                    # Simple column ref that doesn't exist — use output name
                    cols.append(F.col(out_name))
                else:
                    # Expression (computed column, literal, etc.)
                    # Replace raw API column names with Bronze names
                    resolved = expr
                    for raw, clean in col_remap.items():
                        resolved = resolved.replace(raw, clean)
                    # Bare "null" produces a void/NullType column that DuckDB delta
                    # extension cannot read. Cast to BIGINT so Delta log has a real type.
                    if resolved.strip().lower() == "null":
                        resolved = "CAST(null AS BIGINT)"
                    try:
                        cols.append(F.expr(resolved).alias(out_name))
                    except Exception:
                        logger.warning(
                            f"Select: cannot resolve '{resolved}' for '{out_name}', using NULL"
                        )
                        cols.append(F.lit(None).cast("long").alias(out_name))
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
        # Ensure Spark session is active before Delta reads
        self._ensure_active_spark_session()

        if self._graph_builder is None:
            from de_funk.models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)
        self._dims, self._facts = self._graph_builder.build()
        self._is_built = True
        return self._dims, self._facts

    def ensure_built(self):
        """
        Lazy build pattern - only build when needed.

        First tries to load from Silver layer (if it exists).
        Falls back to building from Bronze if Silver doesn't exist.
        """
        if not self._is_built:
            # Ensure Spark session is active before Delta reads
            self._ensure_active_spark_session()

            # Try loading from Silver first (faster, no Bronze transformation)
            if self._load_from_silver():
                self._is_built = True
                return

            # Fall back to building from Bronze
            if self._graph_builder is None:
                from de_funk.models.base.graph_builder import GraphBuilder
                self._graph_builder = GraphBuilder(self)
            self._dims, self._facts = self._graph_builder.build()
            self._is_built = True

    def _get_silver_root(self) -> str:
        """Get the Silver layer root path for this model."""
        model_silver_key = f"{self.model_name}_silver"
        roots = self.storage_cfg.get('roots', {})

        if model_silver_key in roots:
            return roots[model_silver_key]

        # Fallback to generic silver root
        silver_root = roots.get('silver', 'storage/silver')
        return f"{silver_root}/{self.model_name}"

    def _load_from_silver(self) -> bool:
        """
        Try to load model tables directly from Silver layer.

        Returns:
            True if successfully loaded from Silver, False otherwise
        """
        from pathlib import Path

        silver_root = self._get_silver_root()
        silver_path = Path(silver_root)

        # Check if silver path exists
        if not silver_path.exists():
            logger.debug(f"Silver path does not exist: {silver_path}")
            return False

        dims_path = silver_path / "dims"
        facts_path = silver_path / "facts"

        # Check if we have at least dims or facts directory
        if not dims_path.exists() and not facts_path.exists():
            logger.debug(f"No dims or facts directories in Silver: {silver_path}")
            return False

        logger.info(f"Loading {self.model_name} from Silver layer: {silver_path}")

        self._dims = {}
        self._facts = {}

        try:
            # Load dimensions
            if dims_path.exists():
                for table_dir in dims_path.iterdir():
                    if table_dir.is_dir():
                        table_name = table_dir.name
                        df = self._read_silver_table(str(table_dir))
                        if df is not None:
                            self._dims[table_name] = df
                            logger.debug(f"  Loaded dim: {table_name}")

            # Load facts
            if facts_path.exists():
                for table_dir in facts_path.iterdir():
                    if table_dir.is_dir():
                        table_name = table_dir.name
                        df = self._read_silver_table(str(table_dir))
                        if df is not None:
                            self._facts[table_name] = df
                            logger.debug(f"  Loaded fact: {table_name}")

            if self._dims or self._facts:
                logger.info(f"  Loaded from Silver: {len(self._dims)} dims, {len(self._facts)} facts")
                return True
            else:
                logger.warning(f"  Silver layer exists but no tables found")
                return False

        except Exception as e:
            logger.warning(f"Failed to load from Silver layer: {e}")
            return False

    def _get_spark_session(self):
        """
        Get SparkSession with multiple fallback strategies.

        Strategy order:
        1. Get from connection wrapper (self.connection.spark)
        2. Use connection directly if it's a SparkSession
        3. Use SparkSession.builder.getOrCreate() as final fallback

        Returns:
            SparkSession or None
        """
        # Strategy 1: Get from connection wrapper
        spark = getattr(self.connection, 'spark', None)
        if spark is not None and hasattr(spark, '_jvm'):
            return spark

        # Strategy 2: Connection might be SparkSession directly
        if hasattr(self.connection, '_jvm'):
            return self.connection

        # Strategy 3: getOrCreate() - always works if a session exists
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            logger.debug("Using SparkSession.builder.getOrCreate() fallback")
            return spark
        except Exception as e:
            logger.error(f"All SparkSession retrieval strategies failed: {e}")
            return None

    def _read_silver_table(self, path: str):
        """
        Read a table from Silver layer (auto-detects Delta/Parquet).

        Args:
            path: Path to the table directory

        Returns:
            DataFrame or None if read fails
        """
        from pathlib import Path

        table_path = Path(path)
        is_delta = (table_path / "_delta_log").exists()
        format_type = "delta" if is_delta else "parquet"

        logger.debug(f"Reading Silver table: {path} (format={format_type})")

        try:
            if self.backend == 'spark':
                spark = self._get_spark_session()
                if spark is None:
                    logger.error(f"Could not get SparkSession for reading {path}")
                    return None

                if is_delta:
                    df = spark.read.format("delta").load(path)
                else:
                    df = spark.read.parquet(path)

                logger.debug(f"  Successfully read {path}")
                return df
            else:
                # DuckDB
                return self.connection.read_table(path)

        except Exception as e:
            logger.warning(f"Failed to read Silver table {path}: {e}")
            return None

    # ============================================================
    # TABLE ACCESS (delegated to TableAccessor)
    # ============================================================

    def _get_table_accessor(self):
        """Get or create TableAccessor instance."""
        if self._table_accessor is None:
            from de_funk.models.base.table_accessor import TableAccessor
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

    def get_fk_relationships(self, table_name: str) -> Dict[str, str]:
        """Get foreign key relationships for a table."""
        return self._get_table_accessor().get_fk_relationships(table_name)

    def get_relations(self) -> Dict[str, List[str]]:
        """Return relationship graph from edges config."""
        return self._get_table_accessor().get_relations()

    def get_denormalized(
        self,
        fact_table: str,
        include_dims: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> DataFrame:
        """
        Get fact table with dimension columns joined in.

        Joins the specified fact table with its related dimension tables
        based on graph edges, returning a denormalized view with natural
        keys (ticker, trade_date) instead of just foreign keys (security_id, date_id).

        Args:
            fact_table: Name of fact table (e.g., 'fact_stock_prices')
            include_dims: Dimension tables to join. If None, auto-detects
                         from graph edges connected to the fact table.
            columns: Specific columns to include. If None, includes all columns
                    from fact and joined dimensions.

        Returns:
            DataFrame with fact + dimension columns joined

        Example:
            # Get stock prices with ticker, sector, exchange from dim_stock
            df = model.get_denormalized('fact_stock_prices')

            # Get prices with only specific dimensions
            df = model.get_denormalized('fact_stock_prices', include_dims=['dim_stock'])

            # Get prices with only specific columns
            df = model.get_denormalized('fact_stock_prices', columns=['ticker', 'trade_date', 'close', 'sector'])
        """
        self.ensure_built()

        # Get the fact table
        fact_df = self.get_table(fact_table)

        # Get graph edges to find dimension relationships
        graph_config = self.model_cfg.get('graph', {})
        edges_config = graph_config.get('edges', {})

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        if isinstance(edges_config, dict):
            edges = list(edges_config.values())
        else:
            edges = edges_config

        # Find edges FROM this fact table TO dimension tables
        dim_joins = []
        for edge in edges:
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')

            # Skip if not from our fact table
            if edge_from != fact_table:
                continue

            # Skip cross-model edges (e.g., "core.dim_calendar")
            if '.' in edge_to:
                continue

            # Skip if include_dims specified and this dim not in list
            if include_dims is not None and edge_to not in include_dims:
                continue

            # Only join dimension tables (dim_*)
            if not edge_to.startswith('dim_'):
                continue

            # Parse join condition
            # Note: YAML 1.1 treats 'on' as boolean True, so we check both keys
            on_conditions = edge.get('on', edge.get(True, []))  # Handle YAML 1.1 'on' -> True quirk
            if on_conditions:
                join_cols = self._parse_join_conditions(on_conditions)
                dim_joins.append({
                    'dim_table': edge_to,
                    'join_cols': join_cols
                })

        # Execute joins
        result_df = fact_df

        if self.backend == 'spark':
            for join_info in dim_joins:
                dim_table = join_info['dim_table']
                join_cols = join_info['join_cols']

                try:
                    dim_df = self.get_table(dim_table)

                    # Build join condition
                    join_cond = None
                    for left_col, right_col in join_cols:
                        cond = result_df[left_col] == dim_df[right_col]
                        join_cond = cond if join_cond is None else join_cond & cond

                    # Drop duplicate join columns from dim to avoid ambiguity
                    dim_cols_to_drop = [rc for lc, rc in join_cols if lc == rc]
                    if dim_cols_to_drop:
                        dim_df = dim_df.drop(*dim_cols_to_drop)

                    result_df = result_df.join(dim_df, join_cond, 'left')
                    logger.debug(f"Joined {fact_table} with {dim_table}")
                except Exception as e:
                    logger.warning(f"Failed to join {dim_table}: {e}")
        else:
            # DuckDB backend
            for join_info in dim_joins:
                dim_table = join_info['dim_table']
                join_cols = join_info['join_cols']

                try:
                    dim_df = self.get_table(dim_table)

                    # For DuckDB/pandas, use merge
                    import pandas as pd

                    # Convert to pandas if needed
                    if hasattr(result_df, 'df'):
                        result_pdf = result_df.df()
                    elif isinstance(result_df, pd.DataFrame):
                        result_pdf = result_df
                    else:
                        result_pdf = result_df

                    if hasattr(dim_df, 'df'):
                        dim_pdf = dim_df.df()
                    elif isinstance(dim_df, pd.DataFrame):
                        dim_pdf = dim_df
                    else:
                        dim_pdf = dim_df

                    # Build merge keys
                    left_keys = [lc for lc, rc in join_cols]
                    right_keys = [rc for lc, rc in join_cols]

                    # Drop duplicate columns from dim before merge
                    dim_cols_to_drop = [rc for lc, rc in join_cols if lc == rc and rc in dim_pdf.columns]
                    if dim_cols_to_drop:
                        dim_pdf = dim_pdf.drop(columns=dim_cols_to_drop)

                    result_pdf = result_pdf.merge(
                        dim_pdf,
                        left_on=left_keys,
                        right_on=right_keys,
                        how='left',
                        suffixes=('', f'_{dim_table}')
                    )
                    result_df = result_pdf
                    logger.debug(f"Joined {fact_table} with {dim_table}")
                except Exception as e:
                    logger.warning(f"Failed to join {dim_table}: {e}")

        # Filter to specific columns if requested
        if columns is not None:
            if self.backend == 'spark':
                available = set(result_df.columns)
                valid_cols = [c for c in columns if c in available]
                if valid_cols:
                    result_df = result_df.select(*valid_cols)
            else:
                import pandas as pd
                if isinstance(result_df, pd.DataFrame):
                    available = set(result_df.columns)
                    valid_cols = [c for c in columns if c in available]
                    if valid_cols:
                        result_df = result_df[valid_cols]

        return result_df

    def _parse_join_conditions(self, conditions: List[str]) -> List[Tuple[str, str]]:
        """
        Parse join conditions from graph edge config.

        Args:
            conditions: List of conditions like ["security_id=security_id"]

        Returns:
            List of (left_col, right_col) tuples
        """
        result = []
        for cond in conditions:
            if '=' in cond:
                parts = cond.split('=')
                if len(parts) == 2:
                    result.append((parts[0].strip(), parts[1].strip()))
        return result

    def get_metadata(self) -> Dict[str, Any]:
        """Return model metadata."""
        return self._get_table_accessor().get_metadata()

    # ============================================================
    # MEASURE CALCULATIONS (delegated to MeasureCalculator)
    # ============================================================

    def _get_measure_calculator(self):
        """Get or create MeasureCalculator instance."""
        if self._measure_calculator is None:
            from de_funk.models.base.measure_calculator import MeasureCalculator
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
        format: Optional[str] = None,
        mode: str = "overwrite",
        partition_by: Optional[Dict[str, List[str]]] = None,
        quiet: bool = False
    ):
        """Write all model tables to storage.

        Args:
            format: Output format. If None, reads from model config (storage.format),
                   then storage.json defaults, then falls back to "delta".
        """
        if self._model_writer is None:
            from de_funk.models.base.model_writer import ModelWriter
            self._model_writer = ModelWriter(self)
        return self._model_writer.write_tables(
            output_root, format, mode, partition_by, quiet=quiet
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
        """Handle built-in transform markers. Override to add model-specific loaders."""
        transform = node_config.get("_transform")
        if transform == "window":
            return self._build_window_node(node_id, node_config)
        return None

    def _build_window_node(
        self, node_id: str, node_config: Dict
    ) -> Optional[DataFrame]:
        """
        Build a table by applying indicator configs from the schema to a sibling node.
        Delegates to DomainModel._build_window_node if available (has full implementation).
        Base implementation: skip with warning if source not in _building_nodes.
        """
        from de_funk.models.base.indicators import apply_indicator

        source = node_config.get("_window_source", "")
        schema = node_config.get("_schema", [])

        if not source:
            logger.warning(f"Window node '{node_id}': no _window_source — skipping")
            return None

        building = getattr(self, "_building_nodes", {})
        if source not in building:
            logger.warning(
                f"Window node '{node_id}': source '{source}' not yet built — "
                f"ensure it is in an earlier phase"
            )
            return None

        df = building[source]
        cols = set(df.columns)

        if "security_id" in cols and "date_id" in cols:
            partition_col, order_col = "security_id", "date_id"
        elif "ticker" in cols and "trade_date" in cols:
            partition_col, order_col = "ticker", "trade_date"
        else:
            logger.error(
                f"Window node '{node_id}': cannot determine partition/order columns "
                f"from {sorted(cols)[:10]}"
            )
            return None

        logger.info(
            f"Building window table '{node_id}' from '{source}' "
            f"(partition={partition_col}, order={order_col})"
        )

        for col_def in schema:
            if not isinstance(col_def, list):
                continue
            col_name = col_def[0]
            options  = col_def[4] if len(col_def) >= 5 else {}
            if not isinstance(options, dict):
                continue
            if "indicator" in options:
                try:
                    df = apply_indicator(df, col_name, options, partition_col, order_col)
                except Exception as e:
                    logger.error(
                        f"Window node '{node_id}': indicator '{col_name}' failed: {e}",
                        exc_info=True,
                    )
            elif "derived" in options:
                try:
                    from pyspark.sql import functions as F  # noqa: PLC0415
                    df = df.withColumn(col_name, F.expr(options["derived"]))
                except Exception as e:
                    logger.warning(
                        f"Window node '{node_id}': derive '{col_name}' failed: {e}"
                    )

        col_names = [c[0] for c in schema if isinstance(c, list)]
        available = [c for c in col_names if c in df.columns]
        if available:
            df = df.select(*available)

        return df
