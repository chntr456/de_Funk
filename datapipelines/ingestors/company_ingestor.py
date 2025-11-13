# src/ingest/company_ingestor.py
from __future__ import annotations

from datetime import date
from typing import List, Optional

from pyspark.sql import functions as F
from pyspark.sql import SparkSession

from datapipelines.ingestors.base_ingestor import Ingestor
from datapipelines.providers.polygon.polygon_ingestor import PolygonIngestor
from datapipelines.ingestors.bronze_sink import BronzeSink

from datapipelines.providers.polygon.facets.ref_all_tickers_facet import RefAllTickersFacet
from datapipelines.providers.polygon.facets.exchange_facet import ExchangesFacet
from datapipelines.providers.polygon.facets.ref_ticker_facet import RefTickerFacet
from datapipelines.providers.polygon.facets.prices_daily_grouped_facet import PricesDailyGroupedFacet
from datapipelines.providers.polygon.facets.news_by_date_facet import NewsByDateFacet

# Large-cap companies prioritized for top-N selection
# Ordered by approximate market cap (as of 2024)
MAJOR_COMPANIES = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "LLY", "V",
    "UNH", "XOM", "JPM", "JNJ", "WMT", "MA", "PG", "AVGO", "HD", "ORCL",
    "CVX", "MRK", "ABBV", "COST", "KO", "PEP", "BAC", "ADBE", "CRM", "MCD",
    "CSCO", "TMO", "ACN", "LIN", "ABT", "NKE", "NFLX", "AMD", "WFC", "DHR",
    "PM", "TXN", "QCOM", "NEE", "DIS", "INTU", "VZ", "RTX", "CMCSA", "IBM",
    "AMGN", "HON", "GE", "UNP", "SPGI", "CAT", "BA", "LOW", "AMAT", "PFE",
    "ELV", "GS", "BLK", "SYK", "DE", "SBUX", "GILD", "AXP", "NOW", "TJX",
    "BKNG", "ISRG", "PLD", "MDLZ", "LMT", "ADI", "VRTX", "CI", "REGN", "C",
    "MMC", "ADP", "ZTS", "MO", "BDX", "SCHW", "CB", "LRCX", "ETN", "SHW",
    "DUK", "SO", "CME", "BMY", "BSX", "PGR", "ITW", "PANW", "EOG", "USB"
]


