from __future__ import annotations
from datetime import date, timedelta
from pyspark.sql import SparkSession
from src.common.spark_session import get_spark
from src.common.config_loader import ConfigLoader
from src.data_pipelines.base_pipeline.registry import BaseRegistry
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.data_pipelines.polygon.facets.prices_daily_grouped_facet import PricesDailyGroupedFacet
from src.ingest.bronze_writer import BronzeSink

def date_iter(start: str, end: str):
    s = date.fromisoformat(start); e = date.fromisoformat(end)
    d = s
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)

def run_grouped_prices_to_bronze(cfg_path: str, storage_cfg: str, date_from: str, date_to: str):
    spark: SparkSession = get_spark("Bronze_Prices_Grouped")
    sink = BronzeSink(storage_cfg)
    reg = BaseRegistry(cfg_path)
    cfg = ConfigLoader(cfg_path).injected()
    keys = cfg.get("credentials", {}).get("api_keys") or ([cfg.get("credentials", {}).get("api_key")] if cfg.get("credentials", {}).get("api_key") else [])
    pool = ApiKeyPool(keys=keys, cooldown_seconds=90)
    http = HttpClient(base_urls=reg.base_urls, headers=reg.headers, rate_limit_per_sec=reg.rate_limit, api_key_pool=pool)
    facet = PricesDailyGroupedFacet(spark, date_from=date_from, date_to=date_to)

    for day in date_iter(date_from, date_to):
        # fetch one day
        ep, path, query = reg.render("prices_daily_grouped", date=day)
        payload = http.request(ep.base, path, query, ep.method)
        data = payload.get(ep.response_key, [])
        raw_batches = [data if isinstance(data, list) else [data]]
        facet.extra["_current_call_date"] = day
        df = facet.normalize(raw_batches)
        wrote = sink.write_if_missing("prices_daily", {"trade_date": day}, df)
        print(f"[prices_grouped] {day}: {'WROTE' if wrote else 'SKIPPED (exists)'}")
