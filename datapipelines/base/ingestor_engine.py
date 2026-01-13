"""
Unified Ingestor Engine.

Provider-agnostic ingestion engine that works with any BaseProvider implementation.
Uses StreamingBronzeWriter for memory-safe writes to Delta Lake.

v2.7 UNIFIED ENGINE (January 2026):
- Single engine for both ticker-based (Alpha Vantage) and endpoint-based (Socrata) providers
- All writes go through StreamingBronzeWriter
- Eliminates duplicate code paths between providers

Usage:
    from datapipelines.base.ingestor_engine import IngestorEngine
    from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider

    provider = create_alpha_vantage_provider(config, spark)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all work items (data types or endpoints)
    results = engine.run()

    # Or specific work items
    results = engine.run(work_items=["prices", "reference"])

Author: de_Funk Team
Date: December 2025
Updated: January 2026 - Unified engine for all provider types
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from datapipelines.base.provider import BaseProvider, WorkItemResult
from datapipelines.ingestors.bronze_sink import BronzeSink
from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResults:
    """Results from an ingestion run."""
    work_items: List[str] = field(default_factory=list)
    total_work_items: int = 0
    completed_work_items: int = 0
    total_records: int = 0
    total_errors: int = 0
    results: Dict[str, WorkItemResult] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def add_result(self, result: WorkItemResult) -> None:
        """Add a work item result."""
        self.results[result.work_item] = result
        self.work_items.append(result.work_item)

        if result.success:
            self.completed_work_items += 1
            self.total_records += result.record_count
        else:
            self.total_errors += 1

    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_work_items": self.total_work_items,
            "completed": self.completed_work_items,
            "failed": self.total_errors,
            "total_records": self.total_records,
            "elapsed_seconds": self.elapsed_seconds,
            "records_per_second": (
                self.total_records / self.elapsed_seconds
                if self.elapsed_seconds > 0 else 0
            ),
        }

    def print_summary(self) -> None:
        """Print human-readable summary."""
        print(f"\n{'=' * 60}")
        print("INGESTION SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Work items: {self.completed_work_items}/{self.total_work_items} completed")
        print(f"  Records: {self.total_records:,}")
        print(f"  Errors: {self.total_errors}")
        print(f"  Time: {self.elapsed_seconds:.1f}s")
        if self.elapsed_seconds > 0:
            print(f"  Throughput: {self.total_records / self.elapsed_seconds:,.0f} records/sec")
        print(f"{'=' * 60}\n")


class IngestorEngine:
    """
    Unified ingestion engine for all provider types.

    Uses the unified BaseProvider interface (v2.7) which abstracts
    both ticker-based and endpoint-based providers behind the same API.

    All writes go through StreamingBronzeWriter for memory-safe
    incremental writes to Delta Lake.

    Example:
        provider = create_chicago_provider(config, storage_cfg, spark)
        engine = IngestorEngine(provider, storage_cfg)

        # Ingest all endpoints
        results = engine.run(write_batch_size=500000)

        # Ingest specific endpoints
        results = engine.run(work_items=["crimes", "building_permits"])
    """

    def __init__(
        self,
        provider: BaseProvider,
        storage_cfg: Dict,
    ):
        """
        Initialize the ingestion engine.

        Args:
            provider: Provider instance implementing unified interface
            storage_cfg: Storage configuration dict
        """
        self.provider = provider
        self.storage_cfg = storage_cfg
        self.sink = BronzeSink(storage_cfg)

    def run(
        self,
        work_items: List[str] = None,
        write_batch_size: int = 500000,
        max_records: Optional[int] = None,
        silent: bool = False,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion for work items.

        Args:
            work_items: List of work items to ingest (None = all from provider)
            write_batch_size: Records to buffer before Delta write (default 500k)
            max_records: Max records per work item (None = no limit)
            silent: Suppress progress output
            **kwargs: Provider-specific options passed to fetch()

        Returns:
            IngestionResults with summary and per-item results
        """
        start_time = time.time()

        # Get work items from provider if not specified
        if work_items is None:
            work_items = self.provider.list_work_items(**kwargs)

        results = IngestionResults(total_work_items=len(work_items))

        if not silent:
            print(f"\n{'=' * 60}")
            print(f"INGESTOR ENGINE: {self.provider.config.name.upper()}")
            print(f"{'=' * 60}")
            print(f"  Work items: {len(work_items)}")
            print(f"  Batch size: {write_batch_size:,} records")
            if max_records:
                print(f"  Max records per item: {max_records:,}")
            print()

        # Process each work item
        for i, work_item in enumerate(work_items):
            if not silent:
                print(f"[{i+1}/{len(work_items)}] {work_item}...", end=" ", flush=True)

            result = self._ingest_work_item(
                work_item=work_item,
                write_batch_size=write_batch_size,
                max_records=max_records,
                **kwargs
            )

            results.add_result(result)

            if not silent:
                if result.success:
                    print(f"✓ {result.record_count:,} records")
                else:
                    print(f"✗ {result.error}")

        results.elapsed_seconds = time.time() - start_time

        if not silent:
            results.print_summary()

        return results

    def _ingest_work_item(
        self,
        work_item: str,
        write_batch_size: int,
        max_records: Optional[int] = None,
        **kwargs
    ) -> WorkItemResult:
        """
        Ingest a single work item using StreamingBronzeWriter.

        Args:
            work_item: Work item identifier
            write_batch_size: Records to buffer before write
            max_records: Max records to fetch
            **kwargs: Provider-specific options

        Returns:
            WorkItemResult with status and record count
        """
        try:
            # Get table configuration from provider
            table_name = self.provider.get_table_name(work_item)
            partitions = self.provider.get_partitions(work_item)

            # Create DataFrame factory using provider's normalize method
            def df_factory(records):
                return self.provider.normalize(records, work_item)

            # Use StreamingBronzeWriter for memory-safe writes
            with self.sink.streaming_writer(
                table=table_name,
                df_factory=df_factory,
                batch_size=write_batch_size,
                partitions=partitions
            ) as writer:
                # Fetch data and stream to writer
                for batch in self.provider.fetch(
                    work_item,
                    max_records=max_records,
                    **kwargs
                ):
                    writer.add_batch(batch)

                total_records = writer.total_records + writer.buffered_records

            return WorkItemResult(
                work_item=work_item,
                success=True,
                record_count=total_records,
                table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
            )

        except Exception as e:
            logger.error(f"Failed to ingest {work_item}: {e}", exc_info=True)
            return WorkItemResult(
                work_item=work_item,
                success=False,
                error=str(e)[:200]
            )

    def run_with_discovery(
        self,
        write_batch_size: int = 500000,
        max_records: Optional[int] = None,
        silent: bool = False,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion with automatic work item discovery.

        Convenience method that calls list_work_items() and then run().

        Args:
            write_batch_size: Records to buffer before write
            max_records: Max records per work item
            silent: Suppress output
            **kwargs: Provider-specific options

        Returns:
            IngestionResults
        """
        return self.run(
            work_items=None,  # Will be discovered
            write_batch_size=write_batch_size,
            max_records=max_records,
            silent=silent,
            **kwargs
        )


def create_engine(
    provider_name: str,
    api_cfg: Dict,
    storage_cfg: Dict,
    spark=None,
    docs_path=None
) -> IngestorEngine:
    """
    Factory function to create an IngestorEngine for any provider.

    All providers now return the same type (IngestorEngine) for consistency.

    Args:
        provider_name: Provider name (e.g., "alpha_vantage", "chicago", "cook_county")
        api_cfg: API configuration dict
        storage_cfg: Storage configuration dict
        spark: SparkSession
        docs_path: Path to Documents folder (for Socrata providers)

    Returns:
        IngestorEngine wrapping the appropriate provider
    """
    if provider_name == "alpha_vantage":
        from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
        provider = create_alpha_vantage_provider(api_cfg, spark)
        return IngestorEngine(provider, storage_cfg)

    elif provider_name in ("chicago", "chicago_data_portal"):
        from datapipelines.providers.chicago.chicago_provider import create_chicago_provider
        provider = create_chicago_provider(api_cfg, storage_cfg, spark, docs_path)
        return IngestorEngine(provider, storage_cfg)

    elif provider_name in ("cook_county", "cook_county_data_portal"):
        from datapipelines.providers.cook_county.cook_county_provider import create_cook_county_provider
        provider = create_cook_county_provider(api_cfg, storage_cfg, spark, docs_path)
        return IngestorEngine(provider, storage_cfg)

    else:
        raise ValueError(f"Unknown provider: {provider_name}")