class CompanyPolygonIngestor(PolygonIngestor):
    """
    Orchestrates Polygon → bronze ingestion for the Company domain.

    Steps:
      1. Snapshot active tickers (ref_all_tickers) → partitioned by snapshot_dt
      2. Snapshot exchanges                       → partitioned by snapshot_dt
      3. Snapshot per-ticker refs (ref_ticker)    → partitioned by snapshot_dt
      4. Daily grouped prices                     → partitioned by trade_date
      5. Daily news                               → partitioned by publish_date

    Skips each partition if it already exists (before making HTTP calls).
    """

    def __init__(self, polygon_cfg: dict, storage_cfg: dict, spark: SparkSession):
        super().__init__(polygon_cfg=polygon_cfg, storage_cfg=storage_cfg, spark=spark)
        self.sink: BronzeSink  # for type hinting

    def run_all(
        self,
        *,
        date_from: str,
        date_to: str,
        snapshot_dt: Optional[str] = None,
        max_tickers: Optional[int] = None,
        include_news: bool = True
    ) -> List[str]:
        snap = snapshot_dt or date.today().isoformat()

        # ---------------------------
        # 1) All active tickers snapshot
        # ---------------------------
        if not self.sink.exists("ref_all_tickers", {"snapshot_dt": snap}):
            all_f = RefAllTickersFacet(self.spark)
            all_batches = self._fetch_calls(all_f.calls())
            df_all = all_f.normalize(all_batches)
            self.sink.write_if_missing("ref_all_tickers", {"snapshot_dt": snap}, df_all)
        else:
            path = str(self.sink._path("ref_all_tickers", {"snapshot_dt": snap}))
            df_all = (
                self.spark.read
                .option("mergeSchema", "true")
                .parquet(path)
            )

        # Build ticker universe (active only)
        if max_tickers:
            # Use prioritized list of major companies when max_tickers is specified
            # Filter to only active tickers that exist in our major companies list
            active_tickers = df_all.where(F.col("active") == True).select("ticker").distinct()
            active_set = {r["ticker"] for r in active_tickers.collect()}

            # Take first max_tickers from MAJOR_COMPANIES that are active
            tickers_list = []
            for ticker in MAJOR_COMPANIES:
                if ticker in active_set:
                    tickers_list.append(ticker)
                    if len(tickers_list) >= max_tickers:
                        break

            # If we didn't get enough, fill with alphabetically sorted active tickers
            if len(tickers_list) < max_tickers:
                remaining = (
                    active_tickers
                    .filter(~F.col("ticker").isin(tickers_list))
                    .orderBy("ticker")
                    .limit(max_tickers - len(tickers_list))
                )
                tickers_list.extend([r["ticker"] for r in remaining.collect()])
        else:
            # No limit, just get all active tickers
            tickers = (
                df_all.where(F.col("active") == True)
                .select("ticker")
                .distinct()
                .orderBy("ticker")
            )
            tickers_list = [r["ticker"] for r in tickers.collect()]

        # ---------------------------
        # 2) Exchanges snapshot
        # ---------------------------
        if not self.sink.exists("exchanges", {"snapshot_dt": snap}):
            ex_f = ExchangesFacet(self.spark)
            ex_batches = self._fetch_calls(ex_f.calls())
            df_ex = ex_f.normalize(ex_batches)
            self.sink.write_if_missing("exchanges", {"snapshot_dt": snap}, df_ex)

        # ---------------------------
        # 3) Per-ticker reference snapshot (using concurrent fetching for efficiency)
        # ---------------------------
        if not self.sink.exists("ref_ticker", {"snapshot_dt": snap}) and tickers_list:
            r_f = RefTickerFacet(self.spark, tickers=tickers_list)
            # Use concurrent fetching to batch ticker detail requests (10x+ faster)
            r_batches = self._fetch_calls_concurrent(r_f.calls(), max_workers=10)
            df_r = r_f.normalize(r_batches)
            self.sink.write_if_missing("ref_ticker", {"snapshot_dt": snap}, df_r)

        # ---------------------------
        # 4) Prices: grouped by trade_date (batch concurrent fetching by date)
        # ---------------------------
        p_f = PricesDailyGroupedFacet(self.spark, date_from=date_from, date_to=date_to)
        # Collect calls that need fetching
        price_calls = []
        price_dates = []
        for call in p_f.calls():
            trade_day = call["params"]["date"]
            if not self.sink.exists("prices_daily", {"trade_date": trade_day}):
                price_calls.append(call)
                price_dates.append(trade_day)

        # Fetch all needed dates concurrently
        if price_calls:
            batches = self._fetch_calls_concurrent(price_calls, max_workers=10)
            for i, trade_day in enumerate(price_dates):
                df_p = p_f.normalize([batches[i]])
                self.sink.write_if_missing("prices_daily", {"trade_date": trade_day}, df_p)

        # ---------------------------
        # 5) News: by publish_date (batch concurrent fetching by date)
        # ---------------------------
        if include_news:
            n_f = NewsByDateFacet(self.spark, date_from=date_from, date_to=date_to)
            # Collect calls that need fetching
            news_calls = []
            news_dates = []
            for call in n_f.calls():
                pub_day = call["params"]["publish_date"]
                if not self.sink.exists("news", {"publish_date": pub_day}):
                    news_calls.append(call)
                    news_dates.append(pub_day)

            # Fetch all needed dates concurrently
            if news_calls:
                batches = self._fetch_calls_concurrent(news_calls, max_workers=10)
                for i, pub_day in enumerate(news_dates):
                    df_n = n_f.normalize([batches[i]])
                    self.sink.write_if_missing("news", {"publish_date": pub_day}, df_n)



        return tickers_list
