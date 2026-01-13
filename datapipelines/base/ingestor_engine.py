"""
Unified Ingestor Engine with Async Writes.

Provider-agnostic ingestion engine that decouples fetching from writing
using a ThreadPoolExecutor for parallel I/O. This improves throughput
by overlapping API fetches with Delta Lake writes.

Architecture:
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   Fetch Thread  │───▶│  In-Memory Queue │───▶│  Writer Thread  │
    │   (API calls)   │    │  (bounded, ~3)   │    │  (Delta writes) │
    └─────────────────┘    └──────────────────┘    └─────────────────┘

Benefits:
    - ~2-3x throughput improvement (fetch + write overlap)
    - Backpressure prevents OOM (bounded pending writes)
    - Reusable pattern for Airflow migration
    - Same interface as synchronous version

Usage:
    from datapipelines.base.ingestor_engine import IngestorEngine
    from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider

    provider = create_alpha_vantage_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all work items (data types or endpoints)
    results = engine.run()

    # Or specific work items
    results = engine.run(work_items=["prices", "reference"])

Author: de_Funk Team
"""

from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from queue import Queue, Empty

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


@dataclass
class WriteTask:
    """A queued write task."""
    df: Any  # Spark DataFrame
    table_name: str
    partitions: Optional[List[str]]
    record_count: int
    work_item: str


