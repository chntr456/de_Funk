"""
Equity model - Trading instruments and price data.

This model represents tradable securities (equities) identified by ticker symbols.
It contains price/volume data, technical indicators, and trading-related measures.

For corporate entity data (company fundamentals, SEC filings), see the corporate model.
"""

from .model import EquityModel

__all__ = ['EquityModel']
