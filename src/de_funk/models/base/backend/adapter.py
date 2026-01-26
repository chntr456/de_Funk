"""
Abstract backend adapter interface.

Defines the contract that all backend implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class QueryResult:
    """
    Unified query result wrapper.

    Encapsulates query results with metadata regardless of backend.
    """
    data: Any  # DataFrame (Pandas, Spark, Polars, etc.)
    backend: str
    query_time_ms: float
    rows: int
    sql: Optional[str] = None  # Original SQL query


class BackendAdapter(ABC):
    """
    Abstract interface for backend execution.

    All backends (DuckDB, Spark, Polars, etc.) must implement this interface.
    Measures generate SQL, adapters execute it in a backend-specific way.

    Design Philosophy:
    - Measures generate SQL (business logic)
    - Adapters execute SQL (infrastructure)
    - 90% of measure code is backend-agnostic
    """

    def __init__(self, connection, model):
        """
        Initialize backend adapter.

        Args:
            connection: Backend-specific connection (DuckDB conn, Spark session, etc.)
            model: Model instance (for accessing schema/storage config)
        """
        self.connection = connection
        self.model = model
        self.dialect = self.get_dialect()

    @abstractmethod
    def get_dialect(self) -> str:
        """
        Get SQL dialect name.

        Returns:
            Dialect name (e.g., 'duckdb', 'spark', 'postgres')
        """
        pass

    @abstractmethod
    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """
        Execute SQL query and return results.

        Args:
            sql: SQL query string
            params: Optional query parameters for parameterized queries

        Returns:
            QueryResult with data and metadata

        Raises:
            Exception: If query execution fails
        """
        pass

    @abstractmethod
    def get_table_reference(self, table_name: str) -> str:
        """
        Get backend-specific table reference.

        Different backends access tables differently:
        - DuckDB: "read_parquet('/path/to/table/*.parquet')"
        - Spark: "silver.fact_prices"
        - Postgres: "silver.fact_prices"

        Args:
            table_name: Logical table name from model schema

        Returns:
            Backend-specific table reference string

        Raises:
            ValueError: If table not found in model schema
        """
        pass

    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """
        Check if backend supports a SQL feature.

        Features include:
        - 'window_functions': Window functions (ROW_NUMBER, LAG, etc.)
        - 'cte': Common Table Expressions (WITH clause)
        - 'lateral_join': LATERAL joins
        - 'qualify': QUALIFY clause (DuckDB-specific)
        - 'array_agg': ARRAY_AGG function
        - etc.

        Args:
            feature: Feature name

        Returns:
            True if feature is supported, False otherwise
        """
        pass

    def format_limit(self, limit: int) -> str:
        """
        Format LIMIT clause (backend-specific).

        Most backends use "LIMIT n" but some differ.

        Args:
            limit: Number of rows to limit

        Returns:
            Formatted LIMIT clause
        """
        return f"LIMIT {limit}"

    def format_date_literal(self, date_str: str) -> str:
        """
        Format date literal (backend-specific).

        Args:
            date_str: Date string in ISO format (YYYY-MM-DD)

        Returns:
            Backend-specific date literal
        """
        return f"DATE '{date_str}'"

    def format_column_alias(self, column: str, alias: str) -> str:
        """
        Format column with alias.

        Args:
            column: Column name or expression
            alias: Alias name

        Returns:
            Formatted column with alias
        """
        return f"{column} as {alias}"

    def get_null_safe_divide(self, numerator: str, denominator: str) -> str:
        """
        Get null-safe division expression.

        Prevents division by zero and handles nulls.

        Args:
            numerator: Numerator expression
            denominator: Denominator expression

        Returns:
            Null-safe division expression
        """
        return f"{numerator} / NULLIF({denominator}, 0)"
