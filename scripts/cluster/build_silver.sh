#!/bin/bash
#
# Build Silver Layer on Spark Cluster
#
# This script builds the Silver layer from existing Bronze data using
# the Spark cluster for distributed processing.
#
# Usage:
#   ./scripts/cluster/build_silver.sh                    # Build all models
#   ./scripts/cluster/build_silver.sh --models stocks    # Build specific model
#   ./scripts/cluster/build_silver.sh --verbose          # Verbose output
#
# Prerequisites:
#   - Spark cluster running (init-cluster.sh completed)
#   - Bronze data exists in /shared/storage/bronze/
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$REPO_ROOT/configs/cluster.yaml"

# Parse cluster config
if [ -f "$CONFIG_FILE" ]; then
    HEAD_IP=$(python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
print(cfg['cluster']['head']['ip'])
")
    SPARK_PORT=$(python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
print(cfg['spark']['master']['port'])
")
    SPARK_MASTER="spark://${HEAD_IP}:${SPARK_PORT}"
else
    # Fallback defaults
    SPARK_MASTER="spark://192.168.1.212:7077"
fi

echo "======================================================================"
echo "  Building Silver Layer on Spark Cluster"
echo "======================================================================"
echo ""
echo "Spark Master: $SPARK_MASTER"
echo "Storage: ${STORAGE_PATH:-/shared/storage}"
echo ""

cd "$REPO_ROOT"

# Set environment for Spark cluster
export SPARK_MASTER_URL="$SPARK_MASTER"

# Run the Silver build
# Note: build_all_models.py only builds Silver from Bronze (no ingestion)
python -m scripts.build.build_all_models "$@"

echo ""
echo "======================================================================"
echo "  Silver Build Complete"
echo "======================================================================"
