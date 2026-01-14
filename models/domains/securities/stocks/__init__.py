"""
Stocks model - common stock equities.

Provides:
- StocksModel: Domain model for stock data
- StocksBuilder: Builder for stocks silver layer
- StocksMeasures: Complex measure calculations
"""

from .model import StocksModel
from .builder import StocksBuilder
from .measures import StocksMeasures

__all__ = ['StocksModel', 'StocksBuilder', 'StocksMeasures']
