"""News API for company model"""

from typing import List
from pyspark.sql import DataFrame, functions as F
from models.base.service import BaseAPI
from models.company.types import NewsItem


class NewsAPI(BaseAPI):
    """
    API for accessing news data with company context.

    Provides:
    - News articles joined with company information
    - Filtering by date range
    - Type-safe results (NewsItem objects)
    """

    def __init__(self, session):
        """
        Initialize News API.

        Args:
            session: ModelSession or UniversalSession
        """
        super().__init__(session, model_name='company')

    def news_with_company_df(
        self,
        date_from: str,
        date_to: str,
        only_matched: bool = True
    ) -> DataFrame:
        """
        Get news articles with company context.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            only_matched: If True, only return news matched to companies

        Returns:
            DataFrame with news and company columns
        """
        df = self._get_table("news_with_company")
        df = df.where(F.col("publish_date").between(date_from, date_to))

        if only_matched:
            df = df.where(F.col("company_id").isNotNull())

        return df.select(
            "publish_date",
            "ticker",
            "company_name",
            "title",
            "source",
            "sentiment"
        )

    def news_items(
        self,
        date_from: str,
        date_to: str,
        limit: int = 1000
    ) -> List[NewsItem]:
        """
        Get news articles as typed objects.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum number of items to return

        Returns:
            List of NewsItem objects
        """
        df = (
            self.news_with_company_df(date_from, date_to, only_matched=True)
            .orderBy("publish_date", "ticker")
            .limit(limit)
        )

        pdf = df.toPandas()

        return [
            NewsItem(
                publish_date=str(r["publish_date"]),
                ticker=r["ticker"],
                title=r["title"],
                source=r.get("source"),
                sentiment=r.get("sentiment"),
                company_name=r.get("company_name"),
                exchange_code=r.get("exchange_code"),
            )
            for _, r in pdf.iterrows()
        ]

    def bronze_df(self) -> DataFrame:
        """
        Get raw news data from Bronze layer.

        Returns:
            DataFrame with raw news data
        """
        return self.session.bronze("news").read()
