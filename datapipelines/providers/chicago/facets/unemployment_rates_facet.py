from pyspark.sql import functions as F
from datapipelines.providers.chicago.facets.chicago_base_facet import ChicagoFacet

class UnemploymentRatesFacet(ChicagoFacet):
    """
    Facet for Chicago unemployment rates by community area.

    Data source: Unemployment Rates
    Dataset ID: ane4-dwhs
    """

    SPARK_CASTS = {
        "geography": "string",
        "geography_type": "string",
        "date": "string",
        "unemployment_rate": "double",
        "labor_force": "integer",
        "employed": "integer",
        "unemployed": "integer"
    }

    FINAL_COLUMNS = [
        ("geography", "string"),
        ("geography_type", "string"),
        ("date", "string"),
        ("unemployment_rate", "double"),
        ("labor_force", "integer"),
        ("employed", "integer"),
        ("unemployed", "integer")
    ]

    def calls(self):
        """Generate API call specification for unemployment rates."""
        params = {}
        if self.date_from:
            params["$where"] = f"date >= '{self.date_from}'"
        if self.date_to:
            if "$where" in params:
                params["$where"] += f" AND date <= '{self.date_to}'"
            else:
                params["$where"] = f"date <= '{self.date_to}'"

        yield {"ep_name": "unemployment_rates", "params": params}

    def postprocess(self, df):
        """Transform and clean unemployment data."""
        return (
            df.select(
                F.col("geography").cast("string").alias("geography"),
                F.col("geography_type").cast("string").alias("geography_type"),
                F.col("date").cast("string").alias("date"),
                F.col("unemployment_rate").cast("double").alias("unemployment_rate"),
                F.col("labor_force").cast("integer").alias("labor_force"),
                F.col("employed").cast("integer").alias("employed"),
                F.col("unemployed").cast("integer").alias("unemployed")
            )
            .dropna(subset=["geography", "date"])
            .dropDuplicates(["geography", "date"])
        )
