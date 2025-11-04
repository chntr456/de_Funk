from pyspark.sql import functions as F
from datapipelines.providers.chicago.facets.chicago_base_facet import ChicagoFacet

class BuildingPermitsFacet(ChicagoFacet):
    """
    Facet for Chicago building permits data.

    Data source: Building Permits
    Dataset ID: ydr8-5enu
    """

    SPARK_CASTS = {
        "id": "string",
        "permit_": "string",
        "permit_type": "string",
        "issue_date": "timestamp",
        "application_start_date": "timestamp",
        "total_fee": "double",
        "contractor_1_name": "string",
        "work_description": "string",
        "community_area": "string",
        "latitude": "double",
        "longitude": "double"
    }

    FINAL_COLUMNS = [
        ("permit_number", "string"),
        ("permit_type", "string"),
        ("issue_date", "timestamp"),
        ("application_start_date", "timestamp"),
        ("total_fee", "double"),
        ("contractor_name", "string"),
        ("work_description", "string"),
        ("community_area", "string"),
        ("latitude", "double"),
        ("longitude", "double")
    ]

    def calls(self):
        """Generate API call specification for building permits."""
        params = {}
        if self.date_from:
            params["$where"] = f"issue_date >= '{self.date_from}'"
        if self.date_to:
            if "$where" in params:
                params["$where"] += f" AND issue_date <= '{self.date_to}'"
            else:
                params["$where"] = f"issue_date <= '{self.date_to}'"

        yield {"ep_name": "building_permits", "params": params}

    def postprocess(self, df):
        """Transform and clean building permits data."""
        return (
            df.select(
                F.col("permit_").cast("string").alias("permit_number"),
                F.col("permit_type").cast("string").alias("permit_type"),
                F.col("issue_date").cast("timestamp").alias("issue_date"),
                F.col("application_start_date").cast("timestamp").alias("application_start_date"),
                F.col("total_fee").cast("double").alias("total_fee"),
                F.col("contractor_1_name").cast("string").alias("contractor_name"),
                F.col("work_description").cast("string").alias("work_description"),
                F.col("community_area").cast("string").alias("community_area"),
                F.col("latitude").cast("double").alias("latitude"),
                F.col("longitude").cast("double").alias("longitude")
            )
            .dropna(subset=["permit_number"])
            .dropDuplicates(["permit_number"])
        )
