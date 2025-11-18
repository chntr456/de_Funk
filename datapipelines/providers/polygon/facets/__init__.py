"""
Polygon Data Facets

This module contains facets for normalizing Polygon.io API responses into
standardized bronze layer tables.

Architecture v2.0 Facets:
- SecuritiesReferenceFacet: Unified reference data with CIK extraction
- SecuritiesPricesFacet: Unified OHLCV daily prices for all asset types

Legacy Facets (v1.x):
- RefTickerFacet: Individual ticker reference (deprecated, use SecuritiesReferenceFacet)
- RefAllTickersFacet: Bulk ticker reference (deprecated, use SecuritiesReferenceFacet)
- PricesDailyFacet: Daily prices (deprecated, use SecuritiesPricesFacet)
- PricesDailyGroupedFacet: Grouped daily prices (deprecated, use SecuritiesPricesFacet)
- ExchangeFacet: Exchange reference data
- NewsByDateFacet: News articles by date
"""

# v2.0 Unified Facets
from .securities_reference_facet import SecuritiesReferenceFacet
from .securities_prices_facet import SecuritiesPricesFacet

# Legacy Facets (v1.x)
from .ref_ticker_facet import RefTickerFacet
from .ref_all_tickers_facet import RefAllTickersFacet
from .prices_daily_facet import PricesDailyFacet
from .prices_daily_grouped_facet import PricesDailyGroupedFacet
from .exchange_facet import ExchangeFacet
from .news_by_date_facet import NewsByDateFacet

# Base
from .polygon_base_facet import PolygonFacet

__all__ = [
    # v2.0 Unified Facets
    'SecuritiesReferenceFacet',
    'SecuritiesPricesFacet',

    # Legacy Facets
    'RefTickerFacet',
    'RefAllTickersFacet',
    'PricesDailyFacet',
    'PricesDailyGroupedFacet',
    'ExchangeFacet',
    'NewsByDateFacet',

    # Base
    'PolygonFacet',
]
