from __future__ import annotations
from typing import Iterable, List, Tuple
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet
from src.common.spark_df_utils import epoch_ms_to_date

class PricesDailyFacet(Facet):
    name = "prices_daily"

    # ---- Declarative spec ----
    RENAME_MAP = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "volume_weighted",
        "T": "ticker"
    }

    OUTPUT_SCHEMA: List[Tuple[str, str]] = [
        ("trade_date", "date"),
        ("ticker",     "string"),
        ("open",       "double"),
        ("high",       "double"),
        ("low",        "double"),
        ("close",      "double"),
        ("volume_weighted",  "double"),
        ("volume",     "long"),
    ]

    LITERALS = {}  # none by default

    DERIVED = {
        "trade_date": lambda df: epoch_ms_to_date("t")
    }

    # ---- Runtime params ----
    def __init__(self, spark: SparkSession, tickers: List[str], date_from: str, date_to: str, mult: int = 1, timespan: str = "day"):
        super().__init__(spark)
        self.tickers, self.date_from, self.date_to = tickers, date_from, date_to
        self.mult, self.timespan = mult, timespan

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {
                "ep_name": "prices_daily",
                "params": {"ticker": t,
                           "from": self.date_from,
                           "to": self.date_to,
                           "mult": self.mult,
                           "timespan": self.timespan}
            }

    # ---- Facet-specific fix: ensure adj_close present ----
    def postprocess(self, df: DataFrame) -> DataFrame:
        if "volume_weighted" not in df.columns and "close" in df.columns:
            df = df.withColumn("volume_weighted", F.col("close"))
        return df
