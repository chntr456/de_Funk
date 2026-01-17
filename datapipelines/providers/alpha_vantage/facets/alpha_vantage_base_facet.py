"""
Alpha Vantage Base Facet - Thin wrapper over base Facet for AV-specific cleaning.

v2.8: Simplified - All markdown loading is now in base Facet class.
This class only adds Alpha Vantage-specific data cleaning:
- Handle literal "None" strings (AV returns "None" instead of null)

All schema, coercion, field mappings come from endpoint markdown.

Usage:
    class MyAVFacet(AlphaVantageFacet):
        ENDPOINT_ID = "balance_sheet"
        # That's it! Config comes from markdown.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from datapipelines.base.facet import Facet


# ---------- Safe type conversion helpers ----------
# Kept for backwards compatibility with existing facets

def safe_long(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python int or None.

    Avoids Spark CANNOT_DETERMINE_TYPE errors by using Python native types
    instead of pandas Int64/float64 which fail when all values are NaN.
    """
    if series is None:
        return []
    return [int(x) if pd.notna(x) else None for x in pd.to_numeric(series, errors='coerce')]


def safe_double(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python float or None.

    Avoids Spark CANNOT_DETERMINE_TYPE errors by using Python native types.
    """
    if series is None:
        return []
    return [float(x) if pd.notna(x) else None for x in pd.to_numeric(series, errors='coerce')]


def safe_string(series: pd.Series) -> list:
    """
    Convert pandas Series to list of Python str or None.
    """
    if series is None:
        return []
    return [str(x) if pd.notna(x) and str(x) != 'None' else None for x in series]


class AlphaVantageFacet(Facet):
    """
    Base facet for Alpha Vantage data providers.

    Adds Alpha Vantage-specific data cleaning to the base Facet:
    - Handle literal "None" strings (AV returns "None" instead of null)
    - Handle "N/A" and "-" markers

    All configuration (schema, coercion, field mappings) comes from
    endpoint markdown frontmatter via the base Facet class.

    Attributes:
        PROVIDER_ID: Set to "alpha_vantage" by default
        ENDPOINT_ID: Override in subclass to load endpoint-specific config

    Usage:
        class BalanceSheetFacet(AlphaVantageFacet):
            ENDPOINT_ID = "balance_sheet"
            # That's it! All config comes from markdown.

        facet = BalanceSheetFacet(spark)
        df = facet.normalize(raw_data)
    """

    PROVIDER_ID = "alpha_vantage"

    def __init__(self, spark, tickers=None, date_from=None, date_to=None, **kwargs):
        """
        Initialize Alpha Vantage facet.

        Args:
            spark: SparkSession
            tickers: List of ticker symbols (optional, for legacy facets)
            date_from: Start date for time series (optional, for legacy facets)
            date_to: End date for time series (optional, for legacy facets)
            **kwargs: Additional parameters (endpoint_id, etc.)
        """
        # Pass endpoint_id if provided in kwargs
        endpoint_id = kwargs.pop('endpoint_id', None) or self.ENDPOINT_ID
        super().__init__(spark, provider_id=self.PROVIDER_ID, endpoint_id=endpoint_id, **kwargs)

        # Legacy attributes for backwards compatibility
        self.tickers = tickers or []
        self.date_from = date_from
        self.date_to = date_to
        self.extra = kwargs

    def _clean_raw_value(self, value: Any) -> Any:
        """
        Clean a single raw value from Alpha Vantage API response.

        Alpha Vantage-specific handling:
        - Literal "None" string -> None (AV returns "None" for missing values)
        - "N/A", "-", empty string -> None
        - Strip whitespace from strings
        """
        if value is None:
            return None

        if isinstance(value, str):
            cleaned = value.strip()
            # Alpha Vantage returns literal "None" for missing values
            if cleaned in ("None", "N/A", "-", ""):
                return None
            return cleaned

        return value
