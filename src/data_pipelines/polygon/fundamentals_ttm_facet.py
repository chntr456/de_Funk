from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet

class FundamentalsTTMFacet(Facet):
    name = "fundamentals_ttm"

    # Some payloads already return "ticker"; others might use "symbol" => map to ticker.
    RENAME_MAP = {"symbol": "ticker"}

    OUTPUT_SCHEMA: List[Tuple[str, str]] = [
        ("fiscal_period", "string"),
        ("ticker",        "string"),
        ("revenue",       "double"),
        ("ebitda",        "double"),
        ("net_income",    "double"),
        ("eps_diluted",   "double"),
    ]

    LITERALS = {
        "fiscal_period": ("string", "TTM")
    }

    DERIVED = {}  # none

    def __init__(self, spark: SparkSession, tickers: List[str]):
        super().__init__(spark)
        self.tickers = tickers

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {"ep_name": "fundamentals_ttm", "params": {"ticker": t}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        # Ensure 'ticker' exists even if neither symbol nor ticker existed (edge cases)
        if "ticker" not in df.columns:
            df = df.withColumn("ticker", F.lit(None).cast("string"))
        return df
