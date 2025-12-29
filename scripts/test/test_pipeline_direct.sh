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
# Run the full Spark-based pipeline
# =============================================================================
if [ "$SILVER_ONLY" = false ]; then
    log_step "Running Full Pipeline (Spark-based: Bronze → Silver → Forecast)"

    # Use the main full pipeline script which handles everything:
    # 1. AlphaVantageIngestor for Bronze ingestion (with rate limiting)
    # 2. Spark-based Silver layer build (company, stocks models)
    # 3. Forecasting (optional)
    python -m scripts.run_full_pipeline \
        --max-tickers "$MAX_TICKERS" \
        --days "$DAYS" \
        --use-bulk-listing \
        --skip-forecasts || {
        log_warn "Pipeline had some issues, check output above"
    }
else
    # Silver only - just build models
    log_step "Building Silver Layer Models Only"

    log_info "Building company model..."
    python -m scripts.build.rebuild_model --model company || {
        log_warn "Company build failed"
    }

    log_info "Building stocks model..."
    python -m scripts.build.rebuild_model --model stocks || {
        log_warn "Stocks build failed"
    }
fi

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
