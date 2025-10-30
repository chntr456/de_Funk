"""
Filter engine for applying filters to DataFrames.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pyspark.sql import DataFrame
import pyspark.sql.functions as F

from ..schema import Variable, VariableType
from .context import FilterContext
from .types import FilterOperator


class FilterEngine:
    """
    Engine for applying filters to DataFrames.

    Supports various filter types and operators.
    """

    def __init__(self):
        """Initialize filter engine."""
        pass

    def apply_filters(
        self,
        df: DataFrame,
        context: FilterContext,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> DataFrame:
        """
        Apply all filters from context to a dataframe.

        Args:
            df: Source dataframe
            context: Filter context with current values
            column_mapping: Optional mapping of variable_id -> column_name
                          (defaults to using variable_id as column name)

        Returns:
            Filtered dataframe
        """
        result = df

        for var_id, value in context.get_all().items():
            if value is None:
                continue

            variable = context.variables[var_id]
            col_name = column_mapping.get(var_id, var_id) if column_mapping else var_id

            # Check if column exists
            if col_name not in df.columns:
                continue

            result = self.apply_filter(result, variable, col_name, value)

        return result

    def apply_filter(
        self,
        df: DataFrame,
        variable: Variable,
        column_name: str,
        value: Any,
    ) -> DataFrame:
        """
        Apply a single filter to a dataframe.

        Args:
            df: Source dataframe
            variable: Variable definition
            column_name: Column to filter
            value: Filter value

        Returns:
            Filtered dataframe
        """
        if variable.type == VariableType.DATE_RANGE:
            return self._apply_date_range_filter(df, column_name, value)
        elif variable.type == VariableType.MULTI_SELECT:
            return self._apply_multi_select_filter(df, column_name, value)
        elif variable.type == VariableType.SINGLE_SELECT:
            return self._apply_single_select_filter(df, column_name, value)
        elif variable.type == VariableType.NUMBER:
            return self._apply_number_filter(df, column_name, value)
        elif variable.type == VariableType.TEXT:
            return self._apply_text_filter(df, column_name, value)
        elif variable.type == VariableType.BOOLEAN:
            return self._apply_boolean_filter(df, column_name, value)
        else:
            raise ValueError(f"Unsupported filter type: {variable.type}")

    def _apply_date_range_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: Dict[str, datetime],
    ) -> DataFrame:
        """Apply date range filter."""
        start_date = value['start']
        end_date = value['end']

        # Convert to string if needed (for date columns stored as strings)
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')

        return df.filter(
            (F.col(column_name) >= start_date) &
            (F.col(column_name) <= end_date)
        )

    def _apply_multi_select_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: List[Any],
    ) -> DataFrame:
        """Apply multi-select filter."""
        if not value:
            return df

        return df.filter(F.col(column_name).isin(value))

    def _apply_single_select_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: Any,
    ) -> DataFrame:
        """Apply single-select filter."""
        return df.filter(F.col(column_name) == value)

    def _apply_number_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: Any,
    ) -> DataFrame:
        """
        Apply number filter.

        Value can be:
        - Single number: Applies equality filter
        - Dict with 'operator' and 'value': Applies operator filter
        - Dict with 'min' and 'max': Applies range filter
        """
        if isinstance(value, dict):
            if 'operator' in value:
                operator = FilterOperator(value['operator'])
                filter_value = value['value']
                return self._apply_operator_filter(df, column_name, operator, filter_value)
            elif 'min' in value and 'max' in value:
                return df.filter(
                    (F.col(column_name) >= value['min']) &
                    (F.col(column_name) <= value['max'])
                )
        else:
            return df.filter(F.col(column_name) == value)

    def _apply_text_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: Any,
    ) -> DataFrame:
        """
        Apply text filter.

        Value can be:
        - String: Applies contains filter
        - Dict with 'operator' and 'value': Applies operator filter
        """
        if isinstance(value, dict):
            operator = FilterOperator(value['operator'])
            filter_value = value['value']
            return self._apply_operator_filter(df, column_name, operator, filter_value)
        else:
            return df.filter(F.col(column_name).contains(value))

    def _apply_boolean_filter(
        self,
        df: DataFrame,
        column_name: str,
        value: bool,
    ) -> DataFrame:
        """Apply boolean filter."""
        return df.filter(F.col(column_name) == value)

    def _apply_operator_filter(
        self,
        df: DataFrame,
        column_name: str,
        operator: FilterOperator,
        value: Any,
    ) -> DataFrame:
        """Apply filter with specific operator."""
        col = F.col(column_name)

        if operator == FilterOperator.EQUALS:
            return df.filter(col == value)
        elif operator == FilterOperator.NOT_EQUALS:
            return df.filter(col != value)
        elif operator == FilterOperator.GREATER_THAN:
            return df.filter(col > value)
        elif operator == FilterOperator.GREATER_THAN_OR_EQUAL:
            return df.filter(col >= value)
        elif operator == FilterOperator.LESS_THAN:
            return df.filter(col < value)
        elif operator == FilterOperator.LESS_THAN_OR_EQUAL:
            return df.filter(col <= value)
        elif operator == FilterOperator.BETWEEN:
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("BETWEEN operator requires [min, max] value")
            return df.filter((col >= value[0]) & (col <= value[1]))
        elif operator == FilterOperator.IN:
            return df.filter(col.isin(value))
        elif operator == FilterOperator.NOT_IN:
            return df.filter(~col.isin(value))
        elif operator == FilterOperator.CONTAINS:
            return df.filter(col.contains(value))
        elif operator == FilterOperator.STARTS_WITH:
            return df.filter(col.startswith(value))
        elif operator == FilterOperator.ENDS_WITH:
            return df.filter(col.endswith(value))
        elif operator == FilterOperator.IS_NULL:
            return df.filter(col.isNull())
        elif operator == FilterOperator.IS_NOT_NULL:
            return df.filter(col.isNotNull())
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def get_unique_values(
        self,
        df: DataFrame,
        column_name: str,
        limit: Optional[int] = 1000,
    ) -> List[Any]:
        """
        Get unique values from a column for filter options.

        Args:
            df: Source dataframe
            column_name: Column name
            limit: Max number of values to return

        Returns:
            List of unique values
        """
        values = (
            df.select(column_name)
            .distinct()
            .limit(limit)
            .toPandas()[column_name]
            .tolist()
        )

        # Sort values for better UX
        try:
            values = sorted(values)
        except TypeError:
            # Can't sort mixed types
            pass

        return values

    def get_min_max(
        self,
        df: DataFrame,
        column_name: str,
    ) -> tuple:
        """
        Get min and max values for a numeric column.

        Args:
            df: Source dataframe
            column_name: Column name

        Returns:
            Tuple of (min_value, max_value)
        """
        result = df.agg(
            F.min(column_name).alias('min'),
            F.max(column_name).alias('max'),
        ).first()

        return result['min'], result['max']

    def apply_dynamic_time_filter(
        self,
        df: DataFrame,
        date_column: str,
        time_horizon: str,
    ) -> DataFrame:
        """
        Apply a dynamic time filter based on horizon.

        Args:
            df: Source dataframe
            date_column: Date column name
            time_horizon: Time horizon (e.g., '30d', '1y', 'ytd', 'mtd')

        Returns:
            Filtered dataframe
        """
        from ..parser import DateResolver

        # Calculate date range based on horizon
        end_date = datetime.now()

        if time_horizon == 'ytd':
            start_date = datetime(end_date.year, 1, 1)
        elif time_horizon == 'mtd':
            start_date = datetime(end_date.year, end_date.month, 1)
        elif time_horizon == 'qtd':
            quarter = (end_date.month - 1) // 3
            start_date = datetime(end_date.year, quarter * 3 + 1, 1)
        else:
            # Parse as relative date (e.g., '-30d')
            if not time_horizon.startswith('-'):
                time_horizon = '-' + time_horizon
            start_date = DateResolver.resolve(time_horizon, end_date)

        # Apply filter
        return df.filter(
            (F.col(date_column) >= start_date.strftime('%Y-%m-%d')) &
            (F.col(date_column) <= end_date.strftime('%Y-%m-%d'))
        )
