from src.data_pipelines.polygon.registry import PolygonRegistry
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.ingest.bronze_sink import BronzeSink
from src.ingest.base_ingestor import Ingestor

class PolygonIngestor(Ingestor):
    def __init__(self, polygon_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = PolygonRegistry(polygon_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((polygon_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark

    def _fetch_calls(self, calls, response_key="results"):
        batches = []
        for call in calls:
            ep, path, q = self.registry.render(call["ep_name"], **call["params"])
            payload = self.http.request(ep.base, path, q, ep.method)
            data = payload.get(response_key, []) or []
            batches.append(data if isinstance(data, list) else [data])
        return batches
