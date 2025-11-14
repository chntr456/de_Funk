"""
Equity weighting strategies for weighted aggregate calculations.

Provides various weighting methods for creating stock indices and portfolios.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional


class WeightingMethod(Enum):
    """Weighting methods for equities."""
    EQUAL = "equal"
    VOLUME = "volume"
    MARKET_CAP = "market_cap"
    PRICE = "price"
    VOLUME_DEVIATION = "volume_deviation"
    VOLATILITY = "volatility"


class WeightingStrategy(ABC):
    """
    Base class for weighting strategies.

    Each strategy generates SQL for a specific weighting method.
    """

    @abstractmethod
    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        group_by: List[str],
        weight_column: Optional[str] = None,
        filters: Optional[List[str]] = None
    ) -> str:
        """
        Generate SQL for this weighting method.

        Args:
            adapter: Backend adapter for table references
            table_name: Source table name
            value_column: Column to aggregate
            group_by: List of columns to group by
            weight_column: Optional explicit weight column
            filters: Optional additional WHERE conditions

        Returns:
            SQL query string
        """
        pass


class EqualWeightStrategy(WeightingStrategy):
    """
    Equal weighting (simple average).

    All stocks weighted equally regardless of size or volume.
    This is the simplest form of weighting.
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for equal weighting."""
        from models.base.backend.sql_builder import SQLBuilder

        builder = SQLBuilder(adapter)
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build WHERE clause
        where_clauses = [f"{value_column} IS NOT NULL"]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        return f"""
SELECT
    {group_cols},
    AVG({value_column}) as weighted_value,
    COUNT(*) as entity_count
FROM {table_ref}
{where_clause}
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()


