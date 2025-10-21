from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from datetime import date, timedelta
from .polygon_base_facet import PolygonFacet

def _date_iter(start: str, end: str):
    s = date.fromisoformat(start); e = date.fromisoformat(end)
    d = s
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)

class NewsByDateFacet(PolygonFacet):
    name = "news_by_date"

    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("published_utc","string"),
        ("id","string"),
        ("source","string"),
        ("title","string"),
        ("description","string"),
        ("tickers","array<string>")
    ]
    OUTPUT_SCHEMA = [
        ("publish_dt","timestamp"),
        ("ticker","string"),
        ("source","string"),
        ("id","string"),
        ("title","string"),
        ("description","string")
    ]
    DERIVED = { "publish_dt": lambda df: F.to_timestamp("published_utc") }

    def __init__(self, spark: SparkSession, *, date_from: str, date_to: str):
        super().__init__(spark, date_from=date_from, date_to=date_to)

    def calls(self) -> Iterable[dict]:
        for day in _date_iter(self.date_from, self.date_to):
            next_day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
            q = {"published_utc.gte": day, "published_utc.lt": next_day, "limit": 1000, "sort": "published_utc", "order": "asc"}
            yield {"ep_name": "news", "params": {"query": q}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        if "tickers" in df.columns:
            df = df.withColumn("ticker", F.explode_outer("tickers").cast("string"))
        if "ticker" not in df.columns:
            df = df.withColumn("ticker", F.lit(None).cast("string"))
        return df
