#!/bin/bash
#
# Build Silver Layer Only
#
# A convenience wrapper for testing Silver layer builds without
# running the full production pipeline (no seeding, no Bronze ingestion).
#
# Usage:
#   ./scripts/build/build_silver.sh                    # Build all models
#   ./scripts/build/build_silver.sh --models stocks    # Build specific model
#   ./scripts/build/build_silver.sh --dry-run          # Preview only
#   ./scripts/build/build_silver.sh --with-technicals  # Include technicals computation
#
# Environment:
#   STORAGE_PATH  - Override storage location (default: from run_config.json)
#
# Models built (in dependency order):
#   1. temporal - Calendar dimension (foundation)
#   2. company  - Corporate entities, financials
#   3. stocks   - Stock prices (base OHLCV, no technicals)
#
# Technicals (optional, after base build):
#   - SMA (20, 50, 200 day)
#   - RSI (14 day)
#   - Bollinger Bands
#   - Volume ratios
#   - Volatility measures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Default values
STORAGE_PATH="${STORAGE_PATH:-}"
WITH_TECHNICALS=false
MODELS=""
DRY_RUN=""
VERBOSE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --with-technicals)
            WITH_TECHNICALS=true
            shift
            ;;
        --models)
            shift
            while [[ $# -gt 0 && ! $1 =~ ^-- ]]; do
                MODELS="$MODELS $1"
                shift
            done
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --storage-path PATH   Override storage location"
            echo "  --models MODEL [...]  Build specific models (default: all)"
            echo "  --with-technicals     Compute technical indicators after build"
            echo "  --dry-run             Preview what would be done"
            echo "  --verbose             Show detailed output"
            echo "  -h, --help            Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                              # Build all models"
            echo "  $0 --models stocks              # Build stocks only"
            echo "  $0 --with-technicals            # Build all + technicals"
            echo "  $0 --storage-path /shared/storage --models company stocks"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  Build Silver Layer"
echo "======================================================================"
echo ""
echo "Project root: $PROJECT_ROOT"
if [ -n "$STORAGE_PATH" ]; then
    echo "Storage path: $STORAGE_PATH (override)"
else
    echo "Storage path: (from run_config.json)"
fi
echo "With technicals: $WITH_TECHNICALS"
if [ -n "$MODELS" ]; then
    echo "Models:$MODELS"
else
    echo "Models: all (temporal, company, stocks)"
fi
echo ""

# Build command
BUILD_CMD="python -m scripts.build.build_models"
if [ -n "$STORAGE_PATH" ]; then
    BUILD_CMD="$BUILD_CMD --storage-root $STORAGE_PATH"
fi
if [ -n "$MODELS" ]; then
    BUILD_CMD="$BUILD_CMD --models$MODELS"
fi
if [ -n "$DRY_RUN" ]; then
    BUILD_CMD="$BUILD_CMD $DRY_RUN"
fi
if [ -n "$VERBOSE" ]; then
    BUILD_CMD="$BUILD_CMD $VERBOSE"
fi

echo "----------------------------------------------------------------------"
echo "Building Silver Models"
echo "----------------------------------------------------------------------"
$BUILD_CMD

# Optional: Compute technicals
if [ "$WITH_TECHNICALS" = true ] && [ -z "$DRY_RUN" ]; then
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Computing Technical Indicators (Batched)"
    echo "----------------------------------------------------------------------"
    TECH_CMD="python -m scripts.build.compute_technicals"
    if [ -n "$STORAGE_PATH" ]; then
        TECH_CMD="$TECH_CMD --storage-path $STORAGE_PATH"
    fi
    $TECH_CMD
fi

echo ""
echo "======================================================================"
echo "  Silver Build Complete"
echo "======================================================================"
