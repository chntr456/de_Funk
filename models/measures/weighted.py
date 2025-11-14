"""
Weighted measure implementation for weighted aggregations.

Delegates to domain-specific weighting strategies for calculation logic.
"""

from typing import Dict, Any, List

from models.base.measures.base_measure import BaseMeasure, MeasureType
from models.base.measures.registry import MeasureRegistry


@MeasureRegistry.register(MeasureType.WEIGHTED)
class WeightedMeasure(BaseMeasure):
    """
    Weighted aggregate measure.

    Calculates weighted aggregations across multiple entities (stocks, ETFs, etc.)
    using various weighting schemes.

    Delegates to domain-specific weighting strategies for SQL generation.

    Example YAML:
        volume_weighted_index:
            type: weighted
            source: fact_prices.close
            weighting_method: volume
            group_by: [trade_date]
            data_type: double
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize weighted measure.

        Args:
            config: Measure configuration
                Required fields:
                - source: 'table.column'
                - weighting_method: Method name (equal, volume, market_cap, etc.)
                Optional fields:
                - group_by: Columns to group by (default: ['trade_date'])
                - weight_column: Explicit weight column for custom weighting
                - filters: Additional filters
        """
        super().__init__(config)

        self.weighting_method = config.get('weighting_method', 'equal')
        self.group_by = config.get('group_by', ['trade_date'])
        self.weight_column = config.get('weight_column')  # Optional explicit weights
        self.measure_filters = config.get('filters', [])  # Measure-specific filters

    def to_sql(self, adapter) -> str:
        """
        Generate SQL for weighted aggregate.

        Delegates to domain-specific weighting strategy.

        Args:
            adapter: Backend adapter

        Returns:
            SQL query string
        """
        # Import here to avoid circular dependency
        from models.implemented.equity.domains.weighting import get_weighting_strategy

        # Get weighting strategy
        strategy = get_weighting_strategy(self.weighting_method)

        # Parse source
        table_name, value_col = self._parse_source()

        # Generate SQL using strategy
        return strategy.generate_sql(
            adapter=adapter,
            table_name=table_name,
            value_column=value_col,
            group_by=self.group_by,
            weight_column=self.weight_column,
            filters=self.measure_filters
        )

    def execute(self, adapter, filters=None, **kwargs):
        """
        Execute weighted measure.

        Args:
            adapter: Backend adapter
            filters: Optional additional filters (merged with measure filters)
            **kwargs: Additional parameters

        Returns:
            QueryResult
        """
        # Merge execution filters with measure filters
        all_filters = self.measure_filters.copy()
        if filters:
            all_filters.extend(filters if isinstance(filters, list) else [filters])

        # Update measure config with merged filters
        # This is a bit hacky - consider refactoring
        original_filters = self.measure_filters
        self.measure_filters = all_filters

        try:
            # Generate and execute SQL
            sql = self.to_sql(adapter)
            return adapter.execute_sql(sql)
        finally:
            # Restore original filters
            self.measure_filters = original_filters
