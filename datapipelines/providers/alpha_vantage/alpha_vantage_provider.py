"""
Alpha Vantage Provider Implementation.

Implements the unified BaseProvider interface for Alpha Vantage API.

v2.7 UNIFIED INTERFACE (January 2026):
- Implements BaseProvider unified interface
- Work items = DataType values (e.g., "prices", "reference", "income_statement")
- All writes go through IngestorEngine + StreamingBronzeWriter
- Tickers must be set via set_tickers() before running

Features:
- Rate limiting: Pro tier 75 calls/min (1.25 calls/sec)
- Bulk ticker discovery via LISTING_STATUS endpoint
- Seed tickers to Bronze layer
- All financial statement endpoints (income, balance, cash flow, earnings)
- Integration with IngestorEngine for distributed cluster execution

Usage:
    from datapipelines.providers.alpha_vantage import create_alpha_vantage_provider
    from datapipelines.base.ingestor_engine import IngestorEngine

    provider = create_alpha_vantage_provider(config, spark)
    engine = IngestorEngine(provider, storage_cfg)

    # Set tickers to process
    provider.set_tickers(["AAPL", "MSFT", "GOOGL"])

    # Ingest specific data types
    results = engine.run(work_items=["prices", "reference"])

    # Or ingest all data types
    results = engine.run()

Author: de_Funk Team
Date: December 2025
Updated: January 2026 - Unified interface implementation
"""

from __future__ import annotations

import threading
from typing import List, Optional, Callable, Any, Dict, Generator

from pyspark.sql import DataFrame

from datapipelines.base.provider import (
    BaseProvider, DataType, TickerData, ProviderConfig, FetchResult
)
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.providers.alpha_vantage.alpha_vantage_registry import AlphaVantageRegistry
from config.logging import get_logger

logger = get_logger(__name__)


