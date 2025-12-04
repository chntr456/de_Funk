"""
Alpha Vantage Ingestor

Handles data ingestion from Alpha Vantage API to bronze layer.

Key Differences from Polygon:
- Lower rate limits (5 calls/min for free tier, ~75 calls/min for premium)
- No cursor-based pagination (most endpoints return full data)
- API key passed as query parameter (not header)
- Different response structure (nested dicts vs flat arrays)
- No bulk ticker endpoints (one call per ticker)

Rate Limiting Strategy:
- Free tier: 5 calls/minute = 0.08333 calls/second
- Premium: 75 calls/minute = 1.25 calls/second
- Use sequential processing to respect rate limits
- Concurrent requests disabled by default for free tier
"""

import time
import threading
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from config.logging import get_logger
from datapipelines.providers.alpha_vantage.alpha_vantage_registry import AlphaVantageRegistry

logger = get_logger(__name__)


# ============================================================================
# Progress Tracking
# ============================================================================

@dataclass
class ProgressInfo:
    """Information about current ingestion progress."""
    phase: str           # 'reference', 'prices', 'bulk_listing'
    current: int         # Current item number (1-indexed)
    total: int           # Total items to process
    ticker: str          # Current ticker being processed
    success: bool        # Whether the current item succeeded
    error: Optional[str] = None  # Error message if failed
    elapsed_seconds: float = 0.0  # Time elapsed since phase start

    @property
    def percent_complete(self) -> float:
        """Percentage complete (0-100)."""
        return (self.current / self.total * 100) if self.total > 0 else 0.0

    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimated seconds remaining based on current pace."""
        if self.current == 0 or self.elapsed_seconds == 0:
            return None
        rate = self.current / self.elapsed_seconds
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else None

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta = self.eta_seconds
        if eta is None:
            return "calculating..."
        if eta < 60:
            return f"{eta:.0f}s"
        elif eta < 3600:
            return f"{eta/60:.1f}m"
        else:
            return f"{eta/3600:.1f}h"


# Type alias for progress callback
ProgressCallback = Callable[[ProgressInfo], None]


def default_progress_callback(info: ProgressInfo) -> None:
    """Default progress callback that prints status to console and logs."""
    status = "✓" if info.success else "✗"
    eta_str = f" | ETA: {info.format_eta()}" if info.current > 1 else ""
    error_str = f" | {info.error}" if info.error else ""

    msg = (f"  [{info.phase}] {status} {info.current}/{info.total} "
           f"({info.percent_complete:.1f}%) {info.ticker}{eta_str}{error_str}")
    print(msg)

    # Also log (debug for success, warning for failure)
    if info.success:
        logger.debug(f"[{info.phase}] {info.ticker} ({info.current}/{info.total})")
    else:
        logger.warning(f"[{info.phase}] {info.ticker} failed: {info.error}")


from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor


class AlphaVantageIngestor(Ingestor):
    """
    Ingestor for Alpha Vantage API.

    Usage:
        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=config.apis['alpha_vantage'],
            storage_cfg=config.storage,
            spark=spark_session
        )

        # Ingest reference data
        ingestor.ingest_reference_data(tickers=['AAPL', 'MSFT'])

        # Ingest prices
        ingestor.ingest_prices(
            tickers=['AAPL', 'MSFT'],
            date_from='2024-01-01',
            date_to='2024-12-31'
        )
    """

    def __init__(self, alpha_vantage_cfg, storage_cfg, spark):
        """
        Initialize Alpha Vantage ingestor.

        Args:
            alpha_vantage_cfg: Alpha Vantage API configuration dict
            storage_cfg: Storage configuration dict
            spark: SparkSession
        """
        super().__init__(storage_cfg=storage_cfg)

        # Store config for later access (e.g., US exchange filtering)
        self.alpha_vantage_cfg = alpha_vantage_cfg

        self.registry = AlphaVantageRegistry(alpha_vantage_cfg)

        # Create API key pool (store separately for bulk listing)
        self.key_pool = ApiKeyPool(
            (alpha_vantage_cfg.get("credentials") or {}).get("api_keys") or [],
            cooldown_seconds=60.0  # 1-minute cooldown for rate limiting
        )

        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            self.key_pool
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark
        self._http_lock = threading.Lock()

    def _fetch_calls(self, calls, response_key=None,
                     progress_callback: Optional[ProgressCallback] = None,
                     phase: str = "fetching"):
        """
        Fetch data from Alpha Vantage API.

        Alpha Vantage doesn't use pagination like Polygon.
        Most endpoints return full data in single response.

        Args:
            calls: Iterator of call specs (ep_name, params)
            response_key: Key in response containing data (None for top-level)
            progress_callback: Optional callback for progress updates
            phase: Phase name for progress reporting (e.g., 'reference', 'prices')

        Returns:
            List of batches (one batch per call)
        """
        batches = []
        calls_list = list(calls)
        total = len(calls_list)
        start_time = time.time()

        for i, call in enumerate(calls_list):
            ticker = call["params"].get("symbol", "UNKNOWN")
            ep, path, query = self.registry.render(call["ep_name"], **call["params"])

            # Make request (thread-safe)
            error_msg = None
            success = True
            try:
                with self._http_lock:
                    payload = self.http.request(ep.base, path, query, ep.method)
            except Exception as e:
                payload = {}
                error_msg = str(e)
                success = False

            # Check for API-level errors in response
            if isinstance(payload, dict):
                if "Error Message" in payload:
                    error_msg = payload["Error Message"][:80]
                    success = False
                elif "Information" in payload and len(payload) == 1:
                    error_msg = "API limit or invalid request"
                    success = False
                elif "Note" in payload:
                    error_msg = "Rate limit warning"
                    # Still considered success, just a warning

            # Extract data
            if response_key:
                data = payload.get(response_key)
                if isinstance(data, list):
                    batches.append(data)
                elif isinstance(data, dict):
                    # For nested time series data, keep as-is
                    batches.append([payload])
                else:
                    batches.append([])
                    if success and not data:
                        error_msg = f"No data for key '{response_key}'"
                        success = False
            else:
                # No response key - return entire payload
                batches.append([payload])

            # Report progress
            if progress_callback:
                elapsed = time.time() - start_time
                info = ProgressInfo(
                    phase=phase,
                    current=i + 1,
                    total=total,
                    ticker=ticker,
                    success=success,
                    error=error_msg,
                    elapsed_seconds=elapsed
                )
                progress_callback(info)

        return batches

    def _fetch_calls_concurrent(self, calls, response_key=None, max_workers=5,
                                 progress_callback: Optional[ProgressCallback] = None,
                                 phase: str = "fetching"):
        """
        Fetch data with concurrent requests.

        WARNING: Only use for premium tier with higher rate limits!
        Free tier should use sequential _fetch_calls() to avoid hitting limits.

        Args:
            calls: Iterator of call specs
            response_key: Key in response containing data
            max_workers: Maximum concurrent workers (default: 5 for premium tier)
            progress_callback: Optional callback for progress updates
            phase: Phase name for progress reporting

        Returns:
            List of batches (one batch per call)
        """
        calls_list = list(calls)
        total = len(calls_list)
        batches = [None] * total  # Pre-allocate to maintain order
        completed = [0]  # Use list for mutable counter in nested function
        start_time = time.time()
        progress_lock = threading.Lock()

        def fetch_single_call(i, call):
            ticker = call["params"].get("symbol", "UNKNOWN")
            ep, path, query = self.registry.render(call["ep_name"], **call["params"])

            error_msg = None
            success = True

            # Make request (thread-safe)
            try:
                with self._http_lock:
                    payload = self.http.request(ep.base, path, query, ep.method)
            except Exception as e:
                payload = {}
                error_msg = str(e)
                success = False

            # Check for API-level errors
            if isinstance(payload, dict):
                if "Error Message" in payload:
                    error_msg = payload["Error Message"][:80]
                    success = False
                elif "Information" in payload and len(payload) == 1:
                    error_msg = "API limit or invalid request"
                    success = False
                elif "Note" in payload:
                    error_msg = "Rate limit warning"

            # Extract data
            batch = []
            if response_key:
                data = payload.get(response_key)
                if isinstance(data, list):
                    batch = data
                elif isinstance(data, dict):
                    batch = [payload]
                else:
                    if success and not data:
                        error_msg = f"No data for key '{response_key}'"
                        success = False
            else:
                batch = [payload]

            return i, batch, ticker, success, error_msg

        # Execute concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_single_call, i, call): i
                for i, call in enumerate(calls_list)
            }

            for future in as_completed(futures):
                i, batch, ticker, success, error_msg = future.result()
                batches[i] = batch

                # Report progress (thread-safe)
                if progress_callback:
                    with progress_lock:
                        completed[0] += 1
                        elapsed = time.time() - start_time
                        info = ProgressInfo(
                            phase=phase,
                            current=completed[0],
                            total=total,
                            ticker=ticker,
                            success=success,
                            error=error_msg,
                            elapsed_seconds=elapsed
                        )
                        progress_callback(info)

        return batches

    def ingest_reference_data(self, tickers, table_name="securities_reference",
                              use_concurrent=False, show_progress=True,
                              progress_callback: Optional[ProgressCallback] = None,
                              batch_size: int = 500):
        """
        Ingest reference data (company overview) for given tickers.

        Uses Alpha Vantage OVERVIEW endpoint to get company fundamentals.
        Writes data in batches to minimize memory usage.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: securities_reference)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback (if None, uses default)
            batch_size: Number of tickers to process before writing to disk (default: 500)
                       Lower values use less memory but may be slightly slower.

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import SecuritiesReferenceFacetAV
        import gc

        total_tickers = len(tickers)
        print(f"Ingesting reference data for {total_tickers} tickers...")
        print(f"  Batch size: {batch_size} (will write to disk after each batch)")

        # Determine progress callback
        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        total_rows_written = 0
        total_errors = 0
        table_path = None
        num_batches = (total_tickers + batch_size - 1) // batch_size

        # Process in batches to reduce memory usage
        for batch_idx in range(0, total_tickers, batch_size):
            batch_num = batch_idx // batch_size + 1
            batch_tickers = tickers[batch_idx:batch_idx + batch_size]

            print(f"\n📦 Batch {batch_num}/{num_batches}: Processing {len(batch_tickers)} tickers...")

            # Create facet for this batch
            facet = SecuritiesReferenceFacetAV(self.spark, tickers=batch_tickers)
            calls = list(facet.calls())

            # Fetch data for this batch (sequential or concurrent)
            if use_concurrent:
                raw_batches = self._fetch_calls_concurrent(
                    calls, response_key=None,
                    progress_callback=callback, phase="reference"
                )
            else:
                raw_batches = self._fetch_calls(
                    calls, response_key=None,
                    progress_callback=callback, phase="reference"
                )

            # Check for API errors in this batch
            batch_errors = 0
            for i, batch in enumerate(raw_batches):
                for item in batch:
                    if isinstance(item, dict):
                        ticker = batch_tickers[i] if i < len(batch_tickers) else "UNKNOWN"
                        if "Information" in item and len(item) == 1:
                            batch_errors += 1
                            if show_progress:
                                print(f"⚠ API Info for {ticker}: {item['Information'][:60]}")
                        elif "Error Message" in item:
                            batch_errors += 1
                            if show_progress:
                                print(f"✗ API Error for {ticker}: {item['Error Message'][:60]}")
                        elif "Note" in item:
                            batch_errors += 1
                            if show_progress:
                                print(f"⚠ API Note for {ticker}: {item['Note'][:60]}")

            total_errors += batch_errors

            # Skip normalization if all calls in batch failed
            if batch_errors == len(batch_tickers):
                print(f"  ⚠ All {batch_errors} API calls in batch failed, skipping...")
                del raw_batches
                gc.collect()
                continue

            # Normalize to DataFrame
            df = None
            try:
                df = facet.normalize(raw_batches)
                df = facet.validate(df)
                batch_count = df.count()

                if batch_count > 0:
                    # Write to bronze (append mode for subsequent batches)
                    if batch_num == 1:
                        # First batch: overwrite
                        table_path = self.sink.write(df, table_name, partitions=["snapshot_dt", "asset_type"])
                    else:
                        # Subsequent batches: append
                        table_path = self.sink.write(df, table_name, partitions=["snapshot_dt", "asset_type"], mode="append")

                    total_rows_written += batch_count
                    print(f"  ✓ Written {batch_count} rows (total: {total_rows_written})")
                else:
                    print(f"  ⚠ No valid data in batch")

            except Exception as e:
                logger.warning(f"Failed to normalize/write batch {batch_num}: {e}")
                print(f"  ✗ Batch {batch_num} failed: {e}")

            # Aggressive memory cleanup
            # 1. Unpersist Spark DataFrame if it exists
            if df is not None:
                try:
                    df.unpersist()
                except Exception:
                    pass

            # 2. Clear references
            del raw_batches
            raw_batches = None
            del facet
            facet = None
            if df is not None:
                del df
                df = None

            # 3. Clear Spark's internal caches periodically
            if batch_num % 5 == 0:
                try:
                    self.spark.catalog.clearCache()
                    # Trigger JVM garbage collection (Python gc doesn't help JVM heap)
                    self.spark.sparkContext._jvm.System.gc()
                except Exception:
                    pass

            # 4. Force Python garbage collection
            gc.collect()

        # Summary
        print(f"\n{'=' * 60}")
        print(f"✓ Reference data ingestion complete")
        print(f"  Total tickers processed: {total_tickers}")
        print(f"  Total rows written: {total_rows_written}")
        print(f"  Total API errors: {total_errors}")
        if table_path:
            print(f"  Output path: {table_path}")
        print(f"{'=' * 60}")

        if total_errors > 0:
            print("\nCommon causes for API errors:")
            print("  - Rate limit exceeded (free tier: 5 calls/minute, 500 calls/day)")
            print("  - Invalid ticker symbols")
            print("  - Missing or invalid API key")

        return table_path

    def ingest_prices(self, tickers, date_from=None, date_to=None,
                     table_name="securities_prices_daily",
                     adjusted=True, outputsize="full", use_concurrent=False,
                     show_progress=True,
                     progress_callback: Optional[ProgressCallback] = None,
                     batch_size: int = 100):
        """
        Ingest daily OHLCV prices for given tickers.

        Uses Alpha Vantage TIME_SERIES_DAILY_ADJUSTED endpoint.
        Writes data in batches to minimize memory usage.

        Args:
            tickers: List of ticker symbols
            date_from: Start date (YYYY-MM-DD), used for filtering after fetch
            date_to: End date (YYYY-MM-DD), used for filtering after fetch
            table_name: Bronze table name (default: securities_prices_daily)
            adjusted: Use adjusted prices (default: True)
            outputsize: 'compact' (100 days) or 'full' (20+ years)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback (if None, uses default)
            batch_size: Number of tickers to process before writing to disk (default: 100)
                       Smaller default than reference data because price data is larger.

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import SecuritiesPricesFacetAV
        import gc

        total_tickers = len(tickers)
        print(f"Ingesting prices for {total_tickers} tickers...")
        print(f"Date range: {date_from or 'ALL'} to {date_to or 'ALL'}")
        print(f"Output size: {outputsize}, Adjusted: {adjusted}")
        print(f"  Batch size: {batch_size} (will write to disk after each batch)")

        # Determine progress callback
        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        total_rows_written = 0
        total_errors = 0
        table_path = None
        num_batches = (total_tickers + batch_size - 1) // batch_size

        # Process in batches to reduce memory usage
        for batch_idx in range(0, total_tickers, batch_size):
            batch_num = batch_idx // batch_size + 1
            batch_tickers = tickers[batch_idx:batch_idx + batch_size]

            print(f"\n📦 Batch {batch_num}/{num_batches}: Processing {len(batch_tickers)} tickers...")

            # Create facet for this batch
            facet = SecuritiesPricesFacetAV(
                self.spark,
                tickers=batch_tickers,
                date_from=date_from,
                date_to=date_to,
                adjusted=adjusted,
                outputsize=outputsize
            )
            calls = list(facet.calls())

            # Fetch data for this batch
            if use_concurrent:
                raw_batches = self._fetch_calls_concurrent(
                    calls, response_key="Time Series (Daily)",
                    progress_callback=callback, phase="prices"
                )
            else:
                raw_batches = self._fetch_calls(
                    calls, response_key="Time Series (Daily)",
                    progress_callback=callback, phase="prices"
                )

            # Check for API errors in this batch
            batch_errors = 0
            for i, batch in enumerate(raw_batches):
                if batch is None or len(batch) == 0:
                    batch_errors += 1
                    continue

                for item in batch:
                    if isinstance(item, dict):
                        if "Information" in item and len(item) == 1:
                            batch_errors += 1
                        elif "Error Message" in item:
                            batch_errors += 1
                        elif "Note" in item:
                            batch_errors += 1

            total_errors += batch_errors

            # Skip normalization if all calls in batch failed
            if batch_errors == len(batch_tickers):
                print(f"  ⚠ All {batch_errors} API calls in batch failed, skipping...")
                del raw_batches
                gc.collect()
                continue

            # Normalize to DataFrame
            df = None
            try:
                df = facet.normalize(raw_batches)
                df = facet.validate(df)
                batch_count = df.count()

                if batch_count > 0:
                    # Write to bronze (append mode for subsequent batches)
                    if batch_num == 1:
                        # First batch: overwrite
                        table_path = self.sink.write(df, table_name, partitions=["asset_type", "year", "month"])
                    else:
                        # Subsequent batches: append
                        table_path = self.sink.write(df, table_name, partitions=["asset_type", "year", "month"], mode="append")

                    total_rows_written += batch_count
                    print(f"  ✓ Written {batch_count} rows (total: {total_rows_written})")
                else:
                    print(f"  ⚠ No valid data in batch")

            except Exception as e:
                logger.warning(f"Failed to normalize/write prices batch {batch_num}: {e}")
                print(f"  ✗ Batch {batch_num} failed: {e}")

            # Aggressive memory cleanup
            if df is not None:
                try:
                    df.unpersist()
                except Exception:
                    pass

            del raw_batches
            raw_batches = None
            del facet
            facet = None
            if df is not None:
                del df
                df = None

            if batch_num % 5 == 0:
                try:
                    self.spark.catalog.clearCache()
                    self.spark.sparkContext._jvm.System.gc()
                except Exception:
                    pass

            gc.collect()

        # Summary
        print(f"\n{'=' * 60}")
        print(f"✓ Price data ingestion complete")
        print(f"  Total tickers processed: {total_tickers}")
        print(f"  Total rows written: {total_rows_written}")
        print(f"  Total API errors: {total_errors}")
        if table_path:
            print(f"  Output path: {table_path}")
        print(f"{'=' * 60}")

        return table_path

    def ingest_bulk_listing(self, table_name="securities_reference", state="active"):
        """
        Ingest bulk listing of all active/delisted stocks in ONE API call.

        Uses Alpha Vantage LISTING_STATUS endpoint which returns CSV with ALL tickers.
        This is MUCH more efficient than calling OVERVIEW for each ticker.

        Note: This endpoint returns limited data (ticker, name, exchange, type, dates).
        For full company fundamentals (PE ratio, market cap, etc.), use ingest_reference_data().

        Args:
            table_name: Bronze table name (default: securities_reference)
            state: 'active' or 'delisted' (default: active)

        Returns:
            Tuple of (path to written table, list of tickers, dict of ticker->exchange)
        """
        import csv
        import io
        from datetime import date, datetime
        from pyspark.sql.functions import lit, when, col, current_timestamp

        print(f"Ingesting bulk listing ({state} stocks) via LISTING_STATUS...")
        print("This is ONE API call that returns ALL tickers (very efficient!)")

        # Make single API call for bulk listing
        ep, path, query = self.registry.render("listing_status", state=state)
        query['apikey'] = self.key_pool.next_key() if self.key_pool else None

        # Fetch CSV data (use request_text for CSV endpoints, not JSON)
        with self._http_lock:
            response_text = self.http.request_text(ep.base, path, query, ep.method)

        # Parse CSV response
        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)
        print(f"Fetched {len(rows)} tickers from Alpha Vantage")

        if not rows:
            print("Warning: No tickers returned from LISTING_STATUS")
            return None, []

        # Convert to Spark DataFrame
        df = self.spark.createDataFrame(rows, samplingRatio=1.0)

        # Normalize to securities_reference schema
        # LISTING_STATUS fields: symbol, name, exchange, assetType, ipoDate, delistingDate, status
        df_normalized = df.select(
            col("symbol").cast("string").alias("ticker"),
            col("name").cast("string").alias("security_name"),

            # Map assetType to our asset_type
            when(col("assetType") == "Stock", lit("stocks"))
            .when(col("assetType") == "ETF", lit("etfs"))
            .when(col("assetType").contains("Option"), lit("options"))
            .when(col("assetType").contains("Future"), lit("futures"))
            .otherwise(lit("stocks"))
            .cast("string").alias("asset_type"),

            # Fields not available in LISTING_STATUS (set to NULL)
            lit(None).cast("string").alias("cik"),
            lit(None).cast("string").alias("composite_figi"),

            # Exchange info
            col("exchange").cast("string").alias("exchange_code"),
            lit("USD").cast("string").alias("currency"),
            lit("stocks").cast("string").alias("market"),
            lit("US").cast("string").alias("locale"),
            col("assetType").cast("string").alias("type"),
            col("exchange").cast("string").alias("primary_exchange"),

            # Market data (not available)
            lit(None).cast("long").alias("shares_outstanding"),
            lit(None).cast("double").alias("market_cap"),

            # SIC codes (not available)
            lit(None).cast("string").alias("sic_code"),
            lit(None).cast("string").alias("sic_description"),

            # Metadata
            col("symbol").cast("string").alias("ticker_root"),
            lit("USD").cast("string").alias("base_currency_symbol"),
            lit("USD").cast("string").alias("currency_symbol"),

            # Dates (handle "null" strings from CSV)
            when(col("delistingDate").isin("null", "None", ""), lit(None))
            .otherwise(col("delistingDate"))
            .cast("timestamp")
            .alias("delisted_utc"),
            current_timestamp().alias("last_updated_utc"),
            (col("status") == "Active").cast("boolean").alias("is_active"),

            # Additional fields for compatibility
            lit(None).cast("string").alias("sector"),
            lit(None).cast("string").alias("industry"),
            lit(None).cast("string").alias("description"),
            lit(None).cast("double").alias("pe_ratio"),
            lit(None).cast("double").alias("peg_ratio"),
            lit(None).cast("double").alias("book_value"),
            lit(None).cast("double").alias("dividend_per_share"),
            lit(None).cast("double").alias("dividend_yield"),
            lit(None).cast("double").alias("eps"),
            lit(None).cast("double").alias("week_52_high"),
            lit(None).cast("double").alias("week_52_low")
        )

        # Filter out any invalid tickers
        df_normalized = df_normalized.filter(col("ticker").isNotNull())

        # Write to bronze
        table_path = self.sink.write(df_normalized, table_name, partitions=["snapshot_dt", "asset_type"])

        # Return both ticker list AND ticker->exchange mapping for filtering
        tickers = [row['symbol'] for row in rows if row.get('symbol')]  # CSV has 'symbol', not 'ticker'
        ticker_exchanges = {row['symbol']: row.get('exchange', 'UNKNOWN') for row in rows if row.get('symbol')}

        print(f"Written {df_normalized.count()} tickers to {table_path}")
        print(f"Note: For fundamentals (PE, market cap, etc.), call ingest_reference_data() for specific tickers")

        return table_path, tickers, ticker_exchanges

    def run_all(self, tickers=None, date_from=None, date_to=None,
                max_tickers=None, use_concurrent=False, use_bulk_listing=False,
                skip_reference_refresh=False, outputsize="full",
                show_progress=True,
                progress_callback: Optional[ProgressCallback] = None,
                **kwargs):
        """
        Run complete ingestion: reference data + prices.

        This method implements the abstract method from Ingestor base class.
        It orchestrates the full ingestion process for Alpha Vantage data.

        Args:
            tickers: List of ticker symbols (default: top 10 tickers)
            date_from: Start date for prices (YYYY-MM-DD)
            date_to: End date for prices (YYYY-MM-DD)
            max_tickers: Limit number of tickers to ingest
            use_concurrent: Use concurrent fetching (premium tier only)
            use_bulk_listing: Use LISTING_STATUS endpoint for bulk ticker discovery (ONE API call!)
            skip_reference_refresh: Skip OVERVIEW calls (saves ~50% time for daily updates, default: False)
            outputsize: 'compact' (100 days) or 'full' (20+ years) - use compact for daily updates
            show_progress: Show progress updates during ingestion (default: True)
            progress_callback: Custom progress callback function (if None, uses default)
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            List of ingested tickers
        """
        # Option 1: Bulk listing (discover ALL tickers efficiently)
        if use_bulk_listing:
            print("Using BULK LISTING mode (LISTING_STATUS endpoint)")
            print("=" * 80)
            print("Step 1a: Fetching ALL ticker symbols from LISTING_STATUS (1 API call)...")
            print("-" * 80)
            _, all_tickers, ticker_exchanges = self.ingest_bulk_listing()

            # Get US exchanges from config for filtering
            us_exchanges = self.alpha_vantage_cfg.get("us_exchanges", [
                "NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"
            ])

            # Filter to US exchanges only (foreign tickers often don't have OVERVIEW data)
            us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
            foreign_count = len(all_tickers) - len(us_tickers)

            print(f"\n📊 Ticker Discovery Summary:")
            print(f"   Total tickers from LISTING_STATUS: {len(all_tickers)}")
            print(f"   US exchange tickers: {len(us_tickers)}")
            print(f"   Foreign exchange tickers (filtered out): {foreign_count}")
            print(f"   US Exchanges: {', '.join(us_exchanges)}")
            print()

            # Filter to requested tickers if provided
            if tickers:
                tickers = [t for t in tickers if t in us_tickers]
                print(f"✓ Filtered to requested tickers: {len(tickers)}")
            else:
                tickers = us_tickers

            # Apply limit
            if max_tickers:
                tickers = tickers[:max_tickers]
                print(f"✓ Limited to first {max_tickers} tickers")

            print(f"\n✓ Final ticker count for ingestion: {len(tickers)}")
            print()

        # Option 2: Individual ticker mode (default)
        else:
            # Fail explicitly if no tickers provided - NEVER use hardcoded defaults
            # See CLAUDE.md v2.4: "No Hardcoded Default Data" anti-pattern
            if not tickers:
                raise ValueError(
                    "No tickers provided. You must either:\n"
                    "  1. Pass a list of tickers explicitly\n"
                    "  2. Use --use-bulk-listing to discover all tickers from LISTING_STATUS\n"
                    "  3. Use market cap sorting (requires existing reference data)\n\n"
                    "To ingest data for the first time, run:\n"
                    "  python -m scripts.ingest.run_full_pipeline --max-tickers 100 --use-bulk-listing\n\n"
                    "NEVER hardcode default ticker lists - this masks data pipeline issues."
                )

            # Apply ticker limit
            if max_tickers:
                tickers = tickers[:max_tickers]

        # Common ingestion flow (runs for BOTH modes)
        print(f"Running ingestion for {len(tickers)} tickers...")
        print(f"Date range: {date_from} to {date_to}")
        print(f"Concurrent mode: {use_concurrent}")
        print(f"Output size: {outputsize}")
        print(f"Skip reference refresh: {skip_reference_refresh}")
        print()

        # Step 1: Ingest reference data (detailed fundamentals per ticker)
        # This runs for BOTH modes - we need CIK + fundamentals for company model
        # OPTIMIZATION: Skip for daily updates if fundamentals haven't changed
        if skip_reference_refresh:
            print("⚡ SKIPPING reference data refresh (using existing data)")
            print("   This saves ~50% of API calls for daily updates")
            print("   Note: Run full refresh periodically to update fundamentals")
            print()
        else:
            print("Step 1{'b' if use_bulk_listing else ''}: Ingesting reference data (OVERVIEW endpoint)...")
            print("-" * 80)
            self.ingest_reference_data(
                tickers=tickers,
                use_concurrent=use_concurrent,
                show_progress=show_progress,
                progress_callback=progress_callback
            )
            print()

        # Step 2: Ingest prices (same for both modes)
        step_num = '1' if skip_reference_refresh else '2'
        print(f"Step {step_num}: Ingesting prices...")
        print("-" * 80)
        self.ingest_prices(
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            outputsize=outputsize,  # Pass through outputsize parameter
            use_concurrent=use_concurrent,
            show_progress=show_progress,
            progress_callback=progress_callback
        )
        print()

        print(f"✓ Full ingestion complete for {len(tickers)} tickers")
        return tickers

    # =========================================================================
    # Market Cap Ranking Methods
    # =========================================================================

    def get_tickers_by_market_cap(self, max_tickers: int = None,
                                   min_market_cap: float = None) -> list:
        """
        Get tickers sorted by market cap from existing reference data.

        Checks multiple data sources in order:
        1. bronze/securities_reference (OVERVIEW data)
        2. silver/stocks/dims/dim_stock (if silver layer is built)

        Args:
            max_tickers: Maximum number of tickers to return
            min_market_cap: Minimum market cap filter (in dollars)

        Returns:
            List of ticker symbols sorted by market cap (descending)
        """
        from pyspark.sql.functions import col, desc
        from pathlib import Path

        print("Loading market cap rankings from existing data...")

        # Check multiple data sources in order of preference
        bronze_path = Path(self.sink.cfg["roots"]["bronze"])
        silver_path = Path(self.sink.cfg["roots"]["silver"])

        ref_path = bronze_path / "securities_reference"
        silver_dim_path = silver_path / "stocks" / "dims" / "dim_stock"

        df = None
        source_name = None

        def has_valid_market_cap(dataframe):
            """Check if dataframe has actual market cap values (not just the column)."""
            if "market_cap" not in dataframe.columns:
                return False
            # Check for at least one non-null, positive market cap
            count = dataframe.filter(
                (col("market_cap").isNotNull()) &
                (col("market_cap") > 0)
            ).limit(1).count()
            return count > 0

        # Try bronze securities_reference first
        if ref_path.exists():
            try:
                # Auto-detect Delta vs Parquet
                if (ref_path / "_delta_log").exists():
                    temp_df = self.spark.read.format("delta").load(str(ref_path))
                else:
                    temp_df = self.spark.read.parquet(str(ref_path))
                if has_valid_market_cap(temp_df):
                    df = temp_df
                    source_name = "bronze/securities_reference"
                else:
                    print("  bronze/securities_reference exists but has no market cap values")
            except Exception as e:
                print(f"  Could not read bronze/securities_reference: {e}")

        # Fallback to silver dim_stock
        if df is None and silver_dim_path.exists():
            try:
                # Auto-detect Delta vs Parquet
                if (silver_dim_path / "_delta_log").exists():
                    temp_df = self.spark.read.format("delta").load(str(silver_dim_path))
                else:
                    temp_df = self.spark.read.parquet(str(silver_dim_path))
                if has_valid_market_cap(temp_df):
                    df = temp_df
                    source_name = "silver/stocks/dims/dim_stock"
                else:
                    print("  silver/stocks/dims/dim_stock exists but has no market cap values")
            except Exception as e:
                print(f"  Could not read silver dim_stock: {e}")

        if df is None:
            print("\nWarning: No valid market cap data found in bronze or silver layers.")
            print("Run: python -m scripts.ingest.refresh_market_cap_rankings")
            return []

        print(f"  Using data from: {source_name}")

        try:
            from pyspark.sql.functions import isnan, upper, lit

            columns = df.columns

            # Start with market cap filter (required)
            df_with_cap = df.filter(
                (col("market_cap").isNotNull()) &
                (~isnan(col("market_cap"))) &
                (col("market_cap") > 0)
            )

            # Apply asset_type filter only if column exists
            if "asset_type" in columns:
                df_with_cap = df_with_cap.filter(col("asset_type") == "stocks")

            # Apply is_active filter only if column exists
            if "is_active" in columns:
                df_with_cap = df_with_cap.filter(col("is_active") == True)

            # Exclude warrants, preferred shares, units, rights
            df_with_cap = df_with_cap.filter(
                (~upper(col("ticker")).rlike(r".*[-]?W[S]?$")) &
                (~upper(col("ticker")).rlike(r".*-P-.*|.*-P[A-Z]$")) &
                (~upper(col("ticker")).rlike(r".*-U[N]?$")) &
                (~upper(col("ticker")).rlike(r".*-R[T]?$")) &
                (~upper(col("ticker")).rlike(r".*[-][A-Z]{2,}$"))
            )

            # Apply minimum market cap filter if specified
            if min_market_cap:
                df_with_cap = df_with_cap.filter(col("market_cap") >= min_market_cap)
                print(f"Applied minimum market cap filter: ${min_market_cap:,.0f}")

            # Determine name column (security_name or name)
            name_col = "security_name" if "security_name" in columns else ("name" if "name" in columns else None)

            # Deduplicate first, then sort by market cap descending
            select_cols = ["ticker", "market_cap"]
            if name_col:
                select_cols.append(name_col)

            df_ranked = (df_with_cap
                        .select(*select_cols)
                        .dropDuplicates(["ticker"])
                        .orderBy(desc("market_cap")))

            # Apply limit
            if max_tickers:
                df_ranked = df_ranked.limit(max_tickers)

            # Collect full rows to preserve sort order (Spark may drop sort on select)
            rows = df_ranked.collect()
            tickers = [row.ticker for row in rows]

            # Print summary
            if tickers:
                print(f"\n📊 Top {len(tickers)} stocks by market cap:")
                print("-" * 60)
                for i, row in enumerate(rows[:10], 1):
                    cap_billions = row.market_cap / 1e9 if row.market_cap else 0
                    # Get name from whichever column exists
                    name_val = getattr(row, name_col, None) if name_col else None
                    name_display = name_val[:30] if name_val else 'N/A'
                    print(f"  {i:3}. {row.ticker:6} - ${cap_billions:>8.1f}B - {name_display}")
                if len(tickers) > 10:
                    print(f"  ... and {len(tickers) - 10} more")
                print()

            return tickers

        except Exception as e:
            logger.warning(f"Failed to load market cap rankings: {e}")
            print(f"Warning: Could not load market cap data: {e}")
            return []

    def fetch_bulk_quotes(self, tickers: list, show_progress: bool = True) -> list:
        """
        Fetch quotes for tickers using REALTIME_BULK_QUOTES (100 per call).

        Args:
            tickers: List of ticker symbols
            show_progress: Show progress updates

        Returns:
            List of dicts with ticker, price, volume, trading_value
        """
        all_quotes = []
        batch_size = 100
        total_batches = (len(tickers) + batch_size - 1) // batch_size

        for batch_idx in range(0, len(tickers), batch_size):
            batch = tickers[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1

            if show_progress:
                print(f"  Batch {batch_num}/{total_batches}: {len(batch)} symbols...", end=" ", flush=True)

            symbols = ",".join(batch)

            try:
                response = self.http.request("realtime_bulk_quotes", params={"symbol": symbols})

                if isinstance(response, dict):
                    if "data" in response:
                        quotes = response["data"]
                    elif "Error Message" in response or "Information" in response:
                        if show_progress:
                            print("✗ API error")
                        continue
                    else:
                        quotes = []
                elif isinstance(response, list):
                    quotes = response
                else:
                    quotes = []

                batch_quotes = []
                for quote in quotes:
                    if not isinstance(quote, dict):
                        continue
                    ticker = quote.get("symbol") or quote.get("01. symbol")
                    price_str = quote.get("price") or quote.get("05. price") or quote.get("close")
                    volume_str = quote.get("volume") or quote.get("06. volume")

                    if not ticker:
                        continue
                    try:
                        price = float(price_str) if price_str else 0
                        volume = float(volume_str) if volume_str else 0
                        batch_quotes.append({
                            "ticker": ticker,
                            "price": price,
                            "volume": volume,
                            "trading_value": price * volume
                        })
                    except (ValueError, TypeError):
                        continue

                all_quotes.extend(batch_quotes)
                if show_progress:
                    print(f"✓ {len(batch_quotes)}")

            except Exception as e:
                if show_progress:
                    print(f"✗ {str(e)[:30]}")
                logger.warning(f"Bulk quotes batch {batch_num} failed: {e}")

        return all_quotes

    def refresh_market_cap_rankings(self, max_tickers: int,
                                     show_progress: bool = True,
                                     progress_callback: Optional[ProgressCallback] = None) -> list:
        """
        Refresh market cap rankings using bulk quotes + OVERVIEW.

        Process:
        1. LISTING_STATUS - get ALL tickers (1 API call)
        2. REALTIME_BULK_QUOTES - get trading data for ALL tickers (~100 API calls)
        3. Sort by trading value (price × volume) to find top tickers
        4. OVERVIEW - get actual market cap for top N tickers (N API calls)

        Args:
            max_tickers: Number of top tickers to fetch OVERVIEW for
            show_progress: Show progress updates
            progress_callback: Custom progress callback

        Returns:
            List of tickers sorted by market cap
        """
        print("=" * 80)
        print("REFRESHING MARKET CAP RANKINGS")
        print("=" * 80)

        # Step 1: Get ALL tickers from LISTING_STATUS
        print("\nStep 1: Fetching ALL tickers from LISTING_STATUS (1 API call)...")
        _, all_tickers, ticker_exchanges = self.ingest_bulk_listing()

        # Filter to US exchanges
        us_exchanges = self.alpha_vantage_cfg.get("us_exchanges", [
            "NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"
        ])
        us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
        print(f"  Found {len(us_tickers)} US exchange tickers")

        # Step 2: Fetch bulk quotes for ALL tickers to rank by trading value
        bulk_calls = (len(us_tickers) + 99) // 100
        print(f"\nStep 2: Fetching bulk quotes for ALL {len(us_tickers)} tickers ({bulk_calls} API calls)...")
        quotes = self.fetch_bulk_quotes(us_tickers, show_progress=show_progress)
        print(f"  Got quotes for {len(quotes)} tickers")

        # Sort by trading value (price × volume) descending
        quotes_sorted = sorted(quotes, key=lambda x: x.get("trading_value", 0), reverse=True)

        # Get top N tickers by trading value
        top_tickers = [q["ticker"] for q in quotes_sorted[:max_tickers]]

        print(f"\nTop 10 by trading value:")
        for i, q in enumerate(quotes_sorted[:10], 1):
            tv = q.get("trading_value", 0) / 1e6
            print(f"  {i:3}. {q['ticker']:6} - ${q['price']:>8.2f} × {int(q['volume']):>12,} = ${tv:>10.1f}M")

        # Step 3: Fetch OVERVIEW for top tickers to get actual market cap
        print(f"\nStep 3: Fetching OVERVIEW for top {len(top_tickers)} tickers ({len(top_tickers)} API calls)...")
        self.ingest_reference_data(
            tickers=top_tickers,
            use_concurrent=False,
            show_progress=show_progress,
            progress_callback=progress_callback
        )

        # Step 4: Return sorted by actual market cap
        print("\nStep 4: Ranking by actual market cap...")
        ranked_tickers = self.get_tickers_by_market_cap(max_tickers=max_tickers)

        print()
        print("=" * 80)
        print(f"✓ Market cap rankings refreshed for {len(ranked_tickers)} tickers")
        print(f"  API calls used: 1 (listing) + {bulk_calls} (bulk quotes) + {len(top_tickers)} (overview)")

        return ranked_tickers

    # =========================================================================
    # Financial Statement Ingestion Methods
    # =========================================================================

    def ingest_income_statements(self, tickers, table_name="income_statements",
                                  use_concurrent=False, show_progress=True,
                                  progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest income statement data for given tickers.

        Uses Alpha Vantage INCOME_STATEMENT endpoint to get annual and quarterly
        income statements with revenue, expenses, net income, etc.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: income_statements)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import IncomeStatementFacet

        print(f"Ingesting income statements for {len(tickers)} tickers...")

        # Generate API calls
        calls = [{"ep_name": "income_statement", "params": {"symbol": t}} for t in tickers]
        print(f"Generated {len(calls)} API calls")

        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        # Fetch data
        if use_concurrent:
            raw_batches = self._fetch_calls_concurrent(
                calls, response_key=None,
                progress_callback=callback, phase="income_statements"
            )
        else:
            raw_batches = self._fetch_calls(
                calls, response_key=None,
                progress_callback=callback, phase="income_statements"
            )

        # Process each response
        all_dfs = []
        for i, batch in enumerate(raw_batches):
            if not batch or len(batch) == 0:
                continue

            response = batch[0] if isinstance(batch, list) else batch
            if isinstance(response, dict) and "Error Message" not in response:
                ticker = tickers[i] if i < len(tickers) else None
                facet = IncomeStatementFacet(self.spark, ticker=ticker)
                try:
                    df = facet.normalize(response)
                    if df.count() > 0:
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Failed to normalize income statement for {ticker}: {e}")

        if not all_dfs:
            print("No income statement data to write")
            return None

        # Union all DataFrames
        from functools import reduce
        final_df = reduce(lambda a, b: a.union(b), all_dfs)

        # Write to bronze - partition by report_type and snapshot_date (NOT ticker)
        # This reduces file count from 8000+ × 2 to just 2-4 files per ingestion
        # Coalesce to reduce file count further
        final_df = final_df.coalesce(4)
        table_path = self.sink.write(final_df, table_name, partitions=["report_type", "snapshot_date"])
        print(f"Written {final_df.count()} income statement records to {table_path}")

        return table_path

    def ingest_balance_sheets(self, tickers, table_name="balance_sheets",
                               use_concurrent=False, show_progress=True,
                               progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest balance sheet data for given tickers.

        Uses Alpha Vantage BALANCE_SHEET endpoint for assets, liabilities, equity.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: balance_sheets)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import BalanceSheetFacet

        print(f"Ingesting balance sheets for {len(tickers)} tickers...")

        calls = [{"ep_name": "balance_sheet", "params": {"symbol": t}} for t in tickers]
        print(f"Generated {len(calls)} API calls")

        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        if use_concurrent:
            raw_batches = self._fetch_calls_concurrent(
                calls, response_key=None,
                progress_callback=callback, phase="balance_sheets"
            )
        else:
            raw_batches = self._fetch_calls(
                calls, response_key=None,
                progress_callback=callback, phase="balance_sheets"
            )

        all_dfs = []
        for i, batch in enumerate(raw_batches):
            if not batch or len(batch) == 0:
                continue

            response = batch[0] if isinstance(batch, list) else batch
            if isinstance(response, dict) and "Error Message" not in response:
                ticker = tickers[i] if i < len(tickers) else None
                facet = BalanceSheetFacet(self.spark, ticker=ticker)
                try:
                    df = facet.normalize(response)
                    if df.count() > 0:
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Failed to normalize balance sheet for {ticker}: {e}")

        if not all_dfs:
            print("No balance sheet data to write")
            return None

        from functools import reduce
        final_df = reduce(lambda a, b: a.union(b), all_dfs)

        # Partition by report_type and snapshot_date (NOT ticker) to reduce file count
        final_df = final_df.coalesce(4)
        table_path = self.sink.write(final_df, table_name, partitions=["report_type", "snapshot_date"])
        print(f"Written {final_df.count()} balance sheet records to {table_path}")

        return table_path

    def ingest_cash_flows(self, tickers, table_name="cash_flows",
                          use_concurrent=False, show_progress=True,
                          progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest cash flow statement data for given tickers.

        Uses Alpha Vantage CASH_FLOW endpoint for operating, investing,
        and financing cash flows.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: cash_flows)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import CashFlowFacet

        print(f"Ingesting cash flows for {len(tickers)} tickers...")

        calls = [{"ep_name": "cash_flow", "params": {"symbol": t}} for t in tickers]
        print(f"Generated {len(calls)} API calls")

        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        if use_concurrent:
            raw_batches = self._fetch_calls_concurrent(
                calls, response_key=None,
                progress_callback=callback, phase="cash_flows"
            )
        else:
            raw_batches = self._fetch_calls(
                calls, response_key=None,
                progress_callback=callback, phase="cash_flows"
            )

        all_dfs = []
        for i, batch in enumerate(raw_batches):
            if not batch or len(batch) == 0:
                continue

            response = batch[0] if isinstance(batch, list) else batch
            if isinstance(response, dict) and "Error Message" not in response:
                ticker = tickers[i] if i < len(tickers) else None
                facet = CashFlowFacet(self.spark, ticker=ticker)
                try:
                    df = facet.normalize(response)
                    if df.count() > 0:
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Failed to normalize cash flow for {ticker}: {e}")

        if not all_dfs:
            print("No cash flow data to write")
            return None

        from functools import reduce
        final_df = reduce(lambda a, b: a.union(b), all_dfs)

        # Partition by report_type and snapshot_date (NOT ticker) to reduce file count
        final_df = final_df.coalesce(4)
        table_path = self.sink.write(final_df, table_name, partitions=["report_type", "snapshot_date"])
        print(f"Written {final_df.count()} cash flow records to {table_path}")

        return table_path

    def ingest_earnings(self, tickers, table_name="earnings",
                        use_concurrent=False, show_progress=True,
                        progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest earnings data (EPS actual vs estimate) for given tickers.

        Uses Alpha Vantage EARNINGS endpoint for EPS and surprise data.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: earnings)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import EarningsFacet

        print(f"Ingesting earnings for {len(tickers)} tickers...")

        calls = [{"ep_name": "earnings", "params": {"symbol": t}} for t in tickers]
        print(f"Generated {len(calls)} API calls")

        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        if use_concurrent:
            raw_batches = self._fetch_calls_concurrent(
                calls, response_key=None,
                progress_callback=callback, phase="earnings"
            )
        else:
            raw_batches = self._fetch_calls(
                calls, response_key=None,
                progress_callback=callback, phase="earnings"
            )

        all_dfs = []
        for i, batch in enumerate(raw_batches):
            if not batch or len(batch) == 0:
                continue

            response = batch[0] if isinstance(batch, list) else batch
            if isinstance(response, dict) and "Error Message" not in response:
                ticker = tickers[i] if i < len(tickers) else None
                facet = EarningsFacet(self.spark, ticker=ticker)
                try:
                    df = facet.normalize(response)
                    if df.count() > 0:
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Failed to normalize earnings for {ticker}: {e}")

        if not all_dfs:
            print("No earnings data to write")
            return None

        from functools import reduce
        final_df = reduce(lambda a, b: a.union(b), all_dfs)

        # Partition by report_type and snapshot_date (NOT ticker) to reduce file count
        final_df = final_df.coalesce(4)
        table_path = self.sink.write(final_df, table_name, partitions=["report_type", "snapshot_date"])
        print(f"Written {final_df.count()} earnings records to {table_path}")

        return table_path

    def ingest_historical_options(self, tickers, table_name="historical_options",
                                   use_concurrent=False, show_progress=True,
                                   progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest historical options chain data for given tickers.

        Uses Alpha Vantage HISTORICAL_OPTIONS endpoint for options data
        including strike, expiry, Greeks, and implied volatility.

        Note: This is a premium endpoint requiring an upgraded API key.

        Args:
            tickers: List of ticker symbols (underlying stocks)
            table_name: Bronze table name (default: historical_options)
            use_concurrent: Use concurrent requests (only for premium tier!)
            show_progress: Show progress updates (default: True)
            progress_callback: Custom progress callback

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import HistoricalOptionsFacet

        print(f"Ingesting historical options for {len(tickers)} underlyings...")
        print("Note: HISTORICAL_OPTIONS requires a premium Alpha Vantage subscription")

        calls = [{"ep_name": "historical_options", "params": {"symbol": t}} for t in tickers]
        print(f"Generated {len(calls)} API calls")

        callback = progress_callback if progress_callback else (default_progress_callback if show_progress else None)

        if use_concurrent:
            raw_batches = self._fetch_calls_concurrent(
                calls, response_key="data",
                progress_callback=callback, phase="historical_options"
            )
        else:
            raw_batches = self._fetch_calls(
                calls, response_key="data",
                progress_callback=callback, phase="historical_options"
            )

        all_dfs = []
        for i, batch in enumerate(raw_batches):
            if not batch or len(batch) == 0:
                continue

            # For options, batch is the data array directly
            ticker = tickers[i] if i < len(tickers) else None
            facet = HistoricalOptionsFacet(self.spark, underlying_ticker=ticker)
            try:
                df = facet.normalize(batch)
                if df.count() > 0:
                    all_dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to normalize options for {ticker}: {e}")

        if not all_dfs:
            print("No historical options data to write")
            return None

        from functools import reduce
        final_df = reduce(lambda a, b: a.union(b), all_dfs)

        table_path = self.sink.write(final_df, table_name, partitions=["underlying_ticker", "option_type"])
        print(f"Written {final_df.count()} options records to {table_path}")

        return table_path

    def ingest_fundamentals(self, tickers, use_concurrent=False, show_progress=True,
                            progress_callback: Optional[ProgressCallback] = None):
        """
        Ingest complete fundamentals for given tickers.

        This is a convenience method that ingests:
        - Income statements
        - Balance sheets
        - Cash flows
        - Earnings

        Args:
            tickers: List of ticker symbols
            use_concurrent: Use concurrent requests (premium tier only)
            show_progress: Show progress updates
            progress_callback: Custom progress callback

        Returns:
            Dict with paths to all written tables
        """
        print(f"Ingesting complete fundamentals for {len(tickers)} tickers...")
        print("=" * 80)

        results = {}

        print("\n📊 Step 1/4: Income Statements")
        print("-" * 40)
        results['income_statements'] = self.ingest_income_statements(
            tickers, use_concurrent=use_concurrent,
            show_progress=show_progress, progress_callback=progress_callback
        )

        print("\n📊 Step 2/4: Balance Sheets")
        print("-" * 40)
        results['balance_sheets'] = self.ingest_balance_sheets(
            tickers, use_concurrent=use_concurrent,
            show_progress=show_progress, progress_callback=progress_callback
        )

        print("\n📊 Step 3/4: Cash Flows")
        print("-" * 40)
        results['cash_flows'] = self.ingest_cash_flows(
            tickers, use_concurrent=use_concurrent,
            show_progress=show_progress, progress_callback=progress_callback
        )

        print("\n📊 Step 4/4: Earnings")
        print("-" * 40)
        results['earnings'] = self.ingest_earnings(
            tickers, use_concurrent=use_concurrent,
            show_progress=show_progress, progress_callback=progress_callback
        )

        print("\n" + "=" * 80)
        print("✓ Complete fundamentals ingestion finished")

        return results

    def run_comprehensive(self, tickers=None, date_from=None, date_to=None,
                          max_tickers=None, use_concurrent=False, use_bulk_listing=False,
                          include_fundamentals=True, include_options=False,
                          skip_reference_refresh=False, outputsize="full",
                          sort_by_market_cap=True, min_market_cap=None,
                          show_progress=True,
                          progress_callback: Optional[ProgressCallback] = None,
                          **kwargs):
        """
        Run comprehensive ingestion: reference + prices + fundamentals + options.

        This is the extended version of run_all that supports the full data
        coverage needed for forecasting and analysis.

        Args:
            tickers: List of ticker symbols (default: top tickers by market cap)
            date_from: Start date for prices (YYYY-MM-DD)
            date_to: End date for prices (YYYY-MM-DD)
            max_tickers: Limit number of tickers (default: 2000 for fundamentals)
            use_concurrent: Use concurrent requests (premium tier only)
            use_bulk_listing: Use LISTING_STATUS for bulk ticker discovery
            include_fundamentals: Include income statements, balance sheets, cash flows, earnings
            include_options: Include historical options data (premium endpoint)
            skip_reference_refresh: Skip OVERVIEW calls
            outputsize: 'compact' or 'full' for price data
            sort_by_market_cap: Sort tickers by market cap descending (default: True)
            min_market_cap: Minimum market cap filter in dollars (e.g., 1e9 for $1B)
            show_progress: Show progress updates
            progress_callback: Custom progress callback

        Returns:
            Dict with ingested tickers and paths
        """
        # If using bulk listing, skip market cap pre-filtering
        # The bulk listing will provide tickers directly from Alpha Vantage
        if use_bulk_listing:
            # Let run_all() handle ticker discovery via LISTING_STATUS
            tickers = None
            print("Using BULK LISTING mode - will discover tickers from Alpha Vantage")
            print()
        # If sorting by market cap and no specific tickers provided (and not using bulk listing)
        elif sort_by_market_cap and tickers is None:
            if not max_tickers:
                raise ValueError("--max-tickers is required when using market cap sorting")

            print("=" * 80)
            print("MARKET CAP RANKING MODE")
            print("=" * 80)
            print("Selecting top stocks by market capitalization...")
            print()

            # Use existing market cap data from securities_reference
            tickers = self.get_tickers_by_market_cap(
                max_tickers=max_tickers,
                min_market_cap=min_market_cap
            )

            if len(tickers) < max_tickers:
                print()
                print(f"⚠️  Only {len(tickers)} tickers have market cap data.")
                print(f"   Requested: {max_tickers}")
                print()
                print("To populate market cap rankings, run:")
                print("  python -m scripts.ingest.refresh_market_cap_rankings")
                print()

                if len(tickers) == 0:
                    print("ERROR: No market cap data available. Cannot proceed with market cap sorting.")
                    print("Run the refresh script first, or use --no-sort-by-market-cap")
                    raise ValueError("No market cap data available for sorting")

            print(f"Using {len(tickers)} tickers from existing market cap rankings")
            print()

        # First run the standard ingestion (reference + prices)
        effective_skip_reference = skip_reference_refresh

        ingested_tickers = self.run_all(
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            max_tickers=max_tickers,
            use_concurrent=use_concurrent,
            use_bulk_listing=use_bulk_listing,
            skip_reference_refresh=effective_skip_reference,
            outputsize=outputsize,
            show_progress=show_progress,
            progress_callback=progress_callback,
            **kwargs
        )

        results = {'tickers': ingested_tickers}

        # Ingest fundamentals if requested
        if include_fundamentals and ingested_tickers:
            print("\n" + "=" * 80)
            print("FUNDAMENTALS INGESTION")
            print("=" * 80)
            fundamentals_results = self.ingest_fundamentals(
                ingested_tickers,
                use_concurrent=use_concurrent,
                show_progress=show_progress,
                progress_callback=progress_callback
            )
            results.update(fundamentals_results)

        # Ingest options if requested (premium endpoint)
        if include_options and ingested_tickers:
            print("\n" + "=" * 80)
            print("OPTIONS INGESTION (Premium Endpoint)")
            print("=" * 80)
            results['historical_options'] = self.ingest_historical_options(
                ingested_tickers,
                use_concurrent=use_concurrent,
                show_progress=show_progress,
                progress_callback=progress_callback
            )

        print("\n" + "=" * 80)
        print(f"✓ Comprehensive ingestion complete for {len(ingested_tickers)} tickers")

        return results
