"""
Stocks model - BACKWARD COMPATIBILITY LAYER.

DEPRECATED: Import from models.domains.securities.stocks instead.

Example:
    # Old (deprecated)
    from models.domain.stocks import StocksModel

    # New (recommended)
    from models.domains.securities.stocks import StocksModel
"""

from models.domains.securities.stocks import StocksModel, StocksBuilder, StocksMeasures

__all__ = ['StocksModel', 'StocksBuilder', 'StocksMeasures']
