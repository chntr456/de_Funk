"""
Backward compatibility layer for types.

Types have been moved to models/company/types/.
This file re-exports them for backward compatibility.
"""

from __future__ import annotations

# Import from new location
from models.implemented.company.types import NewsItem, PriceBar

__all__ = ['NewsItem', 'PriceBar']
