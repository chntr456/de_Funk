from src.data_pipelines.polygon.facets.prices_daily_facet import PricesDailyFacet
from src.data_pipelines.polygon.registry import PolygonRegistry  # <-- use this
from src.data_pipelines.base_pipeline.http_client import HttpClient
from src.data_pipelines.base_pipeline.key_pool import ApiKeyPool
from src.common.spark_session import get_spark
from src.common.config_loader import ConfigLoader

from pathlib import Path

root = Path(__file__).resolve().parents[1]
cfg_path = root / "configs" / "polygon_endpoints.json"

spark = get_spark("PricesDailyFacetTest")
reg = PolygonRegistry(cfg_path)
cfg = ConfigLoader(cfg_path).injected()
pool = ApiKeyPool(keys=cfg["credentials"]["api_keys"], cooldown_seconds=90)
http = HttpClient(reg.base_urls, reg.headers, reg.rate_limit, pool)

facet = PricesDailyFacet(
    spark,
    tickers=["AAPL", "HUM"],
    date_from="2024-01-01",
    date_to="2024-01-03"
)

raw_batches = []
for call in facet.calls():
    ep, path, query = reg.render(call["ep_name"], **call["params"])
    payload = http.request(ep.base, path, query, ep.method)
    raw_batches.append(payload.get(ep.response_key, []))

df = facet.normalize(raw_batches)
df.show(5)