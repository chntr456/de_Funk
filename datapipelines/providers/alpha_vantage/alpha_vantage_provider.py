"""
Alpha Vantage Provider Implementation.

Implements data ingestion from Alpha Vantage API.
Configuration loaded from markdown documentation (single source of truth).

Features:
- Rate limiting: Pro tier 75 calls/min (1.25 calls/sec)
- Bulk ticker discovery via LISTING_STATUS endpoint
- All financial statement endpoints (income, balance, cash flow, earnings)
- Integration with IngestorEngine for distributed cluster execution

Usage:
    from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider
    from datapipelines.base.ingestor_engine import IngestorEngine

    provider = create_alpha_vantage_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Set tickers to process
    provider.set_tickers(["AAPL", "MSFT", "GOOGL"])

    # Ingest specific data types
    results = engine.run(work_items=["prices", "reference"])

Author: de_Funk Team
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import List, Optional, Any, Dict, Generator
from pathlib import Path

from pyspark.sql import DataFrame

from datapipelines.base.provider import BaseProvider, DataType, FetchResult
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from config.logging import get_logger

logger = get_logger(__name__)


# Mapping from DataType enum to endpoint_id in markdown
DATATYPE_TO_ENDPOINT = {
    DataType.REFERENCE: "company_overview",
    DataType.PRICES: "time_series_daily_adjusted",
    DataType.INCOME_STATEMENT: "income_statement",
    DataType.BALANCE_SHEET: "balance_sheet",
    DataType.CASH_FLOW: "cash_flow",
    DataType.EARNINGS: "earnings",
    DataType.OPTIONS: "historical_options",
}


class AlphaVantageProvider(BaseProvider):
    """
    Alpha Vantage implementation of BaseProvider.

    Configuration loaded from:
    - Data Sources/Providers/Alpha Vantage.md
    - Data Sources/Endpoints/Alpha Vantage/**/*.md
    """

    PROVIDER_NAME = "Alpha Vantage"

    def __init__(
        self,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize Alpha Vantage provider.

        Args:
            spark: SparkSession
            docs_path: Path to repo root
            storage_path: Path to storage root (for raw layer - automatic like Socrata)
        """
        # Tickers to process (set via set_tickers() before running)
        self._tickers: List[str] = []

        # Raw layer storage (automatic when storage_path is set, like Socrata)
        self._storage_path = Path(storage_path) if storage_path else None

        # Initialize base (loads markdown config)
        super().__init__(
            provider_id="alpha_vantage",
            spark=spark,
            docs_path=docs_path
        )

    def _setup(self) -> None:
        """Setup HTTP client and API key pool."""
        # Get API keys from environment
        api_keys = []
        if self.env_api_key:
            env_value = os.environ.get(self.env_api_key, "")
            if env_value:
                api_keys = [k.strip() for k in env_value.split(",") if k.strip()]

        self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0)

        # Build base URLs dict for HttpClient
        base_urls = {"core": self.base_url} if self.base_url else {}

        # Get headers from config (usually empty for Alpha Vantage)
        headers = {}
        if self._provider_config:
            headers = self._provider_config.default_headers or {}

        # Create HTTP client
        self.http = HttpClient(
            base_urls,
            headers,
            self.rate_limit,
            self.key_pool
        )

        # Thread lock for HTTP requests
        self._http_lock = threading.Lock()

        # Get US exchanges from provider settings
        self._us_exchanges = self.get_provider_setting(
            'us_exchanges',
            ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
        )

        logger.info(
            f"AlphaVantageProvider initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={self.rate_limit}"
        )
        if self._storage_path:
            logger.info(f"Raw layer enabled: {self._storage_path}/raw/alpha_vantage/")

    # =========================================================================
    # RAW DATA DUMP (automatic when storage_path is set, like Socrata)
    # =========================================================================

    def enable_raw_save(self, storage_path: Path = None, enabled: bool = True) -> None:
        """
        Enable/disable saving raw API responses (JSON files) before transformation.

        Raw responses are saved to: {storage_path}/raw/alpha_vantage/{endpoint_id}/{ticker}.json

        Args:
            storage_path: Base storage path (optional - updates storage_path if provided)
            enabled: Whether to enable raw saving
        """
        if storage_path:
            self._storage_path = Path(storage_path) if enabled else None
        elif not enabled:
            self._storage_path = None

        if self._storage_path:
            raw_dir = self._storage_path / 'raw' / 'alpha_vantage'
            raw_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Raw data dump enabled: {raw_dir}")
        else:
            logger.info("Raw data dump disabled")

    def _get_raw_path(self, endpoint_id: str, ticker: str) -> Optional[Path]:
        """
        Get the raw layer file path for a JSON response.

        Raw layer structure (consistent with Socrata):
            storage/raw/alpha_vantage/{endpoint_id}/{ticker}.json

        Args:
            endpoint_id: API endpoint identifier
            ticker: Ticker symbol

        Returns:
            Path to raw JSON file, or None if storage_path not configured
        """
        if not self._storage_path:
            return None

        raw_dir = self._storage_path / 'raw' / 'alpha_vantage' / endpoint_id
        return raw_dir / f"{ticker}.json"

    def _save_raw_response(
        self,
        ticker: str,
        endpoint_id: str,
        payload: Any,
        timestamp: datetime = None
    ) -> Optional[Path]:
        """
        Save raw API response to JSON file.

        Args:
            ticker: Ticker symbol
            endpoint_id: API endpoint identifier
            payload: Raw API response (dict or list)
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to saved file, or None if storage_path not configured
        """
        file_path = self._get_raw_path(endpoint_id, ticker)
        if not file_path:
            return None

        try:
            # Create endpoint directory
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Add metadata wrapper
            ts = timestamp or datetime.now()
            raw_data = {
                "_meta": {
                    "ticker": ticker,
                    "endpoint_id": endpoint_id,
                    "fetched_at": ts.isoformat(),
                    "provider": "alpha_vantage"
                },
                "response": payload
            }

            with open(file_path, 'w') as f:
                json.dump(raw_data, f, indent=2, default=str)

            logger.debug(f"Saved raw response: {file_path}")
            return file_path

        except Exception as e:
            logger.warning(f"Failed to save raw response for {ticker}/{endpoint_id}: {e}")
            return None

    # =========================================================================
    # TICKER MANAGEMENT
    # =========================================================================

    def set_tickers(self, tickers: List[str]) -> None:
        """
        Set tickers to process for ingestion.

        Must be called before using fetch() or running with IngestorEngine.

        Args:
            tickers: List of ticker symbols
        """
        self._tickers = tickers
        logger.info(f"AlphaVantageProvider: set {len(tickers)} tickers")

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION
    # =========================================================================

    def list_work_items(self, **kwargs) -> List[str]:
        """List available data types for ingestion."""
        # Return DataType values that have corresponding endpoints configured
        work_items = []
        for dt, endpoint_id in DATATYPE_TO_ENDPOINT.items():
            if endpoint_id in self._endpoints:
                work_items.append(dt.value)
        return work_items

    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch data for a data type, yielding batches of records.

        Iterates through tickers and fetches the specified data type for each.
        """
        data_type = self._get_data_type(work_item)
        if not data_type:
            logger.warning(f"Unknown work item: {work_item}")
            return

        if not self._tickers:
            logger.warning("No tickers set. Call set_tickers() before fetch().")
            return

        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id or endpoint_id not in self._endpoints:
            logger.warning(f"No endpoint configured for: {work_item}")
            return

        logger.info(f"Fetching {work_item} for {len(self._tickers)} tickers")

        total_records = 0
        for ticker in self._tickers:
            if max_records and total_records >= max_records:
                logger.info(f"Reached max_records limit ({max_records})")
                break

            result = self._fetch_single(ticker, data_type, **kwargs)

            if not result.success:
                logger.warning(f"Failed to fetch {work_item} for {ticker}: {result.error}")
                continue

            if result.data:
                records = self._convert_to_records(ticker, data_type, result.data)
                if records:
                    total_records += len(records)
                    yield records

        logger.info(f"Fetched {total_records} records for {work_item}")

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize raw records to a Spark DataFrame."""
        if not records:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        data_type = self._get_data_type(work_item)
        if not data_type:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        try:
            if data_type == DataType.PRICES:
                return self._normalize_prices(records, work_item)
            elif data_type == DataType.REFERENCE:
                return self._normalize_reference(records, work_item)
            elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                              DataType.CASH_FLOW, DataType.EARNINGS):
                return self._normalize_financials(records, data_type)
        except Exception as e:
            logger.warning(f"Failed to normalize {work_item}: {e}", exc_info=True)

        return self.spark.createDataFrame(records, samplingRatio=1.0)

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name from endpoint config.

        If bronze.table is just the provider name (no slash), appends the endpoint_id.
        e.g., bronze: alpha_vantage + endpoint_id: prices_daily -> alpha_vantage/prices_daily
        """
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                endpoint = self._endpoints.get(endpoint_id)
                if endpoint and endpoint.bronze:
                    table = endpoint.bronze.table
                    # If table is just provider name (no slash), append endpoint name
                    if '/' not in table:
                        return f"{table}/{endpoint_id}"
                    return table
        return f"alpha_vantage_{work_item}"

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """Get partition columns from endpoint config."""
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                return super().get_partitions(endpoint_id)
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """Get key columns from endpoint config."""
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                return super().get_key_columns(endpoint_id)
        return ["ticker"]

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_data_type(self, work_item: str) -> Optional[DataType]:
        """Convert work_item string to DataType enum."""
        for dt in DataType:
            if dt.value == work_item:
                return dt
        return None

    def _get_response_key(self, data_type: DataType) -> Optional[str]:
        """Get response key from endpoint config."""
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if endpoint_id:
            endpoint = self._endpoints.get(endpoint_id)
            if endpoint:
                return endpoint.response_key
        return None

    def _convert_to_records(
        self,
        ticker: str,
        data_type: DataType,
        data: Any
    ) -> List[Dict]:
        """Convert raw API data to list of record dicts."""
        records = []

        if data_type == DataType.REFERENCE:
            if isinstance(data, dict):
                record = dict(data)
                # Only add ticker if Symbol not in response (Symbol gets renamed to ticker)
                if 'Symbol' not in record:
                    record['ticker'] = ticker
                records.append(record)

        elif data_type == DataType.PRICES:
            if isinstance(data, dict):
                for date_str, ohlcv in data.items():
                    record = dict(ohlcv)
                    record['ticker'] = ticker
                    record['trade_date'] = date_str
                    records.append(record)

        elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                          DataType.CASH_FLOW):
            if isinstance(data, dict):
                for report_type in ['annualReports', 'quarterlyReports']:
                    for report in data.get(report_type, []):
                        record = dict(report)
                        record['ticker'] = ticker
                        record['report_type'] = 'annual' if 'annual' in report_type.lower() else 'quarterly'
                        records.append(record)

        elif data_type == DataType.EARNINGS:
            # EARNINGS API uses different keys: annualEarnings, quarterlyEarnings
            if isinstance(data, dict):
                for report_type in ['annualEarnings', 'quarterlyEarnings']:
                    for report in data.get(report_type, []):
                        record = dict(report)
                        record['ticker'] = ticker
                        record['report_type'] = 'annual' if 'annual' in report_type.lower() else 'quarterly'
                        records.append(record)

        return records

    # =========================================================================
    # NORMALIZATION METHODS
    # =========================================================================

    def _normalize_prices(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize price records using schema from markdown."""
        from pyspark.sql.types import (
            StructType, StructField, StringType, DateType, DoubleType,
            LongType, BooleanType, IntegerType
        )
        import pandas as pd

        pdf = pd.DataFrame(records)
        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Get field mappings from endpoint schema
        endpoint_id = DATATYPE_TO_ENDPOINT.get(DataType.PRICES)
        field_mappings = self.get_field_mappings(endpoint_id) if endpoint_id else {}

        # Parse trade_date - keep as datetime64 for proper Spark DateType conversion
        pdf['trade_date'] = pd.to_datetime(pdf['trade_date'], errors='coerce')
        pdf['year'] = pdf['trade_date'].dt.year.astype('Int32')
        pdf['month'] = pdf['trade_date'].dt.month.astype('Int32')
        # Normalize to midnight (date only) but keep as datetime64 for Spark compatibility
        pdf['trade_date'] = pdf['trade_date'].dt.normalize()

        # Apply field mappings from schema (source -> target)
        # Reverse mapping for renaming: source_name -> target_name
        rename_map = {src: tgt for src, tgt in field_mappings.items()
                      if src in pdf.columns}
        pdf = pdf.rename(columns=rename_map)

        # Convert numeric fields
        numeric_fields = ['open', 'high', 'low', 'close', 'adjusted_close',
                         'volume', 'dividend_amount', 'split_coefficient']
        for field in numeric_fields:
            if field in pdf.columns:
                pdf[field] = pd.to_numeric(pdf[field], errors='coerce').astype('float64')

        # Calculate VWAP approximation
        if all(f in pdf.columns for f in ['high', 'low', 'close']):
            pdf['volume_weighted'] = ((pdf['high'] + pdf['low'] + pdf['close']) / 3.0).astype('float64')

        # Add missing fields
        pdf['transactions'] = None
        pdf['otc'] = False
        if 'asset_type' not in pdf.columns:
            pdf['asset_type'] = 'stocks'

        # Select final columns
        final_cols = ['trade_date', 'ticker', 'asset_type', 'year', 'month',
                      'open', 'high', 'low', 'close', 'volume', 'volume_weighted',
                      'transactions', 'otc', 'adjusted_close', 'dividend_amount',
                      'split_coefficient']
        for col in final_cols:
            if col not in pdf.columns:
                pdf[col] = None
        pdf = pdf[final_cols]

        schema = StructType([
            StructField("trade_date", DateType(), True),
            StructField("ticker", StringType(), True),
            StructField("asset_type", StringType(), True),
            StructField("year", IntegerType(), True),
            StructField("month", IntegerType(), True),
            StructField("open", DoubleType(), True),
            StructField("high", DoubleType(), True),
            StructField("low", DoubleType(), True),
            StructField("close", DoubleType(), True),
            StructField("volume", DoubleType(), True),
            StructField("volume_weighted", DoubleType(), True),
            StructField("transactions", LongType(), True),
            StructField("otc", BooleanType(), True),
            StructField("adjusted_close", DoubleType(), True),
            StructField("dividend_amount", DoubleType(), True),
            StructField("split_coefficient", DoubleType(), True)
        ])

        return self.spark.createDataFrame(pdf, schema=schema)

    def _normalize_reference(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize reference/overview records using schema from markdown."""
        import pandas as pd
        from datetime import datetime

        pdf = pd.DataFrame(records)
        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Get field mappings and coercions from endpoint schema
        endpoint_id = DATATYPE_TO_ENDPOINT.get(DataType.REFERENCE)
        field_mappings = self.get_field_mappings(endpoint_id) if endpoint_id else {}
        type_coercions = self.get_type_coercions(endpoint_id) if endpoint_id else {}

        # Apply field mappings from schema (source -> target)
        rename_map = {src: tgt for src, tgt in field_mappings.items()
                      if src in pdf.columns}
        pdf = pdf.rename(columns=rename_map)

        # Apply type coercions from schema
        for field_name, coerce_type in type_coercions.items():
            if field_name in pdf.columns:
                if coerce_type in ('long', 'int', 'integer'):
                    pdf[field_name] = pd.to_numeric(pdf[field_name], errors='coerce').astype('Int64')
                elif coerce_type in ('double', 'float'):
                    pdf[field_name] = pd.to_numeric(pdf[field_name], errors='coerce').astype('float64')

        # Add metadata
        pdf['asset_type'] = 'stocks'
        pdf['snapshot_date'] = datetime.now().date()
        pdf['ingestion_timestamp'] = datetime.now()

        return self.spark.createDataFrame(pdf, samplingRatio=1.0)

    def _normalize_financials(self, records: List[Dict], data_type: DataType) -> DataFrame:
        """Normalize financial statement records using schema from markdown."""
        import pandas as pd
        from datetime import datetime

        pdf = pd.DataFrame(records)
        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Get endpoint config
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id:
            return self.spark.createDataFrame(pdf, samplingRatio=1.0)

        # Get field mappings and coercions from markdown schema
        field_mappings = self.get_field_mappings(endpoint_id)
        type_coercions = self.get_type_coercions(endpoint_id)

        # Apply field mappings (source -> target)
        rename_map = {src: tgt for src, tgt in field_mappings.items()
                      if src in pdf.columns}
        pdf = pdf.rename(columns=rename_map)

        # Apply type coercions
        for field_name, coerce_type in type_coercions.items():
            if field_name in pdf.columns:
                if coerce_type in ('long', 'int', 'integer'):
                    pdf[field_name] = pd.to_numeric(pdf[field_name], errors='coerce').astype('Int64')
                elif coerce_type in ('double', 'float'):
                    pdf[field_name] = pd.to_numeric(pdf[field_name], errors='coerce').astype('float64')

        # Parse date fields
        if 'fiscal_date_ending' in pdf.columns:
            pdf['fiscal_date_ending'] = pd.to_datetime(pdf['fiscal_date_ending'], errors='coerce')

        # Add metadata
        pdf['ingestion_timestamp'] = datetime.now()
        pdf['snapshot_date'] = datetime.now().date()

        return self.spark.createDataFrame(pdf, samplingRatio=1.0)

    # =========================================================================
    # API REQUEST HELPERS
    # =========================================================================

    def _fetch_single(
        self,
        ticker: str,
        data_type: DataType,
        **kwargs
    ) -> FetchResult:
        """Fetch a single data type for a ticker."""
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=f"Unsupported data type: {data_type}"
            )

        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=f"Endpoint not configured: {endpoint_id}"
            )

        try:
            # Build query params from endpoint config
            params = dict(endpoint.default_query or {})
            params["symbol"] = ticker
            if data_type == DataType.PRICES:
                params["outputsize"] = kwargs.get("outputsize", "full")

            # Add API key
            params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

            # Make request
            with self._http_lock:
                payload = self.http.request("core", "", params, "GET")

            # Save raw response before any transformation (automatic when storage_path set)
            if self._storage_path:
                self._save_raw_response(ticker, endpoint_id, payload)

            # Check for API errors
            if isinstance(payload, dict):
                if "Error Message" in payload:
                    return FetchResult(
                        ticker=ticker,
                        data_type=data_type,
                        success=False,
                        error=payload["Error Message"][:60]
                    )
                if "Information" in payload and len(payload) == 1:
                    return FetchResult(
                        ticker=ticker,
                        data_type=data_type,
                        success=False,
                        error="API limit reached"
                    )

            # Extract data using response key from config
            response_key = endpoint.response_key
            if response_key:
                data = payload.get(response_key, payload)
            else:
                data = payload

            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=True,
                data=data
            )

        except Exception as e:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=str(e)[:50]
            )

    # =========================================================================
    # TICKER DISCOVERY AND SEEDING
    # =========================================================================

    def discover_tickers(self, state: str = "active", **kwargs) -> tuple:
        """Discover tickers using LISTING_STATUS endpoint."""
        import csv
        import io

        endpoint = self._endpoints.get("listing_status")
        if not endpoint:
            logger.warning("listing_status endpoint not configured")
            return [], {}

        params = dict(endpoint.default_query or {})
        params["state"] = state
        params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

        with self._http_lock:
            response_text = self.http.request_text("core", "", params, "GET")

        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        tickers = [row['symbol'] for row in rows if row.get('symbol')]
        ticker_exchanges = {
            row['symbol']: row.get('exchange', 'UNKNOWN')
            for row in rows if row.get('symbol')
        }

        us_tickers = [t for t in tickers if ticker_exchanges.get(t) in self._us_exchanges]

        return us_tickers, ticker_exchanges

    def get_tickers_by_market_cap(
        self,
        max_tickers: int = None,
        min_market_cap: float = None,
        storage_cfg: Dict = None
    ) -> List[str]:
        """Get tickers sorted by market cap from existing reference data."""
        from pyspark.sql.functions import col, desc, isnan, upper

        if not storage_cfg:
            logger.warning("No storage config provided for market cap ranking")
            return []

        # Market cap is in company_reference (from COMPANY_OVERVIEW), not securities_reference
        bronze_path = Path(storage_cfg["roots"]["bronze"]) / "company_reference"

        if not bronze_path.exists():
            logger.debug(f"company_reference not found at {bronze_path}")
            return []

        try:
            if (bronze_path / "_delta_log").exists():
                df = self.spark.read.format("delta").load(str(bronze_path))
            else:
                df = self.spark.read.parquet(str(bronze_path))

            df_filtered = df.filter(
                (col("market_cap").isNotNull()) &
                (~isnan(col("market_cap"))) &
                (col("market_cap") > 0)
            )

            if "asset_type" in df.columns:
                df_filtered = df_filtered.filter(col("asset_type") == "stocks")

            if min_market_cap:
                df_filtered = df_filtered.filter(col("market_cap") >= min_market_cap)

            df_filtered = df_filtered.filter(
                (~upper(col("ticker")).rlike(r".*[-]?W[S]?$")) &
                (~upper(col("ticker")).rlike(r".*-P-.*|.*-P[A-Z]$"))
            )

            df_ranked = (df_filtered
                        .select("ticker", "market_cap")
                        .dropDuplicates(["ticker"])
                        .orderBy(desc("market_cap")))

            if max_tickers:
                df_ranked = df_ranked.limit(max_tickers)

            rows = df_ranked.collect()
            return [row.ticker for row in rows]

        except Exception as e:
            logger.warning(f"Failed to get market cap rankings: {e}")
            return []

    def seed_tickers(
        self,
        state: str = "active",
        filter_us_exchanges: bool = True
    ) -> Any:
        """Seed tickers from LISTING_STATUS endpoint to Bronze layer."""
        import csv
        import io
        from datetime import datetime
        from pyspark.sql.types import (
            StructType, StructField, StringType, DateType, TimestampType
        )

        logger.info(f"Seeding tickers (state={state})")

        endpoint = self._endpoints.get("listing_status")
        if not endpoint:
            logger.warning("listing_status endpoint not configured")
            return self.spark.createDataFrame([], samplingRatio=1.0)

        params = dict(endpoint.default_query or {})
        params["state"] = state
        params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

        with self._http_lock:
            response_text = self.http.request_text("core", "", params, "GET")

        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        logger.info(f"Fetched {len(rows)} tickers from LISTING_STATUS")

        if filter_us_exchanges:
            rows = [r for r in rows if r.get('exchange') in self._us_exchanges]
            logger.info(f"Filtered to {len(rows)} US exchange tickers")

        now = datetime.now()
        transformed = []
        for row in rows:
            ipo_date = None
            if row.get('ipoDate'):
                try:
                    ipo_date = datetime.strptime(row['ipoDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            delisting_date = None
            if row.get('delistingDate'):
                try:
                    delisting_date = datetime.strptime(row['delistingDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            asset_type_raw = row.get('assetType', 'Stock')
            if asset_type_raw == 'Stock':
                asset_type = 'stocks'
            elif asset_type_raw == 'ETF':
                asset_type = 'etfs'
            else:
                asset_type = 'stocks'

            transformed.append({
                'ticker': row.get('symbol'),
                'security_name': row.get('name'),
                'asset_type': asset_type,
                'exchange_code': row.get('exchange'),
                'ipo_date': ipo_date,
                'delisting_date': delisting_date,
                'status': row.get('status', 'Active'),
                'ingestion_timestamp': now,
                'snapshot_date': now.date(),
            })

        schema = StructType([
            StructField('ticker', StringType(), False),
            StructField('security_name', StringType(), True),
            StructField('asset_type', StringType(), True),
            StructField('exchange_code', StringType(), True),
            StructField('ipo_date', DateType(), True),
            StructField('delisting_date', DateType(), True),
            StructField('status', StringType(), True),
            StructField('ingestion_timestamp', TimestampType(), True),
            StructField('snapshot_date', DateType(), True),
        ])

        df = self.spark.createDataFrame(transformed, schema=schema)
        logger.info(f"Created DataFrame with {df.count()} tickers")

        return df


def create_alpha_vantage_provider(
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None
) -> AlphaVantageProvider:
    """
    Factory function to create an AlphaVantageProvider.

    Args:
        spark: SparkSession
        docs_path: Path to repo root
        storage_path: Path to storage root (enables raw layer when set)

    Returns:
        Configured AlphaVantageProvider
    """
    return AlphaVantageProvider(spark=spark, docs_path=docs_path, storage_path=storage_path)