class IngestorEngine:
    """
    Unified ingestion engine with async writes.

    Decouples data fetching from Delta Lake writes using a ThreadPoolExecutor.
    This allows fetching the next batch while the previous batch is being written,
    improving throughput by 2-3x for I/O bound workloads.

    Features:
        - Async writes via ThreadPoolExecutor
        - Bounded queue with backpressure (prevents OOM)
        - Same interface as synchronous version
        - Reusable pattern for Airflow migration

    Example:
        provider = create_chicago_provider(spark, docs_path)
        engine = IngestorEngine(provider, storage_cfg)

        # Ingest all endpoints with async writes
        results = engine.run(write_batch_size=500000)
    """

    # Class-level executor shared across instances (reusable for Airflow)
    _executor: Optional[ThreadPoolExecutor] = None
    _executor_lock = threading.Lock()

    def __init__(
        self,
        provider: BaseProvider,
        storage_cfg: Dict,
        max_pending_writes: int = 3,
        writer_threads: int = 2,
    ):
        """
        Initialize the ingestion engine.

        Args:
            provider: Provider instance implementing BaseProvider interface
            storage_cfg: Storage configuration dict
            max_pending_writes: Max writes to queue before blocking (backpressure)
            writer_threads: Number of writer threads in pool
        """
        self.provider = provider
        self.storage_cfg = storage_cfg
        self.sink = BronzeSink(storage_cfg)
        self.max_pending_writes = max_pending_writes
        self.writer_threads = writer_threads

        # Track pending writes per work item
        self._pending_futures: List[Future] = []
        self._write_errors: List[str] = []

    @classmethod
    def get_executor(cls, max_workers: int = 2) -> ThreadPoolExecutor:
        """
        Get or create shared ThreadPoolExecutor.

        Shared across all IngestorEngine instances for efficiency.
        Can be reused when migrating to Airflow workers.

        Args:
            max_workers: Number of writer threads

        Returns:
            ThreadPoolExecutor instance
        """
        with cls._executor_lock:
            if cls._executor is None or cls._executor._shutdown:
                cls._executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="delta_writer"
                )
                logger.info(f"Created shared ThreadPoolExecutor with {max_workers} workers")
            return cls._executor

    @classmethod
    def shutdown_executor(cls, wait: bool = True) -> None:
        """Shutdown the shared executor."""
        with cls._executor_lock:
            if cls._executor is not None:
                cls._executor.shutdown(wait=wait)
                cls._executor = None
                logger.info("Shutdown shared ThreadPoolExecutor")

    def run(
        self,
        work_items: List[str] = None,
        write_batch_size: int = 500000,
        max_records: Optional[int] = None,
        silent: bool = False,
        async_writes: bool = True,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion for work items.

        Args:
            work_items: List of work items to ingest (None = all from provider)
            write_batch_size: Records to buffer before each Delta write (default 500k).
                Used in both sync and async modes to keep memory bounded.
            max_records: Max records per work item (None = no limit)
            silent: Suppress progress output
            async_writes: Enable async writes (default True for ~2-3x throughput).
                Async mode overlaps fetch with write operations using chunked writes.
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
            print(f"INGESTOR ENGINE: {self.provider.provider_id.upper()}")
            print(f"{'=' * 60}")
            print(f"  Work items: {len(work_items)}")
            print(f"  Mode: {'async (chunked)' if async_writes else 'sync'}")
            print(f"  Batch size: {write_batch_size:,} records")
            if max_records:
                print(f"  Max records per item: {max_records:,}")
            print()

        # Process each work item
        for i, work_item in enumerate(work_items):
            if not silent:
                print(f"[{i+1}/{len(work_items)}] {work_item}...", end=" ", flush=True)

            if async_writes:
                result = self._ingest_work_item_async(
                    work_item=work_item,
                    write_batch_size=write_batch_size,
                    max_records=max_records,
                    **kwargs
                )
            else:
                result = self._ingest_work_item_sync(
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

        # Wait for all pending async writes to complete
        if async_writes and self._pending_futures:
            if not silent:
                print("Waiting for async writes to complete...", end=" ", flush=True)
            write_errors = []
            for future in self._pending_futures:
                try:
                    future.result()
                except Exception as e:
                    write_errors.append(str(e)[:100])
                    logger.error(f"Async write failed: {e}")
            self._pending_futures = []

            if write_errors:
                if not silent:
                    print(f"✗ {len(write_errors)} write errors")
                results.total_errors += len(write_errors)
            else:
                if not silent:
                    print("✓")

        results.elapsed_seconds = time.time() - start_time

        if not silent:
            results.print_summary()

        return results

    def _wait_for_pending_writes(self, max_pending: int = None) -> None:
        """
        Wait until pending writes are below threshold (backpressure).

        Args:
            max_pending: Max pending writes to allow (None = wait for all)
        """
        if max_pending is None:
            max_pending = 0

        # Clean up completed futures
        self._pending_futures = [f for f in self._pending_futures if not f.done()]

        # Wait if too many pending
        while len(self._pending_futures) > max_pending:
            # Check for any errors in completed futures
            completed = [f for f in self._pending_futures if f.done()]
            for f in completed:
                try:
                    f.result()  # Raises if write failed
                except Exception as e:
                    self._write_errors.append(str(e))
                    logger.error(f"Async write failed: {e}")

            self._pending_futures = [f for f in self._pending_futures if not f.done()]

            if len(self._pending_futures) > max_pending:
                time.sleep(0.1)

    def _async_write(
        self,
        df,
        table_name: str,
        partitions: Optional[List[str]],
        mode: str = "overwrite"
    ) -> int:
        """
        Write DataFrame to Delta Lake (runs in background thread).

        Args:
            df: Spark DataFrame to write
            table_name: Target table name
            partitions: Partition columns
            mode: Write mode - "overwrite" or "append"

        Returns:
            Number of records written
        """
        count = df.count()
        if mode == "append":
            self.sink.append(df, table_name, partitions=partitions)
        else:
            self.sink.overwrite(df, table_name, partitions=partitions)
        logger.info(f"Wrote {table_name}: {count:,} records (mode={mode})")
        return count

    def _ingest_work_item_async(
        self,
        work_item: str,
        write_batch_size: int,
        max_records: Optional[int] = None,
        **kwargs
    ) -> WorkItemResult:
        """
        Ingest a single work item with chunked async writes.

        Collects records up to write_batch_size, queues async write, continues.
        Memory stays bounded while overlapping fetch and write operations.

        Args:
            work_item: Work item identifier
            write_batch_size: Records to buffer before each write
            max_records: Max records to fetch
            **kwargs: Provider-specific options

        Returns:
            WorkItemResult with status and record count
        """
        try:
            # Get table configuration from provider
            table_name = self.provider.get_table_name(work_item)
            partitions = self.provider.get_partitions(work_item)

            # Get shared executor
            executor = self.get_executor(self.writer_threads)

            # Reset write errors for this work item
            self._write_errors = []

            # Track state for chunked writes
            buffer = []
            total_records = 0
            chunk_count = 0
            validated_partitions = None  # Cache validated partitions after first chunk

            for batch in self.provider.fetch(
                work_item,
                max_records=max_records,
                **kwargs
            ):
                buffer.extend(batch)

                # When buffer reaches batch size, write it
                if len(buffer) >= write_batch_size:
                    # Wait for backpressure before queueing more writes
                    self._wait_for_pending_writes(self.max_pending_writes)

                    # Normalize buffer to DataFrame
                    df = self.provider.normalize(buffer, work_item)

                    # Validate partitions on first chunk only
                    if validated_partitions is None:
                        validated_partitions = self._validate_partitions(
                            partitions, df.columns, work_item
                        )

                    # First chunk overwrites, subsequent chunks append
                    mode = "overwrite" if chunk_count == 0 else "append"

                    # Queue async write
                    future = executor.submit(
                        self._async_write,
                        df,
                        table_name,
                        validated_partitions,
                        mode
                    )
                    self._pending_futures.append(future)

                    total_records += len(buffer)
                    chunk_count += 1
                    logger.info(
                        f"{work_item}: queued chunk {chunk_count} "
                        f"({len(buffer):,} records, mode={mode})"
                    )

                    # Clear buffer for next chunk
                    buffer = []

            # Write any remaining records in buffer
            if buffer:
                self._wait_for_pending_writes(self.max_pending_writes)

                df = self.provider.normalize(buffer, work_item)

                if validated_partitions is None:
                    validated_partitions = self._validate_partitions(
                        partitions, df.columns, work_item
                    )

                mode = "overwrite" if chunk_count == 0 else "append"

                future = executor.submit(
                    self._async_write,
                    df,
                    table_name,
                    validated_partitions,
                    mode
                )
                self._pending_futures.append(future)

                total_records += len(buffer)
                chunk_count += 1
                logger.info(
                    f"{work_item}: queued final chunk {chunk_count} "
                    f"({len(buffer):,} records, mode={mode})"
                )

            if total_records == 0:
                return WorkItemResult(
                    work_item=work_item,
                    success=True,
                    record_count=0,
                    table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
                )

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

    def _validate_partitions(
        self,
        partitions: Optional[List[str]],
        df_columns: List[str],
        work_item: str
    ) -> Optional[List[str]]:
        """Validate partition columns exist in DataFrame schema."""
        if not partitions:
            return None

        df_columns_set = set(df_columns)
        valid_partitions = [p for p in partitions if p in df_columns_set]

        if valid_partitions != partitions:
            missing = set(partitions) - set(valid_partitions)
            logger.warning(
                f"Partition columns {missing} not found in {work_item} schema, "
                f"using {valid_partitions or 'no partitions'}"
            )

        return valid_partitions if valid_partitions else None

    def _ingest_work_item_sync(
        self,
        work_item: str,
        write_batch_size: int,
        max_records: Optional[int] = None,
        **kwargs
    ) -> WorkItemResult:
        """
        Ingest a single work item synchronously (original behavior).

        Uses StreamingBronzeWriter for memory-safe writes.
        Kept for compatibility and debugging.

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
    storage_cfg: Dict,
    spark=None,
    docs_path: Optional[Path] = None,
    max_pending_writes: int = 3,
    writer_threads: int = 2,
) -> IngestorEngine:
    """
    Factory function to create an IngestorEngine for any provider.

    Configuration is loaded from markdown documentation (single source of truth).

    Args:
        provider_name: Provider name (e.g., "alpha_vantage", "chicago", "cook_county")
        storage_cfg: Storage configuration dict
        spark: SparkSession
        docs_path: Path to Documents folder
        max_pending_writes: Max writes to queue before blocking
        writer_threads: Number of writer threads

    Returns:
        IngestorEngine wrapping the appropriate provider
    """
    if provider_name == "alpha_vantage":
        from datapipelines.providers.alpha_vantage.alpha_vantage_provider import (
            create_alpha_vantage_provider
        )
        provider = create_alpha_vantage_provider(spark, docs_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    elif provider_name in ("chicago", "chicago_data_portal"):
        from datapipelines.providers.chicago.chicago_provider import (
            create_chicago_provider
        )
        provider = create_chicago_provider(spark, docs_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    elif provider_name in ("cook_county", "cook_county_data_portal"):
        from datapipelines.providers.cook_county.cook_county_provider import (
            create_cook_county_provider
        )
        provider = create_cook_county_provider(spark, docs_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    else:
        raise ValueError(f"Unknown provider: {provider_name}")
