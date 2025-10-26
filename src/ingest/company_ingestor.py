# src/ingest/company_ingestor.py
from __future__ import annotations

from datetime import date
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from pyspark.sql import functions as F
from pyspark.sql import SparkSession

from src.ingest.base_ingestor import Ingestor
from src.ingest.polygon_ingestor import PolygonIngestor
from src.ingest.bronze_sink import BronzeSink

from src.data_pipelines.polygon.facets.ref_all_tickers_facet import RefAllTickersFacet
from src.data_pipelines.polygon.facets.exchange_facet import ExchangesFacet
from src.data_pipelines.polygon.facets.ref_ticker_facet import RefTickerFacet
from src.data_pipelines.polygon.facets.prices_daily_grouped_facet import PricesDailyGroupedFacet
from src.data_pipelines.polygon.facets.news_by_date_facet import NewsByDateFacet


def _cursor_from_next(next_url: Optional[str]) -> Optional[str]:
    """Extract Polygon 'cursor' value from a next_url, if present."""
    if not next_url:
        return None
    qs = parse_qs(urlparse(next_url).query)
    vals = qs.get("cursor")
    return vals[0] if vals else None


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
            df_all = self.spark.read.parquet(
                str(self.sink._path("ref_all_tickers", {"snapshot_dt": snap}))
            )

        # Build ticker universe (active only), optionally truncate
        tickers = (
            df_all.where(F.col("active") == True)
            .select("ticker")
            .distinct()
            .orderBy("ticker")
        )
        if max_tickers:
            tickers = tickers.limit(int(max_tickers))
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
        # 3) Per-ticker reference snapshot
        # ---------------------------
        if not self.sink.exists("ref_ticker", {"snapshot_dt": snap}) and tickers_list:
            r_f = RefTickerFacet(self.spark, tickers=tickers_list)
            r_batches = self._fetch_calls(r_f.calls())
            df_r = r_f.normalize(r_batches)
            self.sink.write_if_missing("ref_ticker", {"snapshot_dt": snap}, df_r)

        # ---------------------------
        # 4) Prices: grouped by trade_date
        # ---------------------------
        p_f = PricesDailyGroupedFacet(self.spark, date_from=date_from, date_to=date_to)
        for call in p_f.calls():
            trade_day = call["params"]["date"]
            if self.sink.exists("prices_daily", {"trade_date": trade_day}):
                continue
            batches = self._fetch_calls([call])
            df_p = p_f.normalize(batches)
            self.sink.write_if_missing("prices_daily", {"trade_date": trade_day}, df_p)

        # ---------------------------
        # 5) News: by publish_date
        # ---------------------------
        if include_news:
            n_f = NewsByDateFacet(self.spark, date_from=date_from, date_to=date_to)
            for call in n_f.calls():
                pub_day = call["params"]["publish_date"]
                if self.sink.exists("news", {"publish_date": pub_day}):
                    continue
                batches = self._fetch_calls([call])
                df_n = n_f.normalize(batches)
                self.sink.write_if_missing("news", {"publish_date": pub_day}, df_n)



        return tickers_list
