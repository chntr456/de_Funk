"""
Simple measure implementation for direct aggregations.

Handles basic aggregation functions: AVG, SUM, MIN, MAX, COUNT, etc.
"""

from typing import Dict, Any

from models.base.measures.base_measure import BaseMeasure, MeasureType
from models.base.measures.registry import MeasureRegistry
from models.base.backend.sql_builder import SQLBuilder


@MeasureRegistry.register(MeasureType.SIMPLE)
class SimpleMeasure(BaseMeasure):
    """
    Simple aggregation measure.

    Performs standard SQL aggregations on a single column.

    Supported aggregations:
    - avg: Average
    - sum: Sum
    - min: Minimum
    - max: Maximum
    - count: Count
    - stddev: Standard deviation
    - variance: Variance

    Example YAML:
        avg_close_price:
            source: fact_prices.close
            aggregation: avg
            data_type: double
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize simple measure.

        Args:
            config: Measure configuration
                Required fields:
                - source: 'table.column'
                - aggregation: Aggregation function name
        """
        super().__init__(config)

        # Get aggregation function
        self.aggregation = config.get('aggregation', 'avg').upper()

        # Validate aggregation function
        valid_aggregations = ['AVG', 'SUM', 'MIN', 'MAX', 'COUNT', 'STDDEV', 'VARIANCE']
        if self.aggregation not in valid_aggregations:
            raise ValueError(
                f"Invalid aggregation '{self.aggregation}'. "
                f"Valid: {valid_aggregations}"
            )

    def to_sql(self, adapter) -> str:
        """
        Generate SQL for simple aggregation.

        Example output:
            SELECT
                ticker,
                AVG(close) as measure_value
            FROM read_parquet('/path/to/fact_prices/*.parquet')
            WHERE close IS NOT NULL
            GROUP BY ticker
            ORDER BY measure_value DESC

        Args:
            adapter: Backend adapter

        Returns:
            SQL query string
        """
        builder = SQLBuilder(adapter)

        table_name, column_name = self._parse_source()

        # For simple measures, we typically group by an entity column
        # This will be provided at execution time via kwargs
        # For now, generate a query without GROUP BY (can be wrapped later)

        table_ref = adapter.get_table_reference(table_name)

        query = f"""
SELECT
    {self.aggregation}({column_name}) as measure_value
FROM {table_ref}
WHERE {column_name} IS NOT NULL
        """.strip()

        return query

    def execute(self, adapter, entity_column=None, filters=None, limit=None, **kwargs):
        """
        Execute simple measure with optional grouping.

        Args:
            adapter: Backend adapter
            entity_column: Optional column to group by
            filters: Optional WHERE clause conditions
            limit: Optional result limit
            **kwargs: Additional parameters

        Returns:
            QueryResult
        """
        if entity_column:
            # Use SQLBuilder for grouped aggregation
            return self._execute_grouped(adapter, entity_column, filters, limit)
        else:
            # Use basic SQL for ungrouped aggregation
            sql = self.to_sql(adapter)
            return adapter.execute_sql(sql)

    def _execute_grouped(self, adapter, entity_column, filters=None, limit=None):
        """Execute with GROUP BY on entity column."""
        builder = SQLBuilder(adapter)

        table_name, column_name = self._parse_source()

        sql = builder.build_simple_aggregate(
            table_name=table_name,
            value_column=column_name,
            agg_function=self.aggregation,
            group_by=[entity_column],
            filters=filters,
            limit=limit
        )

        return adapter.execute_sql(sql)
