#!/bin/bash
#
# Direct Pipeline Test - Bypasses Airflow for simpler testing
#
# Runs the full Bronze→Silver pipeline directly using existing scripts.
# Use this when Airflow is causing issues or for quick testing.
#
# Usage:
#   ./scripts/test/test_pipeline_direct.sh                    # Full pipeline (100 tickers)
#   ./scripts/test/test_pipeline_direct.sh --max-tickers 20   # Limited test
#   ./scripts/test/test_pipeline_direct.sh --skip-seed        # Skip seeding
#   ./scripts/test/test_pipeline_direct.sh --silver-only      # Only build Silver
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STORAGE_PATH="${STORAGE_PATH:-$PROJECT_ROOT/storage}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${GREEN}=== $1 ===${NC}"; }

# Default settings
MAX_TICKERS=100
DAYS=30
SKIP_SEED=false
SILVER_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --days)
            DAYS="$2"
            shift 2
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        --silver-only)
            SILVER_ONLY=true
            shift
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

log_info "Pipeline Configuration:"
echo "  Project Root:  $PROJECT_ROOT"
echo "  Storage Path:  $STORAGE_PATH"
echo "  Max Tickers:   $MAX_TICKERS"
echo "  Days:          $DAYS"
echo "  Skip Seed:     $SKIP_SEED"
echo "  Silver Only:   $SILVER_ONLY"
echo ""

# Activate venv if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
        source "$PROJECT_ROOT/venv/bin/activate"
        log_info "Activated venv"
    fi
fi

# =============================================================================
# Step 1: Seed Tickers (if not skipping)
# =============================================================================
if [ "$SILVER_ONLY" = false ] && [ "$SKIP_SEED" = false ]; then
    log_step "Step 1: Seeding Tickers from LISTING_STATUS"
    python -m scripts.seed.seed_tickers --storage-path "$STORAGE_PATH" || {
        log_warn "Seeding failed or tickers already exist, continuing..."
    }
fi

# =============================================================================
# Step 2: Bronze Ingestion
# =============================================================================
if [ "$SILVER_ONLY" = false ]; then
    log_step "Step 2: Bronze Ingestion - Prices"
    python -m scripts.ingest.run_bronze_ingestion \
        --storage-path "$STORAGE_PATH" \
        --endpoints time_series_daily \
        --max-tickers "$MAX_TICKERS" \
        --days "$DAYS"

    log_step "Step 3: Bronze Ingestion - Company Overview"
    python -m scripts.ingest.run_bronze_ingestion \
        --storage-path "$STORAGE_PATH" \
        --endpoints company_overview \
        --max-tickers "$MAX_TICKERS"

    log_step "Step 4: Bronze Ingestion - Financials"
    python -m scripts.ingest.run_bronze_ingestion \
        --storage-path "$STORAGE_PATH" \
        --endpoints income_statement,balance_sheet,cash_flow,earnings \
        --max-tickers "$MAX_TICKERS" || {
        log_warn "Some financial endpoints may have failed, continuing..."
    }
fi

# =============================================================================
# Step 5: Build Silver Layer
# =============================================================================
log_step "Step 5: Building Silver Layer Models"

# Build in dependency order: temporal → company → stocks
log_info "Building temporal (calendar) model..."
python -m scripts.build.rebuild_model --model temporal --storage-path "$STORAGE_PATH" || {
    log_warn "Temporal build failed, may already exist"
}

log_info "Building company model..."
python -m scripts.build.rebuild_model --model company --storage-path "$STORAGE_PATH" || {
    log_warn "Company build failed"
}

log_info "Building stocks model..."
python -m scripts.build.rebuild_model --model stocks --storage-path "$STORAGE_PATH" || {
    log_warn "Stocks build failed"
}

# =============================================================================
# Summary
# =============================================================================
log_step "Pipeline Complete!"

echo ""
log_info "Bronze Layer:"
ls -la "$STORAGE_PATH/bronze/" 2>/dev/null | head -10 || echo "  (not found)"

echo ""
log_info "Silver Layer:"
ls -la "$STORAGE_PATH/silver/" 2>/dev/null | head -10 || echo "  (not found)"

echo ""
log_info "Next steps:"
echo "  - View data: python -c \"from models.api.registry import get_registry; r = get_registry(); print(r.list_models())\""
echo "  - Run app:   python run_app.py"
echo "  - Forecast:  python -m scripts.forecast.run_stock_forecast --tickers AAPL,MSFT"
