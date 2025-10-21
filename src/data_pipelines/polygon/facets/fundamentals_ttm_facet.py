from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import SparkSession
from .polygon_base_facet import PolygonFacet

class FundamentalsTTMFacet(PolygonFacet):
    name = "fundamentals_ttm"
    SCOPE = "ticker"
    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("ticker","string"), ("financials","string")
    ]
    OUTPUT_SCHEMA = [
        ("ticker","string"), ("financials","string")
    ]

    def __init__(self, spark: SparkSession, *, tickers: List[str]):
        super().__init__(spark, tickers=tickers)

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {"ep_name": "fundamentals_ttm", "params": {"ticker": t}}
