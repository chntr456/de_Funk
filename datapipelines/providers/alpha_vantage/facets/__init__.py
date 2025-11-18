"""
Alpha Vantage Data Facets

This module contains facets for normalizing Alpha Vantage API responses into
standardized bronze layer tables.

Alpha Vantage provides:
- Stock time series (daily, intraday, weekly, monthly)
- Company fundamentals (OVERVIEW endpoint)
- Technical indicators (SMA, RSI, MACD, etc.)
- Forex, crypto, and commodities data

Key Differences from Polygon:
- Lower rate limits (5 calls/min for free tier)
- No CIK field (SEC identifiers not provided)
- Nested JSON response format
- Full history in single call (vs paginated)
- Different field naming conventions

v2.0 Unified Facets:
- SecuritiesReferenceFacetAV: Company overview -> securities_reference
- SecuritiesPricesFacetAV: Time series daily -> securities_prices_daily
"""

from .securities_reference_facet import SecuritiesReferenceFacetAV
from .securities_prices_facet import SecuritiesPricesFacetAV
from .alpha_vantage_base_facet import AlphaVantageFacet

__all__ = [
    'SecuritiesReferenceFacetAV',
    'SecuritiesPricesFacetAV',
    'AlphaVantageFacet',
]
