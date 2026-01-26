"""
Chicago Data Portal Provider.

Provides data ingestion from Chicago's Socrata Open Data API.
Includes finance, public safety, transportation, and housing data.

Configuration loaded from markdown documentation (single source of truth):
- Data Sources/Providers/Chicago Data Portal.md
- Data Sources/Endpoints/Chicago Data Portal/*.md

Usage:
    from datapipelines.providers.chicago import (
        ChicagoProvider,
        create_chicago_provider,
    )
    from datapipelines.base import IngestorEngine

    provider = create_chicago_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)
    results = engine.run()
"""

from datapipelines.providers.chicago.chicago_provider import (
    ChicagoProvider,
    create_chicago_provider,
)

__all__ = [
    "ChicagoProvider",
    "create_chicago_provider",
]
