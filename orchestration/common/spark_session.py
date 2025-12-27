from __future__ import annotations
import os
from typing import Dict, Optional, TYPE_CHECKING
from pyspark.sql import SparkSession

if TYPE_CHECKING:
    from config.models import SparkConfig

def get_spark(
    app_name: str = "App",
    config: Optional[Dict[str, str]] = None,
    spark_config: Optional["SparkConfig"] = None,
    master: Optional[str] = None,
):
    """
    Get or create a Spark session with standard configurations.

    Now supports SparkConfig objects for centralized configuration management.

    Master URL resolution order:
    1. Explicit `master` parameter
    2. SPARK_MASTER_URL environment variable
    3. Local mode (no master set)

    Args:
        app_name: Name of the Spark application
        config: Optional dictionary of additional Spark configuration options (legacy)
        spark_config: Optional SparkConfig object with typed configuration
        master: Optional Spark master URL (e.g., "spark://192.168.1.212:7077")
                If None, checks SPARK_MASTER_URL env var, else runs in local mode.

    Returns:
        SparkSession instance
    """
    # Resolve master URL
    if master is None:
        master = os.environ.get("SPARK_MASTER_URL")
    # Use SparkConfig if provided, otherwise use defaults
    if spark_config:
        base_config = spark_config.to_spark_conf_dict()
    else:
        # Legacy default configuration
        # Increased memory for long-running batch jobs (e.g., 400+ ticker ingestion)
        base_config = {
            "spark.sql.session.timeZone": "UTC",
            "spark.sql.shuffle.partitions": "200",
            "spark.driver.memory": "8g",  # Increased from 4g for batch jobs
            "spark.executor.memory": "8g",  # Increased from 4g for batch jobs
        }

    # Build Spark session with config
    builder = SparkSession.builder.appName(app_name)

    # Set master if provided (cluster mode)
    if master:
        builder = builder.master(master)

    # Apply base configuration
    for key, value in base_config.items():
        builder = builder.config(key, value)

    # Standard configs not in SparkConfig
    builder = (builder
        .config("spark.sql.caseSensitive", "true")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.python.worker.faulthandler.enabled", "true")
        .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")
        # Delta Lake support (v2.3 migration)
        # Note: Use delta-spark_2.13:4.0.0 for Spark 4.x, delta-spark_2.12:3.1.0 for Spark 3.x
        .config("spark.jars.packages", "io.delta:delta-spark_2.13:4.0.0")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Dynamic partition overwrite: only replace partitions being written, not entire table
        # This enables incremental ingestion without losing previously ingested data
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    )

    # Apply additional legacy config if provided (overrides SparkConfig)
    if config:
        for key, value in config.items():
            builder = builder.config(key, value)

    spark = builder.getOrCreate()

    # Suppress noisy Spark warnings (only show ERROR level)
    spark.sparkContext.setLogLevel("ERROR")

    return spark


# Alias for backward compatibility
get_spark_session = get_spark


