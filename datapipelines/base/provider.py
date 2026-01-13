"""
Base Provider Interface.

Defines the abstract interface that all data providers must implement.
This enables the generic IngestorEngine to work with any provider.

v2.7 UNIFIED INTERFACE (January 2026):
- Single interface for both ticker-based (Alpha Vantage) and endpoint-based (Socrata) providers
- Work items = tickers OR endpoints (provider-specific)
- All providers use StreamingBronzeWriter for memory-safe writes
- Eliminates duplicate code paths

Usage:
    from datapipelines.base.provider import BaseProvider

    class MyProvider(BaseProvider):
        def list_work_items(self, **kwargs) -> List[str]:
            return ["endpoint1", "endpoint2"]  # or tickers

        def fetch(self, work_item: str, **kwargs) -> Generator[List[Dict], None, None]:
            for batch in paginate_api(work_item):
                yield batch

        def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
            return spark.createDataFrame(records)

        def get_table_name(self, work_item: str) -> str:
            return f"bronze_{work_item}"

Author: de_Funk Team
Date: December 2025
Updated: January 2026 - Unified interface for all provider types
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Generator
from enum import Enum

from config.logging import get_logger

logger = get_logger(__name__)


class DataType(Enum):
    """Standard data types supported by providers."""
    REFERENCE = "reference"
    PRICES = "prices"
    INCOME_STATEMENT = "income"
    BALANCE_SHEET = "balance"
    CASH_FLOW = "cashflow"
    EARNINGS = "earnings"
    OPTIONS = "options"
    ETF_PROFILE = "etf_profile"


@dataclass
class FetchResult:
    """Result from a single data fetch operation."""
    ticker: str
    data_type: DataType
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    api_calls: int = 1

    def __bool__(self) -> bool:
        return self.success and self.data is not None


@dataclass
class TickerData:
    """All data fetched for a single ticker."""
    ticker: str
    reference: Optional[Any] = None
    prices: Optional[Any] = None
    income_statement: Optional[Any] = None
    balance_sheet: Optional[Any] = None
    cash_flow: Optional[Any] = None
    earnings: Optional[Any] = None
    options: Optional[Any] = None
    errors: List[str] = field(default_factory=list)

    def has_data(self, data_type: DataType) -> bool:
        """Check if data exists for a specific type."""
        attr_name = data_type.value
        # Map enum values to attribute names
        attr_map = {
            'income': 'income_statement',
            'balance': 'balance_sheet',
            'cashflow': 'cash_flow',
        }
        attr_name = attr_map.get(attr_name, attr_name)
        return getattr(self, attr_name, None) is not None

    def set_data(self, data_type: DataType, data: Any) -> None:
        """Set data for a specific type."""
        attr_map = {
            DataType.REFERENCE: 'reference',
            DataType.PRICES: 'prices',
            DataType.INCOME_STATEMENT: 'income_statement',
            DataType.BALANCE_SHEET: 'balance_sheet',
            DataType.CASH_FLOW: 'cash_flow',
            DataType.EARNINGS: 'earnings',
            DataType.OPTIONS: 'options',
        }
        attr_name = attr_map.get(data_type)
        if attr_name:
            setattr(self, attr_name, data)


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    name: str
    base_url: str
    rate_limit: float = 1.0  # calls per second
    max_retries: int = 3
    retry_delay: float = 2.0
    batch_size: int = 20
    credentials_env_var: str = ""
    headers: Dict[str, str] = field(default_factory=dict)

    # Data types supported by this provider
    supported_data_types: List[DataType] = field(default_factory=list)


@dataclass
class WorkItemResult:
    """Result from ingesting a single work item."""
    work_item: str
    success: bool
    record_count: int = 0
    error: Optional[str] = None
    table_path: Optional[str] = None


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    UNIFIED INTERFACE (v2.7):
    All providers implement the same interface regardless of whether they're
    ticker-based (Alpha Vantage) or endpoint-based (Socrata).

    The key abstraction is "work_item":
    - For Alpha Vantage: work_item = DataType (prices, reference, etc.)
    - For Socrata: work_item = endpoint_id (crimes, building_permits, etc.)

    Example:
        class AlphaVantageProvider(BaseProvider):
            def list_work_items(self, **kwargs) -> List[str]:
                return ["prices", "reference", "income"]

            def fetch(self, work_item: str, **kwargs):
                # work_item is a DataType string
                for ticker in self.tickers:
                    data = self.fetch_ticker(ticker, work_item)
                    yield [data]  # yield as batch

        class ChicagoProvider(BaseProvider):
            def list_work_items(self, **kwargs) -> List[str]:
                return ["crimes", "building_permits"]

            def fetch(self, work_item: str, **kwargs):
                # work_item is an endpoint_id
                for batch in self.paginate(work_item):
                    yield batch
    """

    def __init__(self, config: ProviderConfig, spark=None):
        """
        Initialize the provider.

        Args:
            config: Provider configuration
            spark: SparkSession for DataFrame operations
        """
        self.config = config
        self.spark = spark
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """
        Setup provider-specific resources (HTTP client, key pool, etc).
        Called during __init__.
        """
        pass

    # =========================================================================
    # UNIFIED INTERFACE (v2.7) - All providers must implement these
    # =========================================================================

    @abstractmethod
    def list_work_items(self, **kwargs) -> List[str]:
        """
        List available work items for ingestion.

        For ticker-based providers: returns list of DataType values
        For endpoint-based providers: returns list of endpoint IDs

        Args:
            **kwargs: Provider-specific filters (e.g., status='active')

        Returns:
            List of work item identifiers
        """
        pass

    @abstractmethod
    def fetch(
        self,
        work_item: str,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch data for a single work item, yielding batches of raw records.

        This is a generator that yields batches of records. The IngestorEngine
        will pass these to StreamingBronzeWriter for memory-safe writes.

        For ticker-based providers:
            - work_item is a DataType string (e.g., "prices")
            - Internally iterates over tickers
            - Yields batches of normalized records

        For endpoint-based providers:
            - work_item is an endpoint ID (e.g., "crimes")
            - Paginates over the API
            - Yields batches of raw records

        Args:
            work_item: Work item identifier (DataType or endpoint_id)
            **kwargs: Provider-specific options (max_records, tickers, etc.)

        Yields:
            List[Dict] - Batches of raw record dictionaries
        """
        pass

    @abstractmethod
    def normalize(self, records: List[Dict], work_item: str) -> Any:
        """
        Normalize raw records to a Spark DataFrame.

        Args:
            records: List of raw record dictionaries from fetch()
            work_item: The work item these records came from

        Returns:
            Spark DataFrame with proper schema
        """
        pass

    @abstractmethod
    def get_table_name(self, work_item: str) -> str:
        """
        Get the Bronze table name for a work item.

        Args:
            work_item: Work item identifier

        Returns:
            Table name (e.g., "securities_prices_daily", "chicago_crimes")
        """
        pass

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """
        Get partition columns for a work item.

        Override in subclass if partitioning is needed.

        Args:
            work_item: Work item identifier

        Returns:
            List of partition column names, or None
        """
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """
        Get key columns for upsert operations.

        Override in subclass if upsert behavior is needed.

        Args:
            work_item: Work item identifier

        Returns:
            List of column names that form the unique key
        """
        return []

    # =========================================================================
    # LEGACY INTERFACE - Kept for backwards compatibility
    # These methods are used by the old IngestorEngine and will be deprecated
    # =========================================================================

    def fetch_ticker_data(
        self,
        ticker: str,
        data_types: List[DataType],
        progress_callback: Optional[Callable[[str, DataType, bool, Optional[str]], None]] = None,
        **kwargs
    ) -> TickerData:
        """
        [LEGACY] Fetch all requested data types for a single ticker.

        This method is kept for backwards compatibility with existing code.
        New providers should implement the unified interface instead.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement legacy fetch_ticker_data. "
            "Use the unified interface (list_work_items, fetch, normalize) instead."
        )

    def normalize_data(
        self,
        ticker_data: TickerData,
        data_type: DataType
    ) -> Optional[Any]:
        """
        [LEGACY] Normalize raw data to a Spark DataFrame.

        This method is kept for backwards compatibility with existing code.
        New providers should implement normalize(records, work_item) instead.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement legacy normalize_data. "
            "Use normalize(records, work_item) instead."
        )

    def get_bronze_table_name(self, data_type: DataType) -> str:
        """
        [LEGACY] Get the bronze table name for a data type.

        This method is kept for backwards compatibility.
        New providers should implement get_table_name(work_item) instead.
        """
        # Default: delegate to new interface
        return self.get_table_name(data_type.value if isinstance(data_type, DataType) else data_type)

    def get_supported_data_types(self) -> List[DataType]:
        """Get list of data types this provider supports."""
        return self.config.supported_data_types

    def discover_tickers(self, **kwargs) -> List[str]:
        """
        Discover available tickers from the provider.

        Override in subclass if provider supports ticker discovery.

        Returns:
            List of ticker symbols
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support ticker discovery"
        )

    def get_tickers_by_market_cap(
        self,
        max_tickers: int = None,
        min_market_cap: float = None
    ) -> List[str]:
        """
        Get tickers sorted by market cap.

        Override in subclass if provider supports market cap ranking.

        Returns:
            List of ticker symbols sorted by market cap descending
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support market cap ranking"
        )
