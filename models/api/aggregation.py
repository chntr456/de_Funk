"""
Aggregation Handler for UniversalSession.

Provides data aggregation capabilities:
- Group by operations with measure aggregations
- Aggregation inference from model metadata
- Backend-specific aggregation (Spark and DuckDB)

This module is used by UniversalSession via composition.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class AggregationHandler:
    """
    Handles data aggregation operations.

    Provides:
    - Aggregation to new grain using group_by
    - Measure-aware aggregation inference
    - Backend-specific implementations
    """

    def __init__(self, session):
        """
        Initialize aggregation handler.

        Args:
            session: UniversalSession instance
        """
        self.session = session

    @property
    def connection(self):
        return self.session.connection

    @property
    def backend(self) -> str:
        return self.session.backend

    @property
    def registry(self):
        return self.session.registry

    def aggregate_data(
        self,
        model_name: str,
        df: Any,
        required_columns: List[str],
        group_by: List[str],
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Aggregate data to a new grain using group_by and measure aggregations.

        Args:
            model_name: Name of the model (for measure metadata lookup)
            df: DataFrame to aggregate
            required_columns: All columns that should be in result
            group_by: Columns to group by (dimensions at new grain)
            aggregations: Optional dict mapping measure columns to agg functions.
                        If not provided, infers from measure metadata.

        Returns:
            Aggregated DataFrame

        Example:
            Input df: ticker-level daily prices (10M rows)
            group_by: ['trade_date', 'exchange_name']
            aggregations: {'close': 'avg', 'volume': 'sum'}
            Output: exchange-level daily prices (5 exchanges * 365 days = 1,825 rows)
        """
        print(f"🔢 Aggregating to grain: {group_by}")

        # Determine which columns are measures (need aggregation)
        measure_cols = [col for col in required_columns if col not in group_by]

        if not measure_cols:
            # No measures, just distinct dimensions
            if self.backend == 'spark':
                return df.select(*group_by).distinct()
            else:
                distinct_query = f"SELECT DISTINCT {', '.join(group_by)} FROM df"
                return self.connection.conn.execute(distinct_query).df()

        # Get or infer aggregations for each measure
        if not aggregations:
            aggregations = self._infer_aggregations(model_name, measure_cols)

        print(f"   Measures: {aggregations}")

        # Apply aggregations based on backend
        if self.backend == 'spark':
            return self._aggregate_spark(df, group_by, aggregations)
        else:
            return self._aggregate_duckdb(df, group_by, aggregations)

    def _infer_aggregations(self, model_name: str, measure_cols: List[str]) -> Dict[str, str]:
        """
        Infer aggregation functions for measures from model metadata.

        Checks model config for measure definitions and uses specified aggregations.
        Falls back to sensible defaults: avg for prices, sum for volumes/counts.

        Args:
            model_name: Model to look up metadata
            measure_cols: Measure columns to infer aggregations for

        Returns:
            Dict mapping measure column to aggregation function
        """
        aggregations = {}

        try:
            model_config = self.registry.get_model_config(model_name)
            measures = model_config.get('measures', {})

            for col in measure_cols:
                # Check if measure is defined in config
                if col in measures:
                    measure_def = measures[col]
                    agg_func = measure_def.get('aggregation', 'avg')
                    aggregations[col] = agg_func
                else:
                    # Fallback defaults based on column name
                    aggregations[col] = self._default_aggregation(col)

        except Exception as e:
            print(f"   Warning: Could not load measure metadata: {e}")
            # Use defaults for all
            for col in measure_cols:
                aggregations[col] = self._default_aggregation(col)

        return aggregations

    def _default_aggregation(self, column_name: str) -> str:
        """
        Determine default aggregation based on column name.

        Args:
            column_name: Name of the measure column

        Returns:
            Aggregation function: avg, sum, max, min, or first
        """
        col_lower = column_name.lower()

        # Sum aggregations
        if any(term in col_lower for term in ['volume', 'count', 'total', 'quantity', 'qty']):
            return 'sum'

        # Max aggregations
        if any(term in col_lower for term in ['high', 'max', 'peak']):
            return 'max'

        # Min aggregations
        if any(term in col_lower for term in ['low', 'min']):
            return 'min'

        # Default to average for prices and other numeric measures
        return 'avg'

    def _aggregate_spark(
        self,
        df: Any,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> Any:
        """
        Aggregate Spark DataFrame using groupBy and agg.

        Args:
            df: Spark DataFrame
            group_by: Columns to group by
            aggregations: Dict of column -> agg function

        Returns:
            Aggregated Spark DataFrame
        """
        try:
            from pyspark.sql import functions as F
        except ImportError:
            raise RuntimeError("PySpark is required for Spark backend but not installed")

        # Build aggregation expressions
        agg_exprs = []
        for col, agg_func in aggregations.items():
            if agg_func == 'avg':
                agg_exprs.append(F.avg(col).alias(col))
            elif agg_func == 'sum':
                agg_exprs.append(F.sum(col).alias(col))
            elif agg_func == 'max':
                agg_exprs.append(F.max(col).alias(col))
            elif agg_func == 'min':
                agg_exprs.append(F.min(col).alias(col))
            elif agg_func == 'count':
                agg_exprs.append(F.count(col).alias(col))
            elif agg_func == 'first':
                agg_exprs.append(F.first(col).alias(col))
            else:
                print(f"   Warning: Unknown aggregation '{agg_func}' for {col}, using avg")
                agg_exprs.append(F.avg(col).alias(col))

        # Group and aggregate
        result = df.groupBy(*group_by).agg(*agg_exprs)

        # Reorder columns to match group_by + measures order
        measure_order = list(aggregations.keys())
        result = result.select(*group_by, *measure_order)

        return result

    def _aggregate_duckdb(
        self,
        df: Any,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> Any:
        """
        Aggregate DuckDB relation using SQL GROUP BY.

        Args:
            df: DuckDB relation or pandas DataFrame
            group_by: Columns to group by
            aggregations: Dict of column -> agg function

        Returns:
            Aggregated DuckDB relation
        """
        # Build aggregation SQL
        select_parts = []

        # Add group by columns
        for col in group_by:
            select_parts.append(col)

        # Add aggregated measures
        for col, agg_func in aggregations.items():
            if agg_func == 'avg':
                select_parts.append(f"AVG({col}) as {col}")
            elif agg_func == 'sum':
                select_parts.append(f"SUM({col}) as {col}")
            elif agg_func == 'max':
                select_parts.append(f"MAX({col}) as {col}")
            elif agg_func == 'min':
                select_parts.append(f"MIN({col}) as {col}")
            elif agg_func == 'count':
                select_parts.append(f"COUNT({col}) as {col}")
            elif agg_func == 'first':
                select_parts.append(f"FIRST({col}) as {col}")
            else:
                print(f"   Warning: Unknown aggregation '{agg_func}' for {col}, using AVG")
                select_parts.append(f"AVG({col}) as {col}")

        # Build complete SQL
        select_clause = ", ".join(select_parts)
        group_clause = ", ".join(group_by)
        sql = f"SELECT {select_clause} FROM df GROUP BY {group_clause}"

        print(f"   Aggregation SQL: {sql}")

        # Execute query
        try:
            result = self.connection.conn.execute(sql)
            return result.df()
        except Exception as e:
            print(f"   Error in DuckDB aggregation: {e}")
            return df
