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

# Try to import PySpark (may not be available when using DuckDB)
try:
    from pyspark.sql import DataFrame as SparkDataFrame, functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkDataFrame = None
    F = None

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

        # Lazy-loaded caches
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Storage router for path resolution
        from models.api.dal import StorageRouter
        self.storage_router = StorageRouter(self.storage_cfg)

        # Detect backend type
        self._backend = self._detect_backend()

    @property
    def backend(self) -> str:
        """Get backend type (spark or duckdb)."""
        return self._backend

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
                df = self._select_columns(df, node_config['select'])

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
        if self.backend == 'spark':
            if not PYSPARK_AVAILABLE:
                raise ImportError("PySpark not available but Spark backend detected")

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
        else:
            # DuckDB - use SQL expressions
            if expr.startswith('sha1(') and expr.endswith(')'):
                col = expr[5:-1]  # Extract column name
                sql_expr = f"SHA1({col})"
            else:
                # Direct column reference or SQL expression
                sql_expr = expr

            # DuckDB: add column using project with *
            # Get all existing columns plus the new one
            existing_cols = ', '.join([f'"{c}"' for c in df.columns])
            return df.project(f'{existing_cols}, {sql_expr} AS {col_name}')

    def _apply_edges(self, nodes: Dict[str, DataFrame]) -> None:
        """
        Validate that edges exist between nodes.

        Does a dry-run join with limit(1) to validate:
        - Both nodes exist
        - Join columns exist
        - Join is valid

        Note: Skipped for DuckDB backend (joins not yet implemented)

        Args:
            nodes: Dictionary of node_id -> DataFrame
        """
        # Skip edge validation for DuckDB (joins not yet supported)
        if self.backend == 'duckdb':
            return

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

        Note: Skipped for DuckDB backend (joins not yet implemented)

        Args:
            nodes: Dictionary of node_id -> DataFrame

        Returns:
            Dictionary of path_id -> joined DataFrame
        """
        # Skip path materialization for DuckDB (joins not yet supported)
        if self.backend == 'duckdb':
            return {}

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
    # MEASURE CALCULATIONS (generic operations on facts)
    # ============================================================

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
            loader = ParquetLoader(root=output_root.rsplit('/', 1)[0])  # Get parent of model dir

            # Write dimensions
            print(f"\nWriting Dimensions:")
            for name, df in self._dims.items():
                print(f"  Writing {name}...")
                row_count = df.count()

                # ParquetLoader expects relative path
                rel_path = f"{self.model_name}/dims/{name}"
                loader.write_dim(rel_path, df)

                stats['dimensions'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1
                print(f"    ✓ {row_count:,} rows")

            # Write facts
            print(f"\nWriting Facts:")
            for name, df in self._facts.items():
                print(f"  Writing {name}...")
                row_count = df.count()

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

                rel_path = f"{self.model_name}/facts/{name}"
                loader.write_fact(rel_path, df, sort_by=sort_by)

                stats['facts'][name] = row_count
                stats['total_rows'] += row_count
                stats['total_tables'] += 1
                print(f"    ✓ {row_count:,} rows")

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
