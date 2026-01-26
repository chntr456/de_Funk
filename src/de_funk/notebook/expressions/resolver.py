"""
Expression resolver for dynamic defaults in filters and exhibits.

Supports:
- Date functions: current_date(), start_of_month(), end_of_month(), etc.
- Arithmetic: current_date() + 30, current_date() - 7
- Data functions: max(column), min(column), top_n(column, n) [requires session]
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExpressionContext:
    """Context for resolving expressions."""

    current_date: date = field(default_factory=date.today)
    data_source: Optional[str] = None  # For data-dependent expressions (model.table)
    session: Optional[Any] = None  # For querying data (UniversalSession)
    variables: Dict[str, Any] = field(default_factory=dict)  # User-defined variables


class ExpressionResolver:
    """
    Resolves dynamic expressions in YAML configurations.

    Supports:
    - Date functions: current_date(), start_of_month(), end_of_month(),
      start_of_quarter(), start_of_year(), trading_day(-1)
    - Arithmetic: current_date() + 30, current_date() - 7
    - Data functions: max(column), min(column), top_n(column, n) [requires session]

    Usage:
        resolver = ExpressionResolver()
        result = resolver.resolve("current_date() - 30")  # date 30 days ago

        # With context for data functions
        ctx = ExpressionContext(session=my_session, data_source="stocks.dim_stock")
        resolver = ExpressionResolver(ctx)
        result = resolver.resolve("top_n(market_cap, 10)")  # Top 10 tickers
    """

    # Pattern for date function calls
    DATE_FUNCTION_PATTERN = re.compile(
        r'(current_date|start_of_month|end_of_month|start_of_quarter|'
        r'end_of_quarter|start_of_year|end_of_year|trading_day)\(\s*(-?\d*)?\s*\)'
    )

    # Pattern for arithmetic operations on dates
    ARITHMETIC_PATTERN = re.compile(
        r'(.+?)\s*([+-])\s*(\d+)\s*$'
    )

    # Pattern for data-dependent functions
    DATA_FUNCTION_PATTERN = re.compile(
        r'(max|min|avg|first|last|distinct|top_n)\(\s*(\w+)(?:\s*,\s*(\d+))?\s*\)'
    )

    def __init__(self, context: Optional[ExpressionContext] = None):
        """
        Initialize the resolver with optional context.

        Args:
            context: ExpressionContext with current_date, session, etc.
        """
        self.context = context or ExpressionContext()

    def resolve(self, expression: Any) -> Any:
        """
        Resolve an expression to its value.

        Args:
            expression: The expression to resolve (string or other value)

        Returns:
            Resolved value (date, list, scalar, or original value if not an expression)
        """
        if not isinstance(expression, str):
            return expression

        expression = expression.strip()

        # Try date functions
        date_result = self._resolve_date_expression(expression)
        if date_result is not None:
            return date_result

        # Try data functions (requires session)
        if self.context.session and self.context.data_source:
            data_result = self._resolve_data_function(expression)
            if data_result is not None:
                return data_result

        # Return as-is if no match (could be a literal string)
        return expression

    def resolve_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve all expressions in a dictionary recursively.

        Args:
            data: Dictionary with potential expressions

        Returns:
            Dictionary with all expressions resolved
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                result[key] = [self.resolve(item) for item in value]
            else:
                result[key] = self.resolve(value)
        return result

    def _resolve_date_expression(self, expr: str) -> Optional[date]:
        """
        Resolve date function expressions with optional arithmetic.

        Supports:
        - current_date() → today
        - current_date() + 30 → 30 days from now
        - current_date() - 7 → 7 days ago
        - start_of_month() → first day of current month
        - end_of_month() → last day of current month
        - start_of_quarter() → first day of current quarter
        - end_of_quarter() → last day of current quarter
        - start_of_year() → January 1 of current year
        - end_of_year() → December 31 of current year
        - trading_day(-1) → previous trading day (skips weekends)
        """
        # Handle arithmetic first (e.g., "current_date() - 30")
        arith_match = self.ARITHMETIC_PATTERN.match(expr)
        if arith_match:
            base_expr = arith_match.group(1).strip()
            operator = arith_match.group(2)
            days = int(arith_match.group(3))

            # Recursively resolve the base expression
            base_date = self._resolve_date_expression(base_expr)
            if base_date is not None:
                delta = timedelta(days=days)
                if operator == '-':
                    return base_date - delta
                else:
                    return base_date + delta

        # Handle function calls
        func_match = self.DATE_FUNCTION_PATTERN.match(expr)
        if func_match:
            func_name = func_match.group(1)
            arg = func_match.group(2)

            return self._call_date_function(func_name, arg)

        return None

    def _call_date_function(self, func_name: str, arg: Optional[str]) -> Optional[date]:
        """Execute a date function by name."""
        current = self.context.current_date

        if func_name == 'current_date':
            return current

        elif func_name == 'start_of_month':
            return current.replace(day=1)

        elif func_name == 'end_of_month':
            # Go to next month, then back one day
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1, day=1)
            else:
                next_month = current.replace(month=current.month + 1, day=1)
            return next_month - timedelta(days=1)

        elif func_name == 'start_of_quarter':
            quarter = (current.month - 1) // 3
            quarter_start_month = quarter * 3 + 1
            return current.replace(month=quarter_start_month, day=1)

        elif func_name == 'end_of_quarter':
            quarter = (current.month - 1) // 3
            quarter_end_month = (quarter + 1) * 3
            if quarter_end_month > 12:
                quarter_end_month = 12
            # Get last day of quarter end month
            if quarter_end_month == 12:
                next_month = date(current.year + 1, 1, 1)
            else:
                next_month = current.replace(month=quarter_end_month + 1, day=1)
            return next_month - timedelta(days=1)

        elif func_name == 'start_of_year':
            return current.replace(month=1, day=1)

        elif func_name == 'end_of_year':
            return current.replace(month=12, day=31)

        elif func_name == 'trading_day':
            offset = int(arg) if arg else -1
            return self._get_trading_day(offset)

        return None

    def _get_trading_day(self, offset: int) -> date:
        """
        Get trading day with offset (excludes weekends).

        Args:
            offset: Number of trading days from today (negative = past)

        Returns:
            Date of the trading day
        """
        result = self.context.current_date
        step = 1 if offset > 0 else -1
        count = 0

        while count < abs(offset):
            result += timedelta(days=step)
            # Skip weekends (5=Saturday, 6=Sunday)
            if result.weekday() < 5:
                count += 1

        # If we land on a weekend, move to nearest weekday
        while result.weekday() >= 5:
            result += timedelta(days=step)

        return result

    def _resolve_data_function(self, expr: str) -> Optional[Any]:
        """
        Resolve data-dependent functions (requires session and data_source).

        Supports:
        - max(column) → maximum value
        - min(column) → minimum value
        - avg(column) → average value
        - first(column) → first value
        - last(column) → last value (most recent)
        - distinct(column) → all distinct values as list
        - top_n(column, n) → top N values by frequency/value
        """
        match = self.DATA_FUNCTION_PATTERN.match(expr)
        if not match:
            return None

        func_name = match.group(1)
        column = match.group(2)
        n = int(match.group(3)) if match.group(3) else None

        if not self.context.session or not self.context.data_source:
            logger.warning(
                f"Data function {func_name}({column}) requires session and data_source"
            )
            return None

        try:
            return self._execute_data_function(func_name, column, n)
        except Exception as e:
            logger.error(f"Error executing {func_name}({column}): {e}")
            return None

    def _execute_data_function(
        self, func_name: str, column: str, n: Optional[int]
    ) -> Optional[Any]:
        """Execute a data function against the session."""
        source = self.context.data_source
        session = self.context.session

        # Build aggregation query
        if func_name == 'max':
            query = f"SELECT MAX({column}) as result FROM {source}"
        elif func_name == 'min':
            query = f"SELECT MIN({column}) as result FROM {source}"
        elif func_name == 'avg':
            query = f"SELECT AVG({column}) as result FROM {source}"
        elif func_name == 'first':
            query = f"SELECT {column} as result FROM {source} LIMIT 1"
        elif func_name == 'last':
            query = f"SELECT {column} as result FROM {source} ORDER BY 1 DESC LIMIT 1"
        elif func_name == 'distinct':
            query = f"SELECT DISTINCT {column} as result FROM {source} ORDER BY 1"
        elif func_name == 'top_n':
            if n is None:
                n = 10
            # Top N by value (descending)
            query = f"""
                SELECT DISTINCT {column} as result
                FROM {source}
                WHERE {column} IS NOT NULL
                ORDER BY {column} DESC
                LIMIT {n}
            """
        else:
            return None

        # Execute query
        try:
            result_df = session.query(query)
            if result_df is None or len(result_df) == 0:
                return None

            # For distinct and top_n, return list
            if func_name in ('distinct', 'top_n'):
                return result_df['result'].tolist()

            # For scalar functions, return single value
            return result_df['result'].iloc[0]

        except Exception as e:
            logger.error(f"Query failed for {func_name}({column}): {e}")
            return None


# Convenience function for quick resolution
def resolve_expression(
    expression: Any,
    current_date: Optional[date] = None,
    session: Optional[Any] = None,
    data_source: Optional[str] = None,
) -> Any:
    """
    Convenience function to resolve a single expression.

    Args:
        expression: Expression to resolve
        current_date: Override for current date (default: today)
        session: UniversalSession for data functions
        data_source: model.table reference for data functions

    Returns:
        Resolved value
    """
    ctx = ExpressionContext(
        current_date=current_date or date.today(),
        session=session,
        data_source=data_source,
    )
    resolver = ExpressionResolver(ctx)
    return resolver.resolve(expression)
