from __future__ import annotations
from pyspark.sql import SparkSession

def get_spark(app_name: str = "App"):
    spark = (SparkSession.builder
                    .appName("PricesDailyFacetSimple")
                    .master("local[2]")
                    # keep t and T distinct
                    .config("spark.sql.caseSensitive", "true")
                    # better traceback if a worker crashes
                    .config("spark.python.worker.faulthandler.enabled", "true")
                    .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")
                    .getOrCreate())
    return  spark
