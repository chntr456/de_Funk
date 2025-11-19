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
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

from datapipelines.providers.alpha_vantage.alpha_vantage_registry import AlphaVantageRegistry
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
        self.registry = AlphaVantageRegistry(alpha_vantage_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool(
                (alpha_vantage_cfg.get("credentials") or {}).get("api_keys") or [],
                cooldown_seconds=60.0  # 1-minute cooldown for rate limiting
            )
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark
        self._http_lock = threading.Lock()

    def _fetch_calls(self, calls, response_key=None):
        """
        Fetch data from Alpha Vantage API.

        Alpha Vantage doesn't use pagination like Polygon.
        Most endpoints return full data in single response.

        Args:
            calls: Iterator of call specs (ep_name, params)
            response_key: Key in response containing data (None for top-level)

        Returns:
            List of batches (one batch per call)
        """
        batches = []
        for call in calls:
            ep, path, query = self.registry.render(call["ep_name"], **call["params"])

            # Make request (thread-safe)
            with self._http_lock:
                payload = self.http.request(ep.base, path, query, ep.method)

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
            else:
                # No response key - return entire payload
                batches.append([payload])

        return batches

    def _fetch_calls_concurrent(self, calls, response_key=None, max_workers=5):
        """
        Fetch data with concurrent requests.

        WARNING: Only use for premium tier with higher rate limits!
        Free tier should use sequential _fetch_calls() to avoid hitting limits.

        Args:
            calls: Iterator of call specs
            response_key: Key in response containing data
            max_workers: Maximum concurrent workers (default: 5 for premium tier)

        Returns:
            List of batches (one batch per call)
        """
        batches = [None] * len(list(calls))  # Pre-allocate to maintain order
        calls_list = list(calls)

        def fetch_single_call(i, call):
            ep, path, query = self.registry.render(call["ep_name"], **call["params"])

            # Make request (thread-safe)
            with self._http_lock:
                payload = self.http.request(ep.base, path, query, ep.method)

            # Extract data
            if response_key:
                data = payload.get(response_key)
                if isinstance(data, list):
                    return i, data
                elif isinstance(data, dict):
                    return i, [payload]
                else:
                    return i, []
            else:
                return i, [payload]

        # Execute concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_single_call, i, call): i
                for i, call in enumerate(calls_list)
            }

            for future in as_completed(futures):
                i, batch = future.result()
                batches[i] = batch

        return batches

    def ingest_reference_data(self, tickers, table_name="securities_reference", use_concurrent=False):
        """
        Ingest reference data (company overview) for given tickers.

        Uses Alpha Vantage OVERVIEW endpoint to get company fundamentals.

        Args:
            tickers: List of ticker symbols
            table_name: Bronze table name (default: securities_reference)
            use_concurrent: Use concurrent requests (only for premium tier!)

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import SecuritiesReferenceFacetAV

        print(f"Ingesting reference data for {len(tickers)} tickers...")

        # Create facet
        facet = SecuritiesReferenceFacetAV(self.spark, tickers=tickers)

        # Generate API calls
        calls = list(facet.calls())
        print(f"Generated {len(calls)} API calls")

        # Fetch data (sequential or concurrent)
        if use_concurrent:
            print("WARNING: Using concurrent requests. Ensure you have premium tier!")
            raw_batches = self._fetch_calls_concurrent(calls, response_key=None)
        else:
            print(f"Fetching data sequentially (rate limit: {self.registry.rate_limit} calls/sec)")
            raw_batches = self._fetch_calls(calls, response_key=None)

        # Normalize to DataFrame
        df = facet.normalize(raw_batches)
        df = facet.postprocess(df)
        df = facet.validate(df)

        # Write to bronze
        table_path = self.sink.write(df, table_name, partitions=["snapshot_dt", "asset_type"])
        print(f"Written {df.count()} rows to {table_path}")

        return table_path

    def ingest_prices(self, tickers, date_from=None, date_to=None,
                     table_name="securities_prices_daily",
                     adjusted=True, outputsize="full", use_concurrent=False):
        """
        Ingest daily OHLCV prices for given tickers.

        Uses Alpha Vantage TIME_SERIES_DAILY_ADJUSTED endpoint.

        Args:
            tickers: List of ticker symbols
            date_from: Start date (YYYY-MM-DD), used for filtering after fetch
            date_to: End date (YYYY-MM-DD), used for filtering after fetch
            table_name: Bronze table name (default: securities_prices_daily)
            adjusted: Use adjusted prices (default: True)
            outputsize: 'compact' (100 days) or 'full' (20+ years)
            use_concurrent: Use concurrent requests (only for premium tier!)

        Returns:
            Path to written bronze table
        """
        from datapipelines.providers.alpha_vantage.facets import SecuritiesPricesFacetAV

        print(f"Ingesting prices for {len(tickers)} tickers...")
        print(f"Date range: {date_from or 'ALL'} to {date_to or 'ALL'}")
        print(f"Output size: {outputsize}, Adjusted: {adjusted}")

        # Create facet
        facet = SecuritiesPricesFacetAV(
            self.spark,
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            adjusted=adjusted,
            outputsize=outputsize
        )

        # Generate API calls
        calls = list(facet.calls())
        print(f"Generated {len(calls)} API calls")

        # Fetch data (sequential or concurrent)
        if use_concurrent:
            print("WARNING: Using concurrent requests. Ensure you have premium tier!")
            raw_batches = self._fetch_calls_concurrent(calls, response_key="Time Series (Daily)")
        else:
            print(f"Fetching data sequentially (rate limit: {self.registry.rate_limit} calls/sec)")
            raw_batches = self._fetch_calls(calls, response_key="Time Series (Daily)")

        # Normalize to DataFrame
        df = facet.normalize(raw_batches)
        df = facet.postprocess(df)
        df = facet.validate(df)

        # Write to bronze
        table_path = self.sink.write(df, table_name, partitions=["trade_date", "asset_type"])
        print(f"Written {df.count()} rows to {table_path}")

        return table_path

    def ingest_bulk_listing(self, table_name="securities_reference"):
        """
        Ingest bulk listing of all active stocks.

        Uses Alpha Vantage LISTING_STATUS endpoint which returns CSV.
        This is more efficient than calling OVERVIEW for each ticker.

        Note: This endpoint returns limited data (no fundamentals).
        For full company data, use ingest_reference_data() with specific tickers.

        Args:
            table_name: Bronze table name (default: securities_reference)

        Returns:
            Path to written bronze table
        """
        print("Note: LISTING_STATUS returns limited data. For fundamentals, use ingest_reference_data().")

        # TODO: Implement CSV parsing for LISTING_STATUS endpoint
        # Alpha Vantage returns CSV format for this endpoint
        # Need to convert to DataFrame and normalize to securities_reference schema

        raise NotImplementedError("Bulk listing ingestion not yet implemented. Use ingest_reference_data() with ticker list.")

    def run_all(self, tickers=None, date_from=None, date_to=None,
                max_tickers=None, use_concurrent=False, **kwargs):
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
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            List of ingested tickers
        """
        # Default tickers if none provided
        if not tickers:
            tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'WMT']

        # Apply ticker limit
        if max_tickers:
            tickers = tickers[:max_tickers]

        print(f"Running full ingestion for {len(tickers)} tickers...")
        print(f"Date range: {date_from} to {date_to}")
        print(f"Concurrent mode: {use_concurrent}")
        print()

        # Step 1: Ingest reference data
        print("Step 1: Ingesting reference data...")
        print("-" * 80)
        self.ingest_reference_data(tickers=tickers, use_concurrent=use_concurrent)
        print()

        # Step 2: Ingest prices
        print("Step 2: Ingesting prices...")
        print("-" * 80)
        self.ingest_prices(
            tickers=tickers,
            date_from=date_from,
            date_to=date_to,
            use_concurrent=use_concurrent
        )
        print()

        print(f"✓ Full ingestion complete for {len(tickers)} tickers")
        return tickers
