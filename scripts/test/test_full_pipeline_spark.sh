#!/bin/bash
#
# test_full_pipeline_spark.sh - Complete pipeline test with profile support
#
# Runs the full data pipeline: raw → bronze → silver → forecast
#
# Usage:
#   ./scripts/test/test_full_pipeline_spark.sh                             # Default: pipeline_test (10 tickers)
#   ./scripts/test/test_full_pipeline_spark.sh --profile pipeline_test_50  # 50 tickers
#   ./scripts/test/test_full_pipeline_spark.sh --profile raw_to_silver     # Skip forecast
#   ./scripts/test/test_full_pipeline_spark.sh --max-tickers 25            # Override ticker count
#
# Profiles (from run_config.json):
#   pipeline_test     - 10 tickers, full endpoints (prices, reference, financials), forecast
#   pipeline_test_50  - 50 tickers, full endpoints (prices, reference, financials), forecast
#   raw_to_silver     - All tickers, raw → bronze → silver (no forecast)
#   silver_only       - Build silver from existing bronze (no ingest)
#   forecast_only     - Run forecasts on existing silver (no ingest/silver build)
#   quick_test        - 3 tickers, bronze + silver (no forecast, smoke test)
#
# Endpoints included in pipeline_test profiles:
#   prices            - TIME_SERIES_DAILY (OHLCV data)
#   reference         - LISTING_STATUS, COMPANY_OVERVIEW
#   income_statement  - INCOME_STATEMENT (annual/quarterly)
#   balance_sheet     - BALANCE_SHEET (annual/quarterly)
#   cash_flow         - CASH_FLOW (annual/quarterly)
#   earnings          - EARNINGS (quarterly EPS)
#
# Pipeline steps:
#   1. Raw → Bronze: Read cached raw JSON, write to Bronze (Delta Lake)
#   2. Bronze → Silver: Build temporal, stocks models
#   3. Silver → Forecast: Train ARIMA/Prophet models (if enabled)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
PROFILE="pipeline_test"
MAX_TICKERS=""
STORAGE_PATH="/shared/storage"
ENDPOINTS=""
FORECAST_MODELS=""
FORCE_API=false
VERBOSE=false
DRY_RUN=false

# Profile definitions (matching run_config.json)
# Format: "key1=value1 key2=value2 ..."
declare -A PROFILES
PROFILES[pipeline_test]="max_tickers=10 endpoints=prices,reference,income_statement,balance_sheet,cash_flow,earnings build_silver=true build_forecast=true forecast_models=arima_7d,prophet_7d"
PROFILES[pipeline_test_50]="max_tickers=50 endpoints=prices,reference,income_statement,balance_sheet,cash_flow,earnings build_silver=true build_forecast=true forecast_models=arima_7d,prophet_7d"
PROFILES[raw_to_silver]="max_tickers= endpoints=prices,reference build_silver=true build_forecast=false"
PROFILES[silver_only]="max_tickers= build_silver=true build_forecast=false skip_ingest=true"
PROFILES[silver_with_forecast]="max_tickers=50 build_silver=true build_forecast=true forecast_models=arima_7d,prophet_7d skip_ingest=true"
PROFILES[forecast_only]="max_tickers=100 build_silver=false build_forecast=true forecast_models=arima_7d,prophet_7d skip_ingest=true"
PROFILES[quick_test]="max_tickers=3 endpoints=prices,reference build_silver=true build_forecast=false"
PROFILES[dev]="max_tickers=50 endpoints=prices,reference build_silver=true build_forecast=false"
PROFILES[production]="max_tickers= endpoints=prices,reference build_silver=true build_forecast=true forecast_models=arima_7d,arima_30d,prophet_7d,prophet_30d"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile|-p)
            PROFILE="$2"
            shift 2
            ;;
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --endpoints)
            ENDPOINTS="$2"
            shift 2
            ;;
        --forecast-models)
            FORECAST_MODELS="$2"
            shift 2
            ;;
        --force-api)
            FORCE_API=true
            shift
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
            echo "  --profile, -p PROFILE   Profile name (default: pipeline_test)"
            echo "  --max-tickers N         Override max tickers from profile"
            echo "  --storage-path PATH     Storage root (default: /shared/storage)"
            echo "  --endpoints E1,E2       Override endpoints from profile"
            echo "  --forecast-models M1,M2 Override forecast models from profile"
            echo "  --force-api             Force API calls (ignore raw cache)"
            echo "  --verbose, -v           Verbose output"
            echo "  --dry-run               Show what would run"
            echo ""
            echo "Profiles:"
            echo "  pipeline_test     - 10 tickers, full endpoints + forecast (DEFAULT)"
            echo "  pipeline_test_50  - 50 tickers, full endpoints + forecast"
            echo "  raw_to_silver     - All tickers, raw → bronze → silver (no forecast)"
            echo "  silver_only       - Build silver from bronze (no ingest)"
            echo "  silver_with_forecast - Build silver + forecast from bronze (no ingest)"
            echo "  forecast_only     - Run forecasts only (no ingest/silver)"
            echo "  quick_test        - 3 tickers, bronze + silver (smoke test)"
            echo "  dev               - 50 tickers, bronze + silver"
            echo "  production        - All tickers, all models"
            echo ""
            echo "Endpoints (pipeline_test profiles):"
            echo "  prices, reference, income_statement, balance_sheet, cash_flow, earnings"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Load profile settings
