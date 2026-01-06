"""
Generic Ingestor Engine.

Provider-agnostic ingestion engine that works with any BaseProvider implementation.
Uses BatchProgressTracker for clean progress display and MetricsCollector for timing.

Usage:
    from datapipelines.base.ingestor_engine import IngestorEngine
    from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider

    provider = create_alpha_vantage_provider(alpha_vantage_cfg, spark)
    engine = IngestorEngine(provider, storage_cfg)

    results = engine.run(
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        data_types=[DataType.REFERENCE, DataType.PRICES],
        batch_size=20
    )

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import Dict, List, Optional, Any

from datapipelines.base.provider import BaseProvider, DataType, TickerData
from datapipelines.base.progress_tracker import BatchProgressTracker
from datapipelines.base.metrics import MetricsCollector
from datapipelines.ingestors.bronze_sink import BronzeSink
from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionError:
    """Detailed error information from ingestion."""
    ticker: str
    data_type: str
    step: str  # 'fetch', 'normalize', 'write'
    error_type: str
    error_message: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class IngestionResults:
    """Results from an ingestion run."""
    tickers: List[str] = field(default_factory=list)
    total_tickers: int = 0
    completed_tickers: int = 0
    total_errors: int = 0
    tables_written: Dict[str, str] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[IngestionError] = field(default_factory=list)

    def add_error(
        self,
        ticker: str,
        data_type: str,
        step: str,
        error: Exception
    ) -> None:
        """Add an error to the error log."""
        self.errors.append(IngestionError(
            ticker=ticker,
            data_type=data_type,
            step=step,
            error_type=type(error).__name__,
            error_message=str(error)[:200]
        ))
        self.total_errors += 1

    def print_error_summary(self) -> None:
        """Print a summary of errors encountered."""
        if not self.errors:
            return

        print(f"\n{'=' * 70}")
        print("ERROR SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total errors: {len(self.errors)}")

        # Group by step first
        by_step = {}
        for err in self.errors:
            by_step.setdefault(err.step, []).append(err)

        for step, step_errs in by_step.items():
            print(f"\n  {step.upper()} errors ({len(step_errs)}):")

            # Group by data type within step
            by_data_type = {}
            for err in step_errs:
                by_data_type.setdefault(err.data_type, []).append(err)

            for data_type, dt_errs in by_data_type.items():
                # Group by error message (more useful than exception type)
                by_message = {}
                for err in dt_errs:
                    # Use first 60 chars of message as key
                    msg_key = err.error_message[:60]
                    by_message.setdefault(msg_key, []).append(err)

                print(f"    {data_type} ({len(dt_errs)} errors):")
                for msg, msg_errs in by_message.items():
                    sample_tickers = list(set(e.ticker for e in msg_errs))[:5]
                    print(f"      - \"{msg}\"")
                    print(f"        Tickers: {', '.join(sample_tickers)}")

        print(f"\n{'=' * 70}")


class IngestorEngine:
    """
    Generic ingestion engine that works with any BaseProvider.

    Features:
    - Provider-agnostic design
    - Batch-based processing with configurable size
    - Clean progress display with BatchProgressTracker
    - Performance timing with MetricsCollector
    - Per-ticker vertical ingestion (all data for ticker 1, then ticker 2)
    """

    def __init__(
        self,
        provider: BaseProvider,
        storage_cfg: Dict,
        include_company_reference: bool = True
    ):
        """
        Initialize the ingestion engine.

        Args:
            provider: Provider instance (e.g., AlphaVantageProvider)
            storage_cfg: Storage configuration dict
            include_company_reference: Also write company_reference table
        """
        self.provider = provider
        self.storage_cfg = storage_cfg
        self.include_company_reference = include_company_reference
        self.sink = BronzeSink(storage_cfg)

    def run(
        self,
        tickers: List[str],
        data_types: List[DataType] = None,
        batch_size: int = 20,
        silent: bool = False,
        auto_compact: bool = True,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion for a list of tickers.

        Args:
            tickers: List of ticker symbols to ingest
            data_types: Data types to fetch (default: all supported by provider)
            batch_size: Number of tickers per batch (default: 20)
            silent: Suppress progress output
            auto_compact: Run Delta OPTIMIZE after ingestion (default: True for prototyping)
            **kwargs: Provider-specific options (date_from, date_to, outputsize, etc)

        Returns:
            IngestionResults with summary and paths
        """
        # Default to all supported data types
        if data_types is None:
            data_types = self.provider.get_supported_data_types()

        total_tickers = len(tickers)
        num_batches = (total_tickers + batch_size - 1) // batch_size

        if not silent:
            print(f"\n{'=' * 80}")
            print(f"INGESTION ENGINE: {self.provider.config.name.upper()}")
            print(f"{'=' * 80}")
            print(f"  Tickers: {total_tickers}")
            print(f"  Data types: {', '.join(dt.value for dt in data_types)}")
            print(f"  Batch size: {batch_size} ({num_batches} batches)")
            print()

        # Initialize tracking
        metrics = MetricsCollector(name=f"{self.provider.config.name}_ingestion")

        # Convert DataType enums to strings for tracker
        data_type_names = [dt.value for dt in data_types]

        tracker = BatchProgressTracker(
            total_tickers=total_tickers,
            batch_size=batch_size,
            data_types=data_type_names,
            silent=silent
        )

        # Initialize results
        results = IngestionResults(total_tickers=total_tickers)

        # Accumulators for each data type
        accumulators: Dict[DataType, List] = {dt: [] for dt in data_types}
        company_ref_dfs = []  # Special accumulator for company reference

        # Process in batches
        for batch_idx in range(0, total_tickers, batch_size):
            batch_num = batch_idx // batch_size + 1
            batch_tickers = tickers[batch_idx:batch_idx + batch_size]

            # Start batch in tracker
            tracker.start_batch(batch_num, num_batches, batch_tickers)

            # Process each ticker in batch
            for ticker in batch_tickers:
                # Fetch all data for this ticker (aggregate by step type, not per-ticker)
                with metrics.time("fetch"):
                    ticker_data = self.provider.fetch_ticker_data(
                        ticker=ticker,
                        data_types=data_types,
                        progress_callback=lambda t, dt, s, e: tracker.update(t, dt.value, s, e),
                        **kwargs
                    )

                # Capture fetch errors from ticker_data
                for error_msg in ticker_data.errors:
                    # Parse error format "data_type: error_message"
                    if ": " in error_msg:
                        dt_str, err_str = error_msg.split(": ", 1)
                        results.add_error(ticker, dt_str, "fetch", Exception(err_str))
                    else:
                        results.add_error(ticker, "unknown", "fetch", Exception(error_msg))

                # Normalize and accumulate (aggregate by step type)
                with metrics.time("normalize"):
                    self._normalize_and_accumulate(
                        ticker_data, data_types, accumulators, company_ref_dfs, results
                    )

                results.tickers.append(ticker)
                tracker.complete_ticker(ticker)

            # Write batch to storage
            with metrics.time("write_batch"):
                write_start = time.time()
                self._write_batch(accumulators, company_ref_dfs, results)
                write_time_ms = (time.time() - write_start) * 1000
                tracker.complete_batch(write_time_ms=write_time_ms)

            # Clear accumulators
            for dt in data_types:
                accumulators[dt].clear()
            company_ref_dfs.clear()
            gc.collect()

        # Finalize
        final_stats = tracker.finish()
        results.stats = final_stats
        results.completed_tickers = len(results.tickers)
        # Combine errors from tracker stats and our internal error log
        tracker_errors = final_stats.get('total_errors', 0)
        results.total_errors = max(tracker_errors, len(results.errors))

        # Print metrics report
        if not silent:
            print()
            metrics.print_report()

        results.metrics = metrics.summary()

        # Print error summary if there were errors
        if not silent and results.errors:
            results.print_error_summary()

        # Auto-compact Delta tables to prevent file fragmentation
        if auto_compact and results.tables_written:
            self._compact_tables(results.tables_written, silent)

        return results

    def _compact_tables(self, tables_written: Dict[str, str], silent: bool = False) -> None:
        """
        Compact Delta tables after ingestion to prevent file fragmentation.

        Runs Delta OPTIMIZE on each written table to merge small files.

        Args:
            tables_written: Dict of table_name -> path
            silent: Suppress output
        """
        from delta.tables import DeltaTable

        if not silent:
            print(f"\n{'=' * 60}")
            print("COMPACTING DELTA TABLES")
            print(f"{'=' * 60}")

        spark = self.provider.spark

        for table_name, path in tables_written.items():
            try:
                if not silent:
                    print(f"  Compacting {table_name}...")

                # Check if it's a Delta table
                delta_log = Path(path) / "_delta_log"
                if not delta_log.exists():
                    if not silent:
                        print(f"    Skipped (not Delta)")
                    continue

                # Run OPTIMIZE (compaction)
                dt = DeltaTable.forPath(spark, path)
                dt.optimize().executeCompaction()

                if not silent:
                    print(f"    ✓ Compacted")

            except Exception as e:
                logger.warning(f"Failed to compact {table_name}: {e}")
                if not silent:
                    print(f"    ✗ Failed: {e}")

        if not silent:
            print(f"{'=' * 60}\n")

    def _normalize_and_accumulate(
        self,
        ticker_data: TickerData,
        data_types: List[DataType],
        accumulators: Dict[DataType, List],
        company_ref_dfs: List,
        results: IngestionResults
    ) -> None:
        """
        Normalize ticker data and add to accumulators.

        Args:
            ticker_data: Raw data from provider
            data_types: Data types to normalize
            accumulators: Dict of accumulators by data type
            company_ref_dfs: Accumulator for company reference
            results: Results object to track errors
        """
        ticker = ticker_data.ticker

        for data_type in data_types:
            try:
                df = self.provider.normalize_data(ticker_data, data_type)
                if df is not None and df.count() > 0:
                    accumulators[data_type].append(df)
            except Exception as e:
                # Log detailed error with stack trace
                import traceback
                logger.error(
                    f"Failed to normalize {data_type.value} for {ticker}: {e}\n"
                    f"Stack trace: {traceback.format_exc()}"
                )
                results.add_error(ticker, data_type.value, "normalize", e)

        # Also normalize company reference if provider supports it
        if self.include_company_reference and DataType.REFERENCE in data_types:
            if hasattr(self.provider, 'normalize_company_reference'):
                try:
                    comp_df = self.provider.normalize_company_reference(ticker_data)
                    if comp_df is not None and comp_df.count() > 0:
                        company_ref_dfs.append(comp_df)
                except Exception as e:
                    import traceback
                    logger.error(
                        f"Failed to normalize company reference for {ticker}: {e}\n"
                        f"Stack trace: {traceback.format_exc()}"
                    )
                    results.add_error(ticker, "company_reference", "normalize", e)

    # Data types that are immutable (historical data that doesn't change)
    # These use append_immutable() for better performance
    IMMUTABLE_DATA_TYPES = {DataType.PRICES}

    def _write_batch(
        self,
        accumulators: Dict[DataType, List],
        company_ref_dfs: List,
        results: IngestionResults
    ) -> None:
        """
        Write accumulated DataFrames to storage.

        Uses appropriate write strategy based on data type:
        - Immutable data (prices): append_immutable() - faster, avoids MERGE
        - Mutable data (reference, fundamentals): upsert() - handles updates

        Args:
            accumulators: Dict of DataFrames by data type
            company_ref_dfs: Company reference DataFrames
            results: Results object to update with paths
        """
        for data_type, dfs in accumulators.items():
            if not dfs:
                continue

            try:
                # Union all DataFrames for this type
                combined = reduce(lambda a, b: a.union(b), dfs)
                combined = combined.coalesce(4)

                # Get table config from provider and storage.json
                table_name = self.provider.get_bronze_table_name(data_type)
                key_columns = self.provider.get_key_columns(data_type)
                # IMPORTANT: Get partitions from storage.json config (not provider)
                # This ensures single source of truth for partition strategy
                table_cfg = self.sink._table_cfg(table_name)
                partitions = table_cfg.get("partitions", []) or None

                # Choose write strategy based on data type
                if data_type in self.IMMUTABLE_DATA_TYPES:
                    # Immutable time-series data - use efficient append
                    path = self.sink.append_immutable(
                        combined,
                        table_name,
                        key_columns=key_columns,
                        partitions=partitions,
                        date_column="trade_date"
                    )
                else:
                    # Mutable data - use upsert for updates
                    path = self.sink.upsert(
                        combined,
                        table_name,
                        key_columns=key_columns,
                        partitions=partitions
                    )

                if path:
                    results.tables_written[table_name] = path

            except Exception as e:
                import traceback
                logger.error(
                    f"Failed to write {data_type.value}: {e}\n"
                    f"Stack trace: {traceback.format_exc()}"
                )
                results.add_error("batch", data_type.value, "write", e)

        # Write company reference separately
        if company_ref_dfs:
            try:
                combined = reduce(lambda a, b: a.union(b), company_ref_dfs)
                combined = combined.coalesce(4)

                path = self.sink.upsert(
                    combined,
                    "company_reference",
                    key_columns=["cik"],
                    partitions=[]
                )

                if path:
                    results.tables_written["company_reference"] = path

            except Exception as e:
                import traceback
                logger.error(
                    f"Failed to write company_reference: {e}\n"
                    f"Stack trace: {traceback.format_exc()}"
                )
                results.add_error("batch", "company_reference", "write", e)

    def run_with_discovery(
        self,
        max_tickers: int = None,
        use_market_cap: bool = True,
        min_market_cap: float = None,
        data_types: List[DataType] = None,
        batch_size: int = 20,
        silent: bool = False,
        auto_compact: bool = True,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion with automatic ticker discovery.

        Args:
            max_tickers: Maximum tickers to process
            use_market_cap: Sort by market cap (requires existing data)
            min_market_cap: Minimum market cap filter
            data_types: Data types to fetch
            batch_size: Tickers per batch
            silent: Suppress output
            auto_compact: Run Delta OPTIMIZE after ingestion (default: True)
            **kwargs: Provider-specific options

        Returns:
            IngestionResults
        """
        if not silent:
            print("Discovering tickers...")

        # Try market cap ranking first if requested
        tickers = []
        if use_market_cap:
            try:
                tickers = self.provider.get_tickers_by_market_cap(
                    max_tickers=max_tickers,
                    min_market_cap=min_market_cap,
                    storage_cfg=self.storage_cfg
                )
                if tickers and not silent:
                    print(f"  Found {len(tickers)} tickers from market cap ranking")
            except NotImplementedError:
                pass

        # Fall back to discovery if no market cap data
        if not tickers:
            try:
                tickers, _ = self.provider.discover_tickers()
                if max_tickers:
                    tickers = tickers[:max_tickers]
                if not silent:
                    print(f"  Discovered {len(tickers)} tickers")
            except NotImplementedError:
                raise ValueError(
                    f"Provider {self.provider.config.name} does not support ticker discovery. "
                    "Provide tickers explicitly."
                )

        if not tickers:
            raise ValueError("No tickers found for ingestion")

        return self.run(
            tickers=tickers,
            data_types=data_types,
            batch_size=batch_size,
            silent=silent,
            auto_compact=auto_compact,
            **kwargs
        )


def create_engine(
    provider_name: str,
    api_cfg: Dict,
    storage_cfg: Dict,
    spark=None
) -> IngestorEngine:
    """
    Factory function to create an IngestorEngine for a provider.

    Args:
        provider_name: Provider name (e.g., "alpha_vantage")
        api_cfg: API configuration dict
        storage_cfg: Storage configuration dict
        spark: SparkSession

    Returns:
        Configured IngestorEngine
    """
    if provider_name == "alpha_vantage":
        from datapipelines.providers.alpha_vantage.provider import create_alpha_vantage_provider
        provider = create_alpha_vantage_provider(api_cfg, spark)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    return IngestorEngine(provider, storage_cfg)
