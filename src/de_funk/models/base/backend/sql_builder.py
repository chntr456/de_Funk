"""
SQL builder utilities for common query patterns.

Provides reusable SQL generation functions that work across backends.
"""

from typing import List, Optional, Dict

from .adapter import BackendAdapter


class SQLBuilder:
    """
    Utility for building SQL queries with dialect support.

    Provides common SQL patterns (aggregations, joins, etc.) that work
    across different backends with automatic dialect adaptation.
    """

    def __init__(self, adapter: BackendAdapter):
        """
        Initialize SQL builder.

        Args:
            adapter: Backend adapter for dialect-specific SQL generation
        """
        self.adapter = adapter
        self.dialect = adapter.get_dialect()

    def build_simple_aggregate(
        self,
        table_name: str,
        value_column: str,
        agg_function: str,
        group_by: List[str],
        filters: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Build simple aggregate query.

        Example output:
            SELECT
                ticker,
                AVG(close) as measure_value
            FROM fact_prices
            WHERE close IS NOT NULL
            GROUP BY ticker
            ORDER BY measure_value DESC
            LIMIT 10

        Args:
            table_name: Name of source table
            value_column: Column to aggregate
            agg_function: Aggregation function (AVG, SUM, MAX, MIN, COUNT)
            group_by: List of columns to group by
            filters: Optional WHERE clause conditions
            order_by: Optional ORDER BY columns
            limit: Optional row limit

        Returns:
            SQL query string
        """
        # Get backend-specific table reference
        table_ref = self.adapter.get_table_reference(table_name)

        # Build SELECT clause
        group_cols = ', '.join(group_by)
        select_clause = f"{group_cols}, {agg_function}({value_column}) as measure_value"

        # Build FROM clause
        from_clause = f"FROM {table_ref}"

        # Build WHERE clause
        where_clauses = [f"{value_column} IS NOT NULL"]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build GROUP BY clause
        group_clause = f"GROUP BY {group_cols}"

        # Build ORDER BY clause
        order_clause = ""
        if order_by:
            order_clause = "ORDER BY " + ", ".join(order_by)
        else:
            order_clause = "ORDER BY measure_value DESC"

        # Build LIMIT clause
        limit_clause = ""
        if limit:
            limit_clause = self.adapter.format_limit(limit)

        # Assemble query
        query_parts = [
            "SELECT",
            f"    {select_clause}",
            from_clause,
            where_clause,
            group_clause,
            order_clause,
        ]

        if limit_clause:
            query_parts.append(limit_clause)

        return '\n'.join(query_parts)

    def build_weighted_aggregate(
        self,
        table_name: str,
        value_column: str,
        weight_expression: str,
        group_by: List[str],
        filters: Optional[List[str]] = None,
        additional_columns: Optional[List[str]] = None
    ) -> str:
        """
        Build weighted aggregate query.

        Example output:
            SELECT
                trade_date,
                SUM(close * volume) / NULLIF(SUM(volume), 0) as weighted_value,
                COUNT(*) as entity_count,
                SUM(volume) as total_volume
            FROM fact_prices
            WHERE close IS NOT NULL AND volume > 0
            GROUP BY trade_date
            ORDER BY trade_date

        Args:
            table_name: Name of source table
            value_column: Column to aggregate
            weight_expression: Weight expression (e.g., 'volume', 'close * volume')
            group_by: List of columns to group by
            filters: Optional WHERE clause conditions
            additional_columns: Optional additional columns to include

        Returns:
            SQL query string
        """
        table_ref = self.adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build weighted aggregation using null-safe division
        weighted_agg = self.adapter.get_null_safe_divide(
            f"SUM({value_column} * {weight_expression})",
            f"SUM({weight_expression})"
        )

        # Base columns
        select_columns = [
            group_cols,
            f"{weighted_agg} as weighted_value",
            "COUNT(*) as entity_count",
            f"SUM({weight_expression}) as total_weight"
        ]

        # Add additional columns if specified
        if additional_columns:
            select_columns.extend(additional_columns)

        select_clause = ',\n    '.join(select_columns)

        # Build WHERE clause
        where_clauses = [
            f"{value_column} IS NOT NULL",
            f"{weight_expression} IS NOT NULL",
            f"{weight_expression} > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Assemble query
        query = f"""
SELECT
    {select_clause}
FROM {table_ref}
{where_clause}
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()

        return query

    def build_cte_query(
        self,
        ctes: Dict[str, str],
        main_query: str
    ) -> str:
        """
        Build query with Common Table Expressions (CTEs).

        Example output:
            WITH
                cte1 AS (
                    SELECT ...
                ),
                cte2 AS (
                    SELECT ...
                )
            SELECT ...

        Args:
            ctes: Dictionary of CTE name -> CTE query
            main_query: Main query that uses the CTEs

        Returns:
            Full query with CTEs
        """
        if not self.adapter.supports_feature('cte'):
            raise NotImplementedError(f"Backend '{self.dialect}' does not support CTEs")

        cte_clauses = []
        for cte_name, cte_query in ctes.items():
            cte_clauses.append(f"{cte_name} AS (\n{cte_query}\n)")

        cte_section = ",\n".join(cte_clauses)

        return f"""
WITH
    {cte_section}
{main_query}
        """.strip()

    def build_window_function(
        self,
        table_name: str,
        select_columns: List[str],
        window_function: str,
        window_spec: str,
        filters: Optional[List[str]] = None,
        qualify_filter: Optional[str] = None
    ) -> str:
        """
        Build query with window function.

        Example output:
            SELECT
                ticker,
                trade_date,
                close,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
            FROM fact_prices
            WHERE close IS NOT NULL
            QUALIFY rn = 1

        Args:
            table_name: Name of source table
            select_columns: List of columns to select
            window_function: Window function (e.g., 'ROW_NUMBER()', 'LAG(close, 1)')
            window_spec: Window specification (e.g., 'PARTITION BY ticker ORDER BY trade_date')
            filters: Optional WHERE clause conditions
            qualify_filter: Optional QUALIFY filter (DuckDB-specific)

        Returns:
            SQL query string
        """
        table_ref = self.adapter.get_table_reference(table_name)

        # Build SELECT clause
        all_columns = select_columns + [
            f"{window_function} OVER ({window_spec}) as window_result"
        ]
        select_clause = ',\n    '.join(all_columns)

        # Build WHERE clause
        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        # Build QUALIFY clause (DuckDB-specific optimization)
        qualify_clause = ""
        if qualify_filter and self.adapter.supports_feature('qualify'):
            qualify_clause = f"QUALIFY {qualify_filter}"

        # Assemble query
        query_parts = [
            "SELECT",
            f"    {select_clause}",
            f"FROM {table_ref}"
        ]

        if where_clause:
            query_parts.append(where_clause)

        if qualify_clause:
            query_parts.append(qualify_clause)

        return '\n'.join(query_parts)

    def build_join_query(
        self,
        left_table: str,
        right_table: str,
        join_conditions: List[str],
        select_columns: List[str],
        join_type: str = 'INNER',
        filters: Optional[List[str]] = None
    ) -> str:
        """
        Build join query.

        Example output:
            SELECT
                p.ticker,
                p.close,
                c.company_name
            FROM fact_prices p
            INNER JOIN dim_company c
                ON p.ticker = c.ticker
            WHERE p.close IS NOT NULL

        Args:
            left_table: Left table name
            right_table: Right table name
            join_conditions: List of join conditions (e.g., ['p.ticker = c.ticker'])
            select_columns: List of columns to select
            join_type: Join type (INNER, LEFT, RIGHT, FULL)
            filters: Optional WHERE clause conditions

        Returns:
            SQL query string
        """
        left_ref = self.adapter.get_table_reference(left_table)
        right_ref = self.adapter.get_table_reference(right_table)

        # Build SELECT clause
        select_clause = ',\n    '.join(select_columns)

        # Build JOIN clause
        join_on = ' AND '.join(join_conditions)
        join_clause = f"{join_type} JOIN {right_ref}\n    ON {join_on}"

        # Build WHERE clause
        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        # Assemble query
        query_parts = [
            "SELECT",
            f"    {select_clause}",
            f"FROM {left_ref}",
            join_clause
        ]

        if where_clause:
            query_parts.append(where_clause)

        return '\n'.join(query_parts)
