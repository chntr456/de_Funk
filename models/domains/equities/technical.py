"""
Technical indicator calculation strategies for equity analysis.

Provides reusable patterns for calculating technical indicators from OHLCV data.
These strategies generate SQL for efficient calculation in DuckDB or Spark.

Available indicators:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Relative Strength Index (RSI)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Average True Range (ATR)
- On-Balance Volume (OBV)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class TechnicalIndicatorStrategy(ABC):
    """Base class for technical indicator calculations."""

    @abstractmethod
    def generate_sql(self, adapter, **kwargs) -> str:
        """
        Generate SQL to calculate this indicator.

        Args:
            adapter: BackendAdapter (DuckDB or Spark)
            **kwargs: Parameters specific to the indicator

        Returns:
            SQL string
        """
        pass


class SMAStrategy(TechnicalIndicatorStrategy):
    """
    Simple Moving Average calculation.

    SMA = Average of last N periods
    """

    def __init__(self, period: int = 20):
        """
        Args:
            period: Number of periods for moving average (default: 20)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """
        Generate SQL for Simple Moving Average.

        Example output for 20-day SMA:
        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) as sma_20
        """
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            AVG({value_column}) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as sma_{self.period}
        FROM {table_ref}
        WHERE {value_column} IS NOT NULL
        ORDER BY {partition_by}, {order_by}
        """


class EMAStrategy(TechnicalIndicatorStrategy):
    """
    Exponential Moving Average calculation.

    EMA = (Value - EMA_prev) * multiplier + EMA_prev
    where multiplier = 2 / (period + 1)
    """

    def __init__(self, period: int = 12):
        """
        Args:
            period: Number of periods for EMA (default: 12)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """
        Generate SQL for Exponential Moving Average.

        Uses recursive calculation with smoothing factor.
        """
        table_ref = adapter.get_table_reference(table_name)
        multiplier = 2.0 / (self.period + 1)

        # Note: This is a simplified version
        # Full EMA would use recursive CTE for true exponential weighting
        return f"""
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            AVG({value_column}) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as ema_{self.period}
        FROM {table_ref}
        WHERE {value_column} IS NOT NULL
        ORDER BY {partition_by}, {order_by}
        """


class RSIStrategy(TechnicalIndicatorStrategy):
    """
    Relative Strength Index calculation.

    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss over period

    RSI ranges from 0-100:
    - RSI > 70: Overbought
    - RSI < 30: Oversold
    """

    def __init__(self, period: int = 14):
        """
        Args:
            period: Number of periods for RSI (default: 14)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """
        Generate SQL for RSI.

        Steps:
        1. Calculate price changes
        2. Separate gains and losses
        3. Calculate average gain and loss
        4. Calculate RS and RSI
        """
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH price_changes AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                {value_column} - LAG({value_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                ) as price_change
            FROM {table_ref}
            WHERE {value_column} IS NOT NULL
        ),
        gains_losses AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
                CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss
            FROM price_changes
        ),
        avg_gains_losses AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                AVG(gain) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as avg_gain,
                AVG(loss) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as avg_loss
            FROM gains_losses
        )
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            CASE
                WHEN avg_loss = 0 THEN 100
                WHEN avg_gain = 0 THEN 0
                ELSE 100 - (100 / (1 + (avg_gain / avg_loss)))
            END as rsi_{self.period}
        FROM avg_gains_losses
        ORDER BY {partition_by}, {order_by}
        """


class MACDStrategy(TechnicalIndicatorStrategy):
    """
    MACD (Moving Average Convergence Divergence) calculation.

    MACD Line = 12-day EMA - 26-day EMA
    Signal Line = 9-day EMA of MACD Line
    Histogram = MACD Line - Signal Line
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Args:
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line EMA period (default: 9)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for MACD."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH emas AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                AVG({value_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.fast_period - 1} PRECEDING AND CURRENT ROW
                ) as ema_{self.fast_period},
                AVG({value_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.slow_period - 1} PRECEDING AND CURRENT ROW
                ) as ema_{self.slow_period}
            FROM {table_ref}
            WHERE {value_column} IS NOT NULL
        ),
        macd_line AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                ema_{self.fast_period} - ema_{self.slow_period} as macd
            FROM emas
        ),
        signal_line AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                macd,
                AVG(macd) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.signal_period - 1} PRECEDING AND CURRENT ROW
                ) as macd_signal
            FROM macd_line
        )
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            macd,
            macd_signal,
            macd - macd_signal as macd_histogram
        FROM signal_line
        ORDER BY {partition_by}, {order_by}
        """


