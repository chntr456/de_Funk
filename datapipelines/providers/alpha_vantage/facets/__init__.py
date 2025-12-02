"""
Alpha Vantage Facets - Transform API responses to normalized schemas.

Facets handle:
- Securities Reference (company overview)
- Securities Prices (daily OHLCV)
- Income Statement
- Balance Sheet
- Cash Flow
- Earnings
- Historical Options
"""
from __future__ import annotations

# Core securities facets (existing)
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import AlphaVantageBaseFacet
from datapipelines.providers.alpha_vantage.facets.securities_reference_facet import SecuritiesReferenceFacetAV
from datapipelines.providers.alpha_vantage.facets.securities_prices_facet import SecuritiesPricesFacetAV

# Financial statement facets (new)
from datapipelines.providers.alpha_vantage.facets.income_statement_facet import IncomeStatementFacet
from datapipelines.providers.alpha_vantage.facets.balance_sheet_facet import BalanceSheetFacet
from datapipelines.providers.alpha_vantage.facets.cash_flow_facet import CashFlowFacet
from datapipelines.providers.alpha_vantage.facets.earnings_facet import EarningsFacet
from datapipelines.providers.alpha_vantage.facets.historical_options_facet import HistoricalOptionsFacet

__all__ = [
    # Base and core facets
    'AlphaVantageBaseFacet',
    'SecuritiesReferenceFacetAV',
    'SecuritiesPricesFacetAV',
    # Financial statements
    'IncomeStatementFacet',
    'BalanceSheetFacet',
    'CashFlowFacet',
    'EarningsFacet',
    # Options
    'HistoricalOptionsFacet',
]
