from __future__ import annotations
from datetime import date, timedelta
from pyspark.sql import functions as F
from datapipelines.facets.polygon.polygon_base_facet import PolygonFacet

def _date_iter(a: str, b: str):
    s = date.fromisoformat(a); e = date.fromisoformat(b)
    while s <= e:
        yield s.isoformat(); s += timedelta(days=1)

class PricesDailyGroupedFacet(PolygonFacet):
    # Pre-coerce raw JSON numerics so Spark infers stable schema
    NUMERIC_COERCE = {
        "o": "double", "h": "double", "l": "double", "c": "double",
        "v": "double", "vw": "double", "t": "long"
    }

    # Enforce final dtypes
    SPARK_CASTS = {
        "trade_date": "date",
        "ticker": "string",
        "open": "double", "high": "double", "low": "double", "close": "double",
        "volume_weighted": "double", "volume": "double"
    }

    FINAL_COLUMNS = [
        ("trade_date","date"), ("ticker","string"),
        ("open","double"), ("high","double"), ("low","double"), ("close","double"),
        ("volume_weighted","double"), ("volume","double")
    ]

    def __init__(self, spark, *, date_from: str, date_to: str):
        super().__init__(spark, date_from=date_from, date_to=date_to)

    def calls(self):
        for d in _date_iter(self.date_from, self.date_to):
            yield {"ep_name": "prices_daily_grouped", "params": {"date": d}}

    def postprocess(self, df):
        return (
            df
            .withColumnRenamed("T", "ticker")
            .withColumnRenamed("o", "open")
            .withColumnRenamed("h", "high")
            .withColumnRenamed("l", "low")
            .withColumnRenamed("c", "close")
            .withColumnRenamed("v", "volume")
            .withColumnRenamed("vw", "volume_weighted")
            .withColumn("trade_date", F.to_date(F.from_unixtime((F.col("t")/1000).cast("long"))))
            .dropna(subset=["ticker", "trade_date"])
            .dropDuplicates(["trade_date", "ticker"])
        )
