"""
ETF-specific weighting strategies.

Provides holdings-based weighting for calculating ETF metrics from underlying holdings.
"""

from typing import List, Optional
from models.implemented.equity.domains.weighting import WeightingStrategy, WeightingMethod, register_weighting_strategy


class HoldingsWeightStrategy(WeightingStrategy):
    """
    Holdings-based weighting for ETFs.

    Weights by actual ETF holdings percentages.
    Requires an explicit weight column from holdings table.

    Use cases:
    - Calculate ETF return from underlying stock returns
    - Aggregate metrics across ETF holdings
    - Sector exposure analysis
    """

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
        Generate SQL for holdings-based weighting.

        Joins holdings table with price/metric table and weights by holdings percentage.

        Args:
            adapter: Backend adapter
            table_name: Source table (e.g., 'company.fact_prices')
            value_column: Column to aggregate (e.g., 'close', 'volume')
            group_by: Columns to group by (e.g., ['trade_date', 'etf_ticker'])
            weight_column: Holdings weight column (required!)
            filters: Optional additional filters

        Returns:
            SQL query string

        Raises:
            ValueError: If weight_column not provided
        """
        if not weight_column:
            raise ValueError(
                "Holdings weighting requires explicit weight_column. "
                "Specify weight_column in measure config (e.g., 'dim_etf_holdings.weight_percent')"
            )

        # Parse weight column (table.column)
        if '.' in weight_column:
            holdings_table, weight_col = weight_column.rsplit('.', 1)
        else:
            raise ValueError(
                f"weight_column must be 'table.column' format, got: {weight_column}"
            )

        # Get table references
        holdings_ref = adapter.get_table_reference(holdings_table)
        source_ref = adapter.get_table_reference(table_name)

        # Build group by clause
        group_cols = ', '.join(group_by)

        # Build WHERE clause
        where_clauses = [
            f"s.{value_column} IS NOT NULL",
            f"h.{weight_col} IS NOT NULL",
            f"h.{weight_col} > 0"
        ]
        if filters:
            where_clauses.extend(filters)
        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Holdings-based weighted aggregation
        # weight_percent is stored as percentage (0-100), convert to decimal (0-1)
        weighted_agg = adapter.get_null_safe_divide(
            f"SUM(s.{value_column} * (h.{weight_col} / 100.0))",
            "SUM(h.{weight_col} / 100.0)"
        )

        return f"""
SELECT
    h.{group_cols},
    {weighted_agg} as weighted_value,
    COUNT(DISTINCT h.holding_ticker) as holding_count,
    SUM(h.{weight_col}) as total_weight_pct
FROM {holdings_ref} h
JOIN {source_ref} s
    ON h.holding_ticker = s.ticker
    AND h.as_of_date = s.trade_date
{where_clause}
GROUP BY h.{group_cols}
ORDER BY h.{group_cols}
        """.strip()


# Register ETF holdings weighting method
# Extends the WeightingMethod enum dynamically
ETF_HOLDINGS_METHOD = WeightingMethod.__class__('ETF_HOLDINGS', 'etf_holdings')
register_weighting_strategy(ETF_HOLDINGS_METHOD, HoldingsWeightStrategy())
