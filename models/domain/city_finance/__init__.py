"""
City Finance model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.municipal.city_finance instead.

Example:
    # Old (deprecated)
    from models.domain.city_finance import CityFinanceModel

    # New (recommended)
    from models.domains.municipal.city_finance import CityFinanceModel
"""

from models.domains.municipal.city_finance import CityFinanceModel

__all__ = ['CityFinanceModel']
