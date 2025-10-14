from __future__ import annotations
from typing import Iterable, List, Tuple, Any
from pyspark.sql import DataFrame, functions as F
from pyspark.sql import SparkSession
from src.data_pipelines.facets.base_facet import Facet

class NewsFacet(Facet):
    name = "news"

    # Normalize to 'ticker'; map 'symbol' if present
    RENAME_MAP = {"symbol": "ticker"}

    OUTPUT_SCHEMA: List[Tuple[str, str]] = [
        ("publish_dt", "timestamp"),
        ("ticker",     "string"),
        ("sent_score", "double"),
        ("source",     "string"),
        ("topic",      "string"),
        ("id",         "string")
    ]

    LITERALS = {}

    DERIVED = {
        "publish_dt": lambda df: F.to_timestamp("published_utc"),
        "sent_score": lambda df: F.when(F.col("description").isNotNull(),
                                        (F.length("description") % 10).cast("double")/10.0
                                       ).otherwise(F.lit(None).cast("double"))
    }

    def __init__(self, spark: SparkSession, tickers: List[str], limit: int = 50, start: str | None = None, end: str | None = None):
        super().__init__(spark)
        self.tickers, self.limit, self.start, self.end = tickers, limit, start, end

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            q: dict[str, Any] = {"limit": self.limit}
            if self.start: q["published_utc.gte"] = self.start
            if self.end:   q["published_utc.lte"] = self.end
            yield {"ep_name": "news", "params": {"ticker": t, "query": q}}

    def postprocess(self, df: DataFrame) -> DataFrame:
        # Ensure ticker column present
        if "ticker" not in df.columns:
            df = df.withColumn("ticker", F.lit(None).cast("string"))
        return df
