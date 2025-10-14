from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet

class RefTickerFacet(Facet):
    name = "ref_ticker"

    RENAME_MAP = {
        "primary_exchange": "exchange_code",
        "symbol":           "ticker"
    }

    OUTPUT_SCHEMA: List[Tuple[str, str]] = [
        ("company_id",   "bigint"),
        ("ticker",       "string"),
        ("name",         "string"),
        ("exchange_code","string"),
    ]

    LITERALS = {}
    DERIVED = {
        "company_id": lambda df: F.abs(F.hash("ticker")).cast("bigint"),
    }

    def __init__(self, spark: SparkSession, tickers: List[str]):
        super().__init__(spark)
        self.tickers = tickers

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {"ep_name": "ref_ticker", "params": {"ticker": t}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        # Ensure mandatory columns exist
        if "ticker" not in df.columns:
            df = df.withColumn("ticker", F.lit(None).cast("string"))
        if "exchange_code" not in df.columns:
            df = df.withColumn("exchange_code", F.lit(None).cast("string"))
        if "name" not in df.columns:
            df = df.withColumn("name", F.col("ticker"))
        return df
