"""
Silver Storage Service.

Service layer for reading from the Silver layer with caching and filtering.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pyspark.sql import DataFrame, SparkSession
import pyspark.sql.functions as F


class SilverStorageService:
    """
    Service for reading from Silver layer.

    Responsibilities:
    - Read Silver layer tables
    - Apply simple filters (date range, tickers, etc.)
    - Cache DataFrames for performance
    - Abstract storage details from upper layers

    Usage:
        service = SilverStorageService(spark, storage_cfg)
        df = service.get_prices_with_company(
            start_date="2024-01-01",
            end_date="2024-01-05",
            tickers=["AAPL", "GOOGL"]
        )
    """

    def __init__(self, spark: SparkSession, storage_cfg: Dict):
        """
        Initialize storage service.

        Args:
            spark: Spark session
            storage_cfg: Storage configuration (storage.json)
        """
        self.spark = spark
        self.storage_cfg = storage_cfg
        self._cache: Dict[str, DataFrame] = {}

    def _silver_path(self, table: str) -> str:
        """Get Silver layer path for a table."""
        root = self.storage_cfg["roots"]["silver"]
        rel = self.storage_cfg["tables"][table]["rel"]
        return f"{root.rstrip('/')}/{rel}"

    def _read_silver(self, table: str, use_cache: bool = True) -> DataFrame:
        """
        Read Silver table with optional caching.

        Args:
            table: Table name (from storage.json)
            use_cache: Whether to use cached DataFrame

        Returns:
            DataFrame from Silver layer
        """
        if use_cache and table in self._cache:
            return self._cache[table]

        path = self._silver_path(table)
        df = self.spark.read.parquet(path)

        if use_cache:
            df.cache()
            self._cache[table] = df

        return df

    def get_dim_company(
        self,
        tickers: Optional[List[str]] = None
    ) -> DataFrame:
        """
        Get dim_company dimension table.

        Args:
            tickers: Optional list of tickers to filter

        Returns:
            DataFrame with columns: ticker, company_name, exchange_code, company_id
        """
        df = self._read_silver("dim_company")

        if tickers:
            df = df.filter(F.col("ticker").isin(tickers))

        return df

    def get_dim_exchange(self) -> DataFrame:
        """
        Get dim_exchange dimension table.

        Returns:
            DataFrame with columns: exchange_code, exchange_name
        """
        return self._read_silver("dim_exchange")

    def get_fact_prices(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tickers: Optional[List[str]] = None,
    ) -> DataFrame:
        """
        Get fact_prices table with optional filters.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            tickers: List of tickers to filter

        Returns:
            DataFrame with columns: trade_date, ticker, open, high, low, close,
                                   volume_weighted, volume
        """
        df = self._read_silver("fact_prices")

        # Apply filters
        if start_date:
            df = df.filter(F.col("trade_date") >= start_date)
        if end_date:
            df = df.filter(F.col("trade_date") <= end_date)
        if tickers:
            df = df.filter(F.col("ticker").isin(tickers))

        return df

    def get_prices_with_company(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tickers: Optional[List[str]] = None,
    ) -> DataFrame:
        """
        Get prices_with_company materialized path with optional filters.

        This is a pre-joined table: fact_prices + dim_company + dim_exchange

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            tickers: List of tickers to filter

        Returns:
            DataFrame with columns: trade_date, ticker, company_name, exchange_name,
                                   open, high, low, close, volume_weighted, volume
        """
        df = self._read_silver("prices_with_company")

        # Apply filters
        if start_date:
            df = df.filter(F.col("trade_date") >= start_date)
        if end_date:
            df = df.filter(F.col("trade_date") <= end_date)
        if tickers:
            df = df.filter(F.col("ticker").isin(tickers))

        return df

    def clear_cache(self):
        """Clear all cached DataFrames."""
        for df in self._cache.values():
            df.unpersist()
        self._cache.clear()
