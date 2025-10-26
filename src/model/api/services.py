from __future__ import annotations
from typing import Iterable, List, Optional
from pyspark.sql import DataFrame, functions as F
from src.model.api.session import ModelSession
from src.model.api.types import NewsItem, PriceBar

class NewsAPI:
    def __init__(self, ms: ModelSession):
        self.ms = ms

    # ---------- silver (joined with company) ----------
    def news_with_company_df(self, date_from: str, date_to: str, only_matched: bool = True) -> DataFrame:
        df = self.ms.silver_path_df("news_with_company")
        df = df.where(F.col("publish_date").between(date_from, date_to))
        if only_matched:
            df = df.where(F.col("company_id").isNotNull())
        return df.select("publish_date", "ticker", "company_name", "title", "source", "sentiment")

    def news_items(self, date_from: str, date_to: str, limit: int = 1000) -> List[NewsItem]:
        df = (self.news_with_company_df(date_from, date_to, only_matched=True)
              .orderBy("publish_date", "ticker")
              .limit(limit))
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

    # ---------- bronze (raw news) ----------
    def bronze_df(self) -> DataFrame:
        return self.ms.bronze("news").read()

class PricesAPI:
    def __init__(self, ms: ModelSession):
        self.ms = ms

    # ---------- silver (joined path) ----------
    def prices_with_company_df(self, date_from: str, date_to: str, only_matched: bool = False) -> DataFrame:
        df = self.ms.silver_path_df("prices_with_company")
        df = df.where(F.col("trade_date").between(date_from, date_to))
        if only_matched:
            df = df.where(F.col("company_id").isNotNull())
        # Clear, analytics-friendly projection
        return df.select(
            "trade_date", "ticker", "open", "high", "low", "close", "volume_weighted", "volume",
            "company_name", "exchange_code"
        )

    def price_bars(self, tickers: Iterable[str], date_from: str, date_to: str, limit_per_ticker: int = 500) -> List[PriceBar]:
        df = self.prices_with_company_df(date_from, date_to, only_matched=False).where(F.col("ticker").isin(list(tickers)))
        # Optional: limit per ticker
        w = (F.row_number().over(Window.partitionBy("ticker").orderBy(F.col("trade_date").asc())))
        df = df.withColumn("rn", w).where(F.col("rn") <= limit_per_ticker).drop("rn")
        pdf = df.toPandas()
        return [
            PriceBar(
                trade_date=str(r["trade_date"]), ticker=r["ticker"],
                open=float(r["open"]), high=float(r["high"]), low=float(r["low"]), close=float(r["close"]),
                volume_weighted=float(r["volume_weighted"]), volume=float(r["volume"])
            )
            for _, r in pdf.iterrows()
        ]

    # ---------- bronze (raw prices) ----------
    def bronze_df(self) -> DataFrame:
        return self.ms.bronze("prices_daily").read()

class CompanyAPI:
    def __init__(self, ms: ModelSession):
        self.ms = ms

    def dim_company_df(self) -> DataFrame:
        dims, _ = self.ms.ensure_built()
        return dims["dim_company"]

    def active_universe(self, limit: Optional[int] = None) -> DataFrame:
        # Pulls active tickers from bronze snapshot (if you saved it that way)
        df = self.ms.bronze("ref_all_tickers").read()
        df = df.where(F.col("active") == True).select("ticker").distinct().orderBy("ticker")
        if limit:
            df = df.limit(int(limit))
        return df
