"""
Measure aggregation engine.

Executes measure calculations and aggregations on DataFrames.
"""

from typing import Dict, List, Optional, Any
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from pyspark.sql.window import Window

from ..schema import Measure, MeasureType, AggregationType
from ..graph.subgraph import NotebookGraph
from .calculator import ExpressionCalculator
from .window import WindowCalculator


class MeasureEngine:
    """
    Engine for computing measures on notebook graphs.

    Supports:
    - Simple aggregations (sum, avg, etc.)
    - Weighted averages
    - Custom calculations
    - Window functions
    - Ratio calculations
    """

    def __init__(self, graph: NotebookGraph):
        """
        Initialize measure engine.

        Args:
            graph: Notebook graph with loaded data
        """
        self.graph = graph
        self.expression_calculator = ExpressionCalculator()
        self.window_calculator = WindowCalculator()

    def compute_measure(
        self,
        measure: Measure,
        df: DataFrame,
        group_by: Optional[List[str]] = None,
    ) -> DataFrame:
        """
        Compute a measure on a dataframe.

        Args:
            measure: Measure definition
            df: Source dataframe
            group_by: Optional grouping columns

        Returns:
            DataFrame with computed measure
        """
        if measure.type == MeasureType.SIMPLE:
            return self._compute_simple(measure, df, group_by)
        elif measure.type == MeasureType.WEIGHTED_AVERAGE:
            return self._compute_weighted_average(measure, df, group_by)
        elif measure.type == MeasureType.CALCULATION:
            return self._compute_calculation(measure, df, group_by)
        elif measure.type == MeasureType.WINDOW_FUNCTION:
            return self._compute_window_function(measure, df)
        elif measure.type == MeasureType.RATIO:
            return self._compute_ratio(measure, df, group_by)
        else:
            raise ValueError(f"Unsupported measure type: {measure.type}")

    def compute_multiple_measures(
        self,
        measures: List[Measure],
        df: DataFrame,
        group_by: Optional[List[str]] = None,
    ) -> DataFrame:
        """
        Compute multiple measures on a dataframe efficiently.

        Args:
            measures: List of measure definitions
            df: Source dataframe
            group_by: Optional grouping columns

        Returns:
            DataFrame with all computed measures
        """
        # Separate measures by type for efficient computation
        simple_measures = [m for m in measures if m.type == MeasureType.SIMPLE]
        weighted_measures = [m for m in measures if m.type == MeasureType.WEIGHTED_AVERAGE]
        window_measures = [m for m in measures if m.type == MeasureType.WINDOW_FUNCTION]

        result = df

        # Compute simple aggregations in one pass
        if simple_measures and group_by:
            agg_exprs = [
                self._get_agg_expr(m).alias(m.id)
                for m in simple_measures
            ]
            result = result.groupBy(group_by).agg(*agg_exprs)

        # Compute weighted averages
        for measure in weighted_measures:
            result = self._compute_weighted_average(measure, result, group_by)

        # Compute window functions
        for measure in window_measures:
            result = self._compute_window_function(measure, result)

        return result

    def _compute_simple(
        self,
        measure: Measure,
        df: DataFrame,
        group_by: Optional[List[str]],
    ) -> DataFrame:
        """Compute a simple aggregation measure."""
        agg_expr = self._get_agg_expr(measure)

        if group_by:
            return df.groupBy(group_by).agg(agg_expr.alias(measure.id))
        else:
            return df.agg(agg_expr.alias(measure.id))

    def _compute_weighted_average(
        self,
        measure: Measure,
        df: DataFrame,
        group_by: Optional[List[str]],
    ) -> DataFrame:
        """
        Compute a weighted average measure.

        Formula: sum(value * weight) / sum(weight)
        """
        value_col = measure.value_column.column
        weight_col = measure.weight_column.column

        # Calculate weighted sum and total weight
        weighted_sum = F.sum(F.col(value_col) * F.col(weight_col))
        total_weight = F.sum(F.col(weight_col))
        weighted_avg = (weighted_sum / total_weight).alias(measure.id)

        if group_by:
            return df.groupBy(group_by).agg(weighted_avg)
        else:
            return df.agg(weighted_avg)

    def _compute_calculation(
        self,
        measure: Measure,
        df: DataFrame,
        group_by: Optional[List[str]],
    ) -> DataFrame:
        """
        Compute a custom calculation measure.

        Uses ExpressionCalculator to parse and evaluate expressions.
        """
        # Parse expression and get required columns
        expr_result = self.expression_calculator.evaluate(
            expression=measure.expression,
            df=df,
            sources=measure.sources,
        )

        # Add calculated column
        df = df.withColumn(measure.id, expr_result)

        # Apply aggregation if specified
        if measure.aggregation and group_by:
            agg_func = self._get_agg_function(measure.aggregation)
            df = df.groupBy(group_by).agg(
                agg_func(measure.id).alias(measure.id)
            )

        return df

    def _compute_window_function(
        self,
        measure: Measure,
        df: DataFrame,
    ) -> DataFrame:
        """
        Compute a window function measure.

        Uses WindowCalculator to handle window specifications.
        """
        return self.window_calculator.compute(measure, df)

    def _compute_ratio(
        self,
        measure: Measure,
        df: DataFrame,
        group_by: Optional[List[str]],
    ) -> DataFrame:
        """
        Compute a ratio measure.

        Ratio of two columns or aggregations.
        """
        # This would require additional schema fields for numerator/denominator
        # Placeholder for now
        raise NotImplementedError("Ratio measures not yet implemented")

    def _get_agg_expr(self, measure: Measure):
        """Get Spark aggregation expression for a measure."""
        if not measure.source or not measure.source.column:
            raise ValueError(f"Measure {measure.id} missing source column")

        col_name = measure.source.column
        agg_func = self._get_agg_function(measure.aggregation)

        return agg_func(col_name)

    def _get_agg_function(self, aggregation: AggregationType):
        """Get Spark aggregation function."""
        mapping = {
            AggregationType.SUM: F.sum,
            AggregationType.AVG: F.avg,
            AggregationType.MIN: F.min,
            AggregationType.MAX: F.max,
            AggregationType.COUNT: F.count,
            AggregationType.STDDEV: F.stddev,
            AggregationType.VARIANCE: F.variance,
            AggregationType.FIRST: F.first,
            AggregationType.LAST: F.last,
        }

        if aggregation not in mapping:
            raise ValueError(f"Unsupported aggregation type: {aggregation}")

        return mapping[aggregation]

    def format_measure_value(self, value: Any, format_str: Optional[str]) -> str:
        """
        Format a measure value for display.

        Args:
            value: Value to format
            format_str: Format string (e.g., "$#,##0.00", "#,##0%")

        Returns:
            Formatted string
        """
        if value is None:
            return "N/A"

        if format_str is None:
            return str(value)

        # Simple formatting rules
        if "$" in format_str:
            # Currency format
            return f"${value:,.2f}"
        elif "%" in format_str:
            # Percentage format
            return f"{value:.2f}%"
        elif "#,##0" in format_str:
            # Number with thousands separator
            if "." in format_str:
                decimals = format_str.count("0") - format_str.index(".")
                return f"{value:,.{decimals}f}"
            else:
                return f"{int(value):,}"
        else:
            return str(value)
