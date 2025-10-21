from __future__ import annotations
from datetime import date
from pyspark.sql import SparkSession
from src.common.spark_session import get_spark
from src.common.config_loader import ConfigLoader
from src.ingest.bronze_writer import BronzeSink
from src.data_pipelines.base_pipeline.registry import BaseRegistry
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.data_pipelines.polygon.facets.exchanges_facet import ExchangesFacet

def run_exchanges_to_bronze(cfg_path: str, storage_cfg: str, snapshot_dt: str | None = None):
    spark: SparkSession = get_spark("Bronze_Exchanges")
    sink = BronzeSink(storage_cfg)
    reg = BaseRegistry(cfg_path)
    cfg = ConfigLoader(cfg_path).injected()
    keys = cfg.get("credentials", {}).get("api_keys") or ([cfg.get("credentials", {}).get("api_key")] if cfg.get("credentials", {}).get("api_key") else [])
    pool = ApiKeyPool(keys=keys, cooldown_seconds=90)
    http = HttpClient(base_urls=reg.base_urls, headers=reg.headers, rate_limit_per_sec=reg.rate_limit, api_key_pool=pool)

    snap = snapshot_dt or date.today().isoformat()
    facet = ExchangesFacet(spark)
    raw_batches = []
    for call in facet.calls():
        ep, path, query = reg.render(call["ep_name"], **call["params"])
        payload = http.request(ep.base, path, query, ep.method)
        data = payload.get(ep.response_key, [])
        raw_batches.append(data if isinstance(data, list) else [data])

    df = facet.normalize(raw_batches)
    wrote = sink.write_if_missing("exchanges", {"snapshot_dt": snap}, df)
    print(f"[exchanges] {snap}: {'WROTE' if wrote else 'SKIPPED (exists)'}")
