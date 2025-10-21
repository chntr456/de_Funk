from __future__ import annotations
from datetime import date, timedelta
from pyspark.sql import SparkSession, functions as F
from src.common.spark_session import get_spark
from src.common.config_loader import ConfigLoader
from src.ingest.bronze_writer import BronzeSink
from src.data_pipelines.base_pipeline.registry import BaseRegistry
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.data_pipelines.polygon.facets.news_by_date_facet import NewsByDateFacet

def date_iter(start: str, end: str):
    s = date.fromisoformat(start); e = date.fromisoformat(end)
    d = s
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)

def run_news_to_bronze(cfg_path: str, storage_cfg: str, date_from: str, date_to: str):
    spark: SparkSession = get_spark("Bronze_News_By_Date")
    sink = BronzeSink(storage_cfg)
    reg = BaseRegistry(cfg_path)
    cfg = ConfigLoader(cfg_path).injected()
    keys = cfg.get("credentials", {}).get("api_keys") or ([cfg.get("credentials", {}).get("api_key")] if cfg.get("credentials", {}).get("api_key") else [])
    pool = ApiKeyPool(keys=keys, cooldown_seconds=90)
    http = HttpClient(base_urls=reg.base_urls, headers=reg.headers, rate_limit_per_sec=reg.rate_limit, api_key_pool=pool)

    facet = NewsByDateFacet(spark, date_from=date_from, date_to=date_to)

    for day in date_iter(date_from, date_to):
        next_day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        ep, path, query = reg.render("news", query={"published_utc.gte": day, "published_utc.lt": next_day, "limit": 1000, "sort": "published_utc", "order": "asc"})
        payload = http.request(ep.base, path, query, ep.method)
        data = payload.get(ep.response_key, [])
        raw_batches = [data if isinstance(data, list) else [data]]
        df = facet.normalize(raw_batches).withColumn("publish_date", F.to_date("publish_dt"))
        day_df = df.where(F.col("publish_date") == day)
        if day_df.rdd.isEmpty():
            print(f"[news_by_date] {day}: SKIPPED (empty)")
            continue
        wrote = sink.write_if_missing("news", {"publish_date": day}, day_df)
        print(f"[news_by_date] {day}: {'WROTE' if wrote else 'SKIPPED (exists)'}")
