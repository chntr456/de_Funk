"""
Centralized filter engine for applying filters across different backends.

This module provides a unified interface for filter application that works
with both Spark and DuckDB backends, eliminating code duplication across
the codebase.
"""

from typing import Dict, Any, Union, TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import functions as F
else:
    # Make imports optional for DuckDB-only environments
    try:
        from pyspark.sql import DataFrame as SparkDataFrame, functions as F
    except ImportError:
        SparkDataFrame = None
        F = None


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
    def _format_sql_value(value: Any) -> str:
        """
        Format a value for SQL, quoting strings but NOT numbers.

        Args:
            value: Value to format

        Returns:
            SQL-safe string representation

        Examples:
            >>> FilterEngine._format_sql_value(1000000)
            '1000000'
            >>> FilterEngine._format_sql_value('AAPL')
            "'AAPL'"
            >>> FilterEngine._format_sql_value('2024-01-01')
            "'2024-01-01'"
        """
        if value is None:
            return 'NULL'
        elif isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # Strings, dates, and everything else gets quoted
            # Escape single quotes in the value
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

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
            if F is None:
                raise RuntimeError("PySpark is required for Spark backend but not installed")
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
        Apply filters to DuckDB relation or pandas DataFrame.

        Handles both DuckDB relations (SQL-style) and pandas DataFrames
        (already converted from DuckDB).

        Args:
            df: DuckDB relation or pandas DataFrame
            filters: Filter specifications

        Returns:
            Filtered DuckDB relation or pandas DataFrame
        """
        # Check if df is a pandas DataFrame or DuckDB relation
        is_pandas = isinstance(df, pd.DataFrame)

        # Get available columns to skip filters for non-existent columns
        # This prevents errors when filters from one table are applied to another
        try:
            if is_pandas:
                available_columns = set(df.columns)
            else:
                # DuckDB relation
                available_columns = set(df.columns)
        except Exception:
            # If we can't get columns, apply all filters and let it fail naturally
            available_columns = None

        conditions = []

        for col_name, value in filters.items():
            # Skip filter if column doesn't exist in this table
            if available_columns is not None and col_name not in available_columns:
                continue

            if isinstance(value, dict):
                # Range filter - support both min/max AND start/end formats
                # Date ranges use start/end, numeric ranges use min/max
                if 'start' in value and 'end' in value:
                    # Date range format - always quote dates
                    conditions.append(f"{col_name} >= '{value['start']}'")
                    conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    # Use _format_sql_value to handle numeric vs string values
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['min'])}")
                if 'max' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['max'])}")
                if 'gt' in value:
                    conditions.append(f"{col_name} > {FilterEngine._format_sql_value(value['gt'])}")
                if 'lt' in value:
                    conditions.append(f"{col_name} < {FilterEngine._format_sql_value(value['lt'])}")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['gte'])}")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['lte'])}")

            elif isinstance(value, list):
                # IN filter
                if value:  # Only apply if list is not empty
                    if is_pandas:
                        # pandas: use .isin() method - handled separately below
                        pass
                    else:
                        # DuckDB: use SQL IN clause with proper value formatting
                        formatted_values = ", ".join(FilterEngine._format_sql_value(v) for v in value)
                        conditions.append(f"{col_name} IN ({formatted_values})")

            elif value is not None:
                # Exact match (ignore None values)
                conditions.append(f"{col_name} = {FilterEngine._format_sql_value(value)}")

        # Apply all conditions
        if is_pandas:
            # pandas DataFrame: apply filters manually
            for col_name, value in filters.items():
                # Skip filter if column doesn't exist in this table
                if available_columns is not None and col_name not in available_columns:
                    continue

                if isinstance(value, dict):
                    # Range filters
                    if 'start' in value:
                        df = df[df[col_name] >= value['start']]
                    if 'end' in value:
                        df = df[df[col_name] <= value['end']]
                    if 'min' in value:
                        df = df[df[col_name] >= value['min']]
                    if 'max' in value:
                        df = df[df[col_name] <= value['max']]
                    if 'gt' in value:
                        df = df[df[col_name] > value['gt']]
                    if 'lt' in value:
                        df = df[df[col_name] < value['lt']]
                    if 'gte' in value:
                        df = df[df[col_name] >= value['gte']]
                    if 'lte' in value:
                        df = df[df[col_name] <= value['lte']]
                elif isinstance(value, list):
                    if value:
                        df = df[df[col_name].isin(value)]
                elif value is not None:
                    df = df[df[col_name] == value]
        else:
            # DuckDB relation: use SQL WHERE clause
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
                    # Date range format - always quote dates
                    conditions.append(f"{col_name} >= '{value['start']}'")
                    conditions.append(f"{col_name} <= '{value['end']}'")
                elif 'min' in value:
                    # Use _format_sql_value to handle numeric vs string values
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['min'])}")
                if 'max' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['max'])}")
                if 'gt' in value:
                    conditions.append(f"{col_name} > {FilterEngine._format_sql_value(value['gt'])}")
                if 'lt' in value:
                    conditions.append(f"{col_name} < {FilterEngine._format_sql_value(value['lt'])}")
                if 'gte' in value:
                    conditions.append(f"{col_name} >= {FilterEngine._format_sql_value(value['gte'])}")
                if 'lte' in value:
                    conditions.append(f"{col_name} <= {FilterEngine._format_sql_value(value['lte'])}")

            elif isinstance(value, list):
                # IN filter with proper value formatting
                if value:
                    formatted_values = ", ".join(FilterEngine._format_sql_value(v) for v in value)
                    conditions.append(f"{col_name} IN ({formatted_values})")

            elif value is not None:
                # Exact match
                conditions.append(f"{col_name} = {FilterEngine._format_sql_value(value)}")

        return " AND ".join(conditions) if conditions else "1=1"
