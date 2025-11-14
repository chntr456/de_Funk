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
        for node in graph_config.get('nodes', []):
            table_id = node['id']
            table_type = 'dimension' if table_id.startswith('dim_') else 'fact'
            g.add_node(table_id, type=table_type)

        # Add edges from graph.edges configuration
        for edge in graph_config.get('edges', []):
            from_table = edge['from']
            to_table = edge['to']

            # Skip cross-model edges (contain dot notation like "core.dim_calendar")
            if '.' in to_table:
                # TODO: Handle cross-model joins in future enhancement
                continue

            # Add edge with join metadata
            g.add_edge(
                from_table,
                to_table,
                join_on=edge.get('on', []),
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
                join_type = edge_data.get('join_type', 'left')

                # Load right table
                right_df = self.model.get_table(right_table)

                # Execute join
                df = self._join_dataframes(df, right_df, join_on, join_type)

            current_table = join_table

        # Select columns if specified
        if columns:
            df = self._select_columns(df, columns)

        return df

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
        for condition in join_on:
            if '=' in condition:
                left_col, right_col = condition.split('=', 1)
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
        for left_col, right_col in join_pairs:
            condition = left_df[left_col] == right_df[right_col]
            if join_condition is None:
                join_condition = condition
            else:
                join_condition = join_condition & condition

        # Execute join
        return left_df.join(right_df, join_condition, join_type)

    def _duckdb_join(
        self,
        left_df: Any,
        right_df: Any,
        join_pairs: List[Tuple[str, str]],
        join_type: str
    ) -> Any:
        """
        Execute join using DuckDB.

        Note: This is a placeholder for future DuckDB join implementation.
        Currently, DuckDB integration is handled via SQL, not DataFrame API.

        Args:
            left_df: Left DataFrame
            right_df: Right DataFrame
            join_pairs: List of (left_col, right_col) tuples
            join_type: Join type

        Returns:
            Joined DataFrame

        Raises:
            NotImplementedError: DuckDB dynamic joins not yet implemented
        """
        raise NotImplementedError(
            "DuckDB dynamic joins not yet implemented. "
            "Use Spark backend or create materialized views for now."
        )

    def _select_columns(self, df: Any, columns: List[str]) -> Any:
        """
        Select specific columns from DataFrame (backend agnostic).

        Args:
            df: DataFrame (Spark or DuckDB)
            columns: List of column names to select

        Returns:
            DataFrame with only specified columns
        """
        if self.backend == 'spark':
            # Filter columns that exist in DataFrame
            available_cols = [c for c in columns if c in df.columns]
            return df.select(*available_cols)
        else:
            # DuckDB - return as-is for now
            # TODO: Implement DuckDB column selection
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

    def __repr__(self) -> str:
        """String representation of query planner."""
        return (
            f"GraphQueryPlanner(model={self.model_name}, "
            f"tables={self.graph.number_of_nodes()}, "
            f"edges={self.graph.number_of_edges()})"
        )
