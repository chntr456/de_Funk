"""
Spark backend adapter implementation.

Apache Spark is a distributed data processing engine for big data workloads.
Uses catalog-based table management and lazy evaluation.
"""

from typing import Dict, Optional
import time

from .adapter import BackendAdapter, QueryResult


class SparkAdapter(BackendAdapter):
    """
    Apache Spark backend adapter.

    Spark-specific features:
    - Distributed processing
    - Lazy evaluation
    - Catalog-based tables
    - Hive metastore integration
    """

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

        # Execute SQL query
        spark_df = self.connection.sql(sql)

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

        Spark uses catalog tables in the format: database.table

        Args:
            table_name: Logical table name from model schema

        Returns:
            Spark catalog table reference (e.g., "silver.fact_prices")

        Raises:
            ValueError: If table not found in model schema
        """
        # Get database from storage config (default: 'silver')
        database = self.model.model_cfg.get('storage', {}).get('database', 'silver')

        # Verify table exists in schema
        schema = self.model.model_cfg.get('schema', {})
        dimensions = schema.get('dimensions', {})
        facts = schema.get('facts', {})

        if table_name not in dimensions and table_name not in facts:
            raise ValueError(
                f"Table '{table_name}' not found in model '{self.model.model_name}' schema. "
                f"Available tables: {list(dimensions.keys()) + list(facts.keys())}"
            )

        # Return catalog reference
        return f"{database}.{table_name}"

    def supports_feature(self, feature: str) -> bool:
        """
        Check Spark feature support.

        Spark SQL supports most standard SQL features.
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
        self.connection.sql(f"CACHE TABLE {table_name}")

    def uncache_table(self, table_name: str):
        """
        Remove a table from Spark cache.

        Args:
            table_name: Table name to uncache
        """
        self.connection.sql(f"UNCACHE TABLE {table_name}")
