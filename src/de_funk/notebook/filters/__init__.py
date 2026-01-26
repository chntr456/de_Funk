"""
Filter engine for notebooks.

Handles dynamic filtering at notebook and exhibit levels.

NOTE: The duplicate FilterEngine that was previously in this module has been removed.
Use `core.session.filters.FilterEngine` for filter operations.
"""

from .context import FilterContext
from .dynamic import FilterType, FilterOperator, FilterConfig, FilterState, FilterCollection

# Re-export core FilterEngine for backwards compatibility
from de_funk.core.session.filters import FilterEngine

__all__ = [
    "FilterEngine",  # From core.session.filters
    "FilterContext",
    "FilterType",
    "FilterOperator",
    "FilterConfig",
    "FilterState",
    "FilterCollection",
]
