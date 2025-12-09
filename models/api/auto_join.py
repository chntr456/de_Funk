"""
Auto-Join Support for UniversalSession.

Provides transparent graph traversal and automatic join operations:
- Find materialized views containing required columns
- Plan join sequences using model graph
- Execute joins (Spark and DuckDB backends)

This module is used by UniversalSession via composition.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


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

        This allows the system to use pre-computed joins when available,
        making materialized views a performance optimization.

        Args:
            model_name: Model to search in
            required_columns: Columns needed

        Returns:
            Table name of materialized view, or None if not found
        """
        try:
            model = self.session.load_model(model_name)
            tables = model.list_tables()

            # Search in facts (where materialized paths are stored)
            for table_name in tables.get('facts', []):
                try:
                    schema = model.get_table_schema(table_name)
                    table_columns = set(schema.keys())

                    # Check if this table has all required columns
                    if all(col in table_columns for col in required_columns):
                        return table_name
                except Exception:
                    continue

            return None
        except Exception as e:
            print(f"Warning: Error finding materialized view: {e}")
            return None

    def plan_auto_joins(
        self,
        model_name: str,
        base_table: str,
        missing_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Plan join sequence to get missing columns using model graph.

        Args:
            model_name: Model name
            base_table: Starting table
            missing_columns: Columns to find

        Returns:
            Join plan dict with:
                - table_sequence: List of tables to join
                - join_keys: List of (left_col, right_col) pairs for each join
                - target_columns: Which columns come from which table

        Raises:
            ValueError: If no join path found
        """
        import time
        logger.info(f"AUTO-JOIN PLAN: Starting for {model_name}.{base_table}, missing={missing_columns}")
        t_start = time.time()

        model_config = self.registry.get_model_config(model_name)
        graph_config = model_config.get('graph', {})
        logger.debug(f"AUTO-JOIN PLAN: Got model config in {time.time() - t_start:.2f}s")

        if not graph_config or 'edges' not in graph_config:
            raise ValueError(f"No graph edges defined for model {model_name}")

        # Build column-to-table index
        t0 = time.time()
        column_index = self.build_column_index(model_name)
        logger.info(f"AUTO-JOIN PLAN: build_column_index took {time.time() - t0:.2f}s, indexed {len(column_index)} columns")

        # Find which tables have the missing columns
        target_tables = {}
        for col in missing_columns:
            if col in column_index:
                target_tables[col] = column_index[col][0]  # Use first table that has it
                logger.debug(f"AUTO-JOIN PLAN: Column '{col}' found in table '{target_tables[col]}'")
            else:
                raise ValueError(f"Column '{col}' not found in any table in model {model_name}")

        logger.info(f"AUTO-JOIN PLAN: Target tables: {target_tables}")

        # Find join path from base_table to target tables
        table_sequence = [base_table]
        join_keys = []
        seen_tables = {base_table}

        # Handle both v1.x (list) and v2.0 (dict) edge formats
        edges_config = graph_config.get('edges', [])
        if isinstance(edges_config, dict):
            edges = list(edges_config.values())
        else:
            edges = edges_config

        current_tables = {base_table}

        # Keep adding tables until we have all target tables
        while not all(tbl in seen_tables for tbl in target_tables.values()):
            added_table = False

            for edge in edges:
                edge_from = edge.get('from', '')
                edge_to = edge.get('to', '')

                # Skip cross-model edges for now
                if '.' in edge_to:
                    continue

                # Check if this edge connects a current table to a new table
                if edge_from in current_tables and edge_to not in seen_tables:
                    # Add this table to sequence
                    table_sequence.append(edge_to)
                    seen_tables.add(edge_to)
                    current_tables.add(edge_to)

                    # Extract join keys
                    on_conditions = edge.get('on', edge.get(True, []))
                    if on_conditions:
                        # Parse "col1=col2" format
                        join_pair = self._parse_join_condition(on_conditions[0])
                        join_keys.append(join_pair)

                    added_table = True
                    break

            if not added_table:
                raise ValueError(
                    f"Cannot find join path from {base_table} to {missing_columns}. "
                    f"Reached: {seen_tables}, Need: {set(target_tables.values())}"
                )

        return {
            'table_sequence': table_sequence,
            'join_keys': join_keys,
            'target_columns': target_tables
        }

    def build_column_index(self, model_name: str) -> Dict[str, List[str]]:
        """
        Build reverse index: column_name -> [table_names].

        Uses DuckDB schema introspection on views (fast) instead of
        building models from Bronze (slow).

        Args:
            model_name: Model to index

        Returns:
            Dict mapping column names to list of tables that have that column
        """
        import time
        logger.debug(f"AUTO-JOIN INDEX: Building column index for {model_name}")
        t_start = time.time()

        index = {}

        # Strategy 1: Use DuckDB information_schema (fast - no model building)
        if self.backend == 'duckdb' and hasattr(self.connection, 'conn'):
            try:
                # Get all tables/views in this schema from DuckDB catalog
                result = self.connection.conn.execute(f"""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = '{model_name}'
                    ORDER BY table_name, ordinal_position
                """).fetchall()

                if result:
                    for table_name, column_name in result:
                        if column_name not in index:
                            index[column_name] = []
                        if table_name not in index[column_name]:
                            index[column_name].append(table_name)

                    logger.debug(f"AUTO-JOIN INDEX: Built from DuckDB catalog in {time.time() - t_start:.2f}s, "
                                f"indexed {len(index)} columns from {len(set(r[0] for r in result))} tables")
                    return index

            except Exception as e:
                logger.debug(f"AUTO-JOIN INDEX: DuckDB catalog lookup failed: {e}, falling back to model schema")

        # Strategy 2: Fall back to model schema (slower - may trigger build)
        t0 = time.time()
        model = self.session.load_model(model_name)
        logger.debug(f"AUTO-JOIN INDEX: load_model took {time.time() - t0:.2f}s")

        t0 = time.time()
        tables = model.list_tables()
        all_tables = tables.get('dimensions', []) + tables.get('facts', [])
        logger.debug(f"AUTO-JOIN INDEX: list_tables took {time.time() - t0:.2f}s, found {len(all_tables)} tables")

        # Index all tables (dims and facts)
        for table_name in all_tables:
            try:
                t0 = time.time()
                schema = model.get_table_schema(table_name)
                elapsed = time.time() - t0
                if elapsed > 0.1:  # Only log if slow
                    logger.warning(f"AUTO-JOIN INDEX: get_table_schema({table_name}) took {elapsed:.2f}s")
                for column_name in schema.keys():
                    if column_name not in index:
                        index[column_name] = []
                    index[column_name].append(table_name)
            except Exception as e:
                logger.warning(f"AUTO-JOIN INDEX: Failed to get schema for {table_name}: {e}")
                continue

        logger.debug(f"AUTO-JOIN INDEX: Total build time {time.time() - t_start:.2f}s")
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
        join_keys = join_plan['join_keys']

        if self.backend == 'spark':
            return self._execute_spark_joins(
                model, table_sequence, join_keys, required_columns, filters
            )
        else:
            return self._execute_duckdb_joins(
                model_name, model, table_sequence, join_keys, required_columns, filters
            )

    def _execute_spark_joins(
        self,
        model,
        table_sequence: List[str],
        join_keys: List[Tuple[str, str]],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using Spark DataFrame API."""
        from core.session.filters import FilterEngine

        df = model.get_table(table_sequence[0])

        # Apply filters to base table BEFORE joins (pushdown)
        if filters:
            df = FilterEngine.apply_from_session(df, filters, self.session)

        # Join each subsequent table
        for i, next_table in enumerate(table_sequence[1:]):
            right_df = model.get_table(next_table)
            left_col, right_col = join_keys[i]
            df = df.join(right_df, df[left_col] == right_df[right_col], 'left')

        # Select only required columns
        return self.select_columns(df, required_columns)

    def _execute_duckdb_joins(
        self,
        model_name: str,
        model,
        table_sequence: List[str],
        join_keys: List[Tuple[str, str]],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using DuckDB SQL against views."""
        from core.session.filters import FilterEngine
        import time

        base_table = table_sequence[0]

        # Strategy 1: Try using DuckDB views directly (most efficient)
        try:
            view_names = {}
            views_available = True

            # Check if all required tables exist as views
            for table_name in table_sequence:
                view_name = f'"{model_name}"."{table_name}"'
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
                logger.info(f"AUTO-JOIN DUCKDB: Using views for {len(table_sequence)} tables")
                return self._execute_duckdb_joins_via_views(
                    model_name, view_names, table_sequence, join_keys,
                    required_columns, filters
                )

        except Exception as e:
            logger.debug(f"AUTO-JOIN DUCKDB: View-based join failed: {e}")

        # Strategy 2: Fall back to loading tables (slower but always works)
        logger.info(f"AUTO-JOIN DUCKDB: Falling back to table loading for {len(table_sequence)} tables")
        return self._execute_duckdb_joins_via_tables(
            model, table_sequence, join_keys, required_columns, filters
        )

    def _execute_duckdb_joins_via_views(
        self,
        model_name: str,
        view_names: Dict[str, str],
        table_sequence: List[str],
        join_keys: List[Tuple[str, str]],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins using DuckDB SQL against pre-registered views."""
        import time

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

        # Add joins
        for i in range(1, len(table_sequence)):
            left_view = view_names[table_sequence[i - 1]]
            right_view = view_names[table_sequence[i]]
            left_col, right_col = join_keys[i - 1]
            sql += f" LEFT JOIN {right_view} ON {left_view}.{left_col} = {right_view}.{right_col}"

        # Add WHERE clause
        if filters:
            where_clause = self._build_where_clause_for_views(filters, base_view)
            if where_clause:
                sql += f" WHERE {where_clause}"

        logger.debug(f"AUTO-JOIN DUCKDB SQL: {sql[:500]}{'...' if len(sql) > 500 else ''}")

        t0 = time.time()
        result = self.connection.conn.execute(sql)
        result_df = result.fetchdf()
        logger.info(f"AUTO-JOIN DUCKDB: View query took {time.time() - t0:.2f}s, shape={result_df.shape}")

        return self.connection.conn.from_df(result_df)

    def _execute_duckdb_joins_via_tables(
        self,
        model,
        table_sequence: List[str],
        join_keys: List[Tuple[str, str]],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute joins by loading tables into temp tables (fallback method)."""
        from core.session.filters import FilterEngine
        import time

        base_table = table_sequence[0]
        temp_tables = {}

        try:
            # Register tables as temp views
            for table_name in table_sequence:
                t0 = time.time()
                df_temp = model.get_table(table_name)
                t1 = time.time()
                temp_name = f"_autojoin_{table_name}"
                temp_df = df_temp.df()  # Convert to pandas
                t2 = time.time()
                logger.info(f"AUTO-JOIN DUCKDB: {table_name}: get_table={t1-t0:.2f}s, to_pandas={t2-t1:.2f}s, shape={temp_df.shape}")
                self.connection.conn.register(temp_name, temp_df)
                temp_tables[table_name] = temp_name

            # Build SQL with proper qualified column names
            base_temp = temp_tables[base_table]
            select_cols = self._build_select_cols(model, table_sequence, temp_tables, required_columns)

            sql = f"SELECT {', '.join(select_cols)} FROM {base_temp}"

            # Add each join
            for i in range(1, len(table_sequence)):
                left_temp = temp_tables[table_sequence[i - 1]]
                right_temp = temp_tables[table_sequence[i]]
                left_col, right_col = join_keys[i - 1]
                sql += f" LEFT JOIN {right_temp} ON {left_temp}.{left_col} = {right_temp}.{right_col}"

            # Add WHERE clause for filters
            if filters:
                where_clause = self._build_where_clause(filters, base_temp)
                if where_clause:
                    sql += f" WHERE {where_clause}"

            logger.debug(f"AUTO-JOIN DUCKDB SQL: {sql[:500]}{'...' if len(sql) > 500 else ''}")

            # Execute the join query
            t0 = time.time()
            result = self.connection.conn.execute(sql)
            result_df = result.fetchdf()
            logger.info(f"AUTO-JOIN DUCKDB: SQL execution took {time.time() - t0:.2f}s, result shape={result_df.shape}")

            # Cleanup temp tables
            for temp_name in temp_tables.values():
                try:
                    self.connection.conn.unregister(temp_name)
                except Exception:
                    pass

            # Convert to DuckDB relation
            return self.connection.conn.from_df(result_df)

        except Exception as e:
            logger.error(f"AUTO-JOIN DUCKDB FAILED: {e}", exc_info=True)

            # Cleanup temp tables
            for temp_name in temp_tables.values():
                try:
                    self.connection.conn.unregister(temp_name)
                except Exception:
                    pass

            # Fall back to base table
            df = model.get_table(table_sequence[0])
            if filters:
                df = FilterEngine.apply_from_session(df, filters, self.session)
            return df

    def _build_where_clause_for_views(self, filters: Dict[str, Any], base_view: str) -> str:
        """Build WHERE clause from filters for view-based queries."""
        where_clauses = []

        for col, filter_val in filters.items():
            if isinstance(filter_val, dict):
                if 'start' in filter_val and 'end' in filter_val:
                    where_clauses.append(f"{base_view}.{col} BETWEEN '{filter_val['start']}' AND '{filter_val['end']}'")
                elif 'min' in filter_val and 'max' in filter_val:
                    where_clauses.append(f"{base_view}.{col} BETWEEN {filter_val['min']} AND {filter_val['max']}")
                elif 'min' in filter_val:
                    where_clauses.append(f"{base_view}.{col} >= {filter_val['min']}")
                elif 'max' in filter_val:
                    where_clauses.append(f"{base_view}.{col} <= {filter_val['max']}")
            elif isinstance(filter_val, list):
                if all(isinstance(v, str) for v in filter_val):
                    vals = "', '".join(filter_val)
                    where_clauses.append(f"{base_view}.{col} IN ('{vals}')")
                else:
                    vals = ", ".join(str(v) for v in filter_val)
                    where_clauses.append(f"{base_view}.{col} IN ({vals})")
            else:
                if isinstance(filter_val, str):
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
        """Build qualified column names for SELECT clause."""
        select_cols = []
        for col in required_columns:
            found = False
            for table_name in table_sequence:
                try:
                    df = model.get_table(table_name)
                    if col in df.columns:
                        select_cols.append(f"{temp_tables[table_name]}.{col}")
                        found = True
                        break
                except:
                    continue
            if not found:
                select_cols.append(col)
        return select_cols

    def _build_where_clause(self, filters: Dict[str, Any], base_temp: str) -> str:
        """Build WHERE clause from filters."""
        where_clauses = []

        for col, filter_val in filters.items():
            if isinstance(filter_val, dict):
                # Range filter
                if 'start' in filter_val and 'end' in filter_val:
                    where_clauses.append(f"{base_temp}.{col} BETWEEN '{filter_val['start']}' AND '{filter_val['end']}'")
                elif 'min' in filter_val and 'max' in filter_val:
                    where_clauses.append(f"{base_temp}.{col} BETWEEN {filter_val['min']} AND {filter_val['max']}")
                elif 'min' in filter_val:
                    where_clauses.append(f"{base_temp}.{col} >= {filter_val['min']}")
                elif 'max' in filter_val:
                    where_clauses.append(f"{base_temp}.{col} <= {filter_val['max']}")
            elif isinstance(filter_val, list):
                # IN filter
                if all(isinstance(v, str) for v in filter_val):
                    vals = "', '".join(filter_val)
                    where_clauses.append(f"{base_temp}.{col} IN ('{vals}')")
                else:
                    vals = ", ".join(str(v) for v in filter_val)
                    where_clauses.append(f"{base_temp}.{col} IN ({vals})")
            else:
                # Equality filter
                if isinstance(filter_val, str):
                    where_clauses.append(f"{base_temp}.{col} = '{filter_val}'")
                else:
                    where_clauses.append(f"{base_temp}.{col} = {filter_val}")

        return " AND ".join(where_clauses) if where_clauses else ""
