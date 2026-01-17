"""
Alpha Vantage Facets - Transform API responses to normalized schemas.

v2.7: Markdown-driven facets - configuration in endpoint frontmatter, not Python code.

Facets handle:
- Securities Reference (company overview)
- Securities Prices (daily OHLCV)
- Financial Statements (income_statement, balance_sheet, cash_flow, earnings) - via FinancialStatementFacet
- Historical Options

The FinancialStatementFacet is fully markdown-driven:
- facet_config.response_arrays: Which arrays to extract (annualReports, etc.)
- facet_config.fixed_fields: Root fields to extract (ticker, fiscal_date_ending)
- schema: Field mappings with {coerce: type} for type casting
- computed_fields: Derived fields like free_cash_flow, beat_estimate
"""
from __future__ import annotations

# Base facet and type conversion helpers
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet, safe_long, safe_double, safe_string
)

# Core securities facets
from datapipelines.providers.alpha_vantage.facets.securities_reference_facet import SecuritiesReferenceFacetAV
from datapipelines.providers.alpha_vantage.facets.securities_prices_facet import SecuritiesPricesFacetAV
from datapipelines.providers.alpha_vantage.facets.company_reference_facet import CompanyReferenceFacet

# Generic markdown-driven facet for financial statements (v2.7)
# Handles: income_statement, balance_sheet, cash_flow, earnings
from datapipelines.providers.alpha_vantage.facets.financial_statement_facet import FinancialStatementFacet

# Options facet
from datapipelines.providers.alpha_vantage.facets.historical_options_facet import HistoricalOptionsFacet

__all__ = [
    # Base and type helpers
    'AlphaVantageFacet',
    'safe_long',
    'safe_double',
    'safe_string',
    # Core facets
    'SecuritiesReferenceFacetAV',
    'SecuritiesPricesFacetAV',
    'CompanyReferenceFacet',
    # Generic markdown-driven facet (handles all financial statements)
    'FinancialStatementFacet',
    # Options
    'HistoricalOptionsFacet',
]
