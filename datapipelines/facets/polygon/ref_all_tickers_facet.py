from pyspark.sql import functions as F
from datapipelines.facets.polygon.polygon_base_facet import PolygonFacet
from datapipelines.facets.base_facet import coalesce_existing

class RefAllTickersFacet(PolygonFacet):
    SPARK_CASTS = {
        "ticker":"string", "name":"string", "exchange_code":"string", "active":"boolean"
    }
    FINAL_COLUMNS = [
        ("ticker","string"), ("name","string"), ("exchange_code","string"), ("active","boolean")
    ]

    def __init__(self, spark):
        super().__init__(spark)

    def calls(self):
        yield {"ep_name": "ref_all_tickers", "params": {}}

    def postprocess(self, df):
        exch_expr = coalesce_existing(df, ["primary_exchange", "primary_exchange_code", "exchange"]).cast("string")
        return (
            df.select(
                F.col("ticker").cast("string").alias("ticker"),
                F.col("name").cast("string").alias("name"),
                exch_expr.alias("exchange_code"),
                F.col("active").cast("boolean").alias("active")
            )
            .dropna(subset=["ticker"])
            .dropDuplicates(["ticker"])
        )
