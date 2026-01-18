#!/bin/bash
#
# test_forecast_pipeline.sh - Test forecasting pipeline with profile support
#
# This script runs the complete forecast pipeline:
# 1. Build silver models (temporal, stocks) if needed
# 2. Run time series forecasts (ARIMA, Prophet, RandomForest)
# 3. Store forecasts and metrics to Silver layer
#
# Usage:
#   ./scripts/test/test_forecast_pipeline.sh                    # Default: 50 tickers, fast models
#   ./scripts/test/test_forecast_pipeline.sh --profile full     # All tickers, all models
#   ./scripts/test/test_forecast_pipeline.sh --tickers 10       # Quick test with 10 tickers
#   ./scripts/test/test_forecast_pipeline.sh --models arima_7d,prophet_7d
#   ./scripts/test/test_forecast_pipeline.sh --skip-silver      # Forecast only (assumes silver built)
#
# Profiles:
#   quick_test       - 10 tickers, arima_7d only (fastest)
#   default          - 50 tickers, arima_7d + prophet_7d
#   full             - all tickers, all 5 models (slow)
#
# Requirements:
#   - Spark cluster or local Spark
#   - Bronze layer populated (securities_prices_daily)
#   - pmdarima, prophet, scikit-learn packages for ML

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
PROFILE="default"
MAX_TICKERS=50
MODELS="arima_7d,prophet_7d"
SKIP_SILVER=false
STORAGE_PATH="/shared/storage"
VERBOSE=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --models)
            MODELS="$2"
            shift 2
            ;;
        --skip-silver)
            SKIP_SILVER=true
            shift
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE     Profile: quick_test, default, full"
            echo "  --tickers N           Max tickers to forecast"
            echo "  --models M1,M2        Comma-separated model names"
            echo "  --skip-silver         Skip silver build (forecast only)"
            echo "  --storage-path PATH   Storage root path"
            echo "  --verbose, -v         Verbose output"
            echo "  --dry-run             Show what would run"
            echo ""
            echo "Profiles:"
            echo "  quick_test  - 10 tickers, arima_7d only"
            echo "  default     - 50 tickers, arima_7d + prophet_7d"
            echo "  full        - all tickers, all models"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Apply profile settings
case $PROFILE in
    quick_test)
        MAX_TICKERS=10
        MODELS="arima_7d"
        echo "Profile: quick_test (10 tickers, arima_7d only)"
        ;;
    default)
        MAX_TICKERS=50
        MODELS="arima_7d,prophet_7d"
        echo "Profile: default (50 tickers, fast models)"
        ;;
    full)
        MAX_TICKERS=""  # all
        MODELS="arima_7d,arima_30d,prophet_7d,prophet_30d,random_forest_14d"
        echo "Profile: full (all tickers, all models - this may take a while)"
        ;;
    *)
        echo "Unknown profile: $PROFILE"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "  Forecast Pipeline Test"
echo "========================================"
echo ""
echo "Storage path:  $STORAGE_PATH"
echo "Max tickers:   ${MAX_TICKERS:-all}"
echo "Models:        $MODELS"
echo "Skip silver:   $SKIP_SILVER"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would execute the following:"
    echo ""
fi

# Change to repo root
cd "$REPO_ROOT"

# ============================================================
# Step 1: Build Silver models (if not skipping)
# ============================================================
if [ "$SKIP_SILVER" = false ]; then
    echo "Step 1: Building Silver layer models..."
    echo "----------------------------------------"

    BUILD_ARGS="--storage-root $STORAGE_PATH"
    if [ -n "$MAX_TICKERS" ]; then
        BUILD_ARGS="$BUILD_ARGS --max-tickers $MAX_TICKERS"
    fi
    if [ "$VERBOSE" = true ]; then
        BUILD_ARGS="$BUILD_ARGS --verbose"
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "python -m scripts.build.build_models --models temporal stocks forecast $BUILD_ARGS"
    else
        python -m scripts.build.build_models --models temporal stocks forecast $BUILD_ARGS
    fi
    echo ""
else
    echo "Step 1: SKIPPED (--skip-silver)"
    echo ""
fi

# ============================================================
# Step 2: Run forecasts (standalone, for more control)
# ============================================================
echo "Step 2: Running forecasts..."
echo "----------------------------------------"

FORECAST_ARGS="--models $MODELS"
if [ -n "$MAX_TICKERS" ]; then
    FORECAST_ARGS="$FORECAST_ARGS --max-tickers $MAX_TICKERS"
fi
if [ "$VERBOSE" = true ]; then
    FORECAST_ARGS="$FORECAST_ARGS --verbose"
fi

if [ "$DRY_RUN" = true ]; then
    echo "python -m scripts.forecast.run_forecasts $FORECAST_ARGS"
else
    python -m scripts.forecast.run_forecasts $FORECAST_ARGS
fi

echo ""
echo "========================================"
echo "  Forecast Pipeline Complete"
echo "========================================"
echo ""

# ============================================================
# Step 3: Verify results
# ============================================================
echo "Step 3: Verifying results..."
echo "----------------------------------------"

FORECAST_PATH="$STORAGE_PATH/silver/forecast"
if [ -d "$FORECAST_PATH" ]; then
    echo "Forecast tables:"
    ls -la "$FORECAST_PATH" 2>/dev/null || echo "  (empty or not accessible)"

    # Check for Delta tables
    for table in fact_forecast_price fact_forecast_volume fact_forecast_metrics dim_model_registry; do
        if [ -d "$FORECAST_PATH/$table" ]; then
            if [ -d "$FORECAST_PATH/$table/_delta_log" ]; then
                echo "  ✓ $table (Delta)"
            else
                echo "  ✓ $table (Parquet)"
            fi
        else
            echo "  ✗ $table (missing)"
        fi
    done
else
    echo "  Warning: Forecast directory not found at $FORECAST_PATH"
fi

echo ""
echo "Done."
