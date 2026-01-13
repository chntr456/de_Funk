"""
Chicago Data Portal Provider Implementation.

Implements data ingestion from Chicago's Socrata Open Data API.
Configuration loaded from markdown documentation (single source of truth).

Features:
- Offset-based pagination for large datasets
- SoQL query support ($where, $select, $order, etc.)
- Rate limiting with app token support
- Schema-driven transformation using markdown configs

Usage:
    from datapipelines.providers.chicago import create_chicago_provider
    from datapipelines.base.ingestor_engine import IngestorEngine

    provider = create_chicago_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all endpoints
    results = engine.run(write_batch_size=500000)

    # Ingest specific endpoints
    results = engine.run(work_items=["crimes", "building_permits"])

Author: de_Funk Team
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

from datapipelines.base.socrata_provider import SocrataBaseProvider
from config.logging import get_logger

logger = get_logger(__name__)


class ChicagoProvider(SocrataBaseProvider):
    """
    Provider for Chicago Data Portal (Socrata API).

    Inherits all functionality from SocrataBaseProvider.
    Configuration loaded from:
    - Documents/Data Sources/Providers/Chicago Data Portal.md
    - Documents/Data Sources/Endpoints/Chicago Data Portal/*.md
    """

    PROVIDER_NAME = "Chicago Data Portal"

    def __init__(
        self,
        spark=None,
        docs_path: Optional[Path] = None
    ):
        """
        Initialize Chicago provider.

        Args:
            spark: SparkSession
            docs_path: Path to Documents folder
        """
        super().__init__(
            provider_id="chicago",
            spark=spark,
            docs_path=docs_path
        )


def create_chicago_provider(
    spark=None,
    docs_path: Optional[Path] = None
) -> ChicagoProvider:
    """
    Factory function to create a ChicagoProvider.

    Args:
        spark: SparkSession
        docs_path: Path to Documents folder

    Returns:
        Configured ChicagoProvider
    """
    return ChicagoProvider(spark=spark, docs_path=docs_path)
