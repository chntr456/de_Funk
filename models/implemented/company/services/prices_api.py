"""Prices API for company model"""

from typing import Iterable, List
from pyspark.sql import DataFrame, Window, functions as F
from models.base.service import BaseAPI
from models.implemented.company.types import PriceBar


class PricesAPI(BaseAPI):
    """
    API for accessing price data with company context.

    Provides:
    - Price bars joined with company information
    - Filtering by date range and ticker
    - Type-safe results (PriceBar objects)
    """

    def __init__(self, session):
        """
        Initialize Prices API.

        Args:
            session: ModelSession or UniversalSession
        """
        super().__init__(session, model_name='company')

    def prices_with_company_df(
        self,
        date_from: str,
        date_to: str,
        only_matched: bool = False
    ) -> DataFrame:
        """
        Get price data with company context.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            only_matched: If True, only return prices matched to companies

        Returns:
            DataFrame with prices and company columns
        """
        df = self._get_table("prices_with_company")
        df = df.where(F.col("trade_date").between(date_from, date_to))

        if only_matched:
            df = df.where(F.col("company_id").isNotNull())

        # Clear, analytics-friendly projection
        return df.select(
            "trade_date",
            "ticker",
            "open",
            "high",
            "low",
            "close",
            "volume_weighted",
            "volume",
            "company_name",
            "exchange_code"
        )

    def price_bars(
        self,
        tickers: Iterable[str],
        date_from: str,
        date_to: str,
        limit_per_ticker: int = 500
    ) -> List[PriceBar]:
        """
        Get price bars for specific tickers as typed objects.

        Args:
            tickers: List of ticker symbols
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit_per_ticker: Maximum bars per ticker

        Returns:
            List of PriceBar objects
        """
        df = self.prices_with_company_df(
            date_from,
            date_to,
            only_matched=False
        ).where(F.col("ticker").isin(list(tickers)))

        # Limit per ticker
        w = (
            F.row_number()
            .over(Window.partitionBy("ticker").orderBy(F.col("trade_date").asc()))
        )
        df = df.withColumn("rn", w).where(F.col("rn") <= limit_per_ticker).drop("rn")

        pdf = df.toPandas()

        return [
            PriceBar(
                trade_date=str(r["trade_date"]),
                ticker=r["ticker"],
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume_weighted=float(r["volume_weighted"]),
                volume=float(r["volume"])
            )
            for _, r in pdf.iterrows()
        ]

    def bronze_df(self) -> DataFrame:
        """
        Get raw price data from Bronze layer.

        Returns:
            DataFrame with raw price data
        """
        return self.session.bronze("prices_daily").read()
