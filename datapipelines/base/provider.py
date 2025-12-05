"""
Base Provider Interface.

Defines the abstract interface that all data providers must implement.
This enables the generic IngestorEngine to work with any provider.

Usage:
    from datapipelines.base.provider import BaseProvider

    class MyProvider(BaseProvider):
        def fetch_data(self, ticker, data_type, **kwargs):
            # Implementation
            pass

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
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


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    All providers must implement this interface to work with the
    generic IngestorEngine.

    Example:
        class AlphaVantageProvider(BaseProvider):
            def fetch_ticker_data(self, ticker, data_types, **kwargs):
                # Fetch all data types for a single ticker
                pass
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

    @abstractmethod
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
            **kwargs: Provider-specific options (date_from, date_to, etc)

        Returns:
            TickerData with all fetched data
        """
        pass

    @abstractmethod
    def normalize_data(
        self,
        ticker_data: TickerData,
        data_type: DataType
    ) -> Optional[Any]:
        """
        Normalize raw data to a Spark DataFrame.

        Args:
            ticker_data: Raw data from fetch_ticker_data
            data_type: Which data type to normalize

        Returns:
            Spark DataFrame or None if no data
        """
        pass

    @abstractmethod
    def get_bronze_table_name(self, data_type: DataType) -> str:
        """
        Get the bronze table name for a data type.

        Args:
            data_type: The data type

        Returns:
            Bronze table name (e.g., "securities_reference")
        """
        pass

    @abstractmethod
    def get_key_columns(self, data_type: DataType) -> List[str]:
        """
        Get the key columns for upsert operations.

        Args:
            data_type: The data type

        Returns:
            List of column names that form the unique key
        """
        pass

    @abstractmethod
    def get_partition_columns(self, data_type: DataType) -> List[str]:
        """
        Get the partition columns for a data type.

        Args:
            data_type: The data type

        Returns:
            List of partition column names
        """
        pass

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
