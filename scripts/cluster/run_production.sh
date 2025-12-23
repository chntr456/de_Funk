#!/bin/bash
#
# Production Pipeline Run Script
#
# This script runs the full de_Funk data pipeline:
# 1. Seeds calendar dimension (if needed)
# 2. Runs distributed pipeline with all tickers
#
# Usage:
#   ./scripts/cluster/run_production.sh                    # Full production run
#   ./scripts/cluster/run_production.sh --max-tickers 100  # Limited run
#   ./scripts/cluster/run_production.sh --skip-calendar    # Skip calendar seed
#
# Prerequisites:
#   - Ray cluster running (ray start --head on bigbark)
#   - NFS mounted at /shared/storage on all nodes
#   - Workers set up via setup-worker.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STORAGE_PATH="${STORAGE_PATH:-/shared/storage}"

# Parse arguments
SKIP_CALENDAR=false
PIPELINE_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-calendar)
            SKIP_CALENDAR=true
            shift
            ;;
        *)
            PIPELINE_ARGS="$PIPELINE_ARGS $1"
            shift
            ;;
    esac
done

echo "======================================================================"
echo "  de_Funk Production Pipeline"
echo "======================================================================"
echo ""
echo "Configuration:"
echo "  Repository: $REPO_ROOT"
echo "  Storage: $STORAGE_PATH"
echo "  Skip Calendar: $SKIP_CALENDAR"
echo "  Pipeline Args: $PIPELINE_ARGS"
echo ""

cd "$REPO_ROOT"

# Step 1: Seed calendar (if needed)
if [ "$SKIP_CALENDAR" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 1: Seeding Calendar Dimension"
    echo "----------------------------------------------------------------------"
    python -m scripts.seed.seed_calendar --storage-path "$STORAGE_PATH"
    echo ""
fi

# Step 2: Run distributed pipeline
echo "----------------------------------------------------------------------"
echo "Step 2: Running Distributed Pipeline"
echo "----------------------------------------------------------------------"
python -m scripts.cluster.run_distributed_pipeline $PIPELINE_ARGS

echo ""
echo "======================================================================"
echo "  Production Pipeline Complete"
echo "======================================================================"
