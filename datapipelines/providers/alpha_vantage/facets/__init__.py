"""
Alpha Vantage Facets - Transform API responses to normalized schemas.

v2.8: Simplified - Provider has inline normalization, facets are optional helpers.

Available Facets:
- AlphaVantageFacet: Base class with AV-specific cleaning (None string handling)
- FinancialStatementFacet: Generic markdown-driven facet for any financial statement

The provider (alpha_vantage_provider.py) has its own normalization logic
and doesn't require these facets. They're available for custom pipelines.
"""
from __future__ import annotations

# Base facet and type conversion helpers
from datapipelines.providers.alpha_vantage.facets.alpha_vantage_base_facet import (
    AlphaVantageFacet, safe_long, safe_double, safe_string
)

# Generic markdown-driven facet for financial statements (v2.7)
# Handles: income_statement, balance_sheet, cash_flow, earnings
from datapipelines.providers.alpha_vantage.facets.financial_statement_facet import FinancialStatementFacet

__all__ = [
    # Base and type helpers
    'AlphaVantageFacet',
    'safe_long',
    'safe_double',
    'safe_string',
    # Generic markdown-driven facet (handles all financial statements)
    'FinancialStatementFacet',
]
