"""
Risk metric calculation strategies for equity analysis.

Provides reusable patterns for calculating risk metrics such as:
- Beta (systematic risk vs. market)
- Volatility (standard deviation of returns)
- Sharpe Ratio (risk-adjusted returns)
- Value at Risk (VaR)
- Maximum Drawdown
- Alpha (excess return vs. market)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class RiskMetricStrategy(ABC):
    """Base class for risk metric calculations."""

    @abstractmethod
    def generate_sql(self, adapter, **kwargs) -> str:
        """
        Generate SQL to calculate this risk metric.

        Args:
            adapter: BackendAdapter (DuckDB or Spark)
            **kwargs: Parameters specific to the metric

        Returns:
            SQL string
        """
        pass


class BetaStrategy(RiskMetricStrategy):
    """
    Beta calculation (systematic risk vs. market).

    Beta = Covariance(asset_returns, market_returns) / Variance(market_returns)

    Beta interpretation:
    - Beta = 1: Moves with market
    - Beta > 1: More volatile than market
    - Beta < 1: Less volatile than market
    - Beta < 0: Moves opposite to market
    """

    def __init__(self, period: int = 252):
        """
        Args:
            period: Number of periods for calculation (default: 252 trading days = 1 year)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        asset_table: str,
        market_table: str,
        asset_price_column: str = 'close',
        market_price_column: str = 'close',
        asset_id_column: str = 'ticker',
        date_column: str = 'trade_date',
        **kwargs
    ) -> str:
        """
        Generate SQL for Beta calculation.

        Requires both asset and market (e.g., SPY) price data.
        """
        asset_ref = adapter.get_table_reference(asset_table)
        market_ref = adapter.get_table_reference(market_table)

        return f"""
        WITH asset_returns AS (
            SELECT
                {asset_id_column},
                {date_column},
                ({asset_price_column} - LAG({asset_price_column}) OVER (
                    PARTITION BY {asset_id_column}
                    ORDER BY {date_column}
                )) / LAG({asset_price_column}) OVER (
                    PARTITION BY {asset_id_column}
                    ORDER BY {date_column}
                ) as asset_return
            FROM {asset_ref}
            WHERE {asset_price_column} IS NOT NULL
        ),
        market_returns AS (
            SELECT
                {date_column},
                ({market_price_column} - LAG({market_price_column}) OVER (ORDER BY {date_column}))
                / LAG({market_price_column}) OVER (ORDER BY {date_column}) as market_return
            FROM {market_ref}
            WHERE {market_price_column} IS NOT NULL
        ),
        joined_returns AS (
            SELECT
                a.{asset_id_column},
                a.{date_column},
                a.asset_return,
                m.market_return
            FROM asset_returns a
            INNER JOIN market_returns m ON a.{date_column} = m.{date_column}
            WHERE a.asset_return IS NOT NULL AND m.market_return IS NOT NULL
        ),
        rolling_beta AS (
            SELECT
                {asset_id_column},
                {date_column},
                -- Covariance / Variance formula for beta
                (
                    AVG(asset_return * market_return) OVER w
                    - AVG(asset_return) OVER w * AVG(market_return) OVER w
                ) / (
                    AVG(market_return * market_return) OVER w
                    - AVG(market_return) OVER w * AVG(market_return) OVER w
                ) as beta
            FROM joined_returns
            WINDOW w AS (
                PARTITION BY {asset_id_column}
                ORDER BY {date_column}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            )
        )
        SELECT
            {asset_id_column},
            {date_column},
            beta
        FROM rolling_beta
        WHERE beta IS NOT NULL
        ORDER BY {asset_id_column}, {date_column}
        """


