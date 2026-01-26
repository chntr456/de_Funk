"""
Cook County Data Portal Provider.

Provides data ingestion from Cook County's Socrata Open Data API.
Includes property tax, assessor, and parcel data.

Configuration loaded from markdown documentation (single source of truth):
- Data Sources/Providers/Cook County Data Portal.md
- Data Sources/Endpoints/Cook County Data Portal/*.md

Usage:
    from datapipelines.providers.cook_county import (
        CookCountyProvider,
        create_cook_county_provider,
    )
    from datapipelines.base import IngestorEngine

    provider = create_cook_county_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)
    results = engine.run()
"""

from datapipelines.providers.cook_county.cook_county_provider import (
    CookCountyProvider,
    create_cook_county_provider,
)

__all__ = [
    "CookCountyProvider",
    "create_cook_county_provider",
]
