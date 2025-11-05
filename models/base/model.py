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
from typing import Dict, Any, Optional, List, Tuple
from pyspark.sql import DataFrame, functions as F


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

        # Lazy-loaded caches
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Storage router for path resolution
        from models.api.dal import StorageRouter
        self.storage_router = StorageRouter(self.storage_cfg)

    # ============================================================
    # GENERIC GRAPH BUILDING (from company_model.py)
    # ============================================================

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """
        Generic build process - works for any model with YAML config.

        Steps:
        1. Build nodes from schema (read Bronze, apply transformations)
        2. Validate edges (ensure join paths exist)
        3. Materialize paths (create joined views)
        4. Separate into dims and facts

        Returns:
            Tuple of (dimensions, facts)
        """
        # Call before hook
        self.before_build()

        # Build graph
        nodes = self._build_nodes()
        self._apply_edges(nodes)
        paths = self._materialize_paths(nodes)

        # Separate by naming convention
        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {
            **{k: v for k, v in nodes.items() if k.startswith("fact_")},
            **paths
        }

        # Call after hook
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

        for node_config in graph.get('nodes', []):
            node_id = node_config['id']

            # Try custom loading first
            custom_df = self.custom_node_loading(node_id, node_config)
            if custom_df is not None:
                nodes[node_id] = custom_df
                continue

            # Default: load from Bronze
            layer, table = node_config['from'].split('.', 1)
            assert layer == 'bronze', f"Node {node_id} must load from bronze, got {layer}"

            # Load Bronze table
            df = self._load_bronze_table(table)

            # Apply select (column selection/aliasing)
            if 'select' in node_config and node_config['select']:
                cols = [
                    F.col(expr).alias(out_name)
                    for out_name, expr in node_config['select'].items()
                ]
                df = df.select(*cols)

            # Apply derive (computed columns)
            if 'derive' in node_config and node_config['derive']:
                for out_name, expr in node_config['derive'].items():
                    df = self._apply_derive(df, out_name, expr, node_id)

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
        from models.api.dal import BronzeTable

        # Use connection type to determine how to load
        if hasattr(self.connection, 'read'):  # Spark
            bronze = BronzeTable(self.connection, self.storage_router, table_name)
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
        - More expressions can be added as needed

        Args:
            df: Input DataFrame
            col_name: Output column name
            expr: Derive expression
            node_id: Node ID (for error messages)

        Returns:
            DataFrame with new column
        """
        # SHA1 hash
        if expr.startswith('sha1(') and expr.endswith(')'):
            col = expr[5:-1]  # Extract column name
            return df.withColumn(col_name, F.sha1(F.col(col)))

        # Direct column reference
        elif expr in df.columns:
            return df.withColumn(col_name, F.col(expr))

        # Unknown expression
        else:
            raise ValueError(
                f"Unsupported derive expression '{expr}' in node '{node_id}'. "
                f"Supported: column references, sha1(column)"
            )

    def _apply_edges(self, nodes: Dict[str, DataFrame]) -> None:
        """
        Validate that edges exist between nodes.

        Does a dry-run join with limit(1) to validate:
        - Both nodes exist
        - Join columns exist
        - Join is valid

        Args:
            nodes: Dictionary of node_id -> DataFrame
        """
        graph = self.model_cfg.get('graph', {})

        for edge in graph.get('edges', []):
            from_id = edge['from']
            to_id = edge['to']

            # Validate nodes exist
            if from_id not in nodes:
                raise ValueError(f"Edge source '{from_id}' not found in nodes")
            if to_id not in nodes:
                raise ValueError(f"Edge target '{to_id}' not found in nodes")

            # Get DataFrames
            left = nodes[from_id]
            right = nodes[to_id]

            # Get join keys
            pairs = (
                self._join_pairs_from_strings(edge['on'])
                if edge.get('on')
                else self._infer_join_pairs(left, right)
            )

            # Dry-run validation (limit to keep it cheap)
            try:
                _ = left.limit(1).join(
                    right.limit(1),
                    on=[left[l] == right[r] for l, r in pairs],
                    how='left'
                )
            except Exception as e:
                raise ValueError(
                    f"Edge validation failed: {from_id} -> {to_id}. "
                    f"Join pairs: {pairs}. Error: {e}"
                )

    def _materialize_paths(self, nodes: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        """
        Materialize path definitions by joining nodes.

        Paths represent materialized views (e.g., fact_prices joined with dim_company).

        Args:
            nodes: Dictionary of node_id -> DataFrame

        Returns:
            Dictionary of path_id -> joined DataFrame
        """
        graph = self.model_cfg.get('graph', {})
        paths = {}

        for path_config in graph.get('paths', []):
            path_id = path_config['id']
            hops_spec = path_config['hops']

            # Parse hops into chain
            # Supports: "fact_prices -> dim_company -> dim_exchange"
            # Or: ["fact_prices", "dim_company", "dim_exchange"]
            if isinstance(hops_spec, str):
                chain = [h.strip() for h in hops_spec.split('->')]
            elif isinstance(hops_spec, list):
                if len(hops_spec) == 1 and '->' in hops_spec[0]:
                    chain = [h.strip() for h in hops_spec[0].split('->')]
                else:
                    chain = hops_spec
            else:
                raise ValueError(f"Invalid hops format for path {path_id}: {hops_spec}")

            # Start with first node
            if chain[0] not in nodes:
                raise ValueError(f"Path base '{chain[0]}' not found in nodes")

            df = nodes[chain[0]]

            # Join remaining nodes in sequence
            for i in range(len(chain) - 1):
                left_id = chain[i]
                right_id = chain[i + 1]

                if right_id not in nodes:
                    raise ValueError(f"Path node '{right_id}' not found in nodes")

                right_df = nodes[right_id]

                # Find edge definition for join keys
                edge = self._find_edge(left_id, right_id)
                pairs = (
                    self._join_pairs_from_strings(edge['on'])
                    if edge and edge.get('on')
                    else self._infer_join_pairs(df, right_df)
                )

                # Join with dedupe (avoid duplicate columns)
                right_prefix = f"{right_id}__"
                df = self._join_with_dedupe(df, right_df, pairs, right_prefix, how='left')

            paths[path_id] = df

        return paths

    def _find_edge(self, from_id: str, to_id: str) -> Optional[Dict]:
        """Find edge definition between two nodes"""
        graph = self.model_cfg.get('graph', {})
        for edge in graph.get('edges', []):
            if edge['from'] == from_id and edge['to'] == to_id:
                return edge
        return None

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
