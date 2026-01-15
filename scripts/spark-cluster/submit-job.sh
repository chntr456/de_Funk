#!/bin/bash
#
# Submit Job to Spark Cluster
#
# Wrapper around spark-submit for the de_Funk project.
#
# Usage:
#   ./submit-job.sh script.py [args...]
#   ./submit-job.sh scripts/build/build_models.py --models stocks
#   ./submit-job.sh --class org.example.MyClass app.jar
#
# Examples:
#   # Build all Silver models
#   ./submit-job.sh scripts/build/build_models.py
#
#   # Build specific model
#   ./submit-job.sh scripts/build/build_models.py --models stocks
#
#   # Compute technicals
#   ./submit-job.sh scripts/build/compute_technicals.py
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

if [ $# -eq 0 ]; then
    echo "Usage: $0 script.py [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 scripts/build/build_models.py"
    echo "  $0 scripts/build/build_models.py --models stocks company"
    echo "  $0 scripts/build/compute_technicals.py --batch-size 100"
    exit 1
fi

SCRIPT="$1"
shift

# Check if it's a Python file or module
if [[ "$SCRIPT" == *.py ]]; then
    # If absolute path provided, use it directly; otherwise prepend PROJECT_ROOT
    if [[ "$SCRIPT" == /* ]]; then
        SCRIPT_PATH="$SCRIPT"
    else
        SCRIPT_PATH="$PROJECT_ROOT/$SCRIPT"
    fi
    if [ ! -f "$SCRIPT_PATH" ]; then
        echo "ERROR: Script not found: $SCRIPT_PATH"
        exit 1
    fi
else
    # Assume it's passed directly
    SCRIPT_PATH="$SCRIPT"
fi

echo "======================================================================"
echo "  Submitting Job to Spark Cluster"
echo "======================================================================"
echo ""
echo "Master: $SPARK_MASTER_URL"
echo "Script: $SCRIPT"
echo "Args: $@"
echo "Driver Memory: $SPARK_DRIVER_MEMORY"
echo "Executor Memory: $SPARK_EXECUTOR_MEMORY"
echo ""

# Activate venv if it exists (not all environments require it)
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
fi

# Submit to cluster
exec spark-submit \
    --master "$SPARK_MASTER_URL" \
    --deploy-mode client \
    --driver-memory "$SPARK_DRIVER_MEMORY" \
    --executor-memory "$SPARK_EXECUTOR_MEMORY" \
    --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
    --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
    --conf "spark.eventLog.enabled=true" \
    --conf "spark.eventLog.dir=$SPARK_HISTORY_DIR" \
    --conf "spark.driver.extraJavaOptions=-Duser.timezone=UTC" \
    --conf "spark.executor.extraJavaOptions=-Duser.timezone=UTC" \
    --packages "io.delta:delta-spark_2.13:4.0.0" \
    "$SCRIPT_PATH" \
    "$@"
