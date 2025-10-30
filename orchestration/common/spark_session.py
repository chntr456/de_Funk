from __future__ import annotations
from pyspark.sql import SparkSession

def get_spark(app_name: str = "App"):
    spark = (SparkSession.builder
                .appName(app_name)
                .config("spark.sql.session.timeZone", "UTC")
                .config("spark.sql.caseSensitive", "true")
                .config("spark.sql.shuffle.partitions", "200")
                # better traceback if a worker crashes
                .config("spark.python.worker.faulthandler.enabled", "true")
                .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")
                .getOrCreate())
    return  spark


