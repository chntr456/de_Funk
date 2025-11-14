"""
Simple measure implementation for direct aggregations.

Handles basic aggregation functions: AVG, SUM, MIN, MAX, COUNT, etc.
"""

from typing import Dict, Any, List

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
            filters: Optional WHERE clause conditions (dict or list)
            limit: Optional result limit
            **kwargs: Additional filter parameters (e.g., trade_date={'start': ..., 'end': ...}, ticker=[...])

        Returns:
            QueryResult
        """
        # Merge filters from both filters param and kwargs
        all_filters = self._build_filter_list(filters, **kwargs)

        if entity_column:
            # Use SQLBuilder for grouped aggregation
            return self._execute_grouped(adapter, entity_column, all_filters, limit)
        else:
            # Use basic SQL for ungrouped aggregation
            sql = self.to_sql(adapter)
            if all_filters:
                # Add filters to ungrouped query
                table_name, column_name = self._parse_source()
                where_clauses = [f"{column_name} IS NOT NULL"] + all_filters
                sql += "\nAND " + " AND ".join(all_filters)
            return adapter.execute_sql(sql)

    def _build_filter_list(self, filters=None, **kwargs):
        """
        Build list of SQL WHERE clauses from filters and kwargs.

        Args:
            filters: Optional dict or list of filter conditions
            **kwargs: Additional filter parameters (e.g., trade_date={'start': ..., 'end': ...}, ticker=[...])

        Returns:
            List of SQL WHERE clause strings

        Example:
            Input: filters=None, trade_date={'start': '2024-01-01', 'end': '2024-12-31'}, ticker=['AAPL', 'MSFT']
            Output: ["trade_date >= '2024-01-01'", "trade_date <= '2024-12-31'", "ticker IN ('AAPL', 'MSFT')"]
        """
        filter_list = []

        # Add filters from filters parameter
        if filters:
            if isinstance(filters, list):
                filter_list.extend(filters)
            elif isinstance(filters, dict):
                # Convert dict to SQL clauses
                for col, value in filters.items():
                    filter_list.extend(self._convert_filter_to_sql(col, value))

        # Add filters from kwargs
        for col, value in kwargs.items():
            filter_list.extend(self._convert_filter_to_sql(col, value))

        return filter_list

    def _convert_filter_to_sql(self, column: str, value) -> List[str]:
        """
        Convert a filter value to SQL WHERE clause(s).

        Args:
            column: Column name
            value: Filter value (can be scalar, list, or dict with start/end/gte/lte)

        Returns:
            List of SQL WHERE clause strings

        Examples:
            _convert_filter_to_sql('ticker', ['AAPL', 'MSFT'])
            -> ["ticker IN ('AAPL', 'MSFT')"]

            _convert_filter_to_sql('trade_date', {'start': '2024-01-01', 'end': '2024-12-31'})
            -> ["trade_date >= '2024-01-01'", "trade_date <= '2024-12-31'"]

            _convert_filter_to_sql('price', {'gte': 100, 'lte': 200})
            -> ["price >= 100", "price <= 200"]
        """
        clauses = []

        if value is None:
            return clauses

        # Handle dict with start/end or gte/lte
        if isinstance(value, dict):
            if 'start' in value:
                clauses.append(f"{column} >= '{value['start']}'")
            if 'end' in value:
                clauses.append(f"{column} <= '{value['end']}'")
            if 'gte' in value:
                if isinstance(value['gte'], str):
                    clauses.append(f"{column} >= '{value['gte']}'")
                else:
                    clauses.append(f"{column} >= {value['gte']}")
            if 'lte' in value:
                if isinstance(value['lte'], str):
                    clauses.append(f"{column} <= '{value['lte']}'")
                else:
                    clauses.append(f"{column} <= {value['lte']}")
            if 'gt' in value:
                if isinstance(value['gt'], str):
                    clauses.append(f"{column} > '{value['gt']}'")
                else:
                    clauses.append(f"{column} > {value['gt']}")
            if 'lt' in value:
                if isinstance(value['lt'], str):
                    clauses.append(f"{column} < '{value['lt']}'")
                else:
                    clauses.append(f"{column} < {value['lt']}")
            if 'eq' in value or 'equals' in value:
                val = value.get('eq', value.get('equals'))
                if isinstance(val, str):
                    clauses.append(f"{column} = '{val}'")
                else:
                    clauses.append(f"{column} = {val}")

        # Handle list (IN clause)
        elif isinstance(value, (list, tuple)):
            if len(value) > 0:
                # Quote string values
                if isinstance(value[0], str):
                    quoted = "', '".join(value)
                    clauses.append(f"{column} IN ('{quoted}')")
                else:
                    vals = ', '.join(str(v) for v in value)
                    clauses.append(f"{column} IN ({vals})")

        # Handle scalar value (equality)
        else:
            if isinstance(value, str):
                clauses.append(f"{column} = '{value}'")
            else:
                clauses.append(f"{column} = {value}")

        return clauses

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
