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

# Filter parameter translation map
# These are filter PARAMETERS (not column names) that need special handling.
# They get translated to column conditions with specific operators.
# Format: parameter_name -> (target_column, operator)
FILTER_PARAMETER_MAP: Dict[str, Tuple[str, str]] = {
    'start_date': ('date', '>='),   # start_date -> date >= value
    'end_date': ('date', '<='),     # end_date -> date <= value
}

# Filter parameters that should be silently dropped (not applicable to all tables)
# These are valid notebook filters but don't apply to all data sources
DROPPABLE_FILTER_PARAMS: Set[str] = {
    'report_type',    # Only applies to financial statements, not price data
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
        # Cache view column information to avoid expensive queries
        self._view_columns_cache: Dict[str, Set[str]] = {}
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
        missing_columns: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Plan join sequence to get missing columns using model graph.

        Supports star schemas where a fact table joins to multiple dimensions,
        not just linear chains.

        Args:
            model_name: Model name
            base_table: Starting table
            missing_columns: Columns to find
            filters: Optional filters dict - will join tables needed to apply filters

        Returns:
            Join plan dict with:
                - table_sequence: List of tables to join
                - joins: List of join info dicts with from_table, to_table, left_col, right_col
                - target_columns: Which columns come from which table

        Raises:
            ValueError: If no join path found
        """
        import time
        logger.debug(f"AUTO-JOIN PLAN: Starting for {model_name}.{base_table}, missing={missing_columns}, filters={list(filters.keys()) if filters else []}")
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

        # Get base table schema to check which filter columns already exist
        base_table_cols = set()
        try:
            model = self.session.load_model(model_name)
            base_schema = model.get_table_schema(base_table)
            base_table_cols = set(base_schema.keys())
            logger.debug(f"AUTO-JOIN PLAN: Base table '{base_table}' has {len(base_table_cols)} columns")
        except Exception as e:
            logger.warning(f"AUTO-JOIN PLAN: Could not get base table schema: {e}")

        # Also find tables needed for filter columns
        if filters:
            logger.debug(f"AUTO-JOIN PLAN: Checking filter columns: {list(filters.keys())}")
            for filter_col in filters.keys():
                # Skip if column is already in target_tables
                if filter_col in target_tables:
                    continue

                # Skip if column exists in base table (no join needed)
                if filter_col in base_table_cols:
                    logger.debug(f"AUTO-JOIN PLAN: Filter column '{filter_col}' exists in base table, no join needed")
                    continue

                # Look up the filter column in the column index
                if filter_col in column_index:
                    filter_table = column_index[filter_col][0]
                    # Only add if it's not the base table
                    if filter_table != base_table:
                        target_tables[filter_col] = filter_table
                        logger.info(f"AUTO-JOIN PLAN: Filter column '{filter_col}' requires joining '{filter_table}'")
                    else:
                        logger.debug(f"AUTO-JOIN PLAN: Filter column '{filter_col}' is in base table")
                else:
                    # Not an error - filter might apply via period overlap or other mechanism
                    logger.debug(f"AUTO-JOIN PLAN: Filter column '{filter_col}' not in column index (may use period overlap)")

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
        # Note: YAML 1.1 treats 'on' as boolean True, so we check both keys
        for i, edge in enumerate(edges):
            edge_from = edge.get('from', '')
            edge_to = edge.get('to', '')
            edge_on = edge.get('on', edge.get(True, []))  # Handle YAML 1.1 'on' -> True quirk
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

            added_any_table = False
            remaining = needed_tables - seen_tables
            logger.debug(f"AUTO-JOIN PLAN: Iteration {iteration}, still need: {remaining}")

            # Star schema support: Add reachable tables in each iteration,
            # but ONLY add edges that lead toward target tables to avoid unnecessary joins.
            # Special case: If we're looking for 'date' column on a table with period columns,
            # prefer the period_end edge over period_start
            prefer_period_end = (
                'date' in missing_columns and
                'dim_calendar' in needed_tables and
                base_table in current_tables
            )
            logger.debug(f"AUTO-JOIN PLAN: prefer_period_end={prefer_period_end}")

            for edge in edges:
                # Early exit: stop if we've reached all target tables
                if all(tbl in seen_tables for tbl in target_tables.values()):
                    logger.debug(f"AUTO-JOIN PLAN: All target tables reached, stopping edge traversal")
                    break

                edge_from = edge.get('from', '')
                edge_to = edge.get('to', '')
                cross_model = None  # Track if this is a cross-model edge

                # Handle cross-model edges (e.g., temporal.dim_calendar, company.dim_company)
                # These are foundational/shared dimensions that models can join to
                if '.' in edge_to:
                    # Parse cross-model reference: "model.table" or "category.model.table"
                    parts = edge_to.split('.')
                    cross_model = parts[0]  # e.g., "temporal", "company"
                    edge_to = parts[-1]  # e.g., "dim_calendar", "dim_company"
                    logger.debug(f"AUTO-JOIN PLAN: Cross-model edge {edge_from} -> {cross_model}.{edge_to}")

                # Check if this edge connects a current table to a new table
                if edge_from in current_tables and edge_to not in seen_tables:
                    # Special handling: If we're joining to dim_calendar for 'date' column,
                    # prefer period_end edge over period_start
                    if prefer_period_end and edge_to == 'dim_calendar':
                        # Handle both v1.x ('on' key) and v2.0 (True key) formats
                        on_conditions = edge.get('on', edge.get(True, []))
                        if on_conditions:
                            first_condition = on_conditions[0] if isinstance(on_conditions, list) else on_conditions
                            # Skip period_start edges when looking for 'date'
                            if 'period_start' in str(first_condition).lower():
                                logger.debug(f"AUTO-JOIN PLAN: Skipping period_start edge for 'date' column: {first_condition}")
                                continue  # Skip this edge, continue to find period_end edge
                            else:
                                logger.debug(f"AUTO-JOIN PLAN: Using period_end edge for 'date' column: {first_condition}")
                    # OPTIMIZATION: Only add edges that lead toward our target tables
                    # Skip edges that go to tables not needed for our required columns
                    is_target_table = edge_to in needed_tables
                    is_on_path_to_target = edge_to in ('dim_security', 'dim_stock')  # Common intermediate tables

                    # For non-target tables, check if they might lead to a target
                    # We need to traverse intermediate tables to reach our targets
                    # But skip tables like dim_calendar/dim_company if not needed
                    if not is_target_table and not is_on_path_to_target:
                        logger.debug(f"AUTO-JOIN PLAN: Skipping edge to {edge_to} - not needed for target columns")
                        continue

                    # Add this table to sequence
                    table_sequence.append(edge_to)
                    seen_tables.add(edge_to)
                    current_tables.add(edge_to)

                    # Extract join keys - track the source table for star schema support
                    on_conditions = edge.get('on', edge.get(True, []))
                    if on_conditions:
                        # Parse "col1=col2" format
                        left_col, right_col = self._parse_join_condition(on_conditions[0])
                        join_info = {
                            'from_table': edge_from,
                            'to_table': edge_to,
                            'left_col': left_col,
                            'right_col': right_col
                        }
                        # Track cross-model reference for loading from correct model
                        if cross_model:
                            join_info['cross_model'] = cross_model
                            logger.debug(f"AUTO-JOIN PLAN: Added cross-model join {edge_from}.{left_col} = {cross_model}.{edge_to}.{right_col}")
                        else:
                            logger.debug(f"AUTO-JOIN PLAN: Added join {edge_from}.{left_col} = {edge_to}.{right_col}")
                        joins.append(join_info)

                    added_any_table = True
                    # Continue to potentially find more needed tables in this iteration

            if not added_any_table:
                # Log detailed failure info for debugging
                logger.error(f"AUTO-JOIN PLAN: Failed to find any connecting edges.")
                logger.error(f"  Current tables: {current_tables}")
                logger.error(f"  Seen tables: {seen_tables}")
                logger.error(f"  Still need: {remaining}")
                logger.error(f"  Available edges:")
                for edge in edges:
                    ef = edge.get('from', '')
                    et = edge.get('to', '')
                    # Show cross-model edges clearly
                    if '.' in et:
                        cross_model = et.split('.')[0]
                        table_name = et.split('.')[-1]
                        logger.error(f"    {ef} -> {cross_model}.{table_name}")
                    else:
                        logger.error(f"    {ef} -> {et}")

                raise ValueError(
                    f"Cannot find join path from {base_table} to columns {missing_columns}. "
                    f"Reached tables: {seen_tables}. Still need: {remaining}. "
                    f"Ensure model graph has edges connecting these tables."
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
                # Also include foundational/shared schemas that models commonly join to:
                # - temporal: calendar dimension (date_id, date, year, month, etc.)
                # - company: company dimension (sector, industry, etc.)
                # - securities: master security dimension (ticker, asset_type, etc.)
                # - stocks: stock dimension (sector, industry, market_cap, etc.)
                result = self.connection.conn.execute(f"""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = '{model_name}'
                       OR table_schema = 'temporal'
                       OR table_schema = 'company'
                       OR table_schema = 'securities'
                       OR table_schema = 'stocks'
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

                    # Sort tables by priority:
                    # 1. Tables from the same schema as requested model (highest priority)
                    # 2. Tables from related/foundational schemas
                    # 3. Tables that are cross-model joins (lower priority to avoid wrong ticker sources)
                    #
                    # Get table schema info for proper priority assignment
                    table_schemas = {}
                    for table_name, column_name in result:
                        if table_name not in table_schemas:
                            # Get schema for this table from the query
                            schema_result = self.connection.conn.execute(f"""
                                SELECT table_schema FROM information_schema.columns
                                WHERE table_name = '{table_name}' LIMIT 1
                            """).fetchone()
                            table_schemas[table_name] = schema_result[0] if schema_result else 'unknown'

                    def table_priority(table_name: str) -> int:
                        table_schema = table_schemas.get(table_name, '')

                        # Tables from the requested model's schema get highest priority
                        if table_schema == model_name:
                            return 0

                        # Tables from 'securities' base schema (when model IS securities)
                        # or from a closely related schema get medium-high priority
                        if model_name == 'securities.master' and table_schema == 'securities':
                            return 0
                        if model_name == 'securities.stocks' and table_schema in ('stocks', 'securities'):
                            # For stocks model, prefer stocks tables, then securities
                            return 0 if table_schema == 'stocks' else 1

                        # Temporal dimension is commonly joined - medium priority
                        if table_schema == 'temporal':
                            return 2

                        # Company dimension is often cross-model - lower priority
                        # to avoid picking company.dim_company.ticker over securities.dim_security.ticker
                        if table_schema == 'company':
                            return 3

                        # Other cross-model tables
                        return 4

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

                    # If we got a good index from DuckDB, skip model schema augmentation
                    # This avoids triggering Bronze reads via model.list_tables() -> ensure_built()
                    if index:
                        # Log key columns for debugging join issues
                        for key_col in ['ticker', 'company_id', 'date_id', 'date', 'sector', 'industry']:
                            if key_col in index:
                                logger.debug(f"AUTO-JOIN INDEX: '{key_col}' found in tables: {index[key_col]}")

                        # Cache for future calls
                        self._column_index_cache[model_name] = index
                        return index

            except Exception as e:
                logger.debug(f"AUTO-JOIN INDEX: DuckDB catalog lookup failed: {e}, falling back to model schema")

        # Strategy 2: Augment with model schema for tables not found in DuckDB
        # This is a FALLBACK only used when DuckDB views aren't available
        # WARNING: This can trigger Bronze reads via model.list_tables() -> ensure_built()
        logger.debug(f"AUTO-JOIN INDEX: Falling back to model schema (DuckDB index empty or failed)")
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
        for key_col in ['ticker', 'company_id', 'date_id', 'date', 'sector', 'industry']:
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

    def translate_filter_parameters(
        self,
        filters: Optional[Dict[str, Any]],
        available_cols: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Translate filter parameters to column-based filters.

        This converts special filter parameters like 'start_date' and 'end_date'
        into proper column filters that can be applied to the query.

        For example:
            {'start_date': '2024-01-01', 'end_date': '2024-12-31', 'ticker': 'AAPL'}
        becomes:
            {'date': {'start': '2024-01-01', 'end': '2024-12-31'}, 'ticker': 'AAPL'}

        Args:
            filters: Original filter dict with potential parameter names
            available_cols: Set of columns available in the query (for validation)

        Returns:
            Translated filter dict with column names and proper operators
        """
        if not filters:
            return filters or {}

        translated = {}
        date_range = {}  # Collect date range components

        for key, val in filters.items():
            # Check if this is a filter parameter that needs translation
            if key in FILTER_PARAMETER_MAP:
                target_col, operator = FILTER_PARAMETER_MAP[key]
                logger.info(f"FILTER PARAM: Translating '{key}' -> '{target_col}' {operator} '{val}'")

                # Build date range filter
                if operator == '>=':
                    date_range['start'] = val
                elif operator == '<=':
                    date_range['end'] = val
                else:
                    # Direct operator filter (for future extensions)
                    translated[target_col] = {'operator': operator, 'value': val}

            elif key in DROPPABLE_FILTER_PARAMS:
                # Only drop if the column doesn't actually exist in this table
                # If it exists, pass it through (e.g., report_type exists in company tables)
                if available_cols is not None and key in available_cols:
                    translated[key] = val
                else:
                    logger.debug(f"FILTER PARAM: Dropping '{key}' (not applicable to this table)")
                    continue

            else:
                # Pass through as-is (column filter)
                translated[key] = val

        # If we collected date range components, add as range filter
        if date_range:
            if 'start' in date_range and 'end' in date_range:
                translated['date'] = {'start': date_range['start'], 'end': date_range['end']}
                logger.info(f"FILTER PARAM: Created date range filter: {date_range['start']} to {date_range['end']}")
            elif 'start' in date_range:
                translated['date'] = {'start': date_range['start'], 'end': '9999-12-31'}
                logger.info(f"FILTER PARAM: Created date filter with start only: >= {date_range['start']}")
            elif 'end' in date_range:
                translated['date'] = {'start': '1900-01-01', 'end': date_range['end']}
                logger.info(f"FILTER PARAM: Created date filter with end only: <= {date_range['end']}")

        logger.info(f"FILTER PARAM: Input {len(filters)} filters -> Output {len(translated)} filters")
        return translated

    def translate_date_filters(
        self,
        model_name: str,
        base_table: str,
        filters: Dict[str, Any],
        available_cols: Set[str]
    ) -> Dict[str, Any]:
        """
        Translate universal date filters to use dim_calendar.date when available.

        IMPROVED: When dim_calendar is in the join (which has a proper 'date' column),
        we filter on dim_calendar.date directly instead of converting to date_id integers.
        This is cleaner and avoids date format conversion issues.

        IMPORTANT: If the original filters contain an explicit 'date' filter, that takes
        priority. Other universal date columns (forecast_date, trade_date, etc.) will only
        translate to 'date' if no explicit 'date' filter exists.

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

        # Check if dim_calendar's 'date' column is available in the join
        # If so, we can filter on it directly - no need to use date_id
        calendar_date_available = 'date' in available_cols

        # Check if the original filters have an explicit 'date' filter
        # If so, that takes priority over other universal date columns
        has_explicit_date_filter = 'date' in filters

        # Check for period overlap case
        # If we have period_start_date_id and period_end_date_id, date filters should use overlap logic
        has_period_columns = 'period_start_date_id' in available_cols and 'period_end_date_id' in available_cols
        # Don't log massive available_cols set - it can have thousands of columns from all views!
        logger.info(f"DATE TRANSLATE START: has_period_columns={has_period_columns}, {len(available_cols)} columns available")

        translated = {}
        logger.info(f"DATE TRANSLATE: About to loop over {len(filters)} filters: {list(filters.keys())}")
        for col, val in filters.items():
            logger.info(f"DATE TRANSLATE: Processing '{col}'")
            # Check if this is a universal date column that needs translation
            if col in UNIVERSAL_DATE_COLUMNS:
                logger.info(f"DATE TRANSLATE: '{col}' IS universal date column")
                if col == 'date':
                    # Explicit 'date' filter - always keep it (highest priority)
                    if calendar_date_available:
                        logger.debug(f"DATE TRANSLATE: {col} -> date (explicit date filter, using dim_calendar.date)")
                        translated['date'] = val
                    elif col in available_cols:
                        translated[col] = val
                    elif has_period_columns:
                        # IMPORTANT: Keep 'date' as-is when period columns exist
                        # The WHERE clause builder will detect this and apply period overlap logic
                        logger.info(f"DATE TRANSLATE: {col} -> date (period overlap case - keeping original key)")
                        translated['date'] = val
                    else:
                        # Fallback to local date column
                        local_date_col = self.get_calendar_date_column(model_name, base_table)
                        if local_date_col and local_date_col in available_cols:
                            logger.debug(f"DATE TRANSLATE: {col} -> {local_date_col} (fallback to local column)")
                            translated[local_date_col] = val
                        else:
                            logger.debug(f"DATE TRANSLATE: Skipping {col} - no suitable date column found")
                elif has_explicit_date_filter:
                    # Other universal date columns (forecast_date, trade_date, etc.)
                    # Skip them if we already have an explicit 'date' filter to avoid overwriting
                    logger.debug(f"DATE TRANSLATE: Skipping {col} - explicit 'date' filter takes priority")
                elif calendar_date_available and 'date' not in translated:
                    # No explicit date filter, translate this to 'date' (only if not already set)
                    logger.debug(f"DATE TRANSLATE: {col} -> date (using dim_calendar.date directly)")
                    translated['date'] = val
                elif col in available_cols:
                    # Column exists as-is, keep it
                    translated[col] = val
                else:
                    # Try to get the local date column (like date_id)
                    local_date_col = self.get_calendar_date_column(model_name, base_table)
                    if local_date_col and local_date_col in available_cols:
                        logger.debug(f"DATE TRANSLATE: {col} -> {local_date_col} (fallback to local column)")
                        translated[local_date_col] = val
                    else:
                        logger.debug(f"DATE TRANSLATE: Skipping {col} - no suitable date column found")
            else:
                # Keep non-date filters as-is
                logger.info(f"DATE TRANSLATE: '{col}' is NOT a date column, keeping as-is")
                translated[col] = val

        logger.info(f"DATE TRANSLATE: LOOP COMPLETE - returning {len(translated)} translated filters")
        return translated

    def execute_auto_joins(
        self,
        model_name: str,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Execute the join plan to get required columns with optional SQL-level aggregation.

        Args:
            model_name: Model name
            join_plan: Join plan from plan_auto_joins
            required_columns: Columns to return
            filters: Optional filters to apply in WHERE clause
            group_by: Optional columns to GROUP BY (pushed to SQL)
            aggregations: Optional dict of column -> agg function (e.g., {'volume': 'sum'})

        Returns:
            DataFrame with required columns (filtered and aggregated if specified)
        """
        from de_funk.core.session.filters import FilterEngine

        # Log input filters for debugging
        if filters:
            logger.info(f"AUTO-JOIN EXECUTE: Input filters = {filters}")
        else:
            logger.info(f"AUTO-JOIN EXECUTE: No filters provided")

        if group_by:
            logger.info(f"AUTO-JOIN EXECUTE: SQL GROUP BY = {group_by}, aggregations = {aggregations}")

        model = self.session.load_model(model_name)
        table_sequence = join_plan['table_sequence']

        if self.backend == 'spark':
            return self._execute_spark_joins(
                model, join_plan, required_columns, filters,
                group_by=group_by, aggregations=aggregations
            )
        else:
            return self._execute_duckdb_joins(
                model_name, model, join_plan, required_columns, filters,
                group_by=group_by, aggregations=aggregations
            )

    def _execute_spark_joins(
        self,
        model,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]],
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """Execute joins using Spark DataFrame API with optional aggregation."""
        from de_funk.core.session.filters import FilterEngine

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

        # Apply GROUP BY aggregation if specified
        if group_by:
            from pyspark.sql import functions as F

            # Normalize group_by columns to just column names
            group_cols = [gb.split('.')[-1] for gb in group_by]

            # Determine which columns are measures (need aggregation)
            measure_cols = [col for col in required_columns if col not in group_cols]

            # Build aggregation expressions
            agg_exprs = []
            for col in measure_cols:
                agg_func = (aggregations or {}).get(col, 'sum').lower()
                if agg_func == 'sum':
                    agg_exprs.append(F.sum(col).alias(col))
                elif agg_func in ('avg', 'mean'):
                    agg_exprs.append(F.avg(col).alias(col))
                elif agg_func == 'count':
                    agg_exprs.append(F.count(col).alias(col))
                elif agg_func == 'min':
                    agg_exprs.append(F.min(col).alias(col))
                elif agg_func == 'max':
                    agg_exprs.append(F.max(col).alias(col))
                else:
                    agg_exprs.append(F.sum(col).alias(col))

            if agg_exprs:
                df = df.groupBy(*group_cols).agg(*agg_exprs)
                logger.info(f"AUTO-JOIN SPARK: Aggregated by {group_cols}")
            else:
                df = df.select(*group_cols).distinct()

            return df

        # Select only required columns
        return self.select_columns(df, required_columns)

    def _execute_duckdb_joins(
        self,
        model_name: str,
        model,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]],
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """Execute joins using DuckDB SQL against views with optional aggregation."""
        from de_funk.core.session.filters import FilterEngine
        import time

        table_sequence = join_plan['table_sequence']
        base_table = table_sequence[0]

        # Strategy 1: Try using DuckDB views directly (most efficient)
        try:
            view_names = {}
            views_available = True

            # Build map of table -> cross_model schema from joins
            cross_model_map = {}
            for join_info in join_plan.get('joins', []):
                if 'cross_model' in join_info:
                    cross_model_map[join_info['to_table']] = join_info['cross_model']

            # Check if all required tables exist as views
            for table_name in table_sequence:
                # Use cross_model info from joins to determine schema
                if table_name in cross_model_map:
                    schema_name = cross_model_map[table_name]
                    logger.debug(f"AUTO-JOIN DUCKDB: Using cross-model schema '{schema_name}' for '{table_name}'")
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
                    required_columns, filters,
                    group_by=group_by, aggregations=aggregations
                )

        except Exception as e:
            logger.debug(f"AUTO-JOIN DUCKDB: View-based join failed: {e}")

        # Strategy 2: Fall back to loading tables (slower but always works)
        logger.debug(f"AUTO-JOIN DUCKDB: Falling back to table loading for {len(table_sequence)} tables")
        return self._execute_duckdb_joins_via_tables(
            model_name, model, join_plan, required_columns, filters,
            group_by=group_by, aggregations=aggregations
        )

    def _execute_duckdb_joins_via_views(
        self,
        model_name: str,
        view_names: Dict[str, str],
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]],
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """Execute joins using DuckDB SQL against pre-registered views with optional aggregation."""
        logger.info(f">>>>>> _execute_duckdb_joins_via_views CALLED with filters={filters}")
        if group_by:
            logger.info(f">>>>>> SQL GROUP BY: {group_by}, aggregations: {aggregations}")
        import time

        table_sequence = join_plan['table_sequence']
        joins = join_plan.get('joins', [])
        join_keys = join_plan.get('join_keys', [])

        base_table = table_sequence[0]
        base_view = view_names[base_table]

        # Build SELECT clause - qualify columns to avoid ambiguity
        # Use target_columns from join plan to know which table each column comes from
        target_columns = join_plan.get('target_columns', {})
        select_cols = []
        missing_cols = []
        # Track qualified column names for GROUP BY
        qualified_group_cols = []

        logger.info(f"AUTO-JOIN SELECT BUILD: target_columns from join_plan = {target_columns}")
        logger.info(f"AUTO-JOIN SELECT BUILD: table_sequence = {table_sequence}")
        logger.info(f"AUTO-JOIN SELECT BUILD: required_columns = {required_columns}")

        # Normalize group_by columns to just column names (strip model.table prefix)
        group_by_cols = set()
        if group_by:
            for gb in group_by:
                # Handle model.table.column format - extract just the column name
                parts = gb.split('.')
                group_by_cols.add(parts[-1])  # Last part is the column name
            logger.info(f"AUTO-JOIN GROUP BY: Normalized group_by columns: {group_by_cols}")

        for col in required_columns:
            found = False
            qualified_col = None

            # First, check if we know from the join plan which table has this column
            if col in target_columns:
                expected_table = target_columns[col]
                logger.info(f"AUTO-JOIN SELECT: '{col}' expected in table '{expected_table}' per join_plan")
                if expected_table in view_names:
                    view = view_names[expected_table]
                    try:
                        # Verify column exists in the expected view
                        self.connection.conn.execute(f"SELECT {col} FROM {view} LIMIT 0")
                        qualified_col = f"{view}.{col}"
                        found = True
                        logger.info(f"AUTO-JOIN SELECT: Found '{col}' in expected table '{expected_table}'")
                    except Exception as e:
                        logger.warning(f"AUTO-JOIN SELECT: Column '{col}' not found in expected view {view}: {e}")

            # If not found via target_columns, search all views
            if not found:
                for table_name in table_sequence:
                    view = view_names[table_name]
                    try:
                        # Check if column exists in this view
                        self.connection.conn.execute(f"SELECT {col} FROM {view} LIMIT 0")
                        qualified_col = f"{view}.{col}"
                        found = True
                        logger.debug(f"AUTO-JOIN SELECT: Found '{col}' via scan in '{table_name}'")
                        break
                    except Exception:
                        continue

            if not found:
                # Track missing columns - don't add unqualified which causes Binder Error
                missing_cols.append(col)
                logger.error(f"AUTO-JOIN SELECT: Column '{col}' not found in any joined view!")
            else:
                # Determine if this column needs aggregation or is a group by column
                if group_by and col in group_by_cols:
                    # This is a dimension/group by column - no aggregation
                    select_cols.append(qualified_col)
                    qualified_group_cols.append(qualified_col)
                elif group_by and aggregations:
                    # This is a measure column - apply aggregation
                    agg_func = aggregations.get(col, 'SUM').upper()
                    select_cols.append(f"{agg_func}({qualified_col}) AS {col}")
                    logger.info(f"AUTO-JOIN SELECT: Aggregating '{col}' with {agg_func}")
                elif group_by:
                    # group_by specified but no aggregations - default to SUM for measures
                    select_cols.append(f"SUM({qualified_col}) AS {col}")
                    logger.info(f"AUTO-JOIN SELECT: Aggregating '{col}' with default SUM")
                else:
                    # No aggregation
                    select_cols.append(qualified_col)

        # If we have missing columns, raise a helpful error
        if missing_cols:
            available_tables = list(view_names.keys())
            raise ValueError(
                f"Cannot find required columns {missing_cols} in any joined view. "
                f"Joined tables: {available_tables}. "
                f"This usually means the Silver layer for the target model (e.g., 'temporal') "
                f"needs to be built. Run: python -m scripts.build.build_models --models temporal"
            )

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
        logger.info(f"AUTO-JOIN VIEWS: About to check filters. filters={filters}")
        if filters:
            logger.info(f"AUTO-JOIN VIEWS: Filters present, building WHERE clause...")
            # Collect all available columns from all views
            available_cols = set()
            for view in view_names.values():
                try:
                    # Extract clean view name for query - remove all quotes
                    clean_view = view.replace('"', '')
                    parts = clean_view.split('.')
                    if len(parts) == 2:
                        schema_name, table_only = parts
                        cols_result = self.connection.conn.execute(
                            f"SELECT column_name FROM information_schema.columns "
                            f"WHERE table_schema = '{schema_name}' AND table_name = '{table_only}'"
                        ).fetchall()
                    else:
                        # Fallback - match table name only
                        cols_result = self.connection.conn.execute(
                            f"SELECT column_name FROM information_schema.columns "
                            f"WHERE table_name = '{clean_view}'"
                        ).fetchall()
                    available_cols.update(r[0] for r in cols_result)
                    logger.debug(f"AUTO-JOIN VIEWS: Found {len(cols_result)} columns for view {clean_view}")
                except Exception as e:
                    logger.warning(f"AUTO-JOIN VIEWS: Failed to get columns for view {view}: {e}")

            logger.info(f"AUTO-JOIN VIEWS: Total available columns across all views: {len(available_cols)}")
            logger.info(f"AUTO-JOIN VIEWS: Columns include: {sorted(list(available_cols))[:20]}...")

            # Step 1: Translate filter parameters (start_date/end_date -> date range)
            param_translated = self.translate_filter_parameters(filters, available_cols)

            # Step 2: Translate universal date filters via dim_calendar mapping
            translated_filters = self.translate_date_filters(
                model_name, base_table, param_translated, available_cols
            )

            where_clause = self._build_where_clause_for_views(
                translated_filters, base_view, available_cols, view_names
            )
            if where_clause:
                sql += f" WHERE {where_clause}"
                logger.info(f"AUTO-JOIN WHERE CLAUSE (views): {where_clause}")
            else:
                logger.info(f"AUTO-JOIN WHERE CLAUSE (views): (none - no filters applied)")

        # Add GROUP BY clause if aggregating
        if group_by and qualified_group_cols:
            sql += f" GROUP BY {', '.join(qualified_group_cols)}"
            logger.info(f"AUTO-JOIN GROUP BY CLAUSE: {', '.join(qualified_group_cols)}")

        # Log the full SQL for debugging
        logger.info(f"AUTO-JOIN FULL SQL (views):\n{sql}")

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
        filters: Optional[Dict[str, Any]],
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """Execute joins by loading tables into temp tables with optional aggregation (fallback method)."""
        logger.info(f">>>>>> _execute_duckdb_joins_via_tables CALLED with filters={filters}")
        if group_by:
            logger.info(f">>>>>> SQL GROUP BY (tables): {group_by}, aggregations: {aggregations}")
        from de_funk.core.session.filters import FilterEngine
        import time

        table_sequence = join_plan['table_sequence']
        joins = join_plan.get('joins', [])
        join_keys = join_plan.get('join_keys', [])

        base_table = table_sequence[0]
        temp_tables = {}

        # Build mapping of table -> model from cross-model joins
        # Uses registry.resolve_cross_model() to dynamically resolve category names
        # to actual model names (e.g., 'securities' -> 'stocks', 'corporate' -> 'company')
        table_to_model = {}
        for join_info in joins:
            if 'cross_model' in join_info:
                to_table = join_info['to_table']
                cross_model = join_info['cross_model']
                # Use registry to resolve cross-model reference to actual model name
                resolved_model = self.registry.resolve_cross_model(cross_model)
                table_to_model[to_table] = resolved_model
                logger.debug(f"AUTO-JOIN DUCKDB: Table {to_table} from cross-model {cross_model} -> {resolved_model}")

        try:
            # Register tables as temp views - use DuckDB relations directly (lazy, no pandas)
            for table_name in table_sequence:
                t0 = time.time()
                # Handle cross-model joins using the mapping built from join plan
                if table_name in table_to_model:
                    load_model_name = table_to_model[table_name]
                    load_model = self.session.load_model(load_model_name)
                    logger.debug(f"AUTO-JOIN DUCKDB: Loading {table_name} from cross-model {load_model_name}")
                elif table_name == 'dim_calendar':
                    # Legacy fallback for dim_calendar
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

                # Step 1: Translate filter parameters (start_date/end_date -> date range)
                param_translated = self.translate_filter_parameters(filters, available_cols)

                # Step 2: Translate universal date filters via dim_calendar mapping
                translated_filters = self.translate_date_filters(
                    model_name, base_table, param_translated, available_cols
                )

                where_clause = self._build_where_clause(
                    translated_filters, base_temp, available_cols,
                    table_columns=table_columns, temp_tables=temp_tables
                )
                if where_clause:
                    sql += f" WHERE {where_clause}"
                    logger.info(f"AUTO-JOIN WHERE CLAUSE: {where_clause}")
                else:
                    logger.info(f"AUTO-JOIN WHERE CLAUSE: (none - no filters applied)")

            # Log the full SQL for debugging
            logger.info(f"AUTO-JOIN FULL SQL:\n{sql}")

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
        available_cols: Optional[set] = None,
        view_names: Optional[Dict[str, str]] = None
    ) -> str:
        """Build WHERE clause from filters for view-based queries.

        Only includes filters for columns that exist in the joined tables.
        Handles date_id columns by converting date strings to integers.
        Qualifies columns to the correct view (not always base_view).

        Args:
            filters: Filter dict
            base_view: Base view name (used as fallback)
            available_cols: Set of all available columns across views
            view_names: Dict mapping table_name -> view_name (for column qualification)
        """
        logger.info(f"AUTO-JOIN WHERE BUILD: Input filters = {filters}")
        logger.info(f"AUTO-JOIN WHERE BUILD: Available cols count = {len(available_cols) if available_cols else 0}")
        logger.info(f"AUTO-JOIN WHERE BUILD: View names = {view_names}")

        where_clauses = []

        for col, filter_val in filters.items():
            # Check if this is a universal date column for period overlap
            is_period_overlap = (
                col in UNIVERSAL_DATE_COLUMNS and
                available_cols is not None and
                'period_start_date_id' in available_cols and
                'period_end_date_id' in available_cols and
                col not in available_cols  # Column doesn't exist, so use period overlap
            )

            # Skip filters for columns that don't exist in the tables (UNLESS it's period overlap)
            if not is_period_overlap and available_cols is not None and col not in available_cols:
                logger.info(f"AUTO-JOIN WHERE: Skipping filter on '{col}' - column not in joined tables")
                continue

            # Find which view has this column (with caching to avoid expensive queries)
            qualified_col = f"{base_view}.{col}"  # Default to base view
            if view_names:
                found_in_view = None
                for table_name, view_name in view_names.items():
                    # Strip quotes from view_name for information_schema queries
                    # view_name is like "securities"."fact_security_prices" but info_schema uses unquoted
                    clean_view = view_name.replace('"', '')

                    # Check cache first (use clean_view as cache key for consistency)
                    if clean_view in self._view_columns_cache:
                        has_column = col in self._view_columns_cache.get(clean_view, set())
                    else:
                        # Not in cache - query the view columns once
                        try:
                            # Get all columns for this view in one query
                            # Split schema.table for proper matching
                            parts = clean_view.split('.')
                            if len(parts) == 2:
                                schema_name, table_only = parts
                                result = self.connection.conn.execute(
                                    f"SELECT column_name FROM information_schema.columns "
                                    f"WHERE table_schema = '{schema_name}' AND table_name = '{table_only}'"
                                ).fetchall()
                            else:
                                # Fallback - try matching just the table name
                                result = self.connection.conn.execute(
                                    f"SELECT column_name FROM information_schema.columns "
                                    f"WHERE table_name = '{clean_view}'"
                                ).fetchall()
                            self._view_columns_cache[clean_view] = {row[0] for row in result}
                            logger.debug(f"AUTO-JOIN WHERE: Cached {len(result)} columns for view {clean_view}: {list(self._view_columns_cache[clean_view])[:5]}...")
                        except Exception as e:
                            logger.warning(f"AUTO-JOIN WHERE: Could not cache columns for view {clean_view}: {e}")
                            self._view_columns_cache[clean_view] = set()

                        has_column = col in self._view_columns_cache.get(clean_view, set())

                    if has_column:
                        qualified_col = f"{view_name}.{col}"
                        found_in_view = view_name
                        logger.info(f"AUTO-JOIN WHERE: Column '{col}' found in view {view_name}")
                        break

                if not found_in_view:
                    logger.warning(f"AUTO-JOIN WHERE: Column '{col}' not found in any view, defaulting to {base_view}.{col}")

            # Check if this is a date_id column (integer YYYYMMDD format)
            is_date_id_col = col == 'date_id'

            # Note: is_period_overlap is already defined at the start of the loop

            if isinstance(filter_val, dict):
                if 'start' in filter_val and 'end' in filter_val:
                    start_val = filter_val['start']
                    end_val = filter_val['end']

                    if is_period_overlap:
                        # Period overlap logic: filter_start <= period_end AND filter_end >= period_start
                        # Converts to: period_start_date_id <= filter_end AND period_end_date_id >= filter_start
                        start_int = self._convert_date_to_date_id(start_val)
                        end_int = self._convert_date_to_date_id(end_val)
                        if start_int and end_int:
                            # Find the qualified view for period columns
                            period_start_col = qualified_col.replace(col, 'period_start_date_id')
                            period_end_col = qualified_col.replace(col, 'period_end_date_id')

                            # If we have view_names, find the correct view (using cache)
                            if view_names:
                                for table_name, view_name in view_names.items():
                                    # Strip quotes for cache key
                                    clean_view = view_name.replace('"', '')
                                    # Use cached column info (should already be populated from main loop)
                                    view_cols = self._view_columns_cache.get(clean_view, set())
                                    if 'period_start_date_id' in view_cols and 'period_end_date_id' in view_cols:
                                        period_start_col = f"{view_name}.period_start_date_id"
                                        period_end_col = f"{view_name}.period_end_date_id"
                                        logger.debug(f"AUTO-JOIN WHERE: Period overlap columns found in view {view_name}")
                                        break

                            overlap_clause = (
                                f"{period_start_col} <= {end_int} "
                                f"AND {period_end_col} >= {start_int}"
                            )
                            where_clauses.append(f"({overlap_clause})")
                            logger.info(f"AUTO-JOIN WHERE: Period overlap filter on '{col}': {start_val} to {end_val}")
                        else:
                            # Conversion failed - fall back to string BETWEEN
                            logger.warning(f"AUTO-JOIN WHERE: Failed to convert period overlap filter, using string BETWEEN: {start_val}, {end_val}")
                            where_clauses.append(f"{qualified_col} BETWEEN '{start_val}' AND '{end_val}'")

                    elif is_date_id_col:
                        start_int = self._convert_date_to_date_id(start_val)
                        end_int = self._convert_date_to_date_id(end_val)
                        if start_int and end_int:
                            where_clauses.append(f"{qualified_col} BETWEEN {start_int} AND {end_int}")
                        else:
                            logger.warning(f"AUTO-JOIN WHERE: Failed to convert date_id filter: {start_val}, {end_val}")
                    else:
                        where_clauses.append(f"{qualified_col} BETWEEN '{start_val}' AND '{end_val}'")
                elif 'min' in filter_val and 'max' in filter_val:
                    where_clauses.append(f"{qualified_col} BETWEEN {filter_val['min']} AND {filter_val['max']}")
                elif 'min' in filter_val:
                    where_clauses.append(f"{qualified_col} >= {filter_val['min']}")
                elif 'max' in filter_val:
                    where_clauses.append(f"{qualified_col} <= {filter_val['max']}")
            elif isinstance(filter_val, list):
                if is_date_id_col:
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
        missing_cols = []
        for col in required_columns:
            found = False
            for table_name in table_sequence:
                if col in table_columns.get(table_name, set()):
                    select_cols.append(f"{temp_tables[table_name]}.{col}")
                    found = True
                    logger.debug(f"_build_select_cols: '{col}' found in {table_name}")
                    break
            if not found:
                # Track missing columns instead of adding unqualified
                missing_cols.append(col)
                logger.error(f"_build_select_cols: '{col}' NOT FOUND in any table!")

        # If we have missing columns, raise a helpful error
        if missing_cols:
            available_tables = list(temp_tables.keys())
            all_available_cols = set()
            for cols in table_columns.values():
                all_available_cols.update(cols)
            raise ValueError(
                f"Cannot find required columns {missing_cols} in any joined table. "
                f"Joined tables: {available_tables}. "
                f"Available columns: {sorted(all_available_cols)[:20]}... "
                f"This usually means the Silver layer for the target model (e.g., 'temporal') "
                f"needs to be built. Run: python -m scripts.build.build_models --models temporal"
            )

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

            # Check if this is a date filter on a table with period columns
            is_period_overlap = (
                col in UNIVERSAL_DATE_COLUMNS and
                available_cols is not None and
                'period_start_date_id' in available_cols and
                'period_end_date_id' in available_cols
            )

            if isinstance(filter_val, dict):
                # Range filter
                if 'start' in filter_val and 'end' in filter_val:
                    start_val = filter_val['start']
                    end_val = filter_val['end']

                    if is_period_overlap:
                        # Period overlap logic for fiscal statements
                        start_int = self._convert_date_to_date_id(start_val)
                        end_int = self._convert_date_to_date_id(end_val)
                        if start_int and end_int:
                            # Find the qualified table for period columns
                            period_start_col = qualified_col.replace(col, 'period_start_date_id')
                            period_end_col = qualified_col.replace(col, 'period_end_date_id')

                            # If we have table_columns, find the correct table
                            if table_columns and temp_tables:
                                for table_name, cols in table_columns.items():
                                    if 'period_start_date_id' in cols and 'period_end_date_id' in cols:
                                        period_start_col = f"{temp_tables[table_name]}.period_start_date_id"
                                        period_end_col = f"{temp_tables[table_name]}.period_end_date_id"
                                        break

                            overlap_clause = (
                                f"{period_start_col} <= {end_int} "
                                f"AND {period_end_col} >= {start_int}"
                            )
                            where_clauses.append(f"({overlap_clause})")
                            logger.info(f"AUTO-JOIN WHERE: Period overlap filter on '{col}': {start_val} to {end_val}")
                        else:
                            # Conversion failed - fall back to string BETWEEN
                            logger.warning(f"AUTO-JOIN WHERE: Failed to convert period overlap filter, using string BETWEEN: {start_val}, {end_val}")
                            where_clauses.append(f"{qualified_col} BETWEEN '{start_val}' AND '{end_val}'")

                    elif is_date_id_col:
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