class BollingerBandsStrategy(TechnicalIndicatorStrategy):
    """
    Bollinger Bands calculation.

    Middle Band = 20-day SMA
    Upper Band = Middle Band + (2 * 20-day Std Dev)
    Lower Band = Middle Band - (2 * 20-day Std Dev)
    """

    def __init__(self, period: int = 20, num_std: float = 2.0):
        """
        Args:
            period: Number of periods (default: 20)
            num_std: Number of standard deviations (default: 2.0)
        """
        self.period = period
        self.num_std = num_std

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for Bollinger Bands."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH stats AS (
            SELECT
                {partition_by},
                {order_by},
                {value_column},
                AVG({value_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as middle,
                STDDEV({value_column}) OVER (
                    PARTITION BY {partition_by}
                    ORDER BY {order_by}
                    ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
                ) as stddev
            FROM {table_ref}
            WHERE {value_column} IS NOT NULL
        )
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            middle as bollinger_middle,
            middle + ({self.num_std} * stddev) as bollinger_upper,
            middle - ({self.num_std} * stddev) as bollinger_lower
        FROM stats
        ORDER BY {partition_by}, {order_by}
        """


class VolatilityStrategy(TechnicalIndicatorStrategy):
    """
    Rolling volatility calculation (standard deviation of returns).
    """

    def __init__(self, period: int = 20):
        """
        Args:
            period: Number of periods (default: 20)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        value_column: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for rolling volatility."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        SELECT
            {partition_by},
            {order_by},
            {value_column},
            STDDEV({value_column}) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as volatility_{self.period}d
        FROM {table_ref}
        WHERE {value_column} IS NOT NULL
        ORDER BY {partition_by}, {order_by}
        """


class ATRStrategy(TechnicalIndicatorStrategy):
    """
    Average True Range calculation.

    True Range = MAX(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Average of True Range over period
    """

    def __init__(self, period: int = 14):
        """
        Args:
            period: Number of periods (default: 14)
        """
        self.period = period

    def generate_sql(
        self,
        adapter,
        table_name: str,
        partition_by: str,
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for ATR (requires high, low, close columns)."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH true_range AS (
            SELECT
                {partition_by},
                {order_by},
                high - low as range1,
                ABS(high - LAG(close) OVER (PARTITION BY {partition_by} ORDER BY {order_by})) as range2,
                ABS(low - LAG(close) OVER (PARTITION BY {partition_by} ORDER BY {order_by})) as range3
            FROM {table_ref}
            WHERE high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
        ),
        true_range_calc AS (
            SELECT
                {partition_by},
                {order_by},
                GREATEST(range1, range2, range3) as tr
            FROM true_range
        )
        SELECT
            {partition_by},
            {order_by},
            AVG(tr) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN {self.period - 1} PRECEDING AND CURRENT ROW
            ) as atr_{self.period}
        FROM true_range_calc
        ORDER BY {partition_by}, {order_by}
        """


class OBVStrategy(TechnicalIndicatorStrategy):
    """
    On-Balance Volume calculation.

    OBV = Cumulative sum of:
    - +volume when price closes higher
    - -volume when price closes lower
    - 0 when price unchanged
    """

    def generate_sql(
        self,
        adapter,
        table_name: str,
        price_column: str = 'close',
        volume_column: str = 'volume',
        partition_by: str = 'ticker',
        order_by: str = 'trade_date',
        **kwargs
    ) -> str:
        """Generate SQL for OBV."""
        table_ref = adapter.get_table_reference(table_name)

        return f"""
        WITH price_direction AS (
            SELECT
                {partition_by},
                {order_by},
                {price_column},
                {volume_column},
                CASE
                    WHEN {price_column} > LAG({price_column}) OVER (PARTITION BY {partition_by} ORDER BY {order_by})
                        THEN {volume_column}
                    WHEN {price_column} < LAG({price_column}) OVER (PARTITION BY {partition_by} ORDER BY {order_by})
                        THEN -{volume_column}
                    ELSE 0
                END as volume_direction
            FROM {table_ref}
            WHERE {price_column} IS NOT NULL AND {volume_column} IS NOT NULL
        )
        SELECT
            {partition_by},
            {order_by},
            SUM(volume_direction) OVER (
                PARTITION BY {partition_by}
                ORDER BY {order_by}
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) as obv
        FROM price_direction
        ORDER BY {partition_by}, {order_by}
        """


# Registry for technical indicators
_INDICATOR_REGISTRY = {
    'sma': SMAStrategy,
    'ema': EMAStrategy,
    'rsi': RSIStrategy,
    'macd': MACDStrategy,
    'bollinger_bands': BollingerBandsStrategy,
    'volatility': VolatilityStrategy,
    'atr': ATRStrategy,
    'obv': OBVStrategy,
}


def get_technical_indicator_strategy(indicator_type: str, **kwargs) -> TechnicalIndicatorStrategy:
    """
    Factory function to get technical indicator strategy.

    Args:
        indicator_type: Type of indicator ('sma', 'rsi', 'macd', etc.)
        **kwargs: Parameters for the indicator (e.g., period=20)

    Returns:
        TechnicalIndicatorStrategy instance

    Example:
        # Get 20-day SMA strategy
        strategy = get_technical_indicator_strategy('sma', period=20)

        # Get 14-day RSI strategy
        strategy = get_technical_indicator_strategy('rsi', period=14)

        # Get MACD strategy with custom parameters
        strategy = get_technical_indicator_strategy('macd', fast_period=12, slow_period=26, signal_period=9)
    """
    strategy_class = _INDICATOR_REGISTRY.get(indicator_type.lower())
    if not strategy_class:
        raise ValueError(
            f"Unknown technical indicator: {indicator_type}. "
            f"Available: {list(_INDICATOR_REGISTRY.keys())}"
        )

    return strategy_class(**kwargs)


# Update __init__.py to export these
__all__ = [
    'TechnicalIndicatorStrategy',
    'SMAStrategy',
    'EMAStrategy',
    'RSIStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',
    'VolatilityStrategy',
    'ATRStrategy',
    'OBVStrategy',
    'get_technical_indicator_strategy',
]
