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
    # CRITICAL: Set Python path in environment BEFORE SparkSession creation
    # This overrides conda's PYSPARK_PYTHON which may point to anaconda
    # Without this, executors inherit the wrong Python path from driver environment
    venv_python = "/home/ms_trixie/venv/bin/python3"
    os.environ["PYSPARK_PYTHON"] = venv_python
    os.environ["PYSPARK_DRIVER_PYTHON"] = venv_python

    # Resolve master URL
    if master is None:
        master = os.environ.get("SPARK_MASTER_URL")
    # Use SparkConfig if provided, otherwise use defaults
    if spark_config:
        base_config = spark_config.to_spark_conf_dict()
    else:
        # Memory configuration (can be overridden by environment variables for cluster mode)
        # Cluster workers may have less memory than local machine
        driver_memory = os.environ.get("SPARK_DRIVER_MEMORY", "8g")
        executor_memory = os.environ.get("SPARK_EXECUTOR_MEMORY", "8g")
        # Memory overhead for off-heap (Python, Delta, etc.) - default 10% is often too low
        executor_memory_overhead = os.environ.get("SPARK_EXECUTOR_MEMORY_OVERHEAD", "2g")

        base_config = {
            "spark.sql.session.timeZone": "UTC",
            "spark.sql.shuffle.partitions": "200",
            "spark.driver.memory": driver_memory,
            "spark.executor.memory": executor_memory,
            "spark.executor.memoryOverhead": executor_memory_overhead,
            # Prevent premature executor death during long operations
            "spark.network.timeout": "600s",
            "spark.executor.heartbeatInterval": "60s",
            # Reduce memory pressure from storage
            "spark.memory.fraction": "0.6",
            "spark.memory.storageFraction": "0.3",
        }

    # Build Spark session with config
    builder = SparkSession.builder.appName(app_name)

    # Set master if provided (cluster mode)
    if master:
        builder = builder.master(master)

    # Apply base configuration
    for key, value in base_config.items():
        builder = builder.config(key, value)

    # Determine event log directory (shared storage for cluster, local otherwise)
    event_log_dir = os.environ.get("SPARK_EVENT_LOG_DIR", "/shared/storage/spark-events")
    # Fall back to local if shared storage doesn't exist
    if not os.path.exists("/shared/storage"):
        event_log_dir = os.path.expanduser("~/storage/spark-events")
    os.makedirs(event_log_dir, exist_ok=True)

    # Standard configs not in SparkConfig
    builder = (builder
        .config("spark.sql.caseSensitive", "true")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.python.worker.faulthandler.enabled", "true")
        .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")
        # Executor environment - SPARK_SCALA_VERSION is required for Spark 4.x
        # binary distributions where auto-detection fails
        .config("spark.executorEnv.SPARK_SCALA_VERSION", "2.13")
        # Python environment - ensure workers use correct Python path
        # spark.pyspark.python affects both driver and executor Python binary selection
        .config("spark.pyspark.python", "/home/ms_trixie/venv/bin/python3")
        .config("spark.pyspark.driver.python", os.environ.get("PYSPARK_DRIVER_PYTHON", "/home/ms_trixie/venv/bin/python3"))
        # CRITICAL: spark.executorEnv.PYSPARK_PYTHON sets PYSPARK_PYTHON env var on executors
        # Without this, executors inherit the driver's PYSPARK_PYTHON which may point to anaconda
        .config("spark.executorEnv.PYSPARK_PYTHON", "/home/ms_trixie/venv/bin/python3")
        # Network configuration - use local IP for cluster communication
        # This prevents Spark from using hostnames (like Tailscale) that workers can't resolve
        .config("spark.driver.host", os.environ.get("SPARK_DRIVER_HOST", "192.168.1.212"))
        .config("spark.driver.bindAddress", "0.0.0.0")
        # Delta Lake support (v2.3 migration)
        # Note: Use delta-spark_2.13:4.0.0 for Spark 4.x, delta-spark_2.12:3.1.0 for Spark 3.x
        .config("spark.jars.packages", "io.delta:delta-spark_2.13:4.0.0")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Dynamic partition overwrite: only replace partitions being written, not entire table
        # This enables incremental ingestion without losing previously ingested data
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        # Event logging for History Server (view completed jobs at :18080)
        .config("spark.eventLog.enabled", "true")
        .config("spark.eventLog.dir", f"file://{event_log_dir}")
        .config("spark.eventLog.compress", "true")
        # UI and metrics
        .config("spark.ui.showConsoleProgress", "true")
        .config("spark.ui.retainedJobs", "100")
        .config("spark.ui.retainedStages", "100")
        .config("spark.ui.retainedTasks", "1000")
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


