from pyspark.sql import functions as F
from datapipelines.providers.polygon.facets.polygon_base_facet import PolygonFacet
from datapipelines.facets.base_facet import coalesce_existing

class ExchangesFacet(PolygonFacet):
    SPARK_CASTS = {"code":"string","name":"string"}
    FINAL_COLUMNS = [("code","string"), ("name","string")]

    def __init__(self, spark):
        super().__init__(spark)

    def calls(self):
        yield {"ep_name": "exchanges", "params": {}}

    def postprocess(self, df):
        # Use MIC (Market Identifier Code) as the primary exchange code
        # MIC codes like XNAS, XNYS, ARCX match what ref_ticker returns
        code = coalesce_existing(df, ["mic", "code", "id"]).cast("string").alias("code")
        name = coalesce_existing(df, ["name", "description"]).cast("string").alias("name")
        return (
            df.select(code, name)
              .dropna(subset=["code"])
              .dropDuplicates(["code"])
        )
