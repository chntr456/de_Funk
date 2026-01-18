"""
Base class for domain-specific measure implementations.

Domain measures are complex calculations that can't be expressed in simple YAML.
They're referenced from the model's measures.yaml via python_measures.

IMPORTANT: This class is Spark-first by design. Calculations should use Spark
DataFrames and window functions. Only convert to pandas at the final step
if needed for UI display.

Usage:
    1. Create a measures.py in your domain folder
    2. Inherit from DomainMeasures
    3. Implement measure methods using Spark operations

Example:
    class StocksMeasures(DomainMeasures):
        def calculate_sharpe_ratio(self, ticker=None, window_days=252, **kwargs):
            df = self.get_table('fact_stock_prices', ticker=ticker)
            # Use Spark window functions...
            return result_df
"""

from abc import ABC
from typing import Dict, Any, Optional, List, Union
import logging

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


class DomainMeasures(ABC):
    """
    Base class for domain-specific measure implementations.

    DESIGN PRINCIPLE: Spark-first, pandas-last.
    - All calculations should use Spark DataFrames and window functions
    - Only convert to pandas at the final step if needed for UI
    - Use self.to_pandas() explicitly when conversion is required

    Provides common utilities for:
    - Accessing model data (Spark DataFrames)
    - Window function helpers
    - Aggregation helpers
    - Final pandas conversion (when needed)
    """

    def __init__(self, model):
        """
        Initialize with model instance.

        Args:
            model: Domain model instance (e.g., StocksModel)
                   Provides access to tables, session, and configuration
        """
        self.model = model
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ============================================================
    # DATA ACCESS (Returns Spark DataFrames)
    # ============================================================

    def get_table(
        self,
        table_name: str,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
    ) -> SparkDataFrame:
        """
        Get a table from the model as a Spark DataFrame.

        Args:
            table_name: Name of the table (e.g., 'fact_stock_prices', 'dim_stock')
            ticker: Optional ticker filter (convenience for single-ticker queries)
            filters: Optional list of filter dicts

        Returns:
            Spark DataFrame (NOT pandas)
        """
        df = self.model.get_table(table_name)

        # Apply ticker filter if specified
        if ticker and 'ticker' in df.columns:
            df = df.filter(F.col('ticker') == ticker)

        # Apply additional filters
        if filters and self.model.session:
            df = self.model.session.apply_filters(df, filters)

        return df

    def get_spark(self):
        """Get the Spark session from the model."""
        if hasattr(self.model, 'spark'):
            return self.model.spark
        if hasattr(self.model, 'session') and hasattr(self.model.session, 'spark'):
            return self.model.session.spark
        # Fallback: create one
        from orchestration.common.spark_session import get_spark
        return get_spark("DomainMeasures")

    # ============================================================
    # WINDOW FUNCTION HELPERS
    # ============================================================

    def ticker_window(self, order_col: str = 'trade_date') -> Window:
        """
        Create a window partitioned by ticker, ordered by date.

        Args:
            order_col: Column to order by (default: trade_date)

        Returns:
            Window specification
        """
        return Window.partitionBy('ticker').orderBy(order_col)

    def rolling_window(
        self,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date',
        window_size: int = 20
    ) -> Window:
        """
        Create a rolling window for calculations.

        Args:
            partition_col: Column to partition by
            order_col: Column to order by
            window_size: Number of rows in window

        Returns:
            Window specification for rolling calculations
        """
        return (
            Window
            .partitionBy(partition_col)
            .orderBy(order_col)
            .rowsBetween(-(window_size - 1), 0)
        )

    def expanding_window(
        self,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date'
    ) -> Window:
        """
        Create an expanding (cumulative) window.

        Args:
            partition_col: Column to partition by
            order_col: Column to order by

        Returns:
            Window specification for cumulative calculations
        """
        return (
            Window
            .partitionBy(partition_col)
            .orderBy(order_col)
            .rowsBetween(Window.unboundedPreceding, 0)
        )

    # ============================================================
    # SPARK CALCULATION UTILITIES
    # ============================================================

    def add_returns(
        self,
        df: SparkDataFrame,
        price_col: str = 'close',
        partition_col: str = 'ticker',
        order_col: str = 'trade_date',
        log_returns: bool = False
    ) -> SparkDataFrame:
        """
        Add return column to DataFrame using Spark.

        Args:
            df: Input Spark DataFrame
            price_col: Price column name
            partition_col: Partition column (ticker)
            order_col: Order column (date)
            log_returns: Use log returns instead of simple returns

        Returns:
            DataFrame with 'returns' column added
        """
        window = Window.partitionBy(partition_col).orderBy(order_col)
        prev_price = F.lag(price_col, 1).over(window)

        if log_returns:
            returns = F.log(F.col(price_col) / prev_price)
        else:
            returns = (F.col(price_col) - prev_price) / prev_price

        return df.withColumn('returns', returns)

    def add_rolling_mean(
        self,
        df: SparkDataFrame,
        col: str,
        window_size: int,
        result_col: Optional[str] = None,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date'
    ) -> SparkDataFrame:
        """
        Add rolling mean column.

        Args:
            df: Input DataFrame
            col: Column to average
            window_size: Rolling window size
            result_col: Output column name (default: {col}_sma_{window_size})
            partition_col: Partition column
            order_col: Order column

        Returns:
            DataFrame with rolling mean column added
        """
        if result_col is None:
            result_col = f"{col}_sma_{window_size}"

        window = self.rolling_window(partition_col, order_col, window_size)
        return df.withColumn(result_col, F.avg(col).over(window))

    def add_rolling_std(
        self,
        df: SparkDataFrame,
        col: str,
        window_size: int,
        result_col: Optional[str] = None,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date'
    ) -> SparkDataFrame:
        """
        Add rolling standard deviation column.

        Args:
            df: Input DataFrame
            col: Column to calculate std for
            window_size: Rolling window size
            result_col: Output column name (default: {col}_std_{window_size})
            partition_col: Partition column
            order_col: Order column

        Returns:
            DataFrame with rolling std column added
        """
        if result_col is None:
            result_col = f"{col}_std_{window_size}"

        window = self.rolling_window(partition_col, order_col, window_size)
        return df.withColumn(result_col, F.stddev(col).over(window))

    def add_rolling_max(
        self,
        df: SparkDataFrame,
        col: str,
        window_size: int,
        result_col: Optional[str] = None,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date'
    ) -> SparkDataFrame:
        """
        Add rolling maximum column (useful for drawdown calculations).

        Args:
            df: Input DataFrame
            col: Column to find max for
            window_size: Rolling window size
            result_col: Output column name (default: {col}_max_{window_size})
            partition_col: Partition column
            order_col: Order column

        Returns:
            DataFrame with rolling max column added
        """
        if result_col is None:
            result_col = f"{col}_max_{window_size}"

        window = self.rolling_window(partition_col, order_col, window_size)
        return df.withColumn(result_col, F.max(col).over(window))

    def add_cumulative_max(
        self,
        df: SparkDataFrame,
        col: str,
        result_col: Optional[str] = None,
        partition_col: str = 'ticker',
        order_col: str = 'trade_date'
    ) -> SparkDataFrame:
        """
        Add cumulative (expanding) maximum column.

        Args:
            df: Input DataFrame
            col: Column to find cumulative max for
            result_col: Output column name (default: {col}_cum_max)
            partition_col: Partition column
            order_col: Order column

        Returns:
            DataFrame with cumulative max column added
        """
        if result_col is None:
            result_col = f"{col}_cum_max"

        window = self.expanding_window(partition_col, order_col)
        return df.withColumn(result_col, F.max(col).over(window))

    def normalize_column(
        self,
        df: SparkDataFrame,
        col: str,
        result_col: Optional[str] = None,
        min_val: float = 0.0,
        max_val: float = 1.0,
        partition_col: Optional[str] = None
    ) -> SparkDataFrame:
        """
        Normalize a column to a specified range.

        Args:
            df: Input DataFrame
            col: Column to normalize
            result_col: Output column name (default: {col}_norm)
            min_val: Target minimum (default: 0)
            max_val: Target maximum (default: 1)
            partition_col: Optional partition (normalize within groups)

        Returns:
            DataFrame with normalized column added
        """
        if result_col is None:
            result_col = f"{col}_norm"

        if partition_col:
            window = Window.partitionBy(partition_col)
            col_min = F.min(col).over(window)
            col_max = F.max(col).over(window)
        else:
            # Global min/max - need to compute separately
            stats = df.agg(F.min(col).alias('min_v'), F.max(col).alias('max_v')).collect()[0]
            col_min = F.lit(stats['min_v'])
            col_max = F.lit(stats['max_v'])

        normalized = (
            F.when(col_max == col_min, F.lit(0.5))
            .otherwise(
                min_val + (F.col(col) - col_min) / (col_max - col_min) * (max_val - min_val)
            )
        )

        return df.withColumn(result_col, normalized)

    # ============================================================
    # FINAL CONVERSION (for UI layer)
    # ============================================================

    def to_pandas(self, df: SparkDataFrame, limit: Optional[int] = None):
        """
        Convert Spark DataFrame to pandas.

        Use when result is needed for UI (Streamlit, Plotly).

        Args:
            df: Spark DataFrame
            limit: Optional row limit (applies before conversion)

        Returns:
            pandas DataFrame
        """
        import pandas as pd

        if df is None:
            return pd.DataFrame()

        if limit:
            df = df.limit(limit)

        return df.toPandas()

    # ============================================================
    # LOGGING UTILITIES
    # ============================================================

    def log_start(self, measure_name: str, **params):
        """Log measure calculation start with parameters."""
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        self._logger.info(f"Calculating {measure_name}({param_str})")

    def log_result(self, measure_name: str, df: SparkDataFrame):
        """Log measure calculation result (Spark DataFrame)."""
        count = df.count()
        cols = df.columns
        self._logger.info(f"{measure_name}: {count:,} rows, columns: {cols}")
