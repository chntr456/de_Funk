"""
Backward compatibility layer for services.

Services have been moved to models/company/services/.
This file re-exports them for backward compatibility.
"""

from __future__ import annotations

# Import from new location
from models.domain.company.services import NewsAPI, PricesAPI, CompanyAPI

__all__ = ['NewsAPI', 'PricesAPI', 'CompanyAPI']
