"""
Alpha Vantage Facets - Transform API responses to normalized schemas.

v2.7: Markdown-driven facets - configuration in endpoint frontmatter, not Python code.

Facets handle:
- Securities Reference (company overview)
- Securities Prices (daily OHLCV)
- Financial Statements (income_statement, balance_sheet, cash_flow, earnings) - GENERIC
- Historical Options

The FinancialStatementFacet is fully markdown-driven:
- facet_config.response_arrays: Which arrays to extract (annualReports, etc.)
- facet_config.fixed_fields: Root fields to extract (ticker, fiscal_date_ending)
- schema: Field mappings with {coerce: type} for type casting
- computed_fields: Derived fields like free_cash_flow, beat_estimate
"""
from __future__ import annotations

# Core securities facets (existing)
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet, safe_long, safe_double, safe_string
)
from datapipelines.providers.alpha_vantage.facets.securities_reference_facet import SecuritiesReferenceFacetAV
from datapipelines.providers.alpha_vantage.facets.securities_prices_facet import SecuritiesPricesFacetAV
from datapipelines.providers.alpha_vantage.facets.company_reference_facet import CompanyReferenceFacet

# Generic markdown-driven facet for financial statements (v2.7)
from datapipelines.providers.alpha_vantage.facets.financial_statement_facet import FinancialStatementFacet

# Legacy endpoint-specific facets (kept for backwards compatibility, use FinancialStatementFacet instead)
from datapipelines.providers.alpha_vantage.facets.income_statement_facet import IncomeStatementFacet
from datapipelines.providers.alpha_vantage.facets.balance_sheet_facet import BalanceSheetFacet
from datapipelines.providers.alpha_vantage.facets.cash_flow_facet import CashFlowFacet
from datapipelines.providers.alpha_vantage.facets.earnings_facet import EarningsFacet
from datapipelines.providers.alpha_vantage.facets.historical_options_facet import HistoricalOptionsFacet

__all__ = [
    # Base and core facets
    'AlphaVantageFacet',
    'SecuritiesReferenceFacetAV',
    'SecuritiesPricesFacetAV',
    'CompanyReferenceFacet',
    # Type conversion helpers (for Spark compatibility)
    'safe_long',
    'safe_double',
    'safe_string',
    # Generic markdown-driven facet (preferred)
    'FinancialStatementFacet',
    # Legacy endpoint-specific facets (backwards compatibility)
    'IncomeStatementFacet',
    'BalanceSheetFacet',
    'CashFlowFacet',
    'EarningsFacet',
    # Options
    'HistoricalOptionsFacet',
]
