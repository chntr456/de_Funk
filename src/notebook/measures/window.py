"""
Window function calculator for time-series measures.

Handles window functions like moving averages, cumulative sums, etc.
"""

from typing import List, Optional
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from pyspark.sql.window import Window

from ..schema import Measure, AggregationType, WindowConfig


class WindowCalculator:
    """
    Calculator for window function measures.

    Supports:
    - Moving averages (MA)
    - Cumulative aggregations
    - Ranking functions
    - Lag/Lead operations
    """

    def compute(self, measure: Measure, df: DataFrame) -> DataFrame:
        """
        Compute a window function measure.

        Args:
            measure: Measure definition with window configuration
            df: Source dataframe

        Returns:
            DataFrame with computed window measure
        """
        if not measure.window:
            raise ValueError(f"Measure {measure.id} missing window configuration")

        # Build window specification
        window_spec = self._build_window_spec(measure.window)

        # Get aggregation function
        agg_func = self._get_window_function(measure.function)

        # Get source column
        source_col = measure.source.column

        # Apply window function
        df = df.withColumn(
            measure.id,
            agg_func(F.col(source_col)).over(window_spec)
        )

        return df

    def _build_window_spec(self, window_config: WindowConfig):
        """
        Build a Spark window specification.

        Args:
            window_config: Window configuration

        Returns:
            Window specification
        """
        # Start with partition
        window_spec = Window.partitionBy(*window_config.partition_by)

        # Add ordering
        if window_config.order_by:
            window_spec = window_spec.orderBy(*window_config.order_by)

        # Add frame specification
        if window_config.rows_between:
            start, end = window_config.rows_between
            window_spec = window_spec.rowsBetween(start, end)
        elif window_config.range_between:
            # Range between requires special handling
            # For now, we'll skip this
            pass

        return window_spec

    def _get_window_function(self, function_name: str):
        """
        Get window function by name.

        Args:
            function_name: Function name (avg, sum, etc.)

        Returns:
            Spark function
        """
        mapping = {
            'avg': F.avg,
            'sum': F.sum,
            'min': F.min,
            'max': F.max,
            'count': F.count,
            'first': F.first,
            'last': F.last,
            'lag': F.lag,
            'lead': F.lead,
            'rank': F.rank,
            'dense_rank': F.dense_rank,
            'row_number': F.row_number,
        }

        if function_name not in mapping:
            raise ValueError(f"Unsupported window function: {function_name}")

        return mapping[function_name]

    def create_moving_average(
        self,
        df: DataFrame,
        column: str,
        window_size: int,
        partition_by: List[str],
        order_by: List[str],
        output_column: Optional[str] = None,
    ) -> DataFrame:
        """
        Create a moving average column.

        Args:
            df: Source dataframe
            column: Column to average
            window_size: Size of the moving window
            partition_by: Partition columns
            order_by: Ordering columns
            output_column: Output column name (default: {column}_ma_{window_size})

        Returns:
            DataFrame with moving average column
        """
        if output_column is None:
            output_column = f"{column}_ma_{window_size}"

        window_spec = (
            Window.partitionBy(*partition_by)
            .orderBy(*order_by)
            .rowsBetween(-(window_size - 1), 0)
        )

        return df.withColumn(
            output_column,
            F.avg(column).over(window_spec)
        )

    def create_cumulative_sum(
        self,
        df: DataFrame,
        column: str,
        partition_by: List[str],
        order_by: List[str],
        output_column: Optional[str] = None,
    ) -> DataFrame:
        """
        Create a cumulative sum column.

        Args:
            df: Source dataframe
            column: Column to sum
            partition_by: Partition columns
            order_by: Ordering columns
            output_column: Output column name (default: {column}_cumsum)

        Returns:
            DataFrame with cumulative sum column
        """
        if output_column is None:
            output_column = f"{column}_cumsum"

        window_spec = (
            Window.partitionBy(*partition_by)
            .orderBy(*order_by)
            .rowsBetween(Window.unboundedPreceding, Window.currentRow)
        )

        return df.withColumn(
            output_column,
            F.sum(column).over(window_spec)
        )

    def create_lag_column(
        self,
        df: DataFrame,
        column: str,
        periods: int,
        partition_by: List[str],
        order_by: List[str],
        output_column: Optional[str] = None,
    ) -> DataFrame:
        """
        Create a lag column (value from N rows back).

        Args:
            df: Source dataframe
            column: Column to lag
            periods: Number of periods to lag
            partition_by: Partition columns
            order_by: Ordering columns
            output_column: Output column name (default: {column}_lag_{periods})

        Returns:
            DataFrame with lag column
        """
        if output_column is None:
            output_column = f"{column}_lag_{periods}"

        window_spec = Window.partitionBy(*partition_by).orderBy(*order_by)

        return df.withColumn(
            output_column,
            F.lag(column, periods).over(window_spec)
        )

    def create_percent_change(
        self,
        df: DataFrame,
        column: str,
        periods: int,
        partition_by: List[str],
        order_by: List[str],
        output_column: Optional[str] = None,
    ) -> DataFrame:
        """
        Create a percent change column.

        Formula: (current - previous) / previous * 100

        Args:
            df: Source dataframe
            column: Column to compute change for
            periods: Number of periods to look back
            partition_by: Partition columns
            order_by: Ordering columns
            output_column: Output column name (default: {column}_pct_change_{periods})

        Returns:
            DataFrame with percent change column
        """
        if output_column is None:
            output_column = f"{column}_pct_change_{periods}"

        window_spec = Window.partitionBy(*partition_by).orderBy(*order_by)

        lag_col = F.lag(column, periods).over(window_spec)

        return df.withColumn(
            output_column,
            ((F.col(column) - lag_col) / lag_col * 100)
        )
