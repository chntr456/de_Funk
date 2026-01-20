"""
Securities Model - Master domain for all tradable instruments.

This module provides the normalized foundation for all security types:
- dim_security: Master security dimension
- fact_security_prices: Unified OHLCV for all asset types

Child models (stocks, etfs, options, futures) FK to dim_security.
"""

from models.domains.securities.securities.model import SecuritiesModel
from models.domains.securities.securities.builder import SecuritiesBuilder

__all__ = ['SecuritiesModel', 'SecuritiesBuilder']
