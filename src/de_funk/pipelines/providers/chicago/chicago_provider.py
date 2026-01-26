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
    from de_funk.pipelines.providers.chicago import create_chicago_provider
    from de_funk.pipelines.base.ingestor_engine import IngestorEngine

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

from de_funk.pipelines.base.socrata_provider import SocrataBaseProvider
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class ChicagoProvider(SocrataBaseProvider):
    """
    Provider for Chicago Data Portal (Socrata API).

    Inherits all functionality from SocrataBaseProvider.
    Configuration loaded from:
    - Data Sources/Providers/Chicago Data Portal.md
    - Data Sources/Endpoints/Chicago Data Portal/*.md
    """

    PROVIDER_NAME = "Chicago Data Portal"

    def __init__(
        self,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None,
        preserve_raw: bool = False,
        load_from_raw: bool = False
    ):
        """
        Initialize Chicago provider.

        Args:
            spark: SparkSession
            docs_path: Path to repo root
            storage_path: Path to storage root (for raw layer)
            preserve_raw: If True, keep raw CSV files after Bronze write
            load_from_raw: If True, skip download and load from existing raw CSVs
        """
        super().__init__(
            provider_id="chicago",
            spark=spark,
            docs_path=docs_path,
            storage_path=storage_path,
            preserve_raw=preserve_raw,
            load_from_raw=load_from_raw
        )


def create_chicago_provider(
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None,
    preserve_raw: bool = False,
    load_from_raw: bool = False
) -> ChicagoProvider:
    """
    Factory function to create a ChicagoProvider.

    Args:
        spark: SparkSession
        docs_path: Path to repo root
        storage_path: Path to storage root (for raw layer)
        preserve_raw: If True, keep raw CSV files after Bronze write
        load_from_raw: If True, skip download and load from existing raw CSVs

    Returns:
        Configured ChicagoProvider
    """
    return ChicagoProvider(
        spark=spark,
        docs_path=docs_path,
        storage_path=storage_path,
        preserve_raw=preserve_raw,
        load_from_raw=load_from_raw
    )
