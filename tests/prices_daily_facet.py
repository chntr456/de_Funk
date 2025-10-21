from src.data_pipelines.polygon.facets.prices_daily_facet import PricesDailyFacet

import os, sys

# exact python used by driver & workers
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# ---------------------------------------------------------------------
# 1) start a local spark session
# ---------------------------------------------------------------------
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("PricesDailyFacetSimple")
    .master("local[2]")
    # keep t and T distinct
    .config("spark.sql.caseSensitive", "true")
    # better traceback if a worker crashes
    .config("spark.python.worker.faulthandler.enabled", "true")
    .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true")
    .getOrCreate()
)

import subprocess
print("PYSPARK_PYTHON:", os.environ.get("PYSPARK_PYTHON"))
print("JAVA_HOME:", os.environ.get("JAVA_HOME"))
print("Spark caseSensitive:", spark.conf.get("spark.sql.caseSensitive"))
print("Interpreter:", sys.executable)

try:
    print(subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT, text=True))
except Exception as e:
    print("java -version failed:", e)

# ---------------------------------------------------------------------
# 2) create a small mock payload exactly like polygon returns
# ---------------------------------------------------------------------
raw_batches = [[
    {"t": 1704067200000, "o": 480.0, "h": 485.0, "l": 475.0, "c": 482.5, "v": 2100000, "vw": 481.9, "T": "HUM"},
    {"t": 1704153600000, "o": 482.5, "h": 490.0, "l": 481.0, "c": 488.0, "v": 1800000, "vw": 486.2, "T": "HUM"},
    {"t": 1704067200000, "o": 520.0, "h": 525.0, "l": 515.0, "c": 522.0, "v": 2500000, "vw": 521.3, "T": "UNH"},
    {"t": 1704153600000, "o": 522.0, "h": 530.0, "l": 520.0, "c": 528.5, "v": 2600000, "vw": 526.9, "T": "UNH"}
]]

# ---------------------------------------------------------------------
# 3) initialize the facet (no registry, no HTTP)
# ---------------------------------------------------------------------
facet = PricesDailyFacet(
    spark=spark,
    tickers=["HUM", "UNH"],
    date_from="2024-01-01",
    date_to="2024-01-03"
)

# ---------------------------------------------------------------------
# 4) normalize raw data -> spark dataframe
# ---------------------------------------------------------------------
prices_df = facet.normalize(raw_batches)

# ---------------------------------------------------------------------
# 5) inspect results
# ---------------------------------------------------------------------
prices_df.show(truncate=False)
prices_df.printSchema()

# keep spark alive for exploration
input("\nPress Enter to stop Spark... ")
spark.stop()