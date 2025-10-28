"""
Filter engine for notebooks.

Handles dynamic filtering at notebook and exhibit levels.
"""

from .engine import FilterEngine
from .context import FilterContext
from .types import FilterType, FilterOperator

__all__ = [
    "FilterEngine",
    "FilterContext",
    "FilterType",
    "FilterOperator",
]
