"""
DuckDB backend adapter implementation.

DuckDB is a columnar in-process SQL database optimized for analytics.
It can read directly from Parquet files without loading into memory.
"""

from pathlib import Path
from typing import Dict, Optional
import time

from .adapter import BackendAdapter, QueryResult


class DuckDBAdapter(BackendAdapter):
    """
    DuckDB backend adapter.

    DuckDB-specific features:
    - Reads directly from Parquet files
    - QUALIFY clause for window function filtering
    - Columnar storage optimizations
    - Fast aggregations
    """

    def get_dialect(self) -> str:
        """Get SQL dialect name."""
        return 'duckdb'

    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """
        Execute SQL in DuckDB.

        Args:
            sql: SQL query string
            params: Optional query parameters (not yet implemented)

        Returns:
            QueryResult with Pandas DataFrame and metadata
        """
        start = time.time()

        # Execute query and fetch as Pandas DataFrame
        result_df = self.connection.execute(sql).fetch_df()

        elapsed_ms = (time.time() - start) * 1000

        return QueryResult(
            data=result_df,
            backend='duckdb',
            query_time_ms=elapsed_ms,
            rows=len(result_df),
            sql=sql
        )

    def get_table_reference(self, table_name: str) -> str:
        """
        Get DuckDB table reference.

        DuckDB reads directly from Parquet files using read_parquet().

        Args:
            table_name: Logical table name from model schema

        Returns:
            DuckDB-specific table reference (e.g., "read_parquet('/path/*.parquet')")

        Raises:
            ValueError: If table not found in model schema
        """
        # Resolve table path from model schema
        table_path = self._resolve_table_path(table_name)

        if table_path.is_dir():
            # Read all parquet files in directory
            return f"read_parquet('{table_path}/*.parquet')"
        else:
            # Single file
            return f"read_parquet('{table_path}')"

    def supports_feature(self, feature: str) -> bool:
        """
        Check DuckDB feature support.

        DuckDB supports most modern SQL features including some unique ones.
        """
        supported = {
            'window_functions': True,
            'cte': True,
            'lateral_join': True,
            'array_agg': True,
            'qualify': True,  # DuckDB-specific! Filter after window functions
            'list_agg': True,  # DuckDB uses LIST_AGG instead of ARRAY_AGG
            'struct': True,   # DuckDB supports STRUCT types
            'map': True,      # DuckDB supports MAP types
            'json': True,     # DuckDB has JSON functions
            'pivot': True,    # DuckDB has PIVOT
            'asof_join': True,  # DuckDB has ASOF joins
        }
        return supported.get(feature, False)

    def format_limit(self, limit: int) -> str:
        """Format LIMIT clause (DuckDB standard)."""
        return f"LIMIT {limit}"

    def _resolve_table_path(self, table_name: str) -> Path:
        """
        Resolve logical table name to physical path.

        Args:
            table_name: Logical table name (e.g., 'fact_prices', 'dim_company')

        Returns:
            Path to table data

        Raises:
            ValueError: If table not found in model schema
        """
        # Get schema from model config
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(
                f"Table '{table_name}' not found in model '{self.model.model_name}' schema. "
                f"Available tables: {list(schema.get('dimensions', {}).keys()) + list(schema.get('facts', {}).keys())}"
            )

        # Build full path
        storage_root = Path(self.model.model_cfg['storage']['root'])
        full_path = storage_root / relative_path

        return full_path

    def create_table_view(self, table_name: str):
        """
        Create a temporary view for a table.

        Useful for complex queries that reference the same table multiple times.

        Args:
            table_name: Logical table name
        """
        table_ref = self.get_table_reference(table_name)
        self.connection.execute(f"""
            CREATE OR REPLACE VIEW {table_name} AS
            SELECT * FROM {table_ref}
        """)
