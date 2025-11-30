"""
Graph Builder for BaseModel.

Handles building model tables from Bronze layer:
- Node loading from Bronze
- Transformations (select, derive, filters)
- Cross-model reference resolution
- Join utilities

This module is used by BaseModel via composition.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any


class GraphBuilder:
    """
    Builds model graph from YAML configuration.

    Handles loading nodes from Bronze, applying transformations,
    and resolving cross-model references.
    """

    def __init__(self, model):
        """
        Initialize graph builder.

        Args:
            model: BaseModel instance (provides connection, config, etc.)
        """
        self.model = model

    @property
    def connection(self):
        return self.model.connection

    @property
    def backend(self) -> str:
        return self.model.backend

    @property
    def model_cfg(self) -> Dict:
        return self.model.model_cfg

    @property
    def storage_router(self):
        return self.model.storage_router

    @property
    def session(self):
        return self.model.session

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
        self.model.before_build()

        # Build all tables from Bronze
        nodes = self._build_nodes()

        # Separate by naming convention
        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {k: v for k, v in nodes.items() if k.startswith("fact_")}

        # Call after hook (allows model-specific customization)
        dims, facts = self.model.after_build(dims, facts)

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
            custom_df = self.model.custom_node_loading(node_id, node_config)
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
                df = self.model._apply_filters(df, node_config['filters'])

            # Apply select (column selection/aliasing)
            if 'select' in node_config and node_config['select']:
                df = self.model._select_columns(df, node_config['select'])

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
            from models.api.dal import BronzeTable
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
            from pyspark.sql import functions as F

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

    def resolve_node(self, node_id: str, nodes: Dict[str, DataFrame]) -> DataFrame:
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


class JoinUtils:
    """
    Utility functions for joining DataFrames.

    Used by GraphBuilder and other components that need join operations.
    """

    @staticmethod
    def join_pairs_from_strings(specs: List[str]) -> List[Tuple[str, str]]:
        """
        Parse join specifications like ["ticker=ticker", "date=date"]
        into [(left_col, right_col), ...]
        """
        pairs = []
        for spec in specs:
            left, right = spec.split('=', 1)
            pairs.append((left.strip(), right.strip()))
        return pairs

    @staticmethod
    def infer_join_pairs(left: DataFrame, right: DataFrame) -> List[Tuple[str, str]]:
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

    @staticmethod
    def join_with_dedupe(
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
        from pyspark.sql import functions as F

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