class VolatilityStrategy(RiskMetricStrategy):
    """
    Volatility calculation (annualized standard deviation of returns).

    Volatility = STDDEV(returns) * SQRT(periods_per_year)
    """

    def __init__(self, period: int = 20, annualize: bool = True, periods_per_year: int = 252):
        """
        Args:
            period: Number of periods for rolling window (default: 20)
            annualize: Whether to annualize volatility (default: True)
            periods_per_year: Trading days per year for annualization (default: 252)
        """
        self.period = period
        self.annualize = annualize
        self.periods_per_year = periods_per_year

    def generate_sql(
        self,
        adapter,
        table_name: str,
        price_column: str = 'close',
        partition_by: str = 'ticker',
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for rolling volatility."""
        table_ref = adapter.get_table_reference(table_name)

        # Annualization factor
        annualization = f"* SQRT({self.periods_per_year})" if self.annualize else ""

        return f"""
        WITH returns AS (
            SELECT
                {partition_by},
                {order_by},
                ({price_column} - LAG({price_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                )) / LAG({price_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                ) as return
            FROM {table_ref}
            WHERE {price_column} IS NOT NULL
        )
        SELECT
            {partition_by},
            {order_by},
            STDDEV(return) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) {annualization} as volatility_{self.period}d
        FROM returns
        WHERE return IS NOT NULL
        ORDER BY {partition_by}, {order_by}
        """


class SharpeRatioStrategy(RiskMetricStrategy):
    """
    Sharpe Ratio calculation (risk-adjusted return).

    Sharpe Ratio = (Portfolio Return - Risk Free Rate) / Portfolio Volatility

    Higher Sharpe ratio = better risk-adjusted performance
    """

    def __init__(
        self,
        period: int = 252,
        risk_free_rate: float = 0.02,  # 2% annual
        annualize: bool = True,
        periods_per_year: int = 252
    ):
        """
        Args:
            period: Number of periods for calculation (default: 252 = 1 year)
            risk_free_rate: Annual risk-free rate (default: 0.02 = 2%)
            annualize: Whether to annualize metrics (default: True)
            periods_per_year: Trading days per year (default: 252)
        """
        self.period = period
        self.risk_free_rate = risk_free_rate
        self.annualize = annualize
        self.periods_per_year = periods_per_year

    def generate_sql(
        self,
        adapter,
        table_name: str,
        price_column: str = 'close',
        partition_by: str = 'ticker',
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for Sharpe Ratio."""
        table_ref = adapter.get_table_reference(table_name)

        # Daily risk-free rate
        daily_rf = self.risk_free_rate / self.periods_per_year if self.annualize else self.risk_free_rate

        # Annualization factors
        return_factor = f"* {self.periods_per_year}" if self.annualize else ""
        vol_factor = f"* SQRT({self.periods_per_year})" if self.annualize else ""

        return f"""
        WITH returns AS (
            SELECT
                {partition_by},
                {order_by},
                ({price_column} - LAG({price_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                )) / LAG({price_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                ) as return
            FROM {table_ref}
            WHERE {price_column} IS NOT NULL
        ),
        metrics AS (
            SELECT
                {partition_by},
                {order_by},
                AVG(return) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) {return_factor} as avg_return,
                STDDEV(return) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) {vol_factor} as volatility
            FROM returns
            WHERE return IS NOT NULL
        )
        SELECT
            {partition_by},
            {order_by},
            CASE
                WHEN volatility > 0 THEN (avg_return - {self.risk_free_rate}) / volatility
                ELSE NULL
            END as sharpe_ratio
        FROM metrics
        ORDER BY {partition_by}, {order_by}
        """


class MaxDrawdownStrategy(RiskMetricStrategy):
    """
    Maximum Drawdown calculation (largest peak-to-trough decline).

    Max Drawdown = (Trough Value - Peak Value) / Peak Value

    Measures worst historical loss from peak.
    """

    def __init__(self, period: Optional[int] = None):
        """
        Args:
            period: Optional rolling window period (None = all-time)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        price_column: str = 'close',
        partition_by: str = 'ticker',
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for Maximum Drawdown."""
        table_ref = adapter.get_table_reference(table_name)

        # Window spec for rolling max
        if self.period:
            window_spec = f"""
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            """
        else:
            window_spec = f"""
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            """

        return f"""
        WITH running_max AS (
            SELECT
                {partition_by},
                {order_by},
                {price_column},
                MAX({price_column}) OVER (
                    {window_spec}
                ) as peak_price
            FROM {table_ref}
            WHERE {price_column} IS NOT NULL
        )
        SELECT
            {partition_by},
            {order_by},
            {price_column},
            peak_price,
            ({price_column} - peak_price) / peak_price as drawdown,
            MIN(({price_column} - peak_price) / peak_price) OVER (
                {window_spec}
            ) as max_drawdown
        FROM running_max
        ORDER BY {partition_by}, {order_by}
        """


class AlphaStrategy(RiskMetricStrategy):
    """
    Alpha calculation (excess return vs. market).

    Alpha = Asset Return - (Risk Free Rate + Beta * (Market Return - Risk Free Rate))

    Positive alpha = outperformance vs. market
    """

    def __init__(self, period: int = 252, risk_free_rate: float = 0.02):
        """
        Args:
            period: Number of periods for calculation (default: 252 = 1 year)
            risk_free_rate: Annual risk-free rate (default: 0.02 = 2%)
        """
        self.period = period
        self.risk_free_rate = risk_free_rate

    def generate_sql(
        self,
        adapter,
        asset_table: str,
        market_table: str,
        asset_price_column: str = 'close',
        market_price_column: str = 'close',
        asset_id_column: str = 'ticker',
        date_column: str = 'trade_date',
        **kwargs
    ) -> str:
        """
        Generate SQL for Alpha calculation.

        Requires both asset and market price data, plus beta calculation.
        """
        asset_ref = adapter.get_table_reference(asset_table)
        market_ref = adapter.get_table_reference(market_table)

        # Daily risk-free rate
        daily_rf = self.risk_free_rate / 252

        return f"""
        WITH asset_returns AS (
            SELECT
                {asset_id_column},
                {date_column},
                ({asset_price_column} - LAG({asset_price_column}) OVER (
                    PARTITION BY {asset_id_column}
                    ORDER BY {date_column}
                )) / LAG({asset_price_column}) OVER (
                    PARTITION BY {asset_id_column}
                    ORDER BY {date_column}
                ) as asset_return
            FROM {asset_ref}
            WHERE {asset_price_column} IS NOT NULL
        ),
        market_returns AS (
            SELECT
                {date_column},
                ({market_price_column} - LAG({market_price_column}) OVER (ORDER BY {date_column}))
                / LAG({market_price_column}) OVER (ORDER BY {date_column}) as market_return
            FROM {market_ref}
            WHERE {market_price_column} IS NOT NULL
        ),
        joined_returns AS (
            SELECT
                a.{asset_id_column},
                a.{date_column},
                a.asset_return,
                m.market_return
            FROM asset_returns a
            INNER JOIN market_returns m ON a.{date_column} = m.{date_column}
            WHERE a.asset_return IS NOT NULL AND m.market_return IS NOT NULL
        ),
        beta_calc AS (
            SELECT
                {asset_id_column},
                {date_column},
                asset_return,
                market_return,
                (
                    AVG(asset_return * market_return) OVER w
                    - AVG(asset_return) OVER w * AVG(market_return) OVER w
                ) / (
                    AVG(market_return * market_return) OVER w
                    - AVG(market_return) OVER w * AVG(market_return) OVER w
                ) as beta
            FROM joined_returns
            WINDOW w AS (
                PARTITION BY {asset_id_column}
                ORDER BY {date_column}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            )
        )
        SELECT
            {asset_id_column},
            {date_column},
            asset_return,
            market_return,
            beta,
            -- Alpha = Asset Return - (RF + Beta * (Market Return - RF))
            asset_return - ({daily_rf} + beta * (market_return - {daily_rf})) as alpha
        FROM beta_calc
        WHERE beta IS NOT NULL
        ORDER BY {asset_id_column}, {date_column}
        """


# Registry for risk metrics
_RISK_METRIC_REGISTRY = {
    'beta': BetaStrategy,
    'volatility': VolatilityStrategy,
    'sharpe_ratio': SharpeRatioStrategy,
    'max_drawdown': MaxDrawdownStrategy,
    'alpha': AlphaStrategy,
}


def get_risk_metric_strategy(metric_type: str, **kwargs) -> RiskMetricStrategy:
    """
    Factory function to get risk metric strategy.

    Args:
        metric_type: Type of risk metric ('beta', 'volatility', 'sharpe_ratio', etc.)
        **kwargs: Parameters for the metric

    Returns:
        RiskMetricStrategy instance

    Example:
        # Get beta strategy (252-day rolling)
        strategy = get_risk_metric_strategy('beta', period=252)

        # Get annualized volatility
        strategy = get_risk_metric_strategy('volatility', period=20, annualize=True)

        # Get Sharpe ratio
        strategy = get_risk_metric_strategy('sharpe_ratio', risk_free_rate=0.03)
    """
    strategy_class = _RISK_METRIC_REGISTRY.get(metric_type.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown risk metric: {metric_type}. "
            f"Available: {list(_RISK_METRIC_REGISTRY.keys())}"
        )

    return strategy_class(**kwargs)


__all__ = [
    'RiskMetricStrategy',
    'BetaStrategy',
    'VolatilityStrategy',
    'SharpeRatioStrategy',
    'MaxDrawdownStrategy',
    'AlphaStrategy',
    'get_risk_metric_strategy',
]
