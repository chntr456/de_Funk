"""
BaseModel - Generic model class with YAML-driven graph building.

All domain models inherit from BaseModel, which provides:
- Generic node loading from Bronze
- Graph edge validation
- Path materialization (joins)
- Table access methods
- Metadata extraction

The YAML config is the source of truth for the model structure.
"""

from abc import ABC
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
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

        def bronze_path(self, logical_table: str) -> str:
            root = self.storage_cfg["roots"]["bronze"].rstrip("/")
            rel = self.storage_cfg["tables"][logical_table]["rel"]
            return f"{root}/{rel}"

        def silver_path(self, logical_rel: str) -> str:
            root = self.storage_cfg["roots"]["silver"].rstrip("/")
            return f"{root}/{logical_rel}"

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

    def __init__(self, connection, storage_cfg: Dict, model_cfg: Dict, params: Dict = None):
        """
        Initialize a model.

        Args:
            connection: Database connection (Spark or DuckDB)
            storage_cfg: Storage configuration (roots, table mappings)
            model_cfg: Model configuration from YAML
            params: Runtime parameters for customization
        """
        self.connection = connection
        self.storage_cfg = storage_cfg
        self.model_cfg = model_cfg
        self.params = params or {}
        self.model_name = model_cfg.get('model', 'unknown')

        # Session reference for cross-model access (injected by UniversalSession)
        self.session = None

        # Lazy-loaded caches
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Storage router for path resolution
        self.storage_router = StorageRouter(self.storage_cfg)

        # Detect backend type
        self._backend = self._detect_backend()

        # Unified measure executor (lazy-loaded)
        self._measure_executor = None

        # Query planner for dynamic joins (lazy-loaded)
        self._query_planner = None

        # Python measures module (lazy-loaded)
        self._python_measures = None

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

        Returns:
            MeasureExecutor instance

        Example:
            result = model.measures.execute_measure('avg_close_price', entity_column='ticker')
        """
        if self._measure_executor is None:
            from models.base.measures.executor import MeasureExecutor
            self._measure_executor = MeasureExecutor(self, backend=self.backend)
        return self._measure_executor

    @property
    def query_planner(self):
        """
        Get query planner for dynamic table joins.

        Uses the model's graph edges to plan and execute joins at runtime,
        making materialized views an optional performance optimization.

        Returns:
            GraphQueryPlanner instance

        Example:
            # Get enriched table with dynamic joins
            df = model.query_planner.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange'],
                columns=['ticker', 'close', 'company_name', 'exchange_name']
            )
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
        Python measures handle complex logic that can't be expressed in YAML
        (e.g., rolling windows, correlations, ML models).

        Returns:
            Measures class instance or None if no Python measures defined

        Example:
            # In stocks model
            sharpe = model.python_measures.calculate_sharpe_ratio(
                ticker='AAPL',
                risk_free_rate=0.045,
                window_days=252
            )
        """
        if self._python_measures is None:
            self._python_measures = self._load_python_measures()
        return self._python_measures

    def _load_python_measures(self):
        """
        Load Python measures module for this model.

        Uses ModelConfigLoader to discover and load Python measure classes
        based on the model configuration's measures._python_module setting.

        Returns:
            Measures class instance or None
        """
        try:
            from config.model_loader import ModelConfigLoader
            from pathlib import Path

            # Get models directory from storage config
            models_dir = self.storage_cfg.get('models_dir', 'configs/models')

            # Load Python measures if available
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
        Allows models to load tables from other models via session.load_model().

        Args:
            session: UniversalSession instance
        """
        self.session = session

    def _select_columns(self, df: DataFrame, select_config: Dict[str, str]) -> DataFrame:
        """
        Backend-agnostic column selection.

        Args:
            df: Input DataFrame (Spark or DuckDB)
            select_config: Dict mapping output_name -> expression

        Returns:
            DataFrame with selected/renamed columns
        """
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")
            # Use PySpark
            cols = [
                F.col(expr).alias(out_name)
                for out_name, expr in select_config.items()
            ]
            return df.select(*cols)
        else:
            # DuckDB - use project() method for column selection
            # project() takes column expressions as strings
            col_expressions = [f"{expr} AS {out_name}" for out_name, expr in select_config.items()]
            return df.project(','.join(col_expressions))

    def _apply_filters(self, df: DataFrame, filters: list) -> DataFrame:
        """
        Backend-agnostic filter application.

        Args:
            df: Input DataFrame (Spark or DuckDB)
            filters: List of filter expressions (SQL WHERE clause conditions)

        Returns:
            DataFrame with filters applied
        """
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")
            # Use PySpark - apply each filter using F.expr()
            for filter_expr in filters:
                df = df.filter(F.expr(filter_expr))
            return df
        else:
            # DuckDB - use filter() method with SQL expressions
            for filter_expr in filters:
                df = df.filter(filter_expr)
            return df

    # ============================================================
    # GENERIC GRAPH BUILDING (from company_model.py)
    # ============================================================

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """
        Build model tables from Bronze layer.

        All graph operations (joins, relationships, validation) are handled
        at query time by GraphQueryPlanner and UniversalSession.

        This method simply:
        1. Loads individual tables from Bronze
        2. Applies transformations (select, derive)
        3. Separates into dimensions and facts

        Returns:
            Tuple of (dimensions, facts)
        """
        # Call before hook
        self.before_build()

        # Build all tables from Bronze
        nodes = self._build_nodes()

        # Separate by naming convention
        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {k: v for k, v in nodes.items() if k.startswith("fact_")}

        # Call after hook (allows model-specific customization)
        dims, facts = self.after_build(dims, facts)

        return dims, facts

    def _build_nodes(self) -> Dict[str, DataFrame]:
        """
        Build all nodes from graph.nodes config.

        For each node:
        1. Load from Bronze (via custom loading or default)
        2. Apply select transformations
        3. Apply derive transformations

        Returns:
            Dictionary mapping node_id to DataFrame
        """
        graph = self.model_cfg.get('graph', {})
        nodes = {}

        # Support both dict and list formats for nodes
        nodes_config = graph.get('nodes', {})
        if isinstance(nodes_config, dict):
            # Dict format (modular YAML): {node_id: {from: ..., select: ...}}
            node_items = [(node_id, node_config) for node_id, node_config in nodes_config.items()]
        else:
            # List format (legacy YAML): [{id: node_id, from: ..., select: ...}]
            node_items = [(node_config['id'], node_config) for node_config in nodes_config]

        for node_id, node_config in node_items:

            # Try custom loading first
            custom_df = self.custom_node_loading(node_id, node_config)
            if custom_df is not None:
                nodes[node_id] = custom_df
                continue

            # Check if loading from bronze or from another node
            from_spec = node_config['from']
            if '.' in from_spec:
                # Loading from bronze: bronze.table_name
                layer, table = from_spec.split('.', 1)
                assert layer == 'bronze', f"Node {node_id} must load from bronze, got {layer}"
                df = self._load_bronze_table(table)
            else:
                # Loading from another node (must already be built)
                parent_node = from_spec
                if parent_node not in nodes:
                    raise ValueError(
                        f"Node {node_id} depends on {parent_node}, but {parent_node} hasn't been built yet. "
                        f"Ensure nodes are defined in dependency order in graph.nodes"
                    )
                df = nodes[parent_node]

            # Apply filters (before select to filter source data)
            if 'filters' in node_config and node_config['filters']:
                df = self._apply_filters(df, node_config['filters'])

            # Apply select (column selection/aliasing)
            if 'select' in node_config and node_config['select']:
                df = self._select_columns(df, node_config['select'])

            # Apply derive (computed columns)
            if 'derive' in node_config and node_config['derive']:
                for out_name, expr in node_config['derive'].items():
                    try:
                        df = self._apply_derive(df, out_name, expr, node_id)
                    except Exception as e:
                        # Log warning and skip this derived column
                        # Common reasons: unsupported expressions, nested window functions
                        logger.warning(
                            f"Skipping derived column '{out_name}' in node '{node_id}': {e}"
                        )
                        # Continue with other columns
                        continue

            # Enforce unique_key constraint (deduplication)
            if 'unique_key' in node_config and node_config['unique_key']:
                unique_cols = node_config['unique_key']
                print(f"⚙️  Applying unique_key constraint on {node_id}: deduplicating by {unique_cols}")
                if self.backend == 'spark':
                    df = df.dropDuplicates(unique_cols)
                else:
                    # DuckDB: Convert to pandas if needed, drop duplicates, convert back
                    import pandas as pd
                    if isinstance(df, pd.DataFrame):
                        # Already a pandas DataFrame (from _apply_derive)
                        pdf = df
                    else:
                        # DuckDB relation - convert to pandas
                        pdf = df.df()
                    pdf = pdf.drop_duplicates(subset=unique_cols, keep='last')
                    df = self.connection.conn.from_df(pdf)

            nodes[node_id] = df

        return nodes

    def _load_bronze_table(self, table_name: str) -> DataFrame:
        """
        Load a Bronze table using StorageRouter.

        Args:
            table_name: Logical table name (from storage config)

        Returns:
            DataFrame with merged schema
        """
        # Use backend type to determine how to load
        if self.backend == 'spark':
            if BronzeTable is None:
                raise RuntimeError("PySpark required for Spark backend but not installed")
            # BronzeTable expects SparkSession, not SparkConnection
            bronze = BronzeTable(self.connection.spark, self.storage_router, table_name)
            return bronze.read(merge_schema=True)
        else:
            # DuckDB or other connection types
            path = self.storage_router.bronze_path(table_name)
            return self.connection.read_parquet(path)

    def _apply_derive(self, df: DataFrame, col_name: str, expr: str, node_id: str) -> DataFrame:
        """
        Apply a derive expression to create a computed column.

        Supports:
        - Column references: "ticker" -> F.col("ticker")
        - SHA1 hash: "sha1(ticker)" -> F.sha1(F.col("ticker"))
        - SQL expressions: Window functions, aggregations, etc. via F.expr()

        Args:
            df: Input DataFrame
            col_name: Output column name
            expr: Derive expression (can be any valid SQL expression)
            node_id: Node ID (for error messages)

        Returns:
            DataFrame with new column
        """
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")

            # SHA1 hash (special case for common pattern)
            if expr.startswith('sha1(') and expr.endswith(')'):
                col = expr[5:-1]  # Extract column name
                return df.withColumn(col_name, F.sha1(F.col(col)))

            # Direct column reference
            elif expr in df.columns:
                return df.withColumn(col_name, F.col(expr))

            # Arbitrary SQL expression (window functions, aggregations, etc.)
            else:
                try:
                    return df.withColumn(col_name, F.expr(expr))
                except Exception as e:
                    raise ValueError(
                        f"Failed to apply derive expression '{expr}' in node '{node_id}': {e}"
                    )
        else:
            # DuckDB - use SQL execution for complex expressions
            if expr.startswith('sha1(') and expr.endswith(')'):
                col = expr[5:-1]  # Extract column name
                sql_expr = f"SHA1({col})"
            else:
                # Direct column reference or SQL expression
                sql_expr = expr

            # For complex expressions (especially window functions), use SQL execution
            # Register DataFrame as temp table, execute SQL, return result
            temp_table = f"_temp_{node_id}_{col_name}"

            # Register current DataFrame
            self.connection.conn.register(temp_table, df)

            # Build SQL with all existing columns plus the new derived column
            existing_cols = ', '.join([f'"{c}"' for c in df.columns])
            sql = f"SELECT {existing_cols}, {sql_expr} AS {col_name} FROM {temp_table}"

            # Execute and return result
            result_df = self.connection.conn.execute(sql).fetchdf()

            # Unregister temp table to avoid memory leaks
            self.connection.conn.unregister(temp_table)

            return result_df

    def _resolve_node(self, node_id: str, nodes: Dict[str, DataFrame]) -> DataFrame:
        """
        Resolve a node DataFrame, supporting cross-model references.

        Args:
            node_id: Node identifier (e.g., 'dim_company' or 'core.dim_calendar')
            nodes: Local nodes dictionary

        Returns:
            DataFrame for the node

        Raises:
            ValueError: If node not found
        """
        # Check if it's a cross-model reference (contains dot)
        if '.' in node_id and node_id not in nodes:
            # Cross-model reference: modelname.nodename
            if not self.session:
                raise ValueError(
                    f"Cross-model reference '{node_id}' requires session, "
                    f"but model.session is None. Call model.set_session(session) first."
                )

            model_name, table_name = node_id.split('.', 1)

            # Get the other model from session
            try:
                other_model = self.session.get_model_instance(model_name)
                other_model.ensure_built()

                # Try dimensions first, then facts
                if table_name in other_model._dims:
                    return other_model.get_dimension_df(table_name)
                elif table_name in other_model._facts:
                    return other_model.get_fact_df(table_name)
                else:
                    raise KeyError(
                        f"Table '{table_name}' not found in {model_name}. "
                        f"Available dimensions: {list(other_model._dims.keys())}, "
                        f"Available facts: {list(other_model._facts.keys())}"
                    )
            except Exception as e:
                raise ValueError(
                    f"Cross-model reference '{node_id}' failed: {e}"
                ) from e

        # Local node
        if node_id in nodes:
            return nodes[node_id]

        raise ValueError(f"Node '{node_id}' not found in local nodes or cross-model refs")

    # ============================================================
    # REMOVED: Graph deployment methods
    #
    # The following methods have been removed as part of the graph
    # architecture refactor. All graph operations (joins, relationships,
    # validation) are now handled at query time by:
    # - GraphQueryPlanner (intra-model joins)
    # - UniversalSession (cross-model operations)
    #
    # Removed methods:
    # - _apply_edges(): Edge validation (was already skipped for DuckDB)
    # - _materialize_paths(): Path materialization (was already skipped for DuckDB)
    # - _find_edge(): Helper for above
    #
    # See GRAPH_REFACTOR_SCAN.md for detailed analysis
    # ============================================================

    def _join_pairs_from_strings(self, specs: List[str]) -> List[Tuple[str, str]]:
        """
        Parse join specifications like ["ticker=ticker", "date=date"]
        into [(left_col, right_col), ...]
        """
        pairs = []
        for spec in specs:
            left, right = spec.split('=', 1)
            pairs.append((left.strip(), right.strip()))
        return pairs

    def _infer_join_pairs(self, left: DataFrame, right: DataFrame) -> List[Tuple[str, str]]:
        """
        Infer join keys based on common columns.

        Priority:
        1. ticker (if exists in both)
        2. First common column

        Args:
            left: Left DataFrame
            right: Right DataFrame

        Returns:
            List of (left_col, right_col) tuples
        """
        # Prefer ticker if available
        if 'ticker' in left.columns and 'ticker' in right.columns:
            return [('ticker', 'ticker')]

        # Use first common column
        common = [c for c in left.columns if c in right.columns]
        if common:
            return [(common[0], common[0])]

        raise ValueError(
            f"Cannot infer join keys. "
            f"Left columns: {left.columns}, Right columns: {right.columns}"
        )

    def _join_with_dedupe(
        self,
        left: DataFrame,
        right: DataFrame,
        pairs: List[Tuple[str, str]],
        right_prefix: str,
        how: str = 'left'
    ) -> DataFrame:
        """
        Join two DataFrames while avoiding duplicate columns.

        Deduplication strategy:
        - Join key columns from right side are dropped
        - Columns with same name are prefixed (e.g., dim_company__name)

        Args:
            left: Left DataFrame
            right: Right DataFrame
            pairs: Join key pairs [(left_col, right_col), ...]
            right_prefix: Prefix for duplicate columns (e.g., "dim_company__")
            how: Join type (left, inner, etc.)

        Returns:
            Joined DataFrame with deduplicated columns
        """
        # Build join condition
        cond = None
        for left_col, right_col in pairs:
            c = (left[left_col] == right[right_col])
            cond = c if cond is None else (cond & c)

        # Determine which columns to keep from right
        right_keep = []
        right_join_keys = set(r for _, r in pairs)

        for col in right.columns:
            # Skip join keys (already in left)
            if col in right_join_keys:
                continue

            # Prefix if column exists in left
            alias = col if col not in left.columns else f"{right_prefix}{col}"
            right_keep.append(F.col(col).alias(alias))

        # Perform join
        return left.join(right, cond, how=how).select(left['*'], *right_keep)

    # ============================================================
    # GENERIC TABLE ACCESS
    # ============================================================

    def ensure_built(self):
        """Lazy build pattern - only build when needed"""
        if not self._is_built:
            self._dims, self._facts = self.build()
            self._is_built = True

    def get_table(self, table_name: str) -> DataFrame:
        """
        Get a table by name (searches dims and facts).

        Args:
            table_name: Table identifier

        Returns:
            DataFrame

        Raises:
            KeyError: If table not found
        """
        self.ensure_built()

        if table_name in self._dims:
            return self._dims[table_name]
        elif table_name in self._facts:
            return self._facts[table_name]
        else:
            available = list(self._dims.keys()) + list(self._facts.keys())
            raise KeyError(
                f"Table '{table_name}' not found in {self.model_name} model. "
                f"Available tables: {available}"
            )

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> DataFrame:
        """
        Get table with optional enrichment via dynamic joins.

        Uses graph edges to join related tables at runtime. Falls back to
        materialized views when available for performance.

        Args:
            table_name: Base table name (e.g., 'fact_equity_prices')
            enrich_with: List of tables to join (e.g., ['dim_equity', 'dim_exchange'])
            columns: Columns to select (default: all columns)

        Returns:
            DataFrame with enrichment applied

        Raises:
            ValueError: If no join path exists

        Example:
            # Get prices with company info (dynamic join)
            df = equity_model.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange'],
                columns=['ticker', 'trade_date', 'close', 'company_name', 'exchange_name']
            )

            # System:
            # 1. Checks for materialized view (equity_prices_with_company)
            # 2. If not found, builds join from graph edges
            # 3. Returns enriched DataFrame
        """
        return self.query_planner.get_table_enriched(table_name, enrich_with, columns)

    def get_dimension_df(self, dim_id: str) -> DataFrame:
        """Get a dimension table by ID"""
        self.ensure_built()
        if dim_id not in self._dims:
            raise KeyError(f"Dimension '{dim_id}' not found in {self.model_name}")
        return self._dims[dim_id]

    def get_fact_df(self, fact_id: str) -> DataFrame:
        """Get a fact table by ID"""
        self.ensure_built()
        if fact_id not in self._facts:
            raise KeyError(f"Fact '{fact_id}' not found in {self.model_name}")
        return self._facts[fact_id]

    def has_table(self, table_name: str) -> bool:
        """
        Check if a table exists in this model.

        Args:
            table_name: Table identifier

        Returns:
            True if table exists (in dimensions or facts), False otherwise
        """
        self.ensure_built()
        return table_name in self._dims or table_name in self._facts

    def list_tables(self) -> Dict[str, List[str]]:
        """
        List all available tables.

        Returns:
            Dictionary with 'dimensions' and 'facts' keys
        """
        self.ensure_built()
        return {
            'dimensions': list(self._dims.keys()),
            'facts': list(self._facts.keys())
        }

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """
        Get schema (column definitions) for a table.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary mapping column_name -> data_type

        Raises:
            KeyError: If table not found
        """
        schema_config = self.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema_config.get('dimensions', {}):
            return schema_config['dimensions'][table_name].get('columns', {})

        # Check facts
        if table_name in schema_config.get('facts', {}):
            return schema_config['facts'][table_name].get('columns', {})

        # If not found in schema, try to get columns from actual DataFrame
        try:
            self.ensure_built()
            if table_name in self._dims:
                df = self._dims[table_name]
                return {col: 'unknown' for col in df.columns}
            elif table_name in self._facts:
                df = self._facts[table_name]
                return {col: 'unknown' for col in df.columns}
        except Exception:
            pass

        raise KeyError(f"Table '{table_name}' not found in model schema")

    # ============================================================
    # GENERIC METADATA
    # ============================================================

    def get_relations(self) -> Dict[str, List[str]]:
        """
        Return relationship graph from edges config.

        Returns:
            Dictionary mapping table -> [related_tables]
        """
        graph = self.model_cfg.get('graph', {})
        relations = {}

        for edge in graph.get('edges', []):
            from_table = edge['from']
            to_table = edge['to']

            if from_table not in relations:
                relations[from_table] = []
            relations[from_table].append(to_table)

        return relations

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return model metadata.

        Returns:
            Dictionary with model info
        """
        graph = self.model_cfg.get('graph', {})

        return {
            'name': self.model_name,
            'version': self.model_cfg.get('version', '1.0.0'),
            'description': self.model_cfg.get('description', ''),
            'tags': self.model_cfg.get('tags', []),
            'nodes': [n['id'] for n in graph.get('nodes', [])],
            'paths': [p['id'] for p in graph.get('paths', [])],
            'measures': list(self.model_cfg.get('measures', {}).keys()),
            'dependencies': self.model_cfg.get('depends_on', []),
        }

    # ============================================================
    # MEASURE CALCULATIONS (generic operations on facts)
    # ============================================================

    def calculate_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Calculate any measure defined in model config (UNIFIED METHOD).

        This is the unified measure execution method that works with:
        - All measure types (simple, computed, weighted, Python)
        - All backends (DuckDB, Spark)
        - All domain-specific patterns (weighting, windowing, etc.)

        Replaces calculate_measure_by_entity() with a more flexible interface.

        Args:
            measure_name: Name of measure from config (e.g., 'avg_close_price', 'sharpe_ratio')
            entity_column: Optional entity column to group by (e.g., 'ticker')
            filters: Optional filters to apply
            limit: Optional limit for top-N results
            **kwargs: Additional measure-specific parameters

        Returns:
            QueryResult with data and metadata, or DataFrame for Python measures

        Example:
            # Simple measure (YAML)
            result = model.calculate_measure('avg_close_price', entity_column='ticker', limit=10)

            # Python measure
            result = model.calculate_measure('sharpe_ratio', ticker='AAPL', window_days=252)

            # Access data
            df = result.data if hasattr(result, 'data') else result
        """
        # Check if this is a Python measure
        if self._is_python_measure(measure_name):
            return self._execute_python_measure(measure_name, filters=filters, **kwargs)

        # Otherwise, use standard measure executor
        return self.measures.execute_measure(
            measure_name=measure_name,
            entity_column=entity_column,
            filters=filters,
            limit=limit,
            **kwargs
        )

    def _is_python_measure(self, measure_name: str) -> bool:
        """
        Check if a measure is defined as a Python measure.

        Args:
            measure_name: Name of the measure

        Returns:
            True if it's a Python measure, False otherwise
        """
        measures_config = self.model_cfg.get('measures', {})
        python_measures = measures_config.get('python_measures', {})
        return measure_name in python_measures

    def _execute_python_measure(self, measure_name: str, **kwargs):
        """
        Execute a Python measure function.

        Args:
            measure_name: Name of the Python measure
            **kwargs: Parameters to pass to the measure function

        Returns:
            Result from the Python measure function (typically a DataFrame)

        Raises:
            ValueError: If measure not found or Python measures not available
        """
        # Get measures config
        measures_config = self.model_cfg.get('measures', {})
        python_measures = measures_config.get('python_measures', {})

        if measure_name not in python_measures:
            raise ValueError(f"Python measure '{measure_name}' not found in model '{self.model_name}'")

        # Get Python measures instance
        if self.python_measures is None:
            raise RuntimeError(
                f"No Python measures module loaded for model '{self.model_name}'. "
                f"Check that measures.py exists in models/implemented/{self.model_name}/"
            )

        # Get measure configuration
        measure_cfg = python_measures[measure_name]
        function_name = measure_cfg['function'].split('.')[-1]

        # Get the function from Python measures instance
        if not hasattr(self.python_measures, function_name):
            raise AttributeError(
                f"Function '{function_name}' not found in {self.model_name}.measures module"
            )

        func = getattr(self.python_measures, function_name)

        # Merge params from YAML config and kwargs
        params = measure_cfg.get('params', {}).copy()
        params.update(kwargs)

        logger.info(f"Executing Python measure '{measure_name}' with params: {params}")

        # Execute the function
        try:
            result = func(**params)
            return result
        except Exception as e:
            logger.error(f"Error executing Python measure '{measure_name}': {e}")
            raise

    def calculate_measure_by_entity(
        self,
        measure_name: str,
        entity_column: str,
        limit: Optional[int] = None
    ) -> DataFrame:
        """
        Calculate a measure aggregated by entity (generic method for all models).

        This method reads measure definitions from YAML config and calculates
        them as operations on fact tables. This is proper dimensional modeling:
        measures are calculated from facts, not stored in dimensions.

        Note: Currently only supported for Spark backend

        Args:
            measure_name: Name of measure from config (e.g., 'market_cap', 'avg_close_price')
            entity_column: Column to group by (e.g., 'ticker', 'indicator_id', 'city_id')
            limit: Optional limit for top-N results (ordered descending by measure value)

        Returns:
            DataFrame with columns: <entity_column>, <measure_name>

        Example:
            # In CompanyModel
            df = self.calculate_measure_by_entity('market_cap', 'ticker', limit=10)
            # Returns: DataFrame with [ticker, market_cap]

            # In MacroModel
            df = self.calculate_measure_by_entity('avg_value', 'indicator_id', limit=5)
            # Returns: DataFrame with [indicator_id, avg_value]

        Raises:
            ValueError: If measure not defined in config
        """
        # Measure calculations not yet implemented for DuckDB
        if self.backend == 'duckdb':
            raise NotImplementedError(
                f"Measure calculations not yet supported for DuckDB backend. "
                f"Use Spark backend for measure: '{measure_name}'"
            )

        from pyspark.sql import functions as F

        # Get measure configuration from YAML
        measures = self.model_cfg.get('measures', {})

        if measure_name not in measures:
            available = list(measures.keys())
            raise ValueError(
                f"Measure '{measure_name}' not defined in {self.model_name}. "
                f"Available measures: {available}"
            )

        measure_config = measures[measure_name]

        # Get source table and column
        source = measure_config.get('source', '')
        if '.' not in source:
            raise ValueError(f"Measure source must be 'table.column', got: {source}")

        table_name, column_name = source.split('.', 1)

        # Get the source table
        source_table = self.get_table(table_name)

        # Calculate measure based on type
        measure_type = measure_config.get('type', 'simple')
        aggregation = measure_config.get('aggregation', 'avg')

        if measure_type == 'computed':
            # Computed measure with custom expression (e.g., close * volume)
            expression = measure_config.get('expression', '')
            if not expression:
                raise ValueError(
                    f"Computed measure '{measure_name}' requires 'expression' in config"
                )

            result = (
                source_table
                .withColumn('_measure_value', F.expr(expression))
                .groupBy(entity_column)
                .agg(F.avg('_measure_value').alias(measure_name))
            )

        else:
            # Simple aggregation measure (e.g., avg, sum, max)
            agg_func = getattr(F, aggregation, F.avg)

            result = (
                source_table
                .groupBy(entity_column)
                .agg(agg_func(F.col(column_name)).alias(measure_name))
            )

        # Filter nulls and order by measure value descending
        result = (
            result
            .filter(F.col(measure_name).isNotNull())
            .orderBy(F.desc(measure_name))
        )

        # Apply limit if specified
        if limit:
            result = result.limit(limit)

        return result

    # ============================================================
    # PERSISTENCE (write to storage)
    # ============================================================

    def write_tables(
        self,
        output_root: Optional[str] = None,
        format: str = "parquet",
        mode: str = "overwrite",
        use_optimized_writer: bool = True,
        partition_by: Optional[Dict[str, List[str]]] = None
    ):
        """
        Write all model tables to storage.

        This is the standard way to persist a model's Silver layer.
        Uses optimized ParquetLoader by default for better performance.

        Args:
            output_root: Root path for output (defaults to storage_cfg silver root for this model)
            format: Output format (parquet, delta, etc.)
            mode: Write mode (overwrite, append, etc.)
            use_optimized_writer: Use ParquetLoader for optimized writes (recommended)
            partition_by: Optional dict of table_name -> partition_columns

        Returns:
            Dictionary with write statistics

        Example:
            model = CompanyModel(...)
            stats = model.write_tables(
                output_root="storage/silver/company",
                partition_by={"fact_prices": ["trade_date"]}
            )
        """
        # Ensure model is built
        self.ensure_built()

        # Determine output root
        if output_root is None:
            # Use storage config to find model's silver root
            model_silver_key = f"{self.model_name}_silver"
            if model_silver_key in self.storage_cfg.get('roots', {}):
                output_root = self.storage_cfg['roots'][model_silver_key]
            else:
                # Fallback to generic silver root
                output_root = f"{self.storage_cfg.get('roots', {}).get('silver', 'storage/silver')}/{self.model_name}"

        print(f"\n{'=' * 70}")
        print(f"Writing {self.model_name.upper()} Model to Silver Layer")
        print(f"{'=' * 70}")
        print(f"Output root: {output_root}")
        print(f"Format: {format}")
        print(f"Mode: {mode}")
        print(f"Optimized writer: {use_optimized_writer}")

        stats = {
            'dimensions': {},
            'facts': {},
            'total_rows': 0,
            'total_tables': 0
        }

        # Use optimized ParquetLoader if requested and format is parquet
        if use_optimized_writer and format == "parquet":
            from models.base.parquet_loader import ParquetLoader
            loader = ParquetLoader(root=output_root)  # Use output_root directly

            # Write dimensions
            print(f"\nWriting Dimensions:")
            for name, df in self._dims.items():
                print(f"  Writing {name}...")
                row_count = df.count()

                # ParquetLoader expects relative path from output_root
                rel_path = f"dims/{name}"
                loader.write_dim(rel_path, df, row_count=row_count)

                stats['dimensions'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1
                print(f"    ✓ {row_count:,} rows")

            # Write facts
            print(f"\nWriting Facts:")
            for name, df in self._facts.items():
                print(f"  Writing {name}...")
                # Count rows BEFORE optimizations (more memory-efficient)
                row_count = df.count()
                print(f"    Rows: {row_count:,}")

                # Determine sort columns for optimal query performance
                sort_by = partition_by.get(name, []) if partition_by else []
                if not sort_by:
                    # Default: use common date/time columns if present
                    columns = df.columns
                    for date_col in ['trade_date', 'date', 'publish_date', 'timestamp']:
                        if date_col in columns:
                            sort_by = [date_col]
                            if 'ticker' in columns:
                                sort_by.append('ticker')
                            elif 'symbol' in columns:
                                sort_by.append('symbol')
                            break

                rel_path = f"facts/{name}"
                # Pass pre-computed row_count to avoid re-counting after sort/coalesce
                loader.write_fact(rel_path, df, sort_by=sort_by, row_count=row_count)

                stats['facts'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1

        else:
            # Standard Spark writer (fallback)
            print("\nUsing standard Spark writer...")

            # Write dimensions
            print(f"\nWriting Dimensions:")
            for name, df in self._dims.items():
                path = f"{output_root}/dims/{name}"
                print(f"  Writing {name} to {path}...")

                writer = df.write.mode(mode).format(format)
                if partition_by and name in partition_by:
                    writer = writer.partitionBy(partition_by[name])

                writer.save(path)
                row_count = df.count()
                stats['dimensions'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1
                print(f"    ✓ {row_count:,} rows")

            # Write facts
            print(f"\nWriting Facts:")
            for name, df in self._facts.items():
                path = f"{output_root}/facts/{name}"
                print(f"  Writing {name} to {path}...")

                writer = df.write.mode(mode).format(format)
                if partition_by and name in partition_by:
                    writer = writer.partitionBy(partition_by[name])

                writer.save(path)
                row_count = df.count()
                stats['facts'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1
                print(f"    ✓ {row_count:,} rows")

        print(f"\n{'=' * 70}")
        print(f"✓ Silver Layer Write Complete")
        print(f"{'=' * 70}")
        print(f"Total tables written: {stats['total_tables']}")
        print(f"Total rows written: {stats['total_rows']:,}")
        print(f"  - Dimensions: {len(stats['dimensions'])} tables, {sum(stats['dimensions'].values()):,} rows")
        print(f"  - Facts: {len(stats['facts'])} tables, {sum(stats['facts'].values()):,} rows")

        return stats

    # ============================================================
    # EXTENSION POINTS (override in subclasses)
    # ============================================================

    def before_build(self):
        """
        Hook called before build().
        Override for custom pre-processing.
        """
        pass

    def after_build(
        self,
        dims: Dict[str, DataFrame],
        facts: Dict[str, DataFrame]
    ) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """
        Hook called after build().
        Override for custom post-processing.

        Args:
            dims: Built dimensions
            facts: Built facts

        Returns:
            Modified (dims, facts)
        """
        return dims, facts

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """
        Override to customize how specific nodes are loaded.

        Args:
            node_id: Node identifier
            node_config: Node configuration from YAML

        Returns:
            DataFrame if custom loading needed, None to use default
        """
        return None
