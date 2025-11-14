from __future__ import annotations
from typing import Dict, Optional
from pyspark.sql import SparkSession

def get_spark(app_name: str = "App", config: Optional[Dict[str, str]] = None):
    """
    Get or create a Spark session with standard configurations.

    Args:
        app_name: Name of the Spark application
        config: Optional dictionary of additional Spark configuration options

    Returns:
        SparkSession instance
    """
    builder = (SparkSession.builder
                .appName(app_name)
                .config("spark.sql.session.timeZone", "UTC")
                .config("spark.sql.caseSensitive", "true")
                .config("spark.sql.shuffle.partitions", "200")
                # Memory settings for large datasets with window functions
                .config("spark.driver.memory", "4g")
                .config("spark.executor.memory", "4g")
                .config("spark.driver.maxResultSize", "2g")
                # better traceback if a worker crashes
                .config("spark.python.worker.faulthandler.enabled", "true")
                .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true"))

    # Apply additional config if provided
    if config:
        for key, value in config.items():
            builder = builder.config(key, value)

    spark = builder.getOrCreate()
    return spark


# Alias for backward compatibility
get_spark_session = get_spark


