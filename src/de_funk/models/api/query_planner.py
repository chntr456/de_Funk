"""
GraphQueryPlanner - Intra-model query planning using graph edges.

Uses a model's graph.edges configuration to plan and execute dynamic joins
at runtime, making materialized views an optional performance optimization
rather than a requirement.

Each model instance gets its own query planner that understands the
table-level relationships within that model.
"""

import networkx as nx
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


class GraphQueryPlanner:
    """
    Query planner that uses graph edges for dynamic table joins.

    Each model instance has its own query planner. The planner reads
    the model's graph.edges configuration and builds a NetworkX graph
    of table relationships. This graph is then used to:

    1. Find join paths between tables
    2. Build dynamic joins using edge metadata (join keys, types)
    3. Fall back to materialized views when available for performance

    Example:
        planner = GraphQueryPlanner(equity_model)
        df = planner.get_table_enriched(
            'fact_equity_prices',
            enrich_with=['dim_equity', 'dim_exchange'],
            columns=['ticker', 'trade_date', 'close', 'company_name', 'exchange_name']
        )

        # Planner:
        # 1. Checks if equity_prices_with_company exists (fast path)
        # 2. If not, builds join: prices -> equity -> exchange
        # 3. Returns enriched DataFrame
    """

    def __init__(self, model):
        """
        Initialize query planner for a model.

        Args:
            model: BaseModel instance
        """
        self.model = model
        self.model_name = model.model_name
        self.backend = model.backend
        self.graph = self._build_table_graph()

    def _build_table_graph(self) -> nx.DiGraph:
        """
        Build NetworkX graph from model's graph.edges configuration.

        Creates a directed graph where:
        - Nodes: Table names (dims and facts)
        - Edges: Join relationships with metadata (join_on, join_type)

        Returns:
            nx.DiGraph with table nodes and join edges
        """
        g = nx.DiGraph()

        # Add nodes from graph.nodes (all tables defined in model)
        graph_config = self.model.model_cfg.get('graph', {})
        # Handle both v1.x (list) and v2.0 (dict) node formats
        nodes_config = graph_config.get('nodes', [])
        if isinstance(nodes_config, dict):
            # v2.0 format: {node_id: {from: ..., select: ...}}
            for node_id, node_data in nodes_config.items():
                table_type = 'dimension' if node_id.startswith('dim_') else 'fact'
                g.add_node(node_id, type=table_type)
        else:
            # v1.x format: [{id: node_id, from: ..., select: ...}]
            for node in nodes_config:
                table_id = node['id']
                table_type = 'dimension' if table_id.startswith('dim_') else 'fact'
                g.add_node(table_id, type=table_type)

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = graph_config.get('edges', [])
        if isinstance(edges_config, dict):
            # v2.0 format: {edge_id: {from: ..., to: ...}}
            edges_list = list(edges_config.values())
        else:
            # v1.x format: [{id: edge_id, from: ..., to: ...}]
            edges_list = edges_config

        # Add edges from graph.edges configuration
        for edge in edges_list:
            from_table = edge['from']
            to_table = edge['to']

            # Skip cross-model edges (contain dot notation like "core.dim_calendar")
            if '.' in to_table:
                # TODO: Handle cross-model joins in future enhancement
                continue

            # Add edge with join metadata
            # Note: YAML 1.1 treats 'on' as boolean True, so we check both keys
            g.add_edge(
                from_table,
                to_table,
                join_on=edge.get('on', edge.get(True, [])),  # Handle YAML 1.1 'on' -> True quirk
                join_type=edge.get('type', 'left'),
                description=edge.get('description', '')
            )

        return g

    def get_table_enriched(
        self,
        table_name: str,
        enrich_with: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> Any:
        """
        Get table with optional enrichment via dynamic joins.

        Strategy:
        1. Check if materialized view exists that matches (fast path)
        2. If not, build join dynamically using graph edges
        3. Select only requested columns (if specified)

        Args:
            table_name: Base table name (e.g., 'fact_equity_prices')
            enrich_with: List of tables to join (e.g., ['dim_equity', 'dim_exchange'])
            columns: Columns to select (default: all columns)

        Returns:
            DataFrame with enrichment applied

        Example:
            # Get prices with company info
            df = planner.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity'],
                columns=['ticker', 'trade_date', 'close', 'company_name']
            )
        """
        # If no enrichment needed, just get base table
        if not enrich_with:
            df = self.model.get_table(table_name)
            if columns:
                df = self._select_columns(df, columns)
            return df

        # Fast path: check for materialized view
        materialized = self._find_materialized_view(table_name, enrich_with)
        if materialized:
            print(f"  Using materialized view: {materialized}")
            df = self.model.get_table(materialized)
            if columns:
                df = self._select_columns(df, columns)
            return df

        # Slow path: build join dynamically from graph
        print(f"  Building dynamic join: {table_name} + {enrich_with}")
        return self._build_dynamic_join(table_name, enrich_with, columns)

    def _find_materialized_view(
        self,
        base_table: str,
        join_tables: List[str]
    ) -> Optional[str]:
        """
        Find materialized view (path) that matches the join pattern.

        Searches through model's paths configuration to find a pre-computed
        view that joins the same tables.

        Args:
            base_table: Starting table
            join_tables: Tables to join

        Returns:
            Path ID if matching materialized view exists, None otherwise
        """
        graph_config = self.model.model_cfg.get('graph', {})
        paths = graph_config.get('paths', [])

        for path in paths:
            # Parse hops specification
            hops_spec = path.get('hops', '')
            if isinstance(hops_spec, str):
                tables_in_path = [t.strip() for t in hops_spec.split('->')]
            else:
                tables_in_path = hops_spec

            # Check if this path matches our join pattern
            if len(tables_in_path) == 0:
                continue

            # First table must match base table
            if tables_in_path[0] != base_table:
                continue

            # Check if all join_tables are in the path
            if all(t in tables_in_path for t in join_tables):
                return path['id']

        return None

    def _build_dynamic_join(
        self,
        base_table: str,
        join_tables: List[str],
        columns: Optional[List[str]] = None
    ) -> Any:
        """
        Build join dynamically using graph edges.

        Uses NetworkX to find join paths, then executes joins using
        backend-specific join operations (Spark or DuckDB).

        Args:
            base_table: Starting table
            join_tables: Tables to join
            columns: Columns to select

        Returns:
            Joined DataFrame

        Raises:
            ValueError: If no join path exists in graph
        """
        # For DuckDB, use SQL-based approach (more efficient)
        if self.backend == 'duckdb':
            return self._build_duckdb_join_sql(base_table, join_tables, columns)

        # For Spark, use DataFrame API approach
        # Load base table
        df = self.model.get_table(base_table)

        # Join each table in sequence
        current_table = base_table
        for join_table in join_tables:
            # Find path in graph
            try:
                path = nx.shortest_path(self.graph, current_table, join_table)
            except nx.NetworkXNoPath:
                raise ValueError(
                    f"No join path from {current_table} to {join_table} in {self.model_name} model. "
                    f"Add edge to configs/models/{self.model_name}.yaml"
                )

            # Execute joins along path
            for i in range(len(path) - 1):
                left_table = path[i]
                right_table = path[i + 1]

                # Get edge metadata
                edge_data = self.graph.edges[left_table, right_table]
                join_on = edge_data['join_on']
                join_type_raw = edge_data.get('join_type', 'left').lower()

                # Map join types to standard SQL join types
                join_type_map = {
                    'many_to_one': 'left',
                    'one_to_many': 'left',
                    'left': 'left',
                    'right': 'right',
                    'inner': 'inner',
                    'full': 'outer',
                    'outer': 'outer'
                }
                join_type = join_type_map.get(join_type_raw, 'left')

                # Load right table
                right_df = self.model.get_table(right_table)

                # Execute join
                df = self._join_dataframes(df, right_df, join_on, join_type)

            current_table = join_table

        # Select columns if specified
        if columns:
            df = self._select_columns(df, columns)

        return df

    def _build_duckdb_join_sql(
        self,
        base_table: str,
        join_tables: List[str],
        columns: Optional[List[str]] = None
    ) -> Any:
        """
        Build SQL join query for DuckDB.

        Constructs a SQL query with JOINs based on graph edges, then
        executes it via DuckDB connection.

        Args:
            base_table: Starting table
            join_tables: Tables to join
            columns: Columns to select (if None, selects all from base table + joined cols)

        Returns:
            Pandas DataFrame with joined data

        Raises:
            ValueError: If no join path exists
        """
        # Get table paths from model
        base_table_ref = self._get_duckdb_table_reference(base_table)

        # Build list of all tables in join order
        all_tables = [base_table] + join_tables

        # Build join clauses
        join_clauses = []
        table_aliases = {base_table: 't0'}
        alias_counter = 1

        current_table = base_table
        for join_table in join_tables:
            # Find path
            try:
                path = nx.shortest_path(self.graph, current_table, join_table)
            except nx.NetworkXNoPath:
                raise ValueError(
                    f"No join path from {current_table} to {join_table} in {self.model_name} model"
                )

            # Process each edge in path
            for i in range(len(path) - 1):
                left = path[i]
                right = path[i + 1]

                # Assign alias to right table if not already assigned
                if right not in table_aliases:
                    table_aliases[right] = f't{alias_counter}'
                    alias_counter += 1

                # Get edge metadata
                edge_data = self.graph.edges[left, right]
                join_on = edge_data['join_on']
                join_type_raw = edge_data.get('join_type', 'left').lower()

                # Map join types to SQL join types
                join_type_map = {
                    'many_to_one': 'LEFT',
                    'one_to_many': 'LEFT',
                    'left': 'LEFT',
                    'right': 'RIGHT',
                    'inner': 'INNER',
                    'full': 'FULL OUTER',
                    'outer': 'FULL OUTER'
                }
                join_type = join_type_map.get(join_type_raw, 'LEFT')

                # Get table reference
                right_table_ref = self._get_duckdb_table_reference(right)

                # Build ON clause
                on_conditions = []
                for condition in join_on:
                    if '=' in condition:
                        left_col, right_col = condition.split('=', 1)
                        left_col = left_col.strip()
                        right_col = right_col.strip()
                        on_conditions.append(
                            f"{table_aliases[left]}.{left_col} = {table_aliases[right]}.{right_col}"
                        )
                    else:
                        # Same column name on both sides
                        col = condition.strip()
                        on_conditions.append(
                            f"{table_aliases[left]}.{col} = {table_aliases[right]}.{col}"
                        )

                on_clause = " AND ".join(on_conditions)

                # Add join clause
                join_clauses.append(
                    f"{join_type} JOIN {right_table_ref} AS {table_aliases[right]} ON {on_clause}"
                )

            current_table = join_table

        # Build SELECT clause
        if columns:
            # Select specific columns with correct table aliases
            select_cols = []
            for col in columns:
                # Find which table has this column by checking schema
                table_with_column = None
                for table in all_tables:
                    if self._table_has_column(table, col):
                        table_with_column = table
                        break

                if table_with_column:
                    # Use table alias for column
                    select_cols.append(f"{table_aliases[table_with_column]}.{col}")
                else:
                    # Column not found in any table, let SQL handle the error
                    select_cols.append(col)

            select_clause = ", ".join(select_cols)
        else:
            # Select all columns from all tables (DuckDB will handle duplicates)
            # Generate t0.*, t1.*, t2.*, etc. for all tables in join
            select_clause = ", ".join(f"{alias}.*" for alias in table_aliases.values())

        # Build final SQL
        sql = f"""
SELECT {select_clause}
FROM {base_table_ref} AS {table_aliases[base_table]}
{chr(10).join(join_clauses)}
        """.strip()

        # Execute via DuckDB connection
        result = self.model.connection.execute(sql).fetchdf()

        return result

    def _get_duckdb_table_reference(self, table_name: str) -> str:
        """
        Get DuckDB table reference (parquet path).

        Uses the model's schema to resolve table paths, ensuring tables
        are looked up within the correct model's storage.

        Args:
            table_name: Table name

        Returns:
            DuckDB-compatible table reference (e.g., read_parquet('path/*.parquet'))
        """
        # Get schema from model config (same approach as DuckDBAdapter)
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(
                f"Table '{table_name}' not found in model '{self.model_name}' schema. "
                f"Available tables: {list(schema.get('dimensions', {}).keys()) + list(schema.get('facts', {}).keys())}"
            )

        # Build full path using model's storage root
        storage_root = self.model.model_cfg['storage']['root']
        full_path = f"{storage_root}/{relative_path}"

        # Return DuckDB read_parquet syntax
        return f"read_parquet('{full_path}/*.parquet')"

    def _join_dataframes(
        self,
        left_df: Any,
        right_df: Any,
        join_on: List[str],
        join_type: str = 'left'
    ) -> Any:
        """
        Join two DataFrames using backend-specific operations.

        Args:
            left_df: Left DataFrame
            right_df: Right DataFrame
            join_on: Join conditions (e.g., ["ticker=ticker", "date=date"])
            join_type: Join type (left, inner, outer)

        Returns:
            Joined DataFrame
        """
        # Parse join conditions
        join_pairs = self._parse_join_conditions(join_on)

        if self.backend == 'spark':
            return self._spark_join(left_df, right_df, join_pairs, join_type)
        else:
            return self._duckdb_join(left_df, right_df, join_pairs, join_type)

    def _parse_join_conditions(self, join_on: List[str]) -> List[Tuple[str, str]]:
        """
        Parse join conditions into (left_col, right_col) pairs.

        Args:
            join_on: List of join conditions (e.g., ["ticker=ticker", "date=date"])

        Returns:
            List of (left_col, right_col) tuples

        Example:
            ["ticker=ticker", "date=trade_date"]
            → [("ticker", "ticker"), ("date", "trade_date")]
        """
        pairs = []

        # Validate that join_on is a list
        if not isinstance(join_on, list):
            raise ValueError(f"join_on must be a list, got {type(join_on)}: {join_on}")

        for condition in join_on:
            if not isinstance(condition, str):
                raise ValueError(f"join condition must be a string, got {type(condition)}: {condition}")

            if '=' in condition:
                parts = condition.split('=', 1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid join condition format: {condition}")
                left_col, right_col = parts
                pairs.append((left_col.strip(), right_col.strip()))
            else:
                # If no '=', assume same column name on both sides
                pairs.append((condition.strip(), condition.strip()))
        return pairs

    def _spark_join(
        self,
        left_df: Any,
        right_df: Any,
        join_pairs: List[Tuple[str, str]],
        join_type: str
    ) -> Any:
        """
        Execute join using Spark DataFrame API.

        Args:
            left_df: Left Spark DataFrame
            right_df: Right Spark DataFrame
            join_pairs: List of (left_col, right_col) tuples
            join_type: Join type (left, inner, outer, etc.)

        Returns:
            Joined Spark DataFrame
        """
        # Build join condition
        join_condition = None
        duplicate_cols = []

        for left_col, right_col in join_pairs:
            condition = left_df[left_col] == right_df[right_col]
            if join_condition is None:
                join_condition = condition
            else:
                join_condition = join_condition & condition

            # Track duplicate columns (where left and right have same name)
            if left_col == right_col:
                duplicate_cols.append(right_col)

        # Execute join
        result_df = left_df.join(right_df, join_condition, join_type)

        # Drop duplicate columns from right side to avoid ambiguity
        # After join, Spark keeps both columns causing "AMBIGUOUS_REFERENCE" errors
        for col in duplicate_cols:
            if col in result_df.columns:
                # Drop the duplicate (Spark keeps both, we want only the left one)
                result_df = result_df.drop(right_df[col])

        return result_df

    def _duckdb_join(
        self,
        left_df: Any,
        right_df: Any,
        join_pairs: List[Tuple[str, str]],
        join_type: str
    ) -> Any:
        """
        Execute join using DuckDB pandas DataFrames.

        Note: This method is now deprecated in favor of _build_duckdb_join_sql
        which builds SQL queries directly. Kept for backwards compatibility.

        Args:
            left_df: Left pandas DataFrame
            right_df: Right pandas DataFrame
            join_pairs: List of (left_col, right_col) tuples
            join_type: Join type

        Returns:
            Joined pandas DataFrame
        """
        # Build join keys
        left_on = [pair[0] for pair in join_pairs]
        right_on = [pair[1] for pair in join_pairs]

        # Map join type
        how = join_type.lower()
        if how == 'many_to_one':
            how = 'left'

        # Use pandas merge
        import pandas as pd
        return pd.merge(left_df, right_df, left_on=left_on, right_on=right_on, how=how)

    def _select_columns(self, df: Any, columns: List[str]) -> Any:
        """
        Select specific columns from DataFrame (backend agnostic).

        Args:
            df: DataFrame (Spark or pandas)
            columns: List of column names to select

        Returns:
            DataFrame with only specified columns
        """
        if self.backend == 'spark':
            # Filter columns that exist in DataFrame
            available_cols = [c for c in columns if c in df.columns]
            return df.select(*available_cols)
        else:
            # DuckDB returns pandas DataFrame
            # Filter columns that exist
            available_cols = [c for c in columns if c in df.columns]
            if available_cols:
                return df[available_cols]
            return df

    def get_join_path(self, from_table: str, to_table: str) -> Optional[List[str]]:
        """
        Find join path between two tables.

        Useful for debugging and understanding table relationships.

        Args:
            from_table: Source table
            to_table: Target table

        Returns:
            List of table names forming the path, or None if no path exists

        Example:
            planner.get_join_path('fact_equity_prices', 'dim_exchange')
            → ['fact_equity_prices', 'dim_equity', 'dim_exchange']
        """
        try:
            return nx.shortest_path(self.graph, from_table, to_table)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_table_relationships(self, table_name: str) -> Dict[str, Any]:
        """
        Get all relationships for a table.

        Args:
            table_name: Table to analyze

        Returns:
            Dictionary with relationship information

        Example:
            planner.get_table_relationships('fact_equity_prices')
            → {
                'can_join_to': ['dim_equity'],
                'can_be_joined_from': [],
                'graph_depth': 0
            }
        """
        if table_name not in self.graph:
            return {}

        return {
            'can_join_to': list(self.graph.successors(table_name)),
            'can_be_joined_from': list(self.graph.predecessors(table_name)),
            'graph_depth': len(nx.ancestors(self.graph, table_name))
        }

    def find_tables_with_column(self, column_name: str) -> List[str]:
        """
        Find all tables that contain a specific column.

        Searches the model's schema to find tables that have the specified column.
        Used for auto-enrichment to find which tables to join.

        Args:
            column_name: Column to search for

        Returns:
            List of table names that contain the column

        Example:
            planner.find_tables_with_column('exchange_name')
            → ['dim_exchange']

            planner.find_tables_with_column('ticker')
            → ['dim_equity', 'fact_equity_prices', 'fact_equity_news']
        """
        tables_with_column = []

        schema = self.model.model_cfg.get('schema', {})

        # Search dimensions
        for table_name, table_schema in schema.get('dimensions', {}).items():
            columns = table_schema.get('columns', {})
            if column_name in columns:
                tables_with_column.append(table_name)

        # Search facts
        for table_name, table_schema in schema.get('facts', {}).items():
            columns = table_schema.get('columns', {})
            if column_name in columns:
                tables_with_column.append(table_name)

        return tables_with_column

    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        """
        Check if a table has a specific column.

        Args:
            table_name: Table to check
            column_name: Column to look for

        Returns:
            True if table has the column, False otherwise
        """
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            columns = schema['dimensions'][table_name].get('columns', {})
            return column_name in columns

        # Check facts
        if table_name in schema.get('facts', {}):
            columns = schema['facts'][table_name].get('columns', {})
            return column_name in columns

        return False

    def __repr__(self) -> str:
        """String representation of query planner."""
        return (
            f"GraphQueryPlanner(model={self.model_name}, "
            f"tables={self.graph.number_of_nodes()}, "
            f"edges={self.graph.number_of_edges()})"
        )
