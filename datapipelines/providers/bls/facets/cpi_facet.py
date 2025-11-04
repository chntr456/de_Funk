from pyspark.sql import functions as F
from datapipelines.providers.bls.facets.bls_base_facet import BLSFacet

class CPIFacet(BLSFacet):
    """
    Facet for BLS Consumer Price Index (CPI) data.

    Series ID: CUUR0000SA0 (CPI - All Urban Consumers, All Items)
    """

    SPARK_CASTS = {
        "seriesID": "string",
        "year": "string",
        "period": "string",
        "periodName": "string",
        "value": "double"
    }

    FINAL_COLUMNS = [
        ("series_id", "string"),
        ("year", "integer"),
        ("period", "string"),
        ("period_name", "string"),
        ("value", "double"),
        ("date", "date")
    ]

    def __init__(self, spark, start_year=None, end_year=None, series_ids=None):
        # Default to CPI All Urban Consumers, All Items
        default_series = ["CUUR0000SA0"]
        super().__init__(
            spark,
            series_ids=series_ids or default_series,
            start_year=start_year,
            end_year=end_year,
            calculations=True,
            annual_average=True
        )

    def calls(self):
        """Generate API call specification for CPI data."""
        yield {
            "ep_name": "timeseries",
            "params": {
                "seriesid": self.series_ids,
                "startyear": self.start_year,
                "endyear": self.end_year,
                "calculations": self.calculations,
                "annualaverage": self.annual_average
            }
        }

    def postprocess(self, df):
        """Transform BLS CPI data."""
        # Explode the data array within each series
        df_exploded = df.select(
            F.col("seriesID").alias("series_id"),
            F.explode("data").alias("data_point")
        )

        # Extract fields
        result = df_exploded.select(
            F.col("series_id").cast("string"),
            F.col("data_point.year").cast("integer").alias("year"),
            F.col("data_point.period").cast("string").alias("period"),
            F.col("data_point.periodName").cast("string").alias("period_name"),
            F.col("data_point.value").cast("double").alias("value")
        )

        # Create date from year and period
        result = result.withColumn(
            "date",
            F.when(
                F.col("period").rlike("M[0-9]{2}"),
                F.to_date(
                    F.concat(
                        F.col("year"),
                        F.lit("-"),
                        F.substring(F.col("period"), 2, 2),
                        F.lit("-01")
                    )
                )
            ).otherwise(
                F.to_date(F.concat(F.col("year"), F.lit("-01-01")))
            )
        )

        return result.dropna(subset=["series_id", "year", "value"])
