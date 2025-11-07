"""
Centralized filter engine for applying filters across different backends.

This module provides a unified interface for filter application that works
with both Spark and DuckDB backends, eliminating code duplication across
the codebase.
"""

from typing import Dict, Any, Union
from pyspark.sql import DataFrame as SparkDataFrame, functions as F


class FilterEngine:
    """
    Centralized filter application for all backends.

    Consolidates filter logic that was previously duplicated in:
    - models/base/service.py (BaseAPI._apply_filters)
    - app/notebook/api/notebook_session.py (_build_filters)
    - app/services/storage_service.py (filter application)

    Usage:
        # Detect backend and apply filters
        backend = session.backend  # 'spark' or 'duckdb'
        filtered_df = FilterEngine.apply_filters(df, filters, backend)

        # Or use with UniversalSession directly
        filtered_df = FilterEngine.apply_from_session(df, filters, session)
    """

    @staticmethod
    def apply_filters(
        df: Any,
        filters: Dict[str, Any],
        backend: str
    ) -> Any:
        """
        Apply filters based on backend type.

        Args:
            df: DataFrame (SparkDataFrame or DuckDB relation)
            filters: Filter specifications mapping column names to filter values
            backend: Backend type ('spark' or 'duckdb')

        Returns:
            Filtered DataFrame

        Raises:
            ValueError: If backend is unknown

        Filter Specification Format:
            {
                'column_name': value,              # Exact match
                'column_name': [val1, val2],       # IN clause
                'column_name': {                   # Range filter
                    'min': value,
                    'max': value,
                    'operator': 'gte' | 'lte' | 'gt' | 'lt'
                }
            }

        Examples:
            # Exact match
            filters = {'ticker': 'AAPL'}

            # IN clause
            filters = {'ticker': ['AAPL', 'GOOGL', 'MSFT']}

            # Range filter
            filters = {
                'trade_date': {
                    'min': '2024-01-01',
                    'max': '2024-12-31'
                }
            }

            # Combined filters
            filters = {
                'ticker': ['AAPL', 'GOOGL'],
                'trade_date': {'min': '2024-01-01'},
                'volume': {'min': 1000000}
            }
        """
        if backend == 'spark':
            return FilterEngine._apply_spark_filters(df, filters)
        elif backend == 'duckdb':
            return FilterEngine._apply_duckdb_filters(df, filters)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    @staticmethod
    def apply_from_session(df: Any, filters: Dict[str, Any], session) -> Any:
        """
        Apply filters using session's backend detection.

        Convenience method that automatically detects backend from session.

        Args:
            df: DataFrame
            filters: Filter specifications
            session: UniversalSession instance with backend property

        Returns:
            Filtered DataFrame
        """
        backend = session.backend
        return FilterEngine.apply_filters(df, filters, backend)

    @staticmethod
    def _apply_spark_filters(df: SparkDataFrame, filters: Dict[str, Any]) -> SparkDataFrame:
        """
        Apply filters to Spark DataFrame.

        Args:
            df: Spark DataFrame
            filters: Filter specifications

        Returns:
            Filtered Spark DataFrame
        """
        for col_name, value in filters.items():
            if isinstance(value, dict):
                # Range filter
                if 'min' in value:
                    df = df.filter(F.col(col_name) >= value['min'])
                if 'max' in value:
                    df = df.filter(F.col(col_name) <= value['max'])
                if 'gt' in value:
                    df = df.filter(F.col(col_name) > value['gt'])
                if 'lt' in value:
                    df = df.filter(F.col(col_name) < value['lt'])
                if 'gte' in value:
                    df = df.filter(F.col(col_name) >= value['gte'])
                if 'lte' in value:
                    df = df.filter(F.col(col_name) <= value['lte'])

            elif isinstance(value, list):
                # IN filter
                if value:  # Only apply if list is not empty
                    df = df.filter(F.col(col_name).isin(value))

            elif value is not None:
                # Exact match (ignore None values)
                df = df.filter(F.col(col_name) == value)

        return df

    @staticmethod
    def _apply_duckdb_filters(df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to DuckDB relation.

        DuckDB uses SQL-style filtering, so we build a WHERE clause.

        Args:
            df: DuckDB relation
            filters: Filter specifications

        Returns:
            Filtered DuckDB relation
        """
        conditions = []

        for col_name, value in filters.items():
            if isinstance(value, dict):
                # Range filter - support both min/max AND start/end formats
                # Date ranges use start/end, numeric ranges use min/max
                if 'start' in value and 'end' in value:
                    # Date range format
                    conditions.append(f"{col_name} >= '{value['start']}'")
                    conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    conditions.append(f"{col_name} >= '{value['min']}'")
                if 'max' in value:
                    conditions.append(f"{col_name} <= '{value['max']}'")
                if 'gt' in value:
                    conditions.append(f"{col_name} > '{value['gt']}'")
                if 'lt' in value:
                    conditions.append(f"{col_name} < '{value['lt']}'")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= '{value['gte']}'")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= '{value['lte']}'")

            elif isinstance(value, list):
                # IN filter
                if value:  # Only apply if list is not empty
                    # Format list values for SQL IN clause
                    formatted_values = "', '".join(str(v) for v in value)
                    conditions.append(f"{col_name} IN ('{formatted_values}')")

            elif value is not None:
                # Exact match (ignore None values)
                conditions.append(f"{col_name} = '{value}'")

        # Apply all conditions
        if conditions:
            where_clause = " AND ".join(conditions)
            df = df.filter(where_clause)

        return df

    @staticmethod
    def build_filter_sql(filters: Dict[str, Any]) -> str:
        """
        Build SQL WHERE clause from filter specifications.

        Useful for generating SQL queries with filters.

        Args:
            filters: Filter specifications

        Returns:
            SQL WHERE clause (without 'WHERE' keyword)

        Example:
            >>> filters = {'ticker': ['AAPL', 'GOOGL'], 'volume': {'min': 1000000}}
            >>> FilterEngine.build_filter_sql(filters)
            "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000"
        """
        conditions = []

        for col_name, value in filters.items():
            if isinstance(value, dict):
                # Range filter - support both min/max AND start/end formats
                # Date ranges use start/end, numeric ranges use min/max
                if 'start' in value and 'end' in value:
                    # Date range format
                    conditions.append(f"{col_name} >= '{value['start']}'")
                    conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    conditions.append(f"{col_name} >= '{value['min']}'")
                if 'max' in value:
                    conditions.append(f"{col_name} <= '{value['max']}'")
                if 'gt' in value:
                    conditions.append(f"{col_name} > '{value['gt']}'")
                if 'lt' in value:
                    conditions.append(f"{col_name} < '{value['lt']}'")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= '{value['gte']}'")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= '{value['lte']}'")

            elif isinstance(value, list):
                # IN filter
                if value:
                    formatted_values = "', '".join(str(v) for v in value)
                    conditions.append(f"{col_name} IN ('{formatted_values}')")

            elif value is not None:
                # Exact match
                conditions.append(f"{col_name} = '{value}'")

        return " AND ".join(conditions) if conditions else "1=1"