if [[ -z "${PROFILES[$PROFILE]}" ]]; then
    echo "Unknown profile: $PROFILE"
    echo "Available profiles: ${!PROFILES[@]}"
    exit 1
fi

# Parse profile settings into variables
BUILD_SILVER=true
BUILD_FORECAST=false
SKIP_INGEST=false
PROFILE_MAX_TICKERS=""
PROFILE_ENDPOINTS=""
PROFILE_FORECAST_MODELS=""

for setting in ${PROFILES[$PROFILE]}; do
    key="${setting%%=*}"
    value="${setting#*=}"
    case $key in
        max_tickers)
            PROFILE_MAX_TICKERS="$value"
            ;;
        endpoints)
            PROFILE_ENDPOINTS="$value"
            ;;
        build_silver)
            BUILD_SILVER="$value"
            ;;
        build_forecast)
            BUILD_FORECAST="$value"
            ;;
        forecast_models)
            PROFILE_FORECAST_MODELS="$value"
            ;;
        skip_ingest)
            SKIP_INGEST="$value"
            ;;
    esac
done

# CLI args override profile settings
[[ -z "$MAX_TICKERS" ]] && MAX_TICKERS="$PROFILE_MAX_TICKERS"
[[ -z "$ENDPOINTS" ]] && ENDPOINTS="$PROFILE_ENDPOINTS"
[[ -z "$FORECAST_MODELS" ]] && FORECAST_MODELS="$PROFILE_FORECAST_MODELS"

# Defaults if still empty
[[ -z "$ENDPOINTS" ]] && ENDPOINTS="prices,reference"
[[ -z "$FORECAST_MODELS" ]] && FORECAST_MODELS="arima_7d,prophet_7d"

echo ""
echo "========================================================"
echo "  Full Pipeline Test"
echo "========================================================"
echo ""
echo "Profile:         $PROFILE"
echo "Storage path:    $STORAGE_PATH"
echo "Max tickers:     ${MAX_TICKERS:-all}"
echo "Endpoints:       $ENDPOINTS"
echo "Build silver:    $BUILD_SILVER"
echo "Build forecast:  $BUILD_FORECAST"
if [[ "$BUILD_FORECAST" == "true" ]]; then
    echo "Forecast models: $FORECAST_MODELS"
fi
echo "Force API:       $FORCE_API"
echo ""

# Change to repo root
cd "$REPO_ROOT"

# Track timing
START_TIME=$(date +%s)
STEP1_TIME=$START_TIME
STEP2_TIME=$START_TIME
STEP3_TIME=$START_TIME

# ============================================================
# Step 1: Raw → Bronze (if not skipping)
# ============================================================
if [[ "$SKIP_INGEST" != "true" ]]; then
    echo "Step 1: Raw → Bronze"
    echo "----------------------------------------"

    INGEST_ARGS="--storage-path $STORAGE_PATH --endpoints $ENDPOINTS"
    if [[ -n "$MAX_TICKERS" ]]; then
        INGEST_ARGS="$INGEST_ARGS --max-tickers $MAX_TICKERS"
    fi
    if [[ "$FORCE_API" == "true" ]]; then
        INGEST_ARGS="$INGEST_ARGS --force-api"
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] python -m scripts.ingest.run_bronze_ingestion $INGEST_ARGS"
    else
        echo "Running: python -m scripts.ingest.run_bronze_ingestion $INGEST_ARGS"
        python -m scripts.ingest.run_bronze_ingestion $INGEST_ARGS
    fi

    STEP1_TIME=$(date +%s)
    echo ""
    echo "Step 1 complete ($(($STEP1_TIME - $START_TIME))s)"
    echo ""
else
    echo "Step 1: SKIPPED (profile: $PROFILE)"
    echo ""
fi

# ============================================================
# Step 2: Bronze → Silver (if enabled)
# ============================================================
if [[ "$BUILD_SILVER" == "true" ]]; then
    echo "Step 2: Bronze → Silver"
    echo "----------------------------------------"

    BUILD_ARGS="--storage-root $STORAGE_PATH"
    if [[ -n "$MAX_TICKERS" ]]; then
        BUILD_ARGS="$BUILD_ARGS --max-tickers $MAX_TICKERS"
    fi
    if [[ "$VERBOSE" == "true" ]]; then
        BUILD_ARGS="$BUILD_ARGS --verbose"
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] python -m scripts.build.build_models --models temporal stocks $BUILD_ARGS"
    else
        echo "Running: python -m scripts.build.build_models --models temporal stocks $BUILD_ARGS"
        python -m scripts.build.build_models --models temporal stocks $BUILD_ARGS
    fi

    STEP2_TIME=$(date +%s)
    echo ""
    echo "Step 2 complete ($(($STEP2_TIME - $STEP1_TIME))s)"
    echo ""
