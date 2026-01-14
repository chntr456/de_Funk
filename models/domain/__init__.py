"""
Domain models - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains instead.

Example:
    # Old (deprecated)
    from models.domain.stocks.model import StocksModel

    # New (recommended)
    from models.domains.securities.stocks import StocksModel

This module re-exports from the new locations for backward compatibility.
"""

# Re-export from new domain structure for backward compatibility
from models.domains.corporate.company import CompanyModel
from models.domains.securities.stocks import StocksModel
from models.domains.municipal.city_finance import CityFinanceModel

__all__ = [
    'CompanyModel',
    'StocksModel',
    'CityFinanceModel',
]
