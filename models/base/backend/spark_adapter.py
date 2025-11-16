"""
Spark backend adapter implementation with Delta Lake support.

Apache Spark is a distributed data processing engine for big data workloads.
Uses catalog-based table management and lazy evaluation.
Supports Delta Lake for ACID transactions and time travel.
"""

from typing import Dict, Optional
import time
import logging
from pathlib import Path

from .adapter import BackendAdapter, QueryResult

logger = logging.getLogger(__name__)


class SparkAdapter(BackendAdapter):
    """
    Apache Spark backend adapter with Delta Lake support.

    Spark-specific features:
    - Distributed processing
    - Lazy evaluation
    - Catalog-based tables
    - Hive metastore integration
    - Delta Lake ACID transactions and time travel
    """

    def __init__(self, connection, model):
        """Initialize Spark adapter with enriched table tracking."""
        super().__init__(connection, model)
        self._enriched_tables = set()  # Track tables with enriched temp views

    def get_dialect(self) -> str:
        """Get SQL dialect name."""
        return 'spark'

    def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
        """
        Execute SQL in Spark.

        Args:
            sql: SQL query string
            params: Optional query parameters (not yet implemented)

        Returns:
            QueryResult with Spark DataFrame (or Pandas if converted)

        Note:
            Returns Spark DataFrame by default for lazy evaluation.
            Can be converted to Pandas with result.data.toPandas()
        """
        start = time.time()

        # Execute SQL query (SparkConnection.spark is the SparkSession)
        spark_df = self.connection.spark.sql(sql)

        # For row count, we need to trigger execution
        # This can be expensive - consider making it optional
        row_count = spark_df.count()

        elapsed_ms = (time.time() - start) * 1000

        return QueryResult(
            data=spark_df,  # Return Spark DataFrame (lazy)
            backend='spark',
            query_time_ms=elapsed_ms,
            rows=row_count,
            sql=sql
        )

    def get_table_reference(self, table_name: str) -> str:
        """
        Get Spark table reference.

        Spark can use either:
        1. Enriched temp views (created by set_enriched_table)
        2. Catalog tables (database.table format)
        3. File paths (for direct file access with Delta/Parquet)

        Auto-detects Delta tables when using file paths.

        Args:
            table_name: Logical table name from model schema

        Returns:
            Spark table reference (view name, catalog reference, or delta.`path`)

        Raises:
            ValueError: If table not found in model schema
        """
        # Check if table has been enriched - if so, use the temp view
        if table_name in self._enriched_tables:
            logger.debug(f"Using enriched temp view for table '{table_name}'")
            return table_name  # Return view name, not path

        # Verify table exists in schema
        schema = self.model.model_cfg.get('schema', {})
        dimensions = schema.get('dimensions', {})
        facts = schema.get('facts', {})

        if table_name not in dimensions and table_name not in facts:
            raise ValueError(
                f"Table '{table_name}' not found in model '{self.model.model_name}' schema. "
                f"Available tables: {list(dimensions.keys()) + list(facts.keys())}"
            )

        # Check if we're using catalog or file-based storage
        storage_config = self.model.model_cfg.get('storage', {})

        # If using catalog (Hive metastore)
        if 'database' in storage_config:
            database = storage_config['database']
            return f"{database}.{table_name}"

        # Otherwise, use file-based access
        # Resolve table path
        table_path = self._resolve_table_path(table_name)

        # Check if Delta table
        if self._is_delta_table(table_path):
            logger.debug(f"Using Delta format for table '{table_name}' at {table_path}")
            return f"delta.`{table_path}`"
        else:
            # Parquet table
            return f"parquet.`{table_path}`"

    def _resolve_table_path(self, table_name: str) -> Path:
        """
        Resolve logical table name to physical path.

        Args:
            table_name: Logical table name

        Returns:
            Path to table data
        """
        schema = self.model.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(f"Table '{table_name}' not found in schema")

        # Build full path
        storage_root = Path(self.model.model_cfg['storage']['root'])
        full_path = storage_root / relative_path

        return full_path

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
        Check Spark feature support.

        Spark SQL supports most standard SQL features plus Delta Lake.
        """
        supported = {
            'window_functions': True,
            'cte': True,
            'lateral_join': True,  # Spark 3.1+
            'array_agg': True,     # COLLECT_LIST in Spark
            'qualify': False,      # Not supported (use subquery instead)
            'pivot': True,         # Spark has PIVOT
            'explode': True,       # Spark-specific array explosion
            'percentile': True,    # PERCENTILE_APPROX
            'delta_lake': True,    # Spark supports Delta Lake natively
            'time_travel': True,   # Via Delta Lake
        }
        return supported.get(feature, False)

    def format_limit(self, limit: int) -> str:
        """Format LIMIT clause (Spark standard)."""
        return f"LIMIT {limit}"

    def get_null_safe_divide(self, numerator: str, denominator: str) -> str:
        """
        Get null-safe division expression for Spark.

        Spark uses NULLIF like standard SQL.
        """
        return f"{numerator} / NULLIF({denominator}, 0)"

    def cache_table(self, table_name: str):
        """
        Cache a table in Spark memory for faster repeated access.

        Args:
            table_name: Table name to cache
        """
        self.connection.spark.sql(f"CACHE TABLE {table_name}")

    def uncache_table(self, table_name: str):
        """
        Remove a table from Spark cache.

        Args:
            table_name: Table name to uncache
        """
        self.connection.spark.sql(f"UNCACHE TABLE {table_name}")

    def set_enriched_table(self, table_name: str, enriched_df):
        """
        Set enriched DataFrame for a table (used for auto-enrichment).

        Creates a temporary view from the enriched DataFrame so that
        subsequent queries against table_name will use the enriched data.

        Args:
            table_name: Logical table name
            enriched_df: Spark DataFrame with enriched data

        Example:
            # Get enriched table with joins
            enriched_df = model.get_table_enriched(
                'fact_equity_prices',
                enrich_with=['dim_equity', 'dim_exchange']
            )
            # Make adapter use enriched table for all subsequent queries
            adapter.set_enriched_table('fact_equity_prices', enriched_df)
        """
        # Create or replace temporary view
        enriched_df.createOrReplaceTempView(table_name)

        # Mark this table as enriched so get_table_reference uses the view
        self._enriched_tables.add(table_name)
        logger.debug(f"Table '{table_name}' marked as enriched, will use temp view in queries")
