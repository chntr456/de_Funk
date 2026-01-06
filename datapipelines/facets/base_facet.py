"""
DEPRECATED: Use datapipelines.base.facet instead.

This module re-exports from the new location for backwards compatibility.
All new code should import from datapipelines.base.facet directly.
"""
from datapipelines.base.facet import (
    Facet,
    coalesce_existing,
    first_existing,
    _type_from_str,
)

__all__ = ['Facet', 'coalesce_existing', 'first_existing', '_type_from_str']
