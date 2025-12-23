#!/bin/bash
#
# Production Pipeline Run Script
#
# This script runs the full de_Funk data pipeline:
# 1. Seeds tickers from Alpha Vantage LISTING_STATUS (1 API call for ALL tickers)
# 2. Seeds calendar dimension (if needed)
# 3. Runs distributed pipeline with all tickers
#
# Usage:
#   ./scripts/cluster/run_production.sh                    # Full production run
#   ./scripts/cluster/run_production.sh --max-tickers 100  # Limited run
#   ./scripts/cluster/run_production.sh --skip-seed        # Skip ticker/calendar seed
#   ./scripts/cluster/run_production.sh --force-seed       # Force re-seed tickers
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
SKIP_SEED=false
FORCE_SEED=false
PIPELINE_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-seed|--skip-calendar)
            SKIP_SEED=true
            shift
            ;;
        --force-seed)
            FORCE_SEED=true
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
echo "  Skip Seed: $SKIP_SEED"
echo "  Force Seed: $FORCE_SEED"
echo "  Pipeline Args: $PIPELINE_ARGS"
echo ""

cd "$REPO_ROOT"

# Step 1: Seed tickers from LISTING_STATUS (if needed)
if [ "$SKIP_SEED" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 1: Seeding Tickers from Alpha Vantage LISTING_STATUS"
    echo "----------------------------------------------------------------------"
    if [ "$FORCE_SEED" = true ]; then
        python -m scripts.seed.seed_tickers --storage-path "$STORAGE_PATH" --force
    else
        python -m scripts.seed.seed_tickers --storage-path "$STORAGE_PATH"
    fi
    echo ""

    # Step 2: Seed calendar (if needed)
    echo "----------------------------------------------------------------------"
    echo "Step 2: Seeding Calendar Dimension"
    echo "----------------------------------------------------------------------"
    python -m scripts.seed.seed_calendar --storage-path "$STORAGE_PATH"
    echo ""
fi

# Step 3: Run distributed pipeline
echo "----------------------------------------------------------------------"
echo "Step 3: Running Distributed Pipeline"
echo "----------------------------------------------------------------------"
python -m scripts.cluster.run_distributed_pipeline $PIPELINE_ARGS

echo ""
echo "======================================================================"
echo "  Production Pipeline Complete"
echo "======================================================================"
