from typing import Iterable, List
from pyspark.sql import functions as F
from src.data_pipelines.polygon.facets.polygon_base_facet import PolygonFacet
from src.data_pipelines.facets.base_facet import coalesce_existing

class RefTickerFacet(PolygonFacet):
    SPARK_CASTS = {
        "ticker":"string", "name":"string", "exchange_code":"string"
    }
    FINAL_COLUMNS = [
        ("ticker","string"), ("name","string"), ("exchange_code","string")
    ]

    def __init__(self, spark, *, tickers: List[str]):
        super().__init__(spark, tickers=tickers)

    def calls(self) -> Iterable[dict]:
        for t in self.tickers:
            yield {"ep_name": "ref_ticker", "params": {"ticker": t}}

    def postprocess(self, df):
        exch_expr = coalesce_existing(df, ["primary_exchange", "primary_exchange_code", "exchange"]).cast("string")
        return (
            df.select(
                F.col("ticker").cast("string").alias("ticker"),
                F.col("name").cast("string").alias("name"),
                exch_expr.alias("exchange_code")
            )
            .dropna(subset=["ticker"])
            .dropDuplicates(["ticker"])
        )