else
    echo "Step 2: SKIPPED (profile: $PROFILE)"
    echo ""
    STEP2_TIME=$STEP1_TIME
fi

# ============================================================
# Step 3: Silver → Forecast (if enabled)
# ============================================================
if [[ "$BUILD_FORECAST" == "true" ]]; then
    echo "Step 3: Silver → Forecast"
    echo "----------------------------------------"

    FORECAST_ARGS="--models $FORECAST_MODELS"
    if [[ -n "$MAX_TICKERS" ]]; then
        FORECAST_ARGS="$FORECAST_ARGS --max-tickers $MAX_TICKERS"
    fi
    if [[ "$VERBOSE" == "true" ]]; then
        FORECAST_ARGS="$FORECAST_ARGS --verbose"
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] python -m scripts.forecast.run_forecasts $FORECAST_ARGS"
    else
        echo "Running: python -m scripts.forecast.run_forecasts $FORECAST_ARGS"
        python -m scripts.forecast.run_forecasts $FORECAST_ARGS || {
            echo "Warning: Forecast step had errors (continuing...)"
        }
    fi

    STEP3_TIME=$(date +%s)
    echo ""
    echo "Step 3 complete ($(($STEP3_TIME - $STEP2_TIME))s)"
    echo ""
else
    echo "Step 3: SKIPPED (profile: $PROFILE)"
    echo ""
    STEP3_TIME=$STEP2_TIME
fi

# ============================================================
# Summary
# ============================================================
END_TIME=$(date +%s)
TOTAL_TIME=$(($END_TIME - $START_TIME))

echo "========================================================"
echo "  Pipeline Summary"
echo "========================================================"
echo ""
echo "Profile: $PROFILE"
echo ""
echo "Timing:"
if [[ "$SKIP_INGEST" != "true" ]]; then
    echo "  Step 1 (Raw → Bronze):      $(($STEP1_TIME - $START_TIME))s"
fi
if [[ "$BUILD_SILVER" == "true" ]]; then
    echo "  Step 2 (Bronze → Silver):   $(($STEP2_TIME - $STEP1_TIME))s"
fi
if [[ "$BUILD_FORECAST" == "true" ]]; then
    echo "  Step 3 (Silver → Forecast): $(($STEP3_TIME - $STEP2_TIME))s"
fi
echo "  Total:                      ${TOTAL_TIME}s"
echo ""

# Verify outputs
echo "Output verification:"
echo ""

# Check Bronze
if [[ "$SKIP_INGEST" != "true" ]]; then
    BRONZE_PATH="$STORAGE_PATH/bronze/alpha_vantage"
    if [[ -d "$BRONZE_PATH" ]]; then
        echo "Bronze tables:"
        for table in time_series_daily_adjusted company_overview listing_status; do
            if [[ -d "$BRONZE_PATH/$table" ]]; then
                if [[ -d "$BRONZE_PATH/$table/_delta_log" ]]; then
                    echo "  ✓ $table (Delta)"
                else
                    echo "  ✓ $table (Parquet)"
                fi
            fi
        done
    else
        echo "  Warning: Bronze not found at $BRONZE_PATH"
    fi
    echo ""
fi

# Check Silver
if [[ "$BUILD_SILVER" == "true" ]]; then
    SILVER_PATH="$STORAGE_PATH/silver"
    if [[ -d "$SILVER_PATH" ]]; then
        echo "Silver models:"
        for model in temporal stocks; do
            if [[ -d "$SILVER_PATH/$model" ]] || [[ -d "$SILVER_PATH/securities/$model" ]]; then
                echo "  ✓ $model"
            else
                echo "  ✗ $model (missing)"
            fi
        done
    else
        echo "  Warning: Silver not found at $SILVER_PATH"
    fi
    echo ""
fi

# Check Forecast
if [[ "$BUILD_FORECAST" == "true" ]]; then
    FORECAST_PATH="$STORAGE_PATH/silver/forecast"
    if [[ -d "$FORECAST_PATH" ]]; then
        echo "Forecast tables:"
        for table in fact_forecast_price fact_forecast_metrics dim_model_registry; do
            if [[ -d "$FORECAST_PATH/$table" ]]; then
                echo "  ✓ $table"
            fi
        done
    else
        echo "  Note: Forecast output location varies by configuration"
    fi
    echo ""
fi

echo "Done."
