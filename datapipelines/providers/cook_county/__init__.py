"""
Cook County Data Portal Provider.

Provides data ingestion from Cook County's Socrata Open Data API.
Includes property tax, assessor, and parcel data.
"""

from datapipelines.providers.cook_county.cook_county_provider import (
    CookCountyProvider,
    CookCountyProviderConfig,
    create_cook_county_provider,
)

__all__ = [
    "CookCountyProvider",
    "CookCountyProviderConfig",
    "create_cook_county_provider",
]
