"""
Complex measures for stocks model - Spark-first implementation.

These functions are referenced from stocks/measures.yaml via python_measures.
All calculations use Spark DataFrames and window functions.
Only convert to pandas at the final step if needed for UI.

Version: 2.3 - Spark-first refactor
"""

from typing import Dict, Any, Optional, List
import logging

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from de_funk.models.measures import DomainMeasures

logger = logging.getLogger(__name__)


class StocksMeasures(DomainMeasures):
    """
    Complex measure calculations for stocks using Spark.

    Inherits from DomainMeasures which provides:
    - get_table(): Returns Spark DataFrame
    - ticker_window(), rolling_window(): Window helpers
    - add_returns(), add_rolling_mean(), add_rolling_std(): Calculation helpers
    - to_pandas(): Final conversion (use sparingly)
    - log_start/log_result: Logging helpers
    """

    def calculate_sharpe_ratio(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        risk_free_rate: float = 0.045,
        window_days: int = 252,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate Sharpe ratio for stocks using Spark window functions.

        Args:
            ticker: Specific ticker (optional, calculates for all if None)
            filters: Additional filters to apply
            risk_free_rate: Annual risk-free rate (e.g., 0.045 = 4.5%)
            window_days: Rolling window for calculation
            as_pandas: Convert result to pandas (default: False)

        Returns:
            Spark DataFrame with columns: [ticker, trade_date, sharpe_ratio]
        """
        self.log_start("sharpe_ratio", ticker=ticker, window=window_days, rf=risk_free_rate)

        # Get price data as Spark DataFrame
        df = self.get_table('fact_stock_prices', ticker=ticker, filters=filters)

        # Add returns
        df = self.add_returns(df, price_col='close')

        # Create rolling window
        window = self.rolling_window(window_size=window_days)

        # Calculate rolling mean and std of returns
        daily_rf = (1 + risk_free_rate) ** (1/252) - 1

        df = (df
            .withColumn('rolling_mean', F.avg('returns').over(window))
            .withColumn('rolling_std', F.stddev('returns').over(window))
            .withColumn(
                'sharpe_ratio',
                F.when(
                    (F.col('rolling_std').isNotNull()) & (F.col('rolling_std') != 0),
                    ((F.col('rolling_mean') - daily_rf) / F.col('rolling_std')) * F.sqrt(F.lit(252))
                ).otherwise(None)
            )
            .select('ticker', 'trade_date', 'sharpe_ratio')
            .filter(F.col('sharpe_ratio').isNotNull())
        )

        self.log_result("sharpe_ratio", df)

        if as_pandas:
            return self.to_pandas(df)
        return df

    def calculate_drawdown(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        window_days: int = 252,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate maximum drawdown from peak using Spark.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            window_days: Rolling window for peak calculation
            as_pandas: Convert result to pandas

        Returns:
            Spark DataFrame with columns: [ticker, trade_date, drawdown, peak_price]
        """
        self.log_start("drawdown", ticker=ticker, window=window_days)

        df = self.get_table('fact_stock_prices', ticker=ticker, filters=filters)

        # Add rolling max (peak price)
        df = self.add_rolling_max(df, 'close', window_days, result_col='peak_price')

        # Calculate drawdown as % from peak
        df = df.withColumn(
            'drawdown',
            ((F.col('close') - F.col('peak_price')) / F.col('peak_price')) * 100
        ).select('ticker', 'trade_date', 'drawdown', 'peak_price')

        self.log_result("drawdown", df)

        if as_pandas:
            return self.to_pandas(df)
        return df

    def calculate_rolling_beta(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        market_ticker: str = 'SPY',
        window_days: int = 252,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate rolling beta vs. market index using Spark.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            market_ticker: Market index ticker (default: SPY)
            window_days: Rolling window size
            as_pandas: Convert result to pandas

        Returns:
            Spark DataFrame with columns: [ticker, trade_date, beta]
        """
        self.log_start("rolling_beta", ticker=ticker, market=market_ticker, window=window_days)

        # Get all prices
        df = self.get_table('fact_stock_prices', filters=filters)

        # Add returns for all tickers
        df = self.add_returns(df, price_col='close')

        # Separate market returns
        market_df = (df
            .filter(F.col('ticker') == market_ticker)
            .select(
                F.col('trade_date'),
                F.col('returns').alias('market_returns')
            )
        )

        # Get stock returns (excluding market ticker or specific ticker)
        if ticker:
            stock_df = df.filter(F.col('ticker') == ticker)
        else:
            stock_df = df.filter(F.col('ticker') != market_ticker)

        stock_df = stock_df.select('ticker', 'trade_date', F.col('returns').alias('stock_returns'))

        # Join market returns to stock returns
        merged = stock_df.join(market_df, on='trade_date', how='inner')

        # Calculate rolling covariance and variance using window
        window = self.rolling_window(window_size=window_days)

        # For beta = cov(stock, market) / var(market)
        # We need to calculate these in a rolling window
        merged = (merged
            .withColumn('product', F.col('stock_returns') * F.col('market_returns'))
            .withColumn('market_sq', F.col('market_returns') * F.col('market_returns'))
            .withColumn('rolling_product_mean', F.avg('product').over(window))
            .withColumn('rolling_stock_mean', F.avg('stock_returns').over(window))
            .withColumn('rolling_market_mean', F.avg('market_returns').over(window))
            .withColumn('rolling_market_sq_mean', F.avg('market_sq').over(window))
            # Covariance = E[XY] - E[X]*E[Y]
            .withColumn(
                'covariance',
                F.col('rolling_product_mean') - (F.col('rolling_stock_mean') * F.col('rolling_market_mean'))
            )
            # Variance = E[X^2] - E[X]^2
            .withColumn(
                'market_variance',
                F.col('rolling_market_sq_mean') - (F.col('rolling_market_mean') * F.col('rolling_market_mean'))
            )
            # Beta = Cov / Var
            .withColumn(
                'beta',
                F.when(F.col('market_variance') > 0, F.col('covariance') / F.col('market_variance'))
                .otherwise(None)
            )
            .select('ticker', 'trade_date', 'beta')
            .filter(F.col('beta').isNotNull())
        )

        self.log_result("rolling_beta", merged)

        if as_pandas:
            return self.to_pandas(merged)
        return merged

    def calculate_momentum_score(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        weights: Optional[Dict[str, float]] = None,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate composite momentum score from multiple factors using Spark.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            weights: Dict of factor weights (e.g., {'rsi': 0.3, 'macd': 0.3, ...})
            as_pandas: Convert result to pandas

        Returns:
            Spark DataFrame with momentum score and components
        """
        if weights is None:
            weights = {'rsi': 0.3, 'macd': 0.3, 'price_trend': 0.4}

        self.log_start("momentum_score", ticker=ticker, weights=weights)

        # Get technical data (includes RSI, MACD, etc.)
        df = self.get_table('fact_stock_prices', ticker=ticker, filters=filters)

        # RSI normalization (already 0-100, normalize to 0-1)
        df = df.withColumn(
            'rsi_norm',
            F.when(F.col('rsi_14').isNotNull(), F.col('rsi_14') / 100)
            .otherwise(0.5)
        )

        # Price trend: % above/below 50-day SMA, normalized to [0, 1]
        df = df.withColumn(
            'price_trend_raw',
            F.when(
                (F.col('sma_50').isNotNull()) & (F.col('sma_50') != 0),
                (F.col('close') - F.col('sma_50')) / F.col('sma_50')
            ).otherwise(0)
        ).withColumn(
            'price_trend_norm',
            # Clip to [-1, 1] then scale to [0, 1]
            (F.greatest(F.least(F.col('price_trend_raw'), F.lit(1)), F.lit(-1)) + 1) / 2
        )

        # MACD normalization (if available)
        # MACD as % of price, then normalize
        df = df.withColumn(
            'macd_pct',
            F.when(
                (F.col('close').isNotNull()) & (F.col('close') != 0),
                F.coalesce(F.col('macd'), F.lit(0)) / F.col('close')
            ).otherwise(0)
        )

        # Normalize MACD within each ticker using window
        ticker_window = Window.partitionBy('ticker')
        df = df.withColumn(
            'macd_min', F.min('macd_pct').over(ticker_window)
        ).withColumn(
            'macd_max', F.max('macd_pct').over(ticker_window)
        ).withColumn(
            'macd_norm',
            F.when(
                F.col('macd_max') != F.col('macd_min'),
                (F.col('macd_pct') - F.col('macd_min')) / (F.col('macd_max') - F.col('macd_min'))
            ).otherwise(0.5)
        )

        # Calculate weighted score
        rsi_weight = weights.get('rsi', 0.3)
        macd_weight = weights.get('macd', 0.3)
        trend_weight = weights.get('price_trend', 0.4)

        df = df.withColumn(
            'momentum_score',
            F.greatest(
                F.least(
                    (F.col('rsi_norm') * rsi_weight) +
                    (F.col('macd_norm') * macd_weight) +
                    (F.col('price_trend_norm') * trend_weight),
                    F.lit(1.0)
                ),
                F.lit(0.0)
            )
        ).select(
            'ticker', 'trade_date', 'momentum_score',
            'rsi_norm', 'macd_norm', 'price_trend_norm'
        )

        self.log_result("momentum_score", df)

        if as_pandas:
            return self.to_pandas(df)
        return df

    def calculate_volatility_regime(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        short_window: int = 20,
        long_window: int = 60,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Classify volatility regime (low/normal/high) using Spark.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            short_window: Short-term volatility window
            long_window: Long-term volatility window
            as_pandas: Convert result to pandas

        Returns:
            Spark DataFrame with volatility metrics and regime classification
        """
        self.log_start("volatility_regime", ticker=ticker, short=short_window, long=long_window)

        df = self.get_table('fact_stock_prices', ticker=ticker, filters=filters)

        # Add returns
        df = self.add_returns(df, price_col='close')

        # Calculate short and long term volatility
        df = self.add_rolling_std(df, 'returns', short_window, result_col='vol_short')
        df = self.add_rolling_std(df, 'returns', long_window, result_col='vol_long')

        # Annualize
        df = (df
            .withColumn('vol_short_ann', F.col('vol_short') * F.sqrt(F.lit(252)))
            .withColumn('vol_long_ann', F.col('vol_long') * F.sqrt(F.lit(252)))
        )

        # Calculate volatility ratio
        df = df.withColumn(
            'vol_ratio',
            F.when(F.col('vol_long_ann') > 0, F.col('vol_short_ann') / F.col('vol_long_ann'))
            .otherwise(1.0)
        )

        # Classify regime
        df = df.withColumn(
            'regime',
            F.when(F.col('vol_ratio') < 0.8, 'LOW')
            .when(F.col('vol_ratio') > 1.2, 'HIGH')
            .otherwise('NORMAL')
        ).select(
            'ticker', 'trade_date',
            'vol_short_ann', 'vol_long_ann', 'vol_ratio', 'regime'
        ).filter(
            F.col('vol_long_ann').isNotNull()
        )

        self.log_result("volatility_regime", df)

        if as_pandas:
            return self.to_pandas(df)
        return df

    def calculate_relative_strength(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        benchmark_ticker: str = 'SPY',
        window_days: int = 20,
        as_pandas: bool = False,
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate relative strength vs benchmark using Spark.

        Args:
            ticker: Specific ticker
            filters: Additional filters
            benchmark_ticker: Benchmark ticker (default: SPY)
            window_days: Rolling window for comparison
            as_pandas: Convert result to pandas

        Returns:
            Spark DataFrame with relative strength metrics
        """
        self.log_start("relative_strength", ticker=ticker, benchmark=benchmark_ticker, window=window_days)

        df = self.get_table('fact_stock_prices', filters=filters)

        # Add returns
        df = self.add_returns(df, price_col='close')

        # Separate benchmark
        benchmark_df = (df
            .filter(F.col('ticker') == benchmark_ticker)
            .select(
                F.col('trade_date'),
                F.col('returns').alias('benchmark_returns')
            )
        )

        # Get stock returns
        if ticker:
            stock_df = df.filter(F.col('ticker') == ticker)
        else:
            stock_df = df.filter(F.col('ticker') != benchmark_ticker)

        stock_df = stock_df.select('ticker', 'trade_date', F.col('returns').alias('stock_returns'))

        # Join
        merged = stock_df.join(benchmark_df, on='trade_date', how='inner')

        # Calculate rolling cumulative returns
        window = self.rolling_window(window_size=window_days)

        merged = (merged
            .withColumn('cum_stock', F.sum('stock_returns').over(window))
            .withColumn('cum_benchmark', F.sum('benchmark_returns').over(window))
            .withColumn(
                'relative_strength',
                F.when(
                    F.col('cum_benchmark').isNotNull(),
                    F.col('cum_stock') - F.col('cum_benchmark')
                ).otherwise(None)
            )
            .withColumn(
                'outperforming',
                F.when(F.col('relative_strength') > 0, True).otherwise(False)
            )
            .select('ticker', 'trade_date', 'relative_strength', 'outperforming')
            .filter(F.col('relative_strength').isNotNull())
        )

        self.log_result("relative_strength", merged)

        if as_pandas:
            return self.to_pandas(merged)
        return merged
