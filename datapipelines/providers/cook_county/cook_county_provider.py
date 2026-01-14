"""
Cook County Data Portal Provider Implementation.

Implements data ingestion from Cook County's Socrata Open Data API.
Configuration loaded from markdown documentation (single source of truth).

Features:
- Offset-based pagination for large datasets
- SoQL query support ($where, $select, $order, etc.)
- Rate limiting with app token support
- Schema-driven transformation using markdown configs
- PIN-based property lookups

Usage:
    from datapipelines.providers.cook_county import create_cook_county_provider
    from datapipelines.base.ingestor_engine import IngestorEngine

    provider = create_cook_county_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all endpoints
    results = engine.run(write_batch_size=500000)

    # Ingest specific endpoints
    results = engine.run(work_items=["property_locations", "assessments"])

Author: de_Funk Team
"""

from __future__ import annotations

from typing import Dict, List, Optional, Generator
from pathlib import Path

from datapipelines.base.socrata_provider import SocrataBaseProvider
from config.logging import get_logger

logger = get_logger(__name__)


class CookCountyProvider(SocrataBaseProvider):
    """
    Provider for Cook County Data Portal (Socrata API).

    Inherits all functionality from SocrataBaseProvider.
    Configuration loaded from:
    - Documents/Data Sources/Providers/Cook County Data Portal.md
    - Documents/Data Sources/Endpoints/Cook County Data Portal/*.md
    """

    PROVIDER_NAME = "Cook County Data Portal"

    def __init__(
        self,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize Cook County provider.

        Args:
            spark: SparkSession
            docs_path: Path to Documents folder
            storage_path: Path to storage root (for raw layer)
        """
        super().__init__(
            provider_id="cook_county",
            spark=spark,
            docs_path=docs_path,
            storage_path=storage_path
        )

    # =========================================================================
    # COOK COUNTY SPECIFIC: PIN-BASED LOOKUPS
    # =========================================================================

    def fetch_parcel_data(
        self,
        pins: Optional[List[str]] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch parcel data for specific PINs.

        This is a convenience method for property-specific lookups.

        Args:
            pins: List of Property Index Numbers (PINs)
            **kwargs: Additional query parameters

        Yields:
            List[Dict] - Batches of parcel records
        """
        if not pins:
            return

        endpoint = self._endpoints.get("property_locations")
        if not endpoint:
            logger.warning("property_locations endpoint not configured")
            return

        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            return

        # Build PIN filter
        pin_list = ",".join(f"'{p}'" for p in pins)
        params = {"$where": f"pin IN ({pin_list})"}

        for batch in self.client.fetch_all(
            resource_id=resource_id,
            query_params=params,
            limit=self._default_limit
        ):
            yield batch


def create_cook_county_provider(
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None
) -> CookCountyProvider:
    """
    Factory function to create a CookCountyProvider.

    Args:
        spark: SparkSession
        docs_path: Path to Documents folder
        storage_path: Path to storage root (for raw layer)

    Returns:
        Configured CookCountyProvider
    """
    return CookCountyProvider(spark=spark, docs_path=docs_path, storage_path=storage_path)
