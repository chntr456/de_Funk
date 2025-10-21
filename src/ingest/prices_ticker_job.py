from __future__ import annotations
from pyspark.sql import SparkSession, functions as F
from src.common.spark_session import get_spark
from src.common.config_loader import ConfigLoader
from src.data_pipelines.base_pipeline.registry import BaseRegistry
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.data_pipelines.polygon.facets.prices_daily_facet import PricesDailyFacet
from src.ingest.bronze_writer import BronzeSink

def run_ticker_prices_to_bronze(cfg_path: str, storage_cfg: str, tickers: list[str], date_from: str, date_to: str):
    spark: SparkSession = get_spark("Bronze_Prices_Ticker")
    sink = BronzeSink(storage_cfg)
    reg = BaseRegistry(cfg_path)
    cfg = ConfigLoader(cfg_path).injected()
    keys = cfg.get("credentials", {}).get("api_keys") or ([cfg.get("credentials", {}).get("api_key")] if cfg.get("credentials", {}).get("api_key") else [])
    pool = ApiKeyPool(keys=keys, cooldown_seconds=90)
    http = HttpClient(base_urls=reg.base_urls, headers=reg.headers, rate_limit_per_sec=reg.rate_limit, api_key_pool=pool)

    facet = PricesDailyFacet(spark, tickers=tickers, date_from=date_from, date_to=date_to)
    raw_batches = []
    for call in facet.calls():
        ep, path, query = reg.render(call["ep_name"], **call["params"])
        payload = http.request(ep.base, path, query, ep.method)
        data = payload.get(ep.response_key, [])
        raw_batches.append(data if isinstance(data, list) else [data])

    df = facet.normalize(raw_batches)
    # write per day if missing
    days = [r["trade_date"] for r in df.select("trade_date").distinct().orderBy("trade_date").collect()]
    for day in days:
        day_str = day.isoformat() if hasattr(day, "isoformat") else str(day)
        day_df = df.where(F.col("trade_date") == day_str)
        if day_df.rdd.isEmpty():
            continue
        wrote = sink.write_if_missing("prices_daily", {"trade_date": day_str}, day_df)
        print(f"[prices_ticker] {day_str}: {'WROTE' if wrote else 'SKIPPED (exists)'}")
