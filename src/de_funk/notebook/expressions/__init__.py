"""
Expression resolution for dynamic defaults in filters and exhibits.

This module provides the ExpressionResolver class for resolving dynamic
expressions like current_date(), start_of_quarter(), etc. in YAML configs.
"""
from __future__ import annotations

from app.notebook.expressions.resolver import (
    ExpressionResolver,
    ExpressionContext,
)

__all__ = [
    "ExpressionResolver",
    "ExpressionContext",
]
