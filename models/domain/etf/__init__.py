"""
ETF model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.securities.etfs instead.

Example:
    # Old (deprecated)
    from models.domain.etf import ETFModel

    # New (recommended)
    from models.domains.securities.etfs import ETFModel
"""

from models.domains.securities.etfs import ETFModel

__all__ = ['ETFModel']
