from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import SparkSession
from .polygon_base_facet import PolygonFacet

class RefTickerFacet(PolygonFacet):
    name = "ref_ticker"
    SCOPE = "ticker"
    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("ticker","string"), ("name","string"), ("primary_exchange","string")
    ]
    OUTPUT_SCHEMA = [
        ("ticker","string"), ("name","string"), ("exchange_code","string")
    ]
    RENAME_MAP = {"primary_exchange":"exchange_code"}

    def __init__(self, spark: SparkSession, *, tickers: List[str]):
        super().__init__(spark, tickers=tickers)

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {"ep_name": "ref_ticker", "params": {"ticker": t}}