class AlphaVantageProvider(BaseProvider):
    """
    Alpha Vantage implementation of BaseProvider.

    Handles all API interactions with Alpha Vantage including:
    - Company overview (reference data)
    - Daily prices
    - Financial statements (income, balance, cash flow)
    - Earnings
    - Options (premium)
    """

    # Mapping from DataType to Alpha Vantage endpoint names
    ENDPOINT_MAP = {
        DataType.REFERENCE: "company_overview",
        DataType.PRICES: "time_series_daily_adjusted",
        DataType.INCOME_STATEMENT: "income_statement",
        DataType.BALANCE_SHEET: "balance_sheet",
        DataType.CASH_FLOW: "cash_flow",
        DataType.EARNINGS: "earnings",
        DataType.OPTIONS: "historical_options",
    }

    # Response keys for extracting data
    RESPONSE_KEYS = {
        DataType.REFERENCE: None,  # Top-level response
        DataType.PRICES: "Time Series (Daily)",
        DataType.INCOME_STATEMENT: None,
        DataType.BALANCE_SHEET: None,
        DataType.CASH_FLOW: None,
        DataType.EARNINGS: None,
        DataType.OPTIONS: "data",
    }

    # Bronze table mappings
    TABLE_NAMES = {
        DataType.REFERENCE: "securities_reference",
        DataType.PRICES: "securities_prices_daily",
        DataType.INCOME_STATEMENT: "income_statements",
        DataType.BALANCE_SHEET: "balance_sheets",
        DataType.CASH_FLOW: "cash_flows",
        DataType.EARNINGS: "earnings",
        DataType.OPTIONS: "historical_options",
    }

    # Key columns for upsert
    KEY_COLUMNS = {
        DataType.REFERENCE: ["ticker"],
        DataType.PRICES: ["ticker", "trade_date"],
        DataType.INCOME_STATEMENT: ["ticker", "fiscal_date_ending", "report_type"],
        DataType.BALANCE_SHEET: ["ticker", "fiscal_date_ending", "report_type"],
        DataType.CASH_FLOW: ["ticker", "fiscal_date_ending", "report_type"],
        DataType.EARNINGS: ["ticker", "fiscal_date_ending", "report_type"],
        DataType.OPTIONS: ["contract_id", "trade_date"],
    }

    def __init__(
        self,
        config: ProviderConfig,
        spark=None,
        alpha_vantage_cfg: Dict = None
    ):
        """
        Initialize Alpha Vantage provider.

        Args:
            config: Provider configuration
            spark: SparkSession
            alpha_vantage_cfg: Raw Alpha Vantage config dict (for registry)
        """
        self._alpha_vantage_cfg = alpha_vantage_cfg or {}
        super().__init__(config, spark)

    def _setup(self) -> None:
        """Setup HTTP client and API key pool."""
        # Create registry from config
        self.registry = AlphaVantageRegistry(self._alpha_vantage_cfg)

        # Create API key pool
        credentials = self._alpha_vantage_cfg.get("credentials", {})
        api_keys = credentials.get("api_keys", [])
        self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0)

        # Create HTTP client
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.config.rate_limit,
            self.key_pool
        )

        # Thread lock for HTTP requests
        self._http_lock = threading.Lock()

        # Store US exchanges for filtering
        self._us_exchanges = self._alpha_vantage_cfg.get("us_exchanges", [
            "NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"
        ])

        # Tickers to process (set via set_tickers() before running)
        self._tickers: List[str] = []

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION (v2.7)
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

    def list_work_items(self, **kwargs) -> List[str]:
        """
        List available work items (data types) for ingestion.

        Args:
            **kwargs: Optional filters

        Returns:
            List of data type strings
        """
        return [dt.value for dt in self.config.supported_data_types]

    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch data for a data type, yielding batches of records.

        Iterates through tickers and fetches the specified data type for each.

        Args:
            work_item: Data type string (e.g., "prices", "reference")
            max_records: Maximum records to fetch (None = no limit)
            **kwargs: Additional options (outputsize, etc.)

        Yields:
            List[Dict] - Batches of raw records
        """
        # Convert work_item string to DataType
        data_type = self._get_data_type(work_item)
        if not data_type:
            logger.warning(f"Unknown work item: {work_item}")
            return

        if not self._tickers:
            logger.warning("No tickers set. Call set_tickers() before fetch().")
            return

        logger.info(f"Fetching {work_item} for {len(self._tickers)} tickers")

        total_records = 0
        for ticker in self._tickers:
            # Check max_records limit
            if max_records and total_records >= max_records:
                logger.info(f"Reached max_records limit ({max_records})")
                break

            # Fetch single ticker
            result = self._fetch_single(ticker, data_type, **kwargs)

            if not result.success:
                logger.warning(f"Failed to fetch {work_item} for {ticker}: {result.error}")
                continue

            if result.data:
                # Convert to records list
                records = self._convert_to_records(ticker, data_type, result.data)
                if records:
                    total_records += len(records)
                    yield records

        logger.info(f"Fetched {total_records} records for {work_item}")

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """
        Normalize raw records to a Spark DataFrame.

        Records are already flattened by _convert_to_records() with ticker
        and trade_date/fiscal_date fields injected.

        Args:
            records: List of raw record dicts (pre-flattened)
            work_item: Data type string

        Returns:
            Spark DataFrame
        """
        if not records:
            # Return empty DataFrame
            return self.spark.createDataFrame([], samplingRatio=1.0)

        data_type = self._get_data_type(work_item)
        if not data_type:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        try:
            if data_type == DataType.PRICES:
                return self._normalize_prices(records)
            elif data_type == DataType.REFERENCE:
                return self._normalize_reference(records)
            elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                              DataType.CASH_FLOW, DataType.EARNINGS):
                return self._normalize_financials(records, data_type)
        except Exception as e:
            logger.warning(f"Failed to normalize {work_item}: {e}", exc_info=True)

        # Fallback
        return self.spark.createDataFrame(records, samplingRatio=1.0)

    def _normalize_prices(self, records: List[Dict]) -> DataFrame:
        """Normalize price records to DataFrame."""
        from pyspark.sql.types import (
            StructType, StructField, StringType, DateType, DoubleType,
            LongType, BooleanType, IntegerType
        )
        from pyspark.sql import functions as F
        import pandas as pd

        # Convert to pandas for easier type handling
        pdf = pd.DataFrame(records)

        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Parse trade_date
        pdf['trade_date'] = pd.to_datetime(pdf['trade_date'], errors='coerce')
        pdf['year'] = pdf['trade_date'].dt.year.astype('Int32')
        pdf['month'] = pdf['trade_date'].dt.month.astype('Int32')
        pdf['trade_date'] = pdf['trade_date'].dt.date

        # Rename Alpha Vantage fields
        rename_map = {
            "1. open": "open", "2. high": "high", "3. low": "low",
            "4. close": "close", "5. adjusted close": "adjusted_close",
            "6. volume": "volume", "7. dividend amount": "dividend_amount",
            "8. split coefficient": "split_coefficient"
        }
        pdf = pdf.rename(columns=rename_map)

        # Convert numeric fields
        for field in ['open', 'high', 'low', 'close', 'adjusted_close', 'volume',
                      'dividend_amount', 'split_coefficient']:
            if field in pdf.columns:
                pdf[field] = pd.to_numeric(pdf[field], errors='coerce').astype('float64')

        # Calculate VWAP approximation
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

        # Create Spark DataFrame
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

    def _normalize_reference(self, records: List[Dict]) -> DataFrame:
        """Normalize reference/overview records to DataFrame."""
        import pandas as pd
        from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, DateType
        from datetime import datetime

        pdf = pd.DataFrame(records)
        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Add metadata
        pdf['asset_type'] = 'stocks'
        pdf['snapshot_date'] = datetime.now().date()
        pdf['ingestion_timestamp'] = datetime.now()

        # Rename fields to snake_case
        rename_map = {
            'Symbol': 'ticker', 'Name': 'security_name', 'Exchange': 'exchange_code',
            'Sector': 'sector', 'Industry': 'industry', 'MarketCapitalization': 'market_cap',
            'CIK': 'cik', 'Description': 'description', 'SharesOutstanding': 'shares_outstanding'
        }
        pdf = pdf.rename(columns=rename_map)

        # Convert numeric fields
        for field in ['market_cap', 'shares_outstanding']:
            if field in pdf.columns:
                pdf[field] = pd.to_numeric(pdf[field], errors='coerce')

        return self.spark.createDataFrame(pdf, samplingRatio=1.0)

    def _normalize_financials(self, records: List[Dict], data_type: DataType) -> DataFrame:
        """Normalize financial statement records to DataFrame."""
        import pandas as pd
        from datetime import datetime

        pdf = pd.DataFrame(records)
        if pdf.empty:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Add metadata
        pdf['ingestion_timestamp'] = datetime.now()

        # Rename fiscalDateEnding to fiscal_date_ending
        if 'fiscalDateEnding' in pdf.columns:
            pdf = pdf.rename(columns={'fiscalDateEnding': 'fiscal_date_ending'})

        return self.spark.createDataFrame(pdf, samplingRatio=1.0)

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name for a data type."""
        data_type = self._get_data_type(work_item)
        if data_type:
            return self.TABLE_NAMES.get(data_type, f"unknown_{work_item}")
        return f"unknown_{work_item}"

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """Get partition columns for a data type."""
        # Most Alpha Vantage tables don't use partitions
        # Prices could partition by trade_date if needed
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """Get key columns for upsert operations."""
        data_type = self._get_data_type(work_item)
        if data_type:
            return self.KEY_COLUMNS.get(data_type, ["ticker"])
        return ["ticker"]

    def _get_data_type(self, work_item: str) -> Optional[DataType]:
        """Convert work_item string to DataType enum."""
        for dt in DataType:
            if dt.value == work_item:
                return dt
        return None

    def _convert_to_records(
        self,
        ticker: str,
        data_type: DataType,
        data: Any
    ) -> List[Dict]:
        """
        Convert raw API data to list of record dicts.

        Args:
            ticker: Ticker symbol
            data_type: Data type
            data: Raw API response data

        Returns:
            List of record dicts with ticker included
        """
        records = []

        if data_type == DataType.REFERENCE:
            # Single record per ticker
            if isinstance(data, dict):
                record = dict(data)
                record['ticker'] = ticker
                records.append(record)

        elif data_type == DataType.PRICES:
            # Time series data: {date: {open, high, low, close, volume}}
            if isinstance(data, dict):
                for date_str, ohlcv in data.items():
                    record = dict(ohlcv)
                    record['ticker'] = ticker
                    record['trade_date'] = date_str
                    records.append(record)

        elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                          DataType.CASH_FLOW, DataType.EARNINGS):
            # Financial statements: {annualReports: [...], quarterlyReports: [...]}
            if isinstance(data, dict):
                for report_type in ['annualReports', 'quarterlyReports']:
                    for report in data.get(report_type, []):
                        record = dict(report)
                        record['ticker'] = ticker
                        record['report_type'] = 'annual' if 'annual' in report_type.lower() else 'quarterly'
                        records.append(record)

        return records

    # =========================================================================
    # LEGACY INTERFACE (kept for backwards compatibility)
    # =========================================================================

    def fetch_ticker_data(
        self,
        ticker: str,
        data_types: List[DataType],
        progress_callback: Optional[Callable[[str, DataType, bool, Optional[str]], None]] = None,
        **kwargs
    ) -> TickerData:
        """
        Fetch all requested data types for a single ticker.

        Args:
            ticker: Ticker symbol
            data_types: List of data types to fetch
            progress_callback: Optional callback(ticker, data_type, success, error)
            **kwargs: Options like date_from, date_to, outputsize

        Returns:
            TickerData with all fetched data
        """
        result = TickerData(ticker=ticker)
        outputsize = kwargs.get('outputsize', 'full')

        for data_type in data_types:
            fetch_result = self._fetch_single(ticker, data_type, outputsize=outputsize)

            if fetch_result.success:
                result.set_data(data_type, fetch_result.data)
            else:
                result.errors.append(f"{data_type.value}: {fetch_result.error}")

            # Call progress callback
            if progress_callback:
                progress_callback(
                    ticker,
                    data_type,
                    fetch_result.success,
                    fetch_result.error
                )

        return result

    def _fetch_single(
        self,
        ticker: str,
        data_type: DataType,
        **kwargs
    ) -> FetchResult:
        """
        Fetch a single data type for a ticker.

        Args:
            ticker: Ticker symbol
            data_type: Data type to fetch
            **kwargs: Additional parameters

        Returns:
            FetchResult with data or error
        """
        endpoint = self.ENDPOINT_MAP.get(data_type)
        if not endpoint:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=f"Unsupported data type: {data_type}"
            )

        try:
            # Build params based on data type
            params = {"symbol": ticker}
            if data_type == DataType.PRICES:
                params["outputsize"] = kwargs.get("outputsize", "full")

            # Render endpoint
            ep, path, query = self.registry.render(endpoint, **params)

            # Make request (thread-safe)
            with self._http_lock:
                payload = self.http.request(ep.base, path, query, ep.method)

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

            # Extract data using response key
            response_key = self.RESPONSE_KEYS.get(data_type)
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

    def normalize_data(
        self,
        ticker_data: TickerData,
        data_type: DataType
    ) -> Optional[Any]:
        """
        Normalize raw data to a Spark DataFrame.

        Args:
            ticker_data: TickerData from fetch_ticker_data
            data_type: Which data type to normalize

        Returns:
            Spark DataFrame or None
        """
        from datapipelines.providers.alpha_vantage.facets import (
            SecuritiesReferenceFacetAV,
            SecuritiesPricesFacetAV,
            IncomeStatementFacet,
            BalanceSheetFacet,
            CashFlowFacet,
            EarningsFacet
        )

        ticker = ticker_data.ticker

        try:
            if data_type == DataType.REFERENCE and ticker_data.reference:
                facet = SecuritiesReferenceFacetAV(self.spark, tickers=[ticker])
                return facet.normalize([[ticker_data.reference]])

            elif data_type == DataType.PRICES and ticker_data.prices:
                facet = SecuritiesPricesFacetAV(self.spark, tickers=[ticker])
                full_response = {"Time Series (Daily)": ticker_data.prices}
                return facet.normalize([[full_response]])

            elif data_type == DataType.INCOME_STATEMENT and ticker_data.income_statement:
                facet = IncomeStatementFacet(self.spark, ticker=ticker)
                return facet.normalize(ticker_data.income_statement)

            elif data_type == DataType.BALANCE_SHEET and ticker_data.balance_sheet:
                facet = BalanceSheetFacet(self.spark, ticker=ticker)
                return facet.normalize(ticker_data.balance_sheet)

            elif data_type == DataType.CASH_FLOW and ticker_data.cash_flow:
                facet = CashFlowFacet(self.spark, ticker=ticker)
                return facet.normalize(ticker_data.cash_flow)

            elif data_type == DataType.EARNINGS and ticker_data.earnings:
                facet = EarningsFacet(self.spark, ticker=ticker)
                return facet.normalize(ticker_data.earnings)

        except Exception as e:
            logger.warning(f"Failed to normalize {data_type.value} for {ticker}: {e}")

        return None

    def normalize_company_reference(self, ticker_data: TickerData) -> Optional[Any]:
        """
        Normalize reference data to company_reference table format.

        This is separate from securities_reference - stores company-specific
        data like CIK, sector, etc.

        Args:
            ticker_data: TickerData with reference data

        Returns:
            Spark DataFrame or None
        """
        from datapipelines.providers.alpha_vantage.facets.company_reference_facet import CompanyReferenceFacet

        if not ticker_data.reference:
            return None

        try:
            facet = CompanyReferenceFacet(self.spark, tickers=[ticker_data.ticker])
            return facet.normalize([[ticker_data.reference]])
        except Exception as e:
            logger.warning(f"Failed to normalize company reference for {ticker_data.ticker}: {e}")
            return None

    def get_bronze_table_name(self, data_type: DataType) -> str:
        """Get bronze table name for a data type."""
        return self.TABLE_NAMES.get(data_type, f"unknown_{data_type.value}")

    def get_key_columns(self, data_type: DataType) -> List[str]:
        """Get key columns for upsert."""
        return self.KEY_COLUMNS.get(data_type, ["ticker"])

    def discover_tickers(self, state: str = "active", **kwargs) -> tuple:
        """
        Discover tickers using LISTING_STATUS endpoint.

        Args:
            state: 'active' or 'delisted'

        Returns:
            Tuple of (tickers_list, ticker_to_exchange_map)
        """
        import csv
        import io

        ep, path, query = self.registry.render("listing_status", state=state)
        query['apikey'] = self.key_pool.next_key() if self.key_pool else None

        with self._http_lock:
            response_text = self.http.request_text(ep.base, path, query, ep.method)

        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        tickers = [row['symbol'] for row in rows if row.get('symbol')]
        ticker_exchanges = {
            row['symbol']: row.get('exchange', 'UNKNOWN')
            for row in rows if row.get('symbol')
        }

        # Filter to US exchanges
        us_tickers = [t for t in tickers if ticker_exchanges.get(t) in self._us_exchanges]

        return us_tickers, ticker_exchanges

    def get_tickers_by_market_cap(
        self,
        max_tickers: int = None,
        min_market_cap: float = None,
        storage_cfg: Dict = None
    ) -> List[str]:
        """
        Get tickers sorted by market cap from existing reference data.

        Args:
            max_tickers: Maximum tickers to return
            min_market_cap: Minimum market cap filter
            storage_cfg: Storage configuration for paths

        Returns:
            List of tickers sorted by market cap descending
        """
        from pyspark.sql.functions import col, desc, isnan, upper
        from pathlib import Path

        if not storage_cfg:
            logger.warning("No storage config provided for market cap ranking")
            return []

        bronze_path = Path(storage_cfg["roots"]["bronze"]) / "securities_reference"

        if not bronze_path.exists():
            return []

        try:
            # Auto-detect Delta vs Parquet
            if (bronze_path / "_delta_log").exists():
                df = self.spark.read.format("delta").load(str(bronze_path))
            else:
                df = self.spark.read.parquet(str(bronze_path))

            # Filter for valid market cap
            df_filtered = df.filter(
                (col("market_cap").isNotNull()) &
                (~isnan(col("market_cap"))) &
                (col("market_cap") > 0)
            )

            # Apply asset_type filter if column exists
            if "asset_type" in df.columns:
                df_filtered = df_filtered.filter(col("asset_type") == "stocks")

            # Apply min market cap
            if min_market_cap:
                df_filtered = df_filtered.filter(col("market_cap") >= min_market_cap)

            # Exclude warrants, preferred, etc.
            df_filtered = df_filtered.filter(
                (~upper(col("ticker")).rlike(r".*[-]?W[S]?$")) &
                (~upper(col("ticker")).rlike(r".*-P-.*|.*-P[A-Z]$"))
            )

            # Sort and limit
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
        """
        Seed tickers from LISTING_STATUS endpoint to Bronze layer.

        This is a bulk operation that fetches ALL tickers in a single API call
        (CSV format, not JSON) and returns a Spark DataFrame ready for Bronze.

        Args:
            state: 'active' or 'delisted'
            filter_us_exchanges: Only include US exchanges (NYSE, NASDAQ, etc.)

        Returns:
            Spark DataFrame with ticker reference data

        Note:
            This uses 1 API call regardless of ticker count (~12,500 active tickers).
        """
        import csv
        import io
        from datetime import datetime
        from pyspark.sql.types import (
            StructType, StructField, StringType, DateType, TimestampType
        )

        logger.info(f"Testing task: seed tickers (state={state})")

        # Fetch LISTING_STATUS (returns CSV)
        ep, path, query = self.registry.render("listing_status", state=state)
        query['apikey'] = self.key_pool.next_key() if self.key_pool else None

        with self._http_lock:
            response_text = self.http.request_text(ep.base, path, query, ep.method)

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        logger.info(f"Fetched {len(rows)} tickers from LISTING_STATUS")

        # Filter to US exchanges if requested
        if filter_us_exchanges:
            rows = [r for r in rows if r.get('exchange') in self._us_exchanges]
            logger.info(f"Filtered to {len(rows)} US exchange tickers")

        # Transform to Bronze schema
        now = datetime.now()
        transformed = []
        for row in rows:
            # Parse IPO date
            ipo_date = None
            if row.get('ipoDate'):
                try:
                    ipo_date = datetime.strptime(row['ipoDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Parse delisting date
            delisting_date = None
            if row.get('delistingDate'):
                try:
                    delisting_date = datetime.strptime(row['delistingDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Map asset type
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

        # Create DataFrame with explicit schema
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
    alpha_vantage_cfg: Dict,
    spark=None
) -> AlphaVantageProvider:
    """
    Factory function to create an AlphaVantageProvider.

    Args:
        alpha_vantage_cfg: Alpha Vantage API configuration
        spark: SparkSession

    Returns:
        Configured AlphaVantageProvider
    """
    # Pro tier: 75 calls/min = 1.25 calls/sec
    config = ProviderConfig(
        name="alpha_vantage",
        base_url="https://www.alphavantage.co/query",
        rate_limit=alpha_vantage_cfg.get("rate_limit_per_sec", 1.25),
        batch_size=20,
        credentials_env_var="ALPHA_VANTAGE_API_KEYS",
        supported_data_types=[
            DataType.REFERENCE,
            DataType.PRICES,
            DataType.INCOME_STATEMENT,
            DataType.BALANCE_SHEET,
            DataType.CASH_FLOW,
            DataType.EARNINGS,
        ]
    )

    return AlphaVantageProvider(
        config=config,
        spark=spark,
        alpha_vantage_cfg=alpha_vantage_cfg
    )
