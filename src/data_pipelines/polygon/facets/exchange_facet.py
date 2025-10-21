from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import SparkSession, functions as F
from .polygon_base_facet import PolygonFacet

class ExchangesFacet(PolygonFacet):
    name = "exchanges"
    SCOPE = "singleton"
    RAW_SCHEMA_SPEC: List[Tuple[str, str]] = [
        ("exchange","string"), ("name","string"), ("operating_mic","string")
    ]
    OUTPUT_SCHEMA = [
        ("exchange_id","bigint"), ("code","string"), ("name","string")
    ]

    def __init__(self, spark: SparkSession):
        super().__init__(spark)

    def calls(self) -> Iterable[dict]:
        yield {"ep_name": "exchanges", "params": {}}

    def postprocess(self, df):
        return (df.withColumn("exchange_id", F.abs(F.hash("exchange")).cast("bigint"))
                  .withColumnRenamed("exchange", "code")
                  .select("exchange_id","code","name"))