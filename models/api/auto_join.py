"""
Auto-Join Support for UniversalSession.

Provides transparent graph traversal and automatic join operations:
- Find materialized views containing required columns
- Plan join sequences using model graph
- Execute joins (Spark and DuckDB backends)
- Universal date filtering via dim_calendar

This module is used by UniversalSession via composition.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
import logging

logger = logging.getLogger(__name__)

# Universal date columns - all represent "a point in time" and map to dim_calendar.date
# When a filter uses one of these columns but the table has a different one,
# the system will translate via the table's calendar edge mapping.
UNIVERSAL_DATE_COLUMNS: Set[str] = {
    'date',           # dim_calendar's primary date column
    'trade_date',     # stocks, securities prices
    'forecast_date',  # forecasts
    'fiscal_date',    # company financials
    'report_date',    # reports, filings
    'effective_date', # effective dates
    'as_of_date',     # point-in-time snapshots
}


class AutoJoinHandler:
    """
    Handles automatic join operations based on model graph.

    Provides:
    - Materialized view discovery
    - Join path planning
    - Join execution for both backends
    """

    def __init__(self, session):
        """
        Initialize auto-join handler.

        Args:
            session: UniversalSession instance
        """
        self.session = session
        # Cache column indexes per model for performance
        self._column_index_cache: Dict[str, Dict[str, List[str]]] = {}

    @property
    def connection(self):
        return self.session.connection

    @property
    def backend(self) -> str:
        return self.session.backend

    @property
    def registry(self):
        return self.session.registry

    def select_columns(self, df: Any, columns: List[str]) -> Any:
        """
        Select specific columns from DataFrame (backend agnostic).

        Args:
            df: DataFrame (Spark or DuckDB)
            columns: List of column names to select

        Returns:
            DataFrame with only specified columns
        """
        import pandas as pd

        if self.backend == 'spark':
            return df.select(*columns)
        else:
            # DuckDB - check if already pandas DataFrame or DuckDB relation
            if isinstance(df, pd.DataFrame):
                # Already pandas - filter to only columns that exist
                available_columns = [col for col in columns if col in df.columns]
                if not available_columns:
                    return pd.DataFrame(columns=columns)
                return df[available_columns]
            else:
                # DuckDB relation - use project() method
                relation_columns = df.columns
                available_columns = [col for col in columns if col in relation_columns]
                if not available_columns:
                    return df.limit(0)
                return df.project(','.join(available_columns))

    def find_materialized_view(
        self,
        model_name: str,
        required_columns: List[str]
    ) -> Optional[str]:
        """
        Find a materialized view that contains all required columns.

        Uses DuckDB catalog for fast lookup instead of building models.

        Args:
            model_name: Model to search in
            required_columns: Columns needed

        Returns:
            Table name of materialized view, or None if not found
        """
        import time
        t_start = time.time()
        logger.debug(f"AUTO-JOIN MATERIALIZED: Looking for view with columns {required_columns}")

        # Strategy 1: Use DuckDB information_schema (fast)
        if self.backend == 'duckdb' and hasattr(self.connection, 'conn'):
            try:
                # Get all fact tables in this schema
                tables_result = self.connection.conn.execute(f"""
                    SELECT DISTINCT table_name
                    FROM information_schema.columns
                    WHERE table_schema = '{model_name}'
                      AND table_name LIKE 'fact_%'
                """).fetchall()

                fact_tables = [r[0] for r in tables_result]
                logger.debug(f"AUTO-JOIN MATERIALIZED: Found {len(fact_tables)} fact tables in DuckDB catalog")

                for table_name in fact_tables:
                    # Get columns for this table
                    cols_result = self.connection.conn.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = '{model_name}'
                          AND table_name = '{table_name}'
                    """).fetchall()

                    table_columns = {r[0] for r in cols_result}

                    if all(col in table_columns for col in required_columns):
                        logger.debug(f"AUTO-JOIN MATERIALIZED: Found view '{table_name}' with all columns in {time.time() - t_start:.2f}s")
                        return table_name

                logger.debug(f"AUTO-JOIN MATERIALIZED: No matching view found in {time.time() - t_start:.2f}s")
                return None

            except Exception as e:
                logger.debug(f"AUTO-JOIN MATERIALIZED: DuckDB catalog lookup failed: {e}")

        # Strategy 2: Fall back to model-based search (slower)
        try:
            logger.debug(f"AUTO-JOIN MATERIALIZED: Falling back to model-based search")
            model = self.session.load_model(model_name)
            tables = model.list_tables()

            for table_name in tables.get('facts', []):
                try:
                    schema = model.get_table_schema(table_name)
                    table_columns = set(schema.keys())

                    if all(col in table_columns for col in required_columns):
                        logger.debug(f"AUTO-JOIN MATERIALIZED: Found '{table_name}' via model in {time.time() - t_start:.2f}s")
                        return table_name
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.warning(f"AUTO-JOIN MATERIALIZED: Error: {e}")
            return None

    def plan_auto_joins(
        self,
        model_name: str,
        base_table: str,
        missing_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Plan join sequence to get missing columns using model graph.

        Supports star schemas where a fact table joins to multiple dimensions,
        not just linear chains.

        Args:
            model_name: Model name
            base_table: Starting table
            missing_columns: Columns to find

        Returns:
            Join plan dict with:
                - table_sequence: List of tables to join
                - joins: List of join info dicts with from_table, to_table, left_col, right_col
                - target_columns: Which columns come from which table

        Raises:
            ValueError: If no join path found
        """
        import time
        logger.debug(f"AUTO-JOIN PLAN: Starting for {model_name}.{base_table}, missing={missing_columns}")
        t_start = time.time()

        model_config = self.registry.get_model_config(model_name)
        graph_config = model_config.get('graph', {})
        logger.debug(f"AUTO-JOIN PLAN: Got model config in {time.time() - t_start:.2f}s")

        if not graph_config or 'edges' not in graph_config:
            raise ValueError(f"No graph edges defined for model {model_name}")

        # Build column-to-table index
        t0 = time.time()
        column_index = self.build_column_index(model_name)
        logger.debug(f"AUTO-JOIN PLAN: build_column_index took {time.time() - t0:.2f}s, indexed {len(column_index)} columns")

        # Find which tables have the missing columns
        target_tables = {}
        for col in missing_columns:
            if col in column_index:
                target_tables[col] = column_index[col][0]  # Use first table that has it
                logger.debug(f"AUTO-JOIN PLAN: Column '{col}' found in table '{target_tables[col]}'")
            else:
                logger.error(f"AUTO-JOIN PLAN: Column '{col}' NOT found in any table!")
                logger.error(f"AUTO-JOIN PLAN: Available columns: {list(column_index.keys())[:20]}...")
                raise ValueError(f"Column '{col}' not found in any table in model {model_name}")

        logger.debug(f"AUTO-JOIN PLAN: Target tables: {target_tables}")

        # Find join path from base_table to target tables
        table_sequence = [base_table]
        joins = []  # List of {from_table, to_table, left_col, right_col}
        seen_tables = {base_table}

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = graph_config.get('edges', [])
        if isinstance(edges_config, dict):
            edges = list(edges_config.values())
            logger.debug(f"AUTO-JOIN PLAN: Loaded {len(edges)} edges from dict format")
        else:
            edges = edges_config
            logger.debug(f"AUTO-JOIN PLAN: Loaded {len(edges)} edges from list format")

        # Log all edges for debugging
        for i, edge in enumerate(edges):
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')
            edge_on = edge.get('on', [])
            logger.debug(f"AUTO-JOIN PLAN: Edge[{i}]: {edge_from} -> {edge_to} ON {edge_on}")

        current_tables = {base_table}

        # Keep adding tables until we have all target tables
        needed_tables = set(target_tables.values())
        logger.debug(f"AUTO-JOIN PLAN: Need to reach tables: {needed_tables}, starting from: {current_tables}")

        max_iterations = len(edges) + 1  # Prevent infinite loops
        iteration = 0

        while not all(tbl in seen_tables for tbl in target_tables.values()):
            iteration += 1
            if iteration > max_iterations:
                raise ValueError(
                    f"AUTO-JOIN PLAN: Exceeded max iterations ({max_iterations}). "
                    f"Possible cycle in graph. Reached: {seen_tables}, Need: {needed_tables}"
                )

            added_table = False
            remaining = needed_tables - seen_tables
            logger.debug(f"AUTO-JOIN PLAN: Iteration {iteration}, still need: {remaining}")

            for edge in edges:
                edge_from = edge.get('from', '')
                edge_to = edge.get('to', '')

                # Handle cross-model edges to temporal.dim_calendar (foundational dimension)
                # Calendar is a shared dimension that all time-series data joins to
                if '.' in edge_to:
                    if 'temporal.dim_calendar' in edge_to or 'dim_calendar' in edge_to:
                        # Allow calendar joins - normalize the table name
                        edge_to = 'dim_calendar'
                    else:
                        # Skip other cross-model edges
                        logger.debug(f"AUTO-JOIN PLAN: Skipping cross-model edge {edge_from} -> {edge_to}")
                        continue

                # Check if this edge connects a current table to a new table
                if edge_from in current_tables and edge_to not in seen_tables:
                    # Add this table to sequence
                    table_sequence.append(edge_to)
                    seen_tables.add(edge_to)
                    current_tables.add(edge_to)

                    # Extract join keys - track the source table for star schema support
                    on_conditions = edge.get('on', edge.get(True, []))
                    if on_conditions:
                        # Parse "col1=col2" format
                        left_col, right_col = self._parse_join_condition(on_conditions[0])
                        joins.append({
                            'from_table': edge_from,
                            'to_table': edge_to,
                            'left_col': left_col,
                            'right_col': right_col
                        })
                        logger.debug(f"AUTO-JOIN PLAN: Added join {edge_from}.{left_col} = {edge_to}.{right_col}")

                    added_table = True
                    break

            if not added_table:
                # Log detailed failure info
                logger.error(f"AUTO-JOIN PLAN: Failed to find edge. current_tables={current_tables}, seen={seen_tables}, need={remaining}")
                for edge in edges:
                    ef, et = edge.get('from', ''), edge.get('to', '')
                    if '.' in et and 'dim_calendar' not in et:
                        continue  # Cross-model
                    logger.error(f"  Edge {ef} -> {et}: from_match={ef in current_tables}, to_unseen={et not in seen_tables}")

                raise ValueError(
                    f"Cannot find join path from {base_table} to {missing_columns}. "
                    f"Reached: {seen_tables}, Need: {remaining}. "
                    f"Check that model graph has edges connecting these tables."
                )

        # For backwards compatibility, also include join_keys in old format
        join_keys = [(j['left_col'], j['right_col']) for j in joins]

        logger.debug(f"AUTO-JOIN PLAN: table_sequence = {table_sequence}")
        logger.debug(f"AUTO-JOIN PLAN: joins = {joins}")

        return {
            'table_sequence': table_sequence,
            'joins': joins,  # New format with source table info
            'join_keys': join_keys,  # Legacy format for backwards compatibility
            'target_columns': target_tables
        }

    def build_column_index(self, model_name: str) -> Dict[str, List[str]]:
        """
        Build reverse index: column_name -> [table_names].

        Uses DuckDB schema introspection on views (fast) combined with
        model schema (for tables without DuckDB views).

        Prefers model-specific tables (dim_stock) over base templates (dim_security).

        Results are cached per model for the session lifetime.

        Args:
            model_name: Model to index

        Returns:
            Dict mapping column names to list of tables that have that column
        """
        # Return cached index if available
        if model_name in self._column_index_cache:
            logger.debug(f"AUTO-JOIN INDEX: Using cached index for {model_name}")
            return self._column_index_cache[model_name]

        import time
        logger.debug(f"AUTO-JOIN INDEX: Building column index for {model_name}")
        t_start = time.time()

        index = {}
        duckdb_tables = set()  # Track which tables we found in DuckDB

        # Strategy 1: Use DuckDB information_schema (fast - no model building)
        if self.backend == 'duckdb' and hasattr(self.connection, 'conn'):
            try:
                # Get all tables/views in this schema from DuckDB catalog
                # Also include temporal schema for calendar dimension (foundational/shared)
                result = self.connection.conn.execute(f"""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = '{model_name}'
                       OR table_schema = 'temporal'
                    ORDER BY table_name, ordinal_position
                """).fetchall()

                if result:
                    # Group columns by table
                    table_columns = {}
                    for table_name, column_name in result:
                        if table_name not in table_columns:
                            table_columns[table_name] = []
                        table_columns[table_name].append(column_name)
                        duckdb_tables.add(table_name)

                    # Sort tables: prefer model-specific (dim_stock) over base (dim_security)
                    # Heuristic: tables with model name fragment or without "security" come first
                    def table_priority(table_name: str) -> int:
                        # Base templates get lower priority
                        if table_name in ('dim_security', 'fact_prices'):
                            return 2
                        # Model-specific tables get highest priority
                        return 0

                    sorted_tables = sorted(table_columns.keys(), key=table_priority)
                    logger.debug(f"AUTO-JOIN INDEX: DuckDB tables found: {sorted_tables}")

                    # Build index with priority ordering
                    for table_name in sorted_tables:
                        for column_name in table_columns[table_name]:
                            if column_name not in index:
                                index[column_name] = []
                            if table_name not in index[column_name]:
                                index[column_name].append(table_name)

                    logger.debug(f"AUTO-JOIN INDEX: Built from DuckDB catalog in {time.time() - t_start:.2f}s, "
                                f"indexed {len(index)} columns from {len(table_columns)} tables")

            except Exception as e:
                logger.debug(f"AUTO-JOIN INDEX: DuckDB catalog lookup failed: {e}, falling back to model schema")

        # Strategy 2: Augment with model schema for tables not found in DuckDB
        # This ensures we have complete coverage even if some views aren't registered
        t0 = time.time()
        model = self.session.load_model(model_name)
        logger.debug(f"AUTO-JOIN INDEX: load_model took {time.time() - t0:.2f}s")

        t0 = time.time()
        tables = model.list_tables()
        all_tables = tables.get('dimensions', []) + tables.get('facts', [])
        logger.debug(f"AUTO-JOIN INDEX: Model schema has {len(all_tables)} tables: {all_tables}")

        # Find tables missing from DuckDB index
        missing_tables = [t for t in all_tables if t not in duckdb_tables]
        if missing_tables:
            logger.debug(f"AUTO-JOIN INDEX: Augmenting with model schema for tables not in DuckDB: {missing_tables}")

        # Index tables missing from DuckDB (dims and facts)
        for table_name in missing_tables:
            try:
                t0 = time.time()
                schema = model.get_table_schema(table_name)
                elapsed = time.time() - t0
                if elapsed > 0.1:  # Only log if slow
                    logger.warning(f"AUTO-JOIN INDEX: get_table_schema({table_name}) took {elapsed:.2f}s")
                for column_name in schema.keys():
                    if column_name not in index:
                        index[column_name] = []
                    if table_name not in index[column_name]:
                        index[column_name].append(table_name)
            except Exception as e:
                logger.warning(f"AUTO-JOIN INDEX: Failed to get schema for {table_name}: {e}")
                continue

        logger.debug(f"AUTO-JOIN INDEX: Total build time {time.time() - t_start:.2f}s, "
                    f"indexed {len(index)} columns")

        # Log key columns for debugging join issues
        for key_col in ['ticker', 'company_id', 'date_id', 'date']:
            if key_col in index:
                logger.debug(f"AUTO-JOIN INDEX: '{key_col}' found in tables: {index[key_col]}")

        # Cache for future calls
        self._column_index_cache[model_name] = index
        return index

    def _parse_join_condition(self, condition: str) -> Tuple[str, str]:
        """
        Parse join condition like "ticker=ticker" or "exchange_code=exchange_code".

        Args:
            condition: Join condition string

        Returns:
            Tuple of (left_column, right_column)
        """
        parts = condition.split('=')
        if len(parts) == 2:
            return (parts[0].strip(), parts[1].strip())
        raise ValueError(f"Invalid join condition: {condition}")

    def get_calendar_date_column(self, model_name: str, table_name: str) -> Optional[str]:
        """
        Find the local date column for a table based on its edge to dim_calendar.

        This enables universal date filtering - any date column (trade_date, forecast_date,
        fiscal_date) can be used interchangeably because they all represent "a point in time"
        that maps to dim_calendar.date.

        Args:
            model_name: Model to search in
            table_name: Table to find date column for

        Returns:
            Local date column name (e.g., 'trade_date') or None if no calendar edge
        """
        try:
            model_config = self.registry.get_model_config(model_name)
        except Exception:
            return None

        if 'graph' not in model_config or 'edges' not in model_config['graph']:
            return None

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = model_config['graph']['edges']
        if isinstance(edges_config, dict):
            edges_list = list(edges_config.values())
        else:
            edges_list = edges_config

        for edge in edges_list:
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')

            # Check if this edge goes from our table to dim_calendar
            if edge_from == table_name and 'dim_calendar' in edge_to:
                on_conditions = edge.get('on', edge.get(True, []))

                for condition in on_conditions:
                    if isinstance(condition, str):
                        parts = condition.split('=')
                        if len(parts) == 2:
                            local_col = parts[0].strip()  # e.g., 'trade_date' or 'date_id'
                            calendar_col = parts[1].strip()  # e.g., 'date' or 'date_id'
                            # Handle both patterns:
                            # 1. Direct date mapping: trade_date=date
                            # 2. Integer FK mapping: date_id=date_id
                            if calendar_col in ('date', 'date_id'):
                                logger.debug(f"CALENDAR MAPPING: {model_name}.{table_name}.{local_col} -> dim_calendar.{calendar_col}")
                                return local_col

        return None

    def translate_date_filters(
        self,
        model_name: str,
        base_table: str,
        filters: Dict[str, Any],
        available_cols: Set[str]
    ) -> Dict[str, Any]:
        """
        Translate universal date filters to the table's local date column.

        If a filter uses 'forecast_date' but the table has 'trade_date',
        translate it using the calendar edge mapping.

        Args:
            model_name: Model being queried
            base_table: Base table for the query
            filters: Original filter dict
            available_cols: Columns available in the joined tables

        Returns:
            Translated filter dict with date columns mapped appropriately
        """
        if not filters:
            return filters

        # Get the local date column for this table
        local_date_col = self.get_calendar_date_column(model_name, base_table)

        if not local_date_col:
            logger.debug(f"DATE TRANSLATE: No calendar edge for {model_name}.{base_table}")
            return filters

        translated = {}
        for col, val in filters.items():
            # Check if this is a universal date column that needs translation
            if col in UNIVERSAL_DATE_COLUMNS and col not in available_cols:
                if local_date_col in available_cols:
                    # Translate the filter to use the local date column
                    logger.debug(f"DATE TRANSLATE: {col} -> {local_date_col} (via dim_calendar)")
                    translated[local_date_col] = val
                else:
                    logger.debug(f"DATE TRANSLATE: Can't translate {col}, local column {local_date_col} not available")
                    # Skip this filter - neither column exists
            else:
                # Keep the filter as-is
                translated[col] = val

        return translated

    def execute_auto_joins(
        self,
        model_name: str,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute the join plan to get required columns.

        Args:
            model_name: Model name
            join_plan: Join plan from plan_auto_joins
            required_columns: Columns to return
            filters: Optional filters to apply after joins

        Returns:
            DataFrame with required columns (filtered if filters specified)
        """
        from core.session.filters import FilterEngine

        model = self.session.load_model(model_name)
        table_sequence = join_plan['table_sequence']

        if self.backend == 'spark':
            return self._execute_spark_joins(
                model, join_plan, required_columns, filters
            )
        else:
            return self._execute_duckdb_joins(
                model_name, model, join_plan, required_columns, filters
            )

    def _execute_spark_joins(
        self,
        model,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using Spark DataFrame API."""
        from core.session.filters import FilterEngine

        table_sequence = join_plan['table_sequence']
        joins = join_plan.get('joins', [])
        join_keys = join_plan.get('join_keys', [])

        # Load base table
        df = model.get_table(table_sequence[0])

        # Apply filters to base table BEFORE joins (pushdown)
        if filters:
            df = FilterEngine.apply_from_session(df, filters, self.session)

        # Track loaded DataFrames for star schema support
        dfs = {table_sequence[0]: df}

        # Join using new format with source table tracking (star schema support)
        if joins:
            for join_info in joins:
                from_table = join_info['from_table']
                to_table = join_info['to_table']
                left_col = join_info['left_col']
                right_col = join_info['right_col']

                # Handle cross-model joins: dim_calendar is in 'temporal' model
                if to_table == 'dim_calendar':
                    temporal_model = self.session.load_model('temporal')
                    right_df = temporal_model.get_table(to_table)
                else:
                    right_df = model.get_table(to_table)

                dfs[to_table] = right_df

                # Join from the correct source table
                left_df = dfs[from_table]
                df = df.join(right_df, left_df[left_col] == right_df[right_col], 'left')
        else:
            # Fallback to legacy linear chain joins
            for i, next_table in enumerate(table_sequence[1:]):
                if next_table == 'dim_calendar':
                    temporal_model = self.session.load_model('temporal')
                    right_df = temporal_model.get_table(next_table)
                else:
                    right_df = model.get_table(next_table)
                left_col, right_col = join_keys[i]
                df = df.join(right_df, df[left_col] == right_df[right_col], 'left')

        # Select only required columns
        return self.select_columns(df, required_columns)

    def _execute_duckdb_joins(
        self,
        model_name: str,
        model,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using DuckDB SQL against views."""
        from core.session.filters import FilterEngine
        import time

        table_sequence = join_plan['table_sequence']
        base_table = table_sequence[0]

        # Strategy 1: Try using DuckDB views directly (most efficient)
        try:
            view_names = {}
            views_available = True

            # Check if all required tables exist as views
            for table_name in table_sequence:
                # Handle cross-model joins: dim_calendar is in 'temporal' schema
                if table_name == 'dim_calendar':
                    schema_name = 'temporal'
                else:
                    schema_name = model_name
                view_name = f'"{schema_name}"."{table_name}"'
                try:
                    # Quick check if view exists
                    self.connection.conn.execute(f"SELECT 1 FROM {view_name} LIMIT 1")
                    view_names[table_name] = view_name
                    logger.debug(f"AUTO-JOIN DUCKDB: View available: {view_name}")
                except Exception:
                    views_available = False
                    logger.debug(f"AUTO-JOIN DUCKDB: View not available: {view_name}")
                    break

            if views_available:
                logger.debug(f"AUTO-JOIN DUCKDB: Using views for {len(table_sequence)} tables")
                return self._execute_duckdb_joins_via_views(
                    model_name, view_names, join_plan,
                    required_columns, filters
                )

        except Exception as e:
            logger.debug(f"AUTO-JOIN DUCKDB: View-based join failed: {e}")

        # Strategy 2: Fall back to loading tables (slower but always works)
        logger.debug(f"AUTO-JOIN DUCKDB: Falling back to table loading for {len(table_sequence)} tables")
        return self._execute_duckdb_joins_via_tables(
            model_name, model, join_plan, required_columns, filters
        )

    def _execute_duckdb_joins_via_views(
        self,
        model_name: str,
        view_names: Dict[str, str],
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using DuckDB SQL against pre-registered views."""
        import time

        table_sequence = join_plan['table_sequence']
        joins = join_plan.get('joins', [])
        join_keys = join_plan.get('join_keys', [])

        base_table = table_sequence[0]
        base_view = view_names[base_table]

        # Build SELECT clause - qualify columns to avoid ambiguity
        select_cols = []
        for col in required_columns:
            # For each column, find which table has it
            found = False
            for table_name in table_sequence:
                view = view_names[table_name]
                try:
                    # Check if column exists in this view
                    self.connection.conn.execute(f"SELECT {col} FROM {view} LIMIT 0")
                    select_cols.append(f"{view}.{col}")
                    found = True
                    break
                except Exception:
                    continue
            if not found:
                select_cols.append(col)

        sql = f"SELECT {', '.join(select_cols)} FROM {base_view}"

        # Add joins - use joins list with source table tracking (star schema support)
        if joins:
            for join_info in joins:
                from_table = join_info['from_table']
                to_table = join_info['to_table']
                left_col = join_info['left_col']
                right_col = join_info['right_col']
                left_view = view_names[from_table]
                right_view = view_names[to_table]
                sql += f" LEFT JOIN {right_view} ON {left_view}.{left_col} = {right_view}.{right_col}"
        else:
            # Fallback to legacy linear chain format
            for i in range(1, len(table_sequence)):
                left_view = view_names[table_sequence[i - 1]]
                right_view = view_names[table_sequence[i]]
                left_col, right_col = join_keys[i - 1]
                sql += f" LEFT JOIN {right_view} ON {left_view}.{left_col} = {right_view}.{right_col}"

        # Add WHERE clause - only include filters for columns that exist
        if filters:
            # Collect all available columns from all views
            available_cols = set()
            for view in view_names.values():
                try:
                    # Extract clean view name for query
                    clean_view = view.strip('"')
                    table_only = view.split('.')[-1].strip('"')
                    cols_result = self.connection.conn.execute(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_schema || '.' || table_name = '{clean_view}' "
                        f"OR table_name = '{table_only}'"
                    ).fetchall()
                    available_cols.update(r[0] for r in cols_result)
                except Exception:
                    pass

            # Translate universal date filters via dim_calendar mapping
            translated_filters = self.translate_date_filters(
                model_name, base_table, filters, available_cols
            )

            where_clause = self._build_where_clause_for_views(translated_filters, base_view, available_cols)
            if where_clause:
                sql += f" WHERE {where_clause}"

        logger.debug(f"AUTO-JOIN DUCKDB SQL: {sql[:500]}{'...' if len(sql) > 500 else ''}")

        # Return lazy DuckDB relation - do NOT use fetchdf() which loads all data into memory
        t0 = time.time()
        result = self.connection.conn.sql(sql)
        logger.debug(f"AUTO-JOIN DUCKDB: View query prepared (lazy) in {time.time() - t0:.2f}s")

        return result

    def _execute_duckdb_joins_via_tables(
        self,
        model_name: str,
        model,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins by loading tables into temp tables (fallback method)."""
        from core.session.filters import FilterEngine
        import time

        table_sequence = join_plan['table_sequence']
        joins = join_plan.get('joins', [])
        join_keys = join_plan.get('join_keys', [])

        base_table = table_sequence[0]
        temp_tables = {}

        try:
            # Register tables as temp views - use DuckDB relations directly (lazy, no pandas)
            for table_name in table_sequence:
                t0 = time.time()
                # Handle cross-model joins: dim_calendar is in 'temporal' model
                if table_name == 'dim_calendar':
                    load_model_name = 'temporal'
                    load_model = self.session.load_model('temporal')
                else:
                    load_model_name = model_name
                    load_model = model

                # Use session to get table from Silver layer (lazy DuckDB relation)
                # This avoids triggering ensure_built() which would read from Bronze
                try:
                    df_temp = self.session._get_table_from_view_or_build(
                        load_model, load_model_name, table_name, allow_build=False
                    )
                except ValueError as e:
                    # Silver not available - DO NOT fall back to Bronze!
                    # For large tables (22M+ rows), reading from Bronze would crash the app.
                    # Instead, raise a clear error so the user knows to build Silver layer.
                    raise RuntimeError(
                        f"AUTO-JOIN: Cannot load {load_model_name}.{table_name} - Silver layer not available. "
                        f"Run: python -m scripts.build.build_models --models {load_model_name}"
                    ) from e
                t1 = time.time()
                temp_name = f"_autojoin_{table_name}"

                # Register directly as DuckDB view - DON'T convert to pandas!
                # DuckDB can register relations directly, keeping lazy evaluation
                if hasattr(df_temp, 'alias'):
                    # It's a DuckDB relation - create view directly via SQL
                    # Register the relation so we can reference it
                    self.connection.conn.register(temp_name, df_temp)
                    logger.debug(f"AUTO-JOIN DUCKDB: {table_name}: registered as lazy view in {t1-t0:.2f}s")
                elif hasattr(df_temp, 'toPandas'):
                    # Spark DataFrame - must convert (but should be rare in DuckDB path)
                    temp_df = df_temp.toPandas()
                    self.connection.conn.register(temp_name, temp_df)
                    logger.debug(f"AUTO-JOIN DUCKDB: {table_name}: Spark->pandas in {time.time()-t0:.2f}s, shape={temp_df.shape}")
                else:
                    # Already pandas or other
                    self.connection.conn.register(temp_name, df_temp)
                    shape = df_temp.shape if hasattr(df_temp, 'shape') else 'unknown'
                    logger.debug(f"AUTO-JOIN DUCKDB: {table_name}: registered in {t1-t0:.2f}s, shape={shape}")

                temp_tables[table_name] = temp_name

                # Validate that the registered table has columns
                # An empty DataFrame from missing Silver layer would have no columns
                try:
                    cols = self.connection.conn.execute(f"DESCRIBE {temp_name}").fetchall()
                    if not cols:
                        raise RuntimeError(
                            f"AUTO-JOIN: Table {load_model_name}.{table_name} has no columns. "
                            f"Silver layer may be empty or corrupted. "
                            f"Run: python -m scripts.build.build_models --models {load_model_name}"
                        )
                    col_names = {c[0] for c in cols}
                    logger.debug(f"AUTO-JOIN DUCKDB: {table_name} has {len(col_names)} columns: {list(col_names)[:5]}...")
                except RuntimeError:
                    raise
                except Exception as e:
                    raise RuntimeError(
                        f"AUTO-JOIN: Failed to validate {load_model_name}.{table_name}: {e}. "
                        f"Silver layer may not exist. "
                        f"Run: python -m scripts.build.build_models --models {load_model_name}"
                    ) from e

            # Validate join columns exist before building SQL
            for join_info in joins:
                from_table = join_info['from_table']
                to_table = join_info['to_table']
                left_col = join_info['left_col']
                right_col = join_info['right_col']

                # Check left table has left column
                from_temp = temp_tables[from_table]
                from_cols = self.connection.conn.execute(f"DESCRIBE {from_temp}").fetchall()
                from_col_names = {c[0] for c in from_cols}
                if left_col not in from_col_names:
                    raise RuntimeError(
                        f"AUTO-JOIN: Join column '{left_col}' not found in {from_table}. "
                        f"Available columns: {sorted(from_col_names)[:10]}. "
                        f"Silver layer may need to be rebuilt."
                    )

                # Check right table has right column
                to_temp = temp_tables[to_table]
                to_cols = self.connection.conn.execute(f"DESCRIBE {to_temp}").fetchall()
                to_col_names = {c[0] for c in to_cols}
                if right_col not in to_col_names:
                    raise RuntimeError(
                        f"AUTO-JOIN: Join column '{right_col}' not found in {to_table}. "
                        f"Available columns: {sorted(to_col_names)[:10]}. "
                        f"Silver layer may need to be rebuilt."
                    )

            # Build SQL with proper qualified column names
            base_temp = temp_tables[base_table]
            select_cols = self._build_select_cols(model, table_sequence, temp_tables, required_columns)

            sql = f"SELECT {', '.join(select_cols)} FROM {base_temp}"

            # Add each join - use joins list with source table tracking (star schema support)
            # This correctly handles star schemas where fact joins to multiple dims
            if joins:
                # New format: each join specifies from_table and to_table
                for join_info in joins:
                    from_table = join_info['from_table']
                    to_table = join_info['to_table']
                    left_col = join_info['left_col']
                    right_col = join_info['right_col']
                    left_temp = temp_tables[from_table]
                    right_temp = temp_tables[to_table]
                    sql += f" LEFT JOIN {right_temp} ON {left_temp}.{left_col} = {right_temp}.{right_col}"
            else:
                # Fallback to legacy format (linear chain assumption)
                for i in range(1, len(table_sequence)):
                    left_temp = temp_tables[table_sequence[i - 1]]
                    right_temp = temp_tables[table_sequence[i]]
                    left_col, right_col = join_keys[i - 1]
                    sql += f" LEFT JOIN {right_temp} ON {left_temp}.{left_col} = {right_temp}.{right_col}"

            # Add WHERE clause for filters - only include columns that exist
            if filters:
                # Collect available columns from loaded tables AND build table->columns mapping
                # This is needed for proper column qualification in WHERE clause
                available_cols = set()
                table_columns = {}
                for table_name, temp_name in temp_tables.items():
                    try:
                        cols = self.connection.conn.execute(f"DESCRIBE {temp_name}").fetchall()
                        col_set = {c[0] for c in cols}
                        table_columns[table_name] = col_set
                        available_cols.update(col_set)
                    except Exception:
                        table_columns[table_name] = set()

                # Translate universal date filters via dim_calendar mapping
                translated_filters = self.translate_date_filters(
                    model_name, base_table, filters, available_cols
                )

                where_clause = self._build_where_clause(
                    translated_filters, base_temp, available_cols,
                    table_columns=table_columns, temp_tables=temp_tables
                )
                if where_clause:
                    sql += f" WHERE {where_clause}"

            logger.debug(f"AUTO-JOIN DUCKDB SQL: {sql[:500]}{'...' if len(sql) > 500 else ''}")

            # Execute the join query - return LAZY relation, NOT fetchdf()!
            # fetchdf() would load ALL rows into pandas memory (crashes on 22M rows)
            # Use conn.sql() which returns a lazy DuckDB relation
            t0 = time.time()
            result = self.connection.conn.sql(sql)
            logger.debug(f"AUTO-JOIN DUCKDB: SQL prepared (lazy) in {time.time() - t0:.2f}s")

            # NOTE: We intentionally DON'T clean up temp tables here because
            # the lazy result still references them. They'll be cleaned up
            # when the connection closes or when result is garbage collected.
            # For a long-running app, we may want to track and clean them periodically.

            return result

        except Exception as e:
            logger.error(f"AUTO-JOIN DUCKDB FAILED: {e}", exc_info=True)

            # Cleanup temp tables on failure
            for temp_name in temp_tables.values():
                try:
                    self.connection.conn.unregister(temp_name)
                except Exception:
                    pass

            # DON'T fall back to model.get_table() - that triggers Bronze reads!
            # For large fact tables (22M+ rows), this would crash the app.
            # Instead, re-raise the exception so the caller knows there's an issue.
            raise RuntimeError(
                f"AUTO-JOIN failed for {model_name}: {e}. "
                f"Check that Silver layer exists at the configured storage path."
            ) from e

    def _build_where_clause_for_views(
        self,
        filters: Dict[str, Any],
        base_view: str,
        available_cols: Optional[set] = None
    ) -> str:
        """Build WHERE clause from filters for view-based queries.

        Only includes filters for columns that exist in the joined tables.
        Handles date_id columns by converting date strings to integers.
        """
        where_clauses = []

        for col, filter_val in filters.items():
            # Skip filters for columns that don't exist in the tables
            if available_cols is not None and col not in available_cols:
                logger.debug(f"AUTO-JOIN WHERE: Skipping filter on '{col}' - column not in joined tables")
                continue

            # Check if this is a date_id column (integer YYYYMMDD format)
            is_date_id_col = col == 'date_id'

            if isinstance(filter_val, dict):
                if 'start' in filter_val and 'end' in filter_val:
                    start_val = filter_val['start']
                    end_val = filter_val['end']
                    if is_date_id_col:
                        start_int = self._convert_date_to_date_id(start_val)
                        end_int = self._convert_date_to_date_id(end_val)
                        if start_int and end_int:
                            where_clauses.append(f"{base_view}.{col} BETWEEN {start_int} AND {end_int}")
                        else:
                            logger.warning(f"AUTO-JOIN WHERE: Failed to convert date_id filter: {start_val}, {end_val}")
                    else:
                        where_clauses.append(f"{base_view}.{col} BETWEEN '{start_val}' AND '{end_val}'")
                elif 'min' in filter_val and 'max' in filter_val:
                    where_clauses.append(f"{base_view}.{col} BETWEEN {filter_val['min']} AND {filter_val['max']}")
                elif 'min' in filter_val:
                    where_clauses.append(f"{base_view}.{col} >= {filter_val['min']}")
                elif 'max' in filter_val:
                    where_clauses.append(f"{base_view}.{col} <= {filter_val['max']}")
            elif isinstance(filter_val, list):
                if is_date_id_col:
                    int_vals = [self._convert_date_to_date_id(v) for v in filter_val]
                    int_vals = [v for v in int_vals if v is not None]
                    if int_vals:
                        vals = ", ".join(str(v) for v in int_vals)
                        where_clauses.append(f"{base_view}.{col} IN ({vals})")
                elif all(isinstance(v, str) for v in filter_val):
                    vals = "', '".join(filter_val)
                    where_clauses.append(f"{base_view}.{col} IN ('{vals}')")
                else:
                    vals = ", ".join(str(v) for v in filter_val)
                    where_clauses.append(f"{base_view}.{col} IN ({vals})")
            else:
                if is_date_id_col and isinstance(filter_val, str):
                    int_val = self._convert_date_to_date_id(filter_val)
                    if int_val:
                        where_clauses.append(f"{base_view}.{col} = {int_val}")
                    else:
                        where_clauses.append(f"{base_view}.{col} = '{filter_val}'")
                elif isinstance(filter_val, str):
                    where_clauses.append(f"{base_view}.{col} = '{filter_val}'")
                else:
                    where_clauses.append(f"{base_view}.{col} = {filter_val}")

        return " AND ".join(where_clauses) if where_clauses else ""

    def _build_select_cols(
        self,
        model,
        table_sequence: List[str],
        temp_tables: Dict[str, str],
        required_columns: List[str]
    ) -> List[str]:
        """Build qualified column names for SELECT clause.

        Uses DESCRIBE on registered temp tables to find column locations.
        Does NOT call model.get_table() which would trigger Bronze reads.
        """
        logger.debug(f"_build_select_cols: table_sequence={table_sequence}")
        logger.debug(f"_build_select_cols: temp_tables keys={list(temp_tables.keys())}")

        # Build column index from temp tables using DESCRIBE (no Bronze reads!)
        table_columns = {}
        for table_name, temp_name in temp_tables.items():
            try:
                cols = self.connection.conn.execute(f"DESCRIBE {temp_name}").fetchall()
                table_columns[table_name] = {c[0] for c in cols}
                logger.debug(f"_build_select_cols: {table_name} has {len(table_columns[table_name])} columns")
            except Exception as e:
                logger.warning(f"_build_select_cols: DESCRIBE {temp_name} failed: {e}")
                table_columns[table_name] = set()

        select_cols = []
        for col in required_columns:
            found = False
            for table_name in table_sequence:
                if col in table_columns.get(table_name, set()):
                    select_cols.append(f"{temp_tables[table_name]}.{col}")
                    found = True
                    logger.debug(f"_build_select_cols: '{col}' found in {table_name}")
                    break
            if not found:
                # Column not found in any table - add unqualified (will error if missing)
                logger.warning(f"_build_select_cols: '{col}' NOT FOUND in any table!")
                select_cols.append(col)
        return select_cols

    def _convert_date_to_date_id(self, date_str: str) -> Optional[int]:
        """Convert a date string to date_id integer format (YYYYMMDD).

        Args:
            date_str: Date string in various formats (YYYY-MM-DD, YYYY/MM/DD, etc.)

        Returns:
            Integer date_id (e.g., 20260120) or None if conversion fails
        """
        import re
        # Try to extract YYYY, MM, DD from common date formats
        # Handles: 2026-01-20, 2026/01/20, 20260120
        match = re.match(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', str(date_str))
        if match:
            year, month, day = match.groups()
            return int(f"{year}{month}{day}")
        return None

    def _build_where_clause(
        self,
        filters: Dict[str, Any],
        base_temp: str,
        available_cols: Optional[set] = None,
        table_columns: Optional[Dict[str, set]] = None,
        temp_tables: Optional[Dict[str, str]] = None
    ) -> str:
        """Build WHERE clause from filters.

        Only includes filters for columns that exist in the joined tables.
        Qualifies columns to the correct table (not always base_temp).

        Args:
            filters: Filter dict
            base_temp: Base temp table name (used as fallback)
            available_cols: Set of all available columns across joined tables
            table_columns: Dict mapping table_name -> set of columns
            temp_tables: Dict mapping table_name -> temp_table_name
        """
        where_clauses = []

        for col, filter_val in filters.items():
            # Skip filters for columns that don't exist in the tables
            if available_cols is not None and col not in available_cols:
                logger.debug(f"AUTO-JOIN WHERE: Skipping filter on '{col}' - column not in joined tables")
                continue

            # Find which table has this column
            qualified_col = f"{base_temp}.{col}"  # Default to base table
            if table_columns and temp_tables:
                for table_name, cols in table_columns.items():
                    if col in cols:
                        qualified_col = f"{temp_tables[table_name]}.{col}"
                        break

            # Check if this is a date_id column (integer YYYYMMDD format)
            # Date strings need to be converted to integers for these columns
            is_date_id_col = col == 'date_id'

            if isinstance(filter_val, dict):
                # Range filter
                if 'start' in filter_val and 'end' in filter_val:
                    start_val = filter_val['start']
                    end_val = filter_val['end']
                    if is_date_id_col:
                        # Convert date strings to integers
                        start_int = self._convert_date_to_date_id(start_val)
                        end_int = self._convert_date_to_date_id(end_val)
                        if start_int and end_int:
                            where_clauses.append(f"{qualified_col} BETWEEN {start_int} AND {end_int}")
                            logger.debug(f"AUTO-JOIN WHERE: date_id filter converted: {start_val} -> {start_int}, {end_val} -> {end_int}")
                        else:
                            logger.warning(f"AUTO-JOIN WHERE: Failed to convert date_id filter values: {start_val}, {end_val}")
                    else:
                        where_clauses.append(f"{qualified_col} BETWEEN '{start_val}' AND '{end_val}'")
                elif 'min' in filter_val and 'max' in filter_val:
                    where_clauses.append(f"{qualified_col} BETWEEN {filter_val['min']} AND {filter_val['max']}")
                elif 'min' in filter_val:
                    where_clauses.append(f"{qualified_col} >= {filter_val['min']}")
                elif 'max' in filter_val:
                    where_clauses.append(f"{qualified_col} <= {filter_val['max']}")
            elif isinstance(filter_val, list):
                # IN filter
                if is_date_id_col:
                    # Convert all date strings to integers
                    int_vals = [self._convert_date_to_date_id(v) for v in filter_val]
                    int_vals = [v for v in int_vals if v is not None]
                    if int_vals:
                        vals = ", ".join(str(v) for v in int_vals)
                        where_clauses.append(f"{qualified_col} IN ({vals})")
                elif all(isinstance(v, str) for v in filter_val):
                    vals = "', '".join(filter_val)
                    where_clauses.append(f"{qualified_col} IN ('{vals}')")
                else:
                    vals = ", ".join(str(v) for v in filter_val)
                    where_clauses.append(f"{qualified_col} IN ({vals})")
            else:
                # Equality filter
                if is_date_id_col and isinstance(filter_val, str):
                    int_val = self._convert_date_to_date_id(filter_val)
                    if int_val:
                        where_clauses.append(f"{qualified_col} = {int_val}")
                    else:
                        where_clauses.append(f"{qualified_col} = '{filter_val}'")
                elif isinstance(filter_val, str):
                    where_clauses.append(f"{qualified_col} = '{filter_val}'")
                else:
                    where_clauses.append(f"{qualified_col} = {filter_val}")

        return " AND ".join(where_clauses) if where_clauses else ""
