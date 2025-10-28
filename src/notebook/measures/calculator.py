"""
Expression calculator for custom measures.

Parses and evaluates custom expressions.
"""

import re
from typing import Dict, Any
from pyspark.sql import DataFrame
import pyspark.sql.functions as F

from ..schema import SourceReference


class ExpressionCalculator:
    """
    Calculator for custom measure expressions.

    Supports basic arithmetic operations and functions.

    Example expressions:
    - "(close - open) / open * 100"
    - "volume * price"
    - "sqrt(variance)"
    """

    # Supported functions
    FUNCTIONS = {
        'abs': F.abs,
        'sqrt': F.sqrt,
        'log': F.log,
        'exp': F.exp,
        'round': F.round,
        'floor': F.floor,
        'ceil': F.ceil,
        'pow': F.pow,
    }

    def evaluate(
        self,
        expression: str,
        df: DataFrame,
        sources: Dict[str, SourceReference],
    ) -> Any:
        """
        Evaluate an expression on a dataframe.

        Args:
            expression: Expression string
            df: Source dataframe
            sources: Mapping of variable names to source references

        Returns:
            Spark Column expression
        """
        # Replace variable names with column references
        # This is a simplified implementation
        # In production, you'd want a proper expression parser

        # Create a mapping of variables to columns
        var_mapping = {}
        for var_name, source_ref in sources.items():
            col_name = source_ref.column
            var_mapping[var_name] = F.col(col_name)

        # Parse and evaluate the expression
        return self._parse_expression(expression, var_mapping)

    def _parse_expression(
        self,
        expr: str,
        var_mapping: Dict[str, Any],
    ) -> Any:
        """
        Parse an expression string into a Spark column expression.

        Args:
            expr: Expression string
            var_mapping: Variable name to Column mapping

        Returns:
            Spark Column
        """
        # Remove whitespace
        expr = expr.strip()

        # Handle parentheses
        if expr.startswith('(') and expr.endswith(')'):
            return self._parse_expression(expr[1:-1], var_mapping)

        # Handle functions
        for func_name, func in self.FUNCTIONS.items():
            pattern = rf'{func_name}\((.*?)\)'
            match = re.search(pattern, expr)
            if match:
                arg = match.group(1)
                arg_expr = self._parse_expression(arg, var_mapping)
                return func(arg_expr)

        # Handle binary operations
        # Order matters: +, -, *, /, %
        for op in ['+', '-', '*', '/', '%']:
            # Find the operator not inside parentheses
            parts = self._split_by_operator(expr, op)
            if len(parts) == 2:
                left = self._parse_expression(parts[0], var_mapping)
                right = self._parse_expression(parts[1], var_mapping)

                if op == '+':
                    return left + right
                elif op == '-':
                    return left - right
                elif op == '*':
                    return left * right
                elif op == '/':
                    return left / right
                elif op == '%':
                    return left % right

        # Handle variables
        if expr in var_mapping:
            return var_mapping[expr]

        # Handle numeric literals
        try:
            return F.lit(float(expr))
        except ValueError:
            pass

        # Handle string literals
        if expr.startswith('"') and expr.endswith('"'):
            return F.lit(expr[1:-1])

        raise ValueError(f"Could not parse expression: {expr}")

    def _split_by_operator(self, expr: str, op: str) -> list:
        """
        Split expression by operator, respecting parentheses.

        Args:
            expr: Expression string
            op: Operator character

        Returns:
            List of parts (empty if operator not found at top level)
        """
        depth = 0
        for i, char in enumerate(expr):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == op and depth == 0:
                return [expr[:i], expr[i+1:]]
        return []

    def validate_expression(
        self,
        expression: str,
        sources: Dict[str, SourceReference],
    ) -> tuple:
        """
        Validate an expression.

        Args:
            expression: Expression string
            sources: Available sources

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check that all variables in the expression are defined
            # This is a simple check - in production you'd want more validation
            for var_name in sources.keys():
                if var_name not in expression:
                    return False, f"Variable '{var_name}' defined but not used"

            return True, None
        except Exception as e:
            return False, str(e)