class VolumeWeightStrategy(WeightingStrategy):
    """
    Volume-weighted average.

    Stocks weighted by trading volume.
    Higher volume = higher weight in the index.
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for volume weighting."""
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build weighted aggregation
        weighted_agg = adapter.get_null_safe_divide(
            f"SUM({value_column} * volume)",
            "SUM(volume)"
        )

        # Build WHERE clause
        where_clauses = [
            f"{value_column} IS NOT NULL",
            "volume IS NOT NULL",
            "volume > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        return f"""
SELECT
    {group_cols},
    {weighted_agg} as weighted_value,
    COUNT(*) as entity_count,
    SUM(volume) as total_volume
FROM {table_ref}
{where_clause}
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()


class MarketCapWeightStrategy(WeightingStrategy):
    """
    Market capitalization weighted (price × volume as proxy).

    Stocks weighted by market cap.
    Larger companies have higher weight (like S&P 500).
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for market cap weighting."""
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Use close * volume as market cap proxy
        weighted_agg = adapter.get_null_safe_divide(
            f"SUM({value_column} * close * volume)",
            "SUM(close * volume)"
        )

        # Build WHERE clause
        where_clauses = [
            f"{value_column} IS NOT NULL",
            "close IS NOT NULL",
            "volume IS NOT NULL",
            "close > 0",
            "volume > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        return f"""
SELECT
    {group_cols},
    {weighted_agg} as weighted_value,
    COUNT(*) as entity_count,
    SUM(close * volume) as total_market_cap
FROM {table_ref}
{where_clause}
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()


class PriceWeightStrategy(WeightingStrategy):
    """
    Price-weighted average.

    Stocks weighted by their price.
    Higher priced stocks have higher weight (like DJIA).
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for price weighting."""
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Weight by stock price
        weighted_agg = adapter.get_null_safe_divide(
            f"SUM({value_column} * close)",
            "SUM(close)"
        )

        # Build WHERE clause
        where_clauses = [
            f"{value_column} IS NOT NULL",
            "close IS NOT NULL",
            "close > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        return f"""
SELECT
    {group_cols},
    {weighted_agg} as weighted_value,
    COUNT(*) as entity_count,
    SUM(close) as total_price
FROM {table_ref}
{where_clause}
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()


class VolumeDeviationWeightStrategy(WeightingStrategy):
    """
    Volume deviation weighted (unusual activity).

    Stocks weighted by how much their volume deviates from average.
    Highlights stocks with unusual trading activity.
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for volume deviation weighting."""
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build WHERE clause for filters
        filter_clause = ""
        if filters:
            filter_clause = "AND " + " AND ".join(filters)

        # Use CTE to calculate average volumes
        return f"""
WITH avg_volumes AS (
    SELECT
        ticker,
        AVG(volume) as avg_volume
    FROM {table_ref}
    WHERE volume IS NOT NULL
    GROUP BY ticker
)
SELECT
    f.{group_cols},
    SUM(f.{value_column} * ABS(f.volume - av.avg_volume) * f.close) /
        NULLIF(SUM(ABS(f.volume - av.avg_volume) * f.close), 0) as weighted_value,
    COUNT(*) as entity_count,
    AVG(av.avg_volume) as avg_volume
FROM {table_ref} f
JOIN avg_volumes av ON f.ticker = av.ticker
WHERE f.{value_column} IS NOT NULL
  AND f.volume IS NOT NULL
  AND f.close IS NOT NULL
  AND f.close > 0
  {filter_clause}
GROUP BY f.{group_cols}
ORDER BY f.{group_cols}
        """.strip()


class VolatilityWeightStrategy(WeightingStrategy):
    """
    Inverse volatility weighted (risk-adjusted).

    Stocks weighted inversely by their volatility.
    Less volatile stocks get higher weight (risk-adjusted approach).
    """

    def generate_sql(self, adapter, table_name, value_column, group_by,
                     weight_column=None, filters=None):
        """Generate SQL for inverse volatility weighting."""
        table_ref = adapter.get_table_reference(table_name)
        group_cols = ', '.join(group_by)

        # Build WHERE clause for filters
        filter_clause = ""
        if filters:
            filter_clause = "AND " + " AND ".join(filters)

        # Use daily price range as volatility proxy
        return f"""
WITH daily_ranges AS (
    SELECT
        {group_cols},
        ticker,
        {value_column},
        (high - low) as daily_range
    FROM {table_ref}
    WHERE high IS NOT NULL
      AND low IS NOT NULL
      AND high >= low
      AND {value_column} IS NOT NULL
      {filter_clause}
)
SELECT
    {group_cols},
    SUM({value_column} / NULLIF(daily_range, 0)) /
        NULLIF(SUM(1.0 / NULLIF(daily_range, 0)), 0) as weighted_value,
    COUNT(*) as entity_count,
    AVG(daily_range) as avg_volatility
FROM daily_ranges
WHERE daily_range > 0.001
GROUP BY {group_cols}
ORDER BY {group_cols}
        """.strip()


# Registry of strategies
_STRATEGIES: Dict[WeightingMethod, WeightingStrategy] = {
    WeightingMethod.EQUAL: EqualWeightStrategy(),
    WeightingMethod.VOLUME: VolumeWeightStrategy(),
    WeightingMethod.MARKET_CAP: MarketCapWeightStrategy(),
    WeightingMethod.PRICE: PriceWeightStrategy(),
    WeightingMethod.VOLUME_DEVIATION: VolumeDeviationWeightStrategy(),
    WeightingMethod.VOLATILITY: VolatilityWeightStrategy(),
}


def get_weighting_strategy(method: str) -> WeightingStrategy:
    """
    Get weighting strategy by name.

    Args:
        method: Weighting method name (e.g., 'volume', 'market_cap')

    Returns:
        WeightingStrategy instance

    Raises:
        ValueError: If method is unknown
    """
    try:
        method_enum = WeightingMethod(method)
    except ValueError:
        raise ValueError(
            f"Unknown weighting method: '{method}'. "
            f"Valid methods: {[m.value for m in WeightingMethod]}"
        )

    strategy = _STRATEGIES.get(method_enum)

    if not strategy:
        raise ValueError(f"No strategy registered for method: {method}")

    return strategy


def register_weighting_strategy(method: WeightingMethod, strategy: WeightingStrategy):
    """
    Register a custom weighting strategy.

    Allows extending the framework with new weighting methods.

    Args:
        method: Weighting method enum
        strategy: Strategy implementation
    """
    _STRATEGIES[method] = strategy
