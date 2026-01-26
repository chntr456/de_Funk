"""
Computed measure implementation for expression-based calculations.

Handles measures that require custom expressions before aggregation.
"""

from typing import Dict, Any

from de_funk.models.measures.base_measure import BaseMeasure, MeasureType
from de_funk.models.measures.registry import MeasureRegistry
from de_funk.models.base.backend.sql_builder import SQLBuilder


@MeasureRegistry.register(MeasureType.COMPUTED)
class ComputedMeasure(BaseMeasure):
    """
    Computed measure using custom expressions.

    Applies an expression to columns before aggregation.

    Example YAML:
        market_cap:
            type: computed
            source: fact_prices.close
            expression: "close * volume"
            aggregation: avg
            data_type: double

    This will compute: AVG(close * volume)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize computed measure.

        Args:
            config: Measure configuration
                Required fields:
                - source: 'table.column' (primary column)
                - expression: SQL expression
                - aggregation: Aggregation function
        """
        super().__init__(config)

        self.expression = config.get('expression')
        if not self.expression:
            raise ValueError(
                f"Computed measure '{self.name}' requires 'expression' field"
            )

        self.aggregation = config.get('aggregation', 'avg').upper()

        # Validate aggregation
        valid_aggregations = ['AVG', 'SUM', 'MIN', 'MAX', 'COUNT', 'STDDEV', 'VARIANCE']
        if self.aggregation not in valid_aggregations:
            raise ValueError(
                f"Invalid aggregation '{self.aggregation}'. "
                f"Valid: {valid_aggregations}"
            )

    def to_sql(self, adapter) -> str:
        """
        Generate SQL for computed measure.

        Example output:
            SELECT
                AVG(close * volume) as measure_value
            FROM read_parquet('/path/to/fact_prices/*.parquet')
            WHERE close IS NOT NULL AND volume IS NOT NULL

        Args:
            adapter: Backend adapter

        Returns:
            SQL query string
        """
        table_name = self._get_table_name()
        table_ref = adapter.get_table_reference(table_name)

        # Extract columns from expression for WHERE clause
        # Simple heuristic: assume expression columns are not null
        where_clauses = self._build_where_clauses()

        query = f"""
SELECT
    {self.aggregation}({self.expression}) as measure_value
FROM {table_ref}
WHERE {' AND '.join(where_clauses)}
        """.strip()

        return query

    def execute(self, adapter, entity_column=None, filters=None, limit=None, **kwargs):
        """
        Execute computed measure with optional grouping.

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
            return self._execute_grouped(adapter, entity_column, filters, limit)
        else:
            sql = self.to_sql(adapter)
            return adapter.execute_sql(sql)

    def _execute_grouped(self, adapter, entity_column, filters=None, limit=None):
        """Execute with GROUP BY on entity column."""
        table_name = self._get_table_name()
        table_ref = adapter.get_table_reference(table_name)

        # Build WHERE clause
        where_clauses = self._build_where_clauses()
        if filters:
            where_clauses.extend(filters)

        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build ORDER BY
        order_clause = "ORDER BY measure_value DESC"

        # Build LIMIT
        limit_clause = ""
        if limit:
            limit_clause = adapter.format_limit(limit)

        query = f"""
SELECT
    {entity_column},
    {self.aggregation}({self.expression}) as measure_value
FROM {table_ref}
{where_clause}
GROUP BY {entity_column}
{order_clause}
{limit_clause}
        """.strip()

        return adapter.execute_sql(query)

    def _build_where_clauses(self):
        """
        Build WHERE clauses for expression columns.

        Extracts column names from expression and adds IS NOT NULL checks.
        """
        # Simple heuristic: extract identifiers from expression
        # This is basic - could be improved with proper SQL parsing
        import re

        # Match identifiers (column names)
        columns = re.findall(r'\b([a-z_][a-z0-9_]*)\b', self.expression.lower())

        # Remove SQL keywords
        keywords = {'and', 'or', 'not', 'is', 'null', 'true', 'false', 'in', 'between', 'like'}
        columns = [col for col in columns if col not in keywords]

        # Create IS NOT NULL clauses
        return [f"{col} IS NOT NULL" for col in columns]
