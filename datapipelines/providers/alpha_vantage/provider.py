"""
Alpha Vantage Provider Implementation.

Implements the BaseProvider interface for Alpha Vantage API.

Usage:
    from datapipelines.providers.alpha_vantage.provider import AlphaVantageProvider
    from datapipelines.base.provider import DataType, ProviderConfig

    config = ProviderConfig(
        name="alpha_vantage",
        base_url="https://www.alphavantage.co/query",
        rate_limit=1.0,
        supported_data_types=[DataType.REFERENCE, DataType.PRICES, ...]
    )

    provider = AlphaVantageProvider(config, spark=spark_session)
    ticker_data = provider.fetch_ticker_data("AAPL", [DataType.REFERENCE, DataType.PRICES])

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import threading
from typing import List, Optional, Callable, Any, Dict

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

    # DEPRECATED: Partition columns are now defined in configs/storage.json
    # Use BronzeSink._table_cfg(table_name).get("partitions", []) instead
    # This dict is kept for backwards compatibility but should not be used
    # TODO: Remove in v3.0
    PARTITION_COLUMNS = {
        DataType.REFERENCE: ["snapshot_dt", "asset_type"],
        DataType.PRICES: ["asset_type", "year", "month"],
        DataType.INCOME_STATEMENT: ["report_type", "snapshot_date"],
        DataType.BALANCE_SHEET: ["report_type", "snapshot_date"],
        DataType.CASH_FLOW: ["report_type", "snapshot_date"],
        DataType.EARNINGS: ["report_type", "snapshot_date"],
        DataType.OPTIONS: ["underlying_ticker", "option_type"],
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

    def get_partition_columns(self, data_type: DataType) -> List[str]:
        """
        DEPRECATED: Get partition columns.

        Partition config should be read from configs/storage.json instead.
        Use: BronzeSink._table_cfg(table_name).get("partitions", [])
        """
        logger.warning(
            f"get_partition_columns() is deprecated. "
            f"Read partitions from storage.json via BronzeSink._table_cfg() instead."
        )
        return self.PARTITION_COLUMNS.get(data_type, [])

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
    config = ProviderConfig(
        name="alpha_vantage",
        base_url="https://www.alphavantage.co/query",
        rate_limit=alpha_vantage_cfg.get("rate_limit_per_sec", 1.0),
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
