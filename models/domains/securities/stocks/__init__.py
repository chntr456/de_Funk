"""
Stocks model - common stock equities.

Provides:
- StocksModel: Domain model for stock data
- StocksBuilder: Builder for stocks silver layer
- StocksMeasures: Complex measure calculations (requires PySpark)
"""

from .model import StocksModel
from .builder import StocksBuilder

# Conditional import for PySpark-dependent measures
try:
    from .measures import StocksMeasures
    __all__ = ['StocksModel', 'StocksBuilder', 'StocksMeasures']
except ImportError:
    # PySpark not available - measures not supported
    StocksMeasures = None  # type: ignore
    __all__ = ['StocksModel', 'StocksBuilder']
