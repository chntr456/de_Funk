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

        # Cast to string first to avoid type inference issues with coalesce
        # Polygon API returns 'mic' as string, 'id' as int
        if 'mic' in df.columns:
            df = df.withColumn('mic', F.col('mic').cast('string'))
        if 'id' in df.columns:
            df = df.withColumn('id', F.col('id').cast('string'))
        if 'code' in df.columns:
            df = df.withColumn('code', F.col('code').cast('string'))

        code = coalesce_existing(df, ["mic", "code", "id"]).alias("exchange_code")
        name = coalesce_existing(df, ["name", "description"]).alias("exchange_name")

        return (
            df.select(
                code.cast("string").alias("code"),
                name.cast("string").alias("name")
            )
            .dropna(subset=["code"])
            .dropDuplicates(["code"])
        )
