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

class PricesDailyGroupedFacet(PolygonFacet):
    name = "prices_daily_grouped"

    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("T","string"),
        ("t","long"),
        ("o","double"),
        ("h","double"),
        ("l","double"),
        ("c","double"),
        ("v","double"),
        ("vw","double"),
        ("n","long")
    ]
    RENAME_MAP = {
        "T":"ticker",
        "o":"open",
        "h":"high",
        "l":"low",
        "c":"close",
        "v":"volume",
        "vw":"volume_weighted"
    }
    OUTPUT_SCHEMA = [
        ("trade_date","date"),
        ("ticker","string"),
        ("open","double"),
        ("high","double"),
        ("low","double"),
        ("close","double"),
        ("volume_weighted","double"),
        ("volume","double")
    ]

    def __init__(self, spark: SparkSession, *, date_from: str, date_to: str):
        super().__init__(spark, date_from=date_from, date_to=date_to)

    def calls(self) -> Iterable[dict]:
        for day in _date_iter(self.date_from, self.date_to):
            yield {"ep_name": "prices_daily_grouped", "params": {"date": day}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        target_day = self.extra.get("_current_call_date")
        if target_day:
            df = df.withColumn("trade_date", F.lit(target_day).cast("date"))
        else:
            df = df.withColumn("trade_date", F.to_date(F.from_unixtime((F.col("t")/1000).cast("long"))))
        return df
