"""
DuckDB backend adapter implementation with Delta Lake support.

DuckDB is a columnar in-process SQL database optimized for analytics.
It can read directly from Parquet and Delta Lake files without loading into memory.
"""

from pathlib import Path
from typing import Dict, Optional
import time
import logging

from .adapter import BackendAdapter, QueryResult

logger = logging.getLogger(__name__)


class DuckDBAdapter(BackendAdapter):
    """
    DuckDB backend adapter with Delta Lake support.

    DuckDB-specific features:
    - Reads directly from Parquet and Delta Lake files
    - QUALIFY clause for window function filtering
    - Columnar storage optimizations
    - Fast aggregations
    - Delta Lake time travel and ACID transactions
    """

    def __init__(self, connection, model):
        """Initialize DuckDB adapter with enriched table tracking."""
        super().__init__(connection, model)
        self._enriched_tables = set()  # Track tables with enriched views

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

        DuckDB reads directly from Parquet or Delta Lake files.
        Automatically detects format based on directory structure.
        If table has been enriched via set_enriched_table(), uses the view instead.

        Args:
            table_name: Logical table name from model schema

        Returns:
            DuckDB-specific table reference:
            - Enriched: table_name (view created by set_enriched_table)
            - Delta: "delta_scan('/path')"
            - Parquet: "read_parquet('/path/*.parquet')"

        Raises:
            ValueError: If table not found in model schema
        """
        # Check if table has been enriched - if so, use the view
        if table_name in self._enriched_tables:
            logger.debug(f"Using enriched view for table '{table_name}'")
            return table_name

        # Resolve table path from model schema
        table_path = self._resolve_table_path(table_name)

        # Check if this is a Delta table (has _delta_log directory)
        if self._is_delta_table(table_path):
            logger.debug(f"Using delta_scan for table '{table_name}' at {table_path}")
            return f"delta_scan('{table_path}')"

        # Otherwise, read as Parquet
        if table_path.is_dir():
            # Read all parquet files in directory
            return f"read_parquet('{table_path}/*.parquet')"
        else:
            # Single file
            return f"read_parquet('{table_path}')"

    def _is_delta_table(self, path: Path) -> bool:
        """
        Check if a path points to a Delta Lake table.

        Args:
            path: Path to check

        Returns:
            True if path is a Delta table, False otherwise
        """
        if not path.exists():
            return False

        # Delta tables have a _delta_log directory
        delta_log = path / "_delta_log"
        return delta_log.exists() and delta_log.is_dir()

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
            'delta_lake': True,  # DuckDB supports Delta Lake via extension
            'time_travel': True,  # Via Delta Lake
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

    def set_enriched_table(self, table_name: str, enriched_df):
        """
        Set enriched DataFrame for a table (used for auto-enrichment).

        Creates a temporary view from the enriched DataFrame so that
        subsequent queries against table_name will use the enriched data.

        Args:
            table_name: Logical table name
            enriched_df: Pandas DataFrame with enriched data

        Example:
            # Get enriched table with joins
            enriched_df = model.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange']
            )
            # Make adapter use enriched table for all subsequent queries
            adapter.set_enriched_table('fact_equity_prices', enriched_df)
        """
        # Register DataFrame as a view in DuckDB (use underlying conn)
        self.connection.conn.register(f"{table_name}_enriched", enriched_df)

        # Create a view that references the enriched data
        self.connection.execute(f"""
            CREATE OR REPLACE VIEW {table_name} AS
            SELECT * FROM {table_name}_enriched
        """)

        # Mark this table as enriched so get_table_reference uses the view
        self._enriched_tables.add(table_name)
        logger.debug(f"Table '{table_name}' marked as enriched, will use view in queries")
