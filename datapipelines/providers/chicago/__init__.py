"""
Chicago Data Portal Provider.

Provides data ingestion from Chicago's Socrata Open Data API.
Includes finance, public safety, transportation, and housing data.
"""

from datapipelines.providers.chicago.chicago_provider import (
    ChicagoProvider,
    ChicagoProviderConfig,
    create_chicago_provider,
)

__all__ = [
    "ChicagoProvider",
    "ChicagoProviderConfig",
    "create_chicago_provider",
]
