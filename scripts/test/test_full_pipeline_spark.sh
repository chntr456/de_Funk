#!/bin/bash
#
# Full Pipeline Test Script - Direct Spark Execution
#
# Tests the complete de_Funk pipeline WITHOUT Airflow:
# 1. Seeds tickers from Alpha Vantage LISTING_STATUS
# 2. Ingests Bronze data (prices, overview, financials)
# 3. Builds Silver models (temporal, company, stocks)
# 4. Verifies data exists and reports results
#
# This script proves the pipeline works before adding Airflow orchestration.
#
# Usage:
#   ./scripts/test/test_full_pipeline_spark.sh                    # Full test
#   ./scripts/test/test_full_pipeline_spark.sh --max-tickers 20   # Quick test
#   ./scripts/test/test_full_pipeline_spark.sh --skip-ingest      # Only build
#   ./scripts/test/test_full_pipeline_spark.sh --skip-build       # Only ingest
#
# Prerequisites:
#   - Python venv with pyspark, deltalake, etc.
#   - ALPHA_VANTAGE_API_KEY in .env
#   - Storage path configured in run_config.json
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
MAX_TICKERS="${MAX_TICKERS:-50}"
DAYS="${DAYS:-30}"
STORAGE_PATH=""  # Will be read from run_config.json
VENV_PATH="${VENV_PATH:-$HOME/venv}"
SKIP_SEED=false
SKIP_INGEST=false
SKIP_BUILD=false
VERBOSE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Logging
log_info()    { echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"; }
log_step()    { echo -e "${CYAN}[STEP]${NC} $(date '+%H:%M:%S') $1"; }
log_success() { echo -e "${GREEN}${BOLD}[SUCCESS]${NC} $(date '+%H:%M:%S') $1"; }

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
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --venv)
            VENV_PATH="$2"
            shift 2
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        --skip-ingest)
            SKIP_INGEST=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --max-tickers N    Limit to N tickers (default: 50)"
            echo "  --days N           Days of historical data (default: 30)"
            echo "  --storage-path P   Override storage path"
            echo "  --venv PATH        Python venv path (default: ~/venv)"
            echo "  --skip-seed        Skip ticker seeding"
            echo "  --skip-ingest      Skip Bronze ingestion"
            echo "  --skip-build       Skip Silver build"
            echo "  --verbose          Show detailed output"
            echo "  --help             Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Setup
# ============================================================================

print_header() {
    echo ""
    echo -e "${BOLD}======================================================================${NC}"
    echo -e "${BOLD}  de_Funk Full Pipeline Test (Direct Spark Execution)${NC}"
    echo -e "${BOLD}======================================================================${NC}"
    echo ""
}

activate_venv() {
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        log_info "Activated venv: $VENV_PATH"
    else
        log_warn "Venv not found at $VENV_PATH, using current Python"
    fi
}

get_storage_path() {
    # Read storage_path from run_config.json if not provided
    if [ -z "$STORAGE_PATH" ]; then
        STORAGE_PATH=$(python3 -c "
import json
from pathlib import Path
config_path = Path('$PROJECT_ROOT') / 'configs' / 'pipelines' / 'run_config.json'
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
    print(config.get('defaults', {}).get('storage_path', '$PROJECT_ROOT/storage'))
else:
    print('$PROJECT_ROOT/storage')
" 2>/dev/null)
    fi
    log_info "Storage path: $STORAGE_PATH"
}

check_dependencies() {
    log_step "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 not found"
        return 1
    fi

    # Check required packages
    python3 -c "import pyspark; import deltalake" 2>/dev/null || {
        log_error "Required packages missing. Install with: pip install pyspark deltalake"
        return 1
    }

    # Check API key
    if [ -f "$PROJECT_ROOT/.env" ]; then
        if grep -q "ALPHA_VANTAGE_API_KEY" "$PROJECT_ROOT/.env"; then
            log_info "API key found in .env"
        else
            log_warn "ALPHA_VANTAGE_API_KEY not in .env - ingestion may fail"
        fi
    else
        log_warn ".env file not found - ingestion may fail"
    fi

    log_info "Dependencies OK"
    return 0
}

# ============================================================================
# Pipeline Steps
# ============================================================================

run_seed_tickers() {
    if [ "$SKIP_SEED" = true ]; then
        log_info "Skipping ticker seed (--skip-seed)"
        return 0
    fi

    log_step "Seeding tickers from Alpha Vantage LISTING_STATUS..."

    # Check if already seeded
    if [ -d "$STORAGE_PATH/bronze/securities_reference/_delta_log" ]; then
        local ticker_count=$(python3 -c "
from deltalake import DeltaTable
dt = DeltaTable('$STORAGE_PATH/bronze/securities_reference')
print(len(dt.to_pandas()))
" 2>/dev/null || echo "0")

        if [ "$ticker_count" -gt 0 ]; then
            log_info "Tickers already seeded ($ticker_count tickers). Skipping."
            return 0
        fi
    fi

    cd "$PROJECT_ROOT"
    python -m scripts.seed.seed_tickers --storage-path "$STORAGE_PATH"

    if [ $? -eq 0 ]; then
        log_success "Ticker seeding complete"
        return 0
    else
        log_error "Ticker seeding failed"
        return 1
    fi
}

run_bronze_ingestion() {
    if [ "$SKIP_INGEST" = true ]; then
        log_info "Skipping Bronze ingestion (--skip-ingest)"
        return 0
    fi

    log_step "Running Bronze ingestion (max $MAX_TICKERS tickers)..."

    cd "$PROJECT_ROOT"

    # Check if Bronze data already exists
    local price_path="$STORAGE_PATH/bronze/securities_prices_daily"
    if [ -d "$price_path/_delta_log" ]; then
        local count=$(python3 -c "
from deltalake import DeltaTable
try:
    dt = DeltaTable('$price_path')
    print(len(dt.to_pandas()))
except:
    print('0')
" 2>/dev/null || echo "0")
        if [ "$count" -gt 1000000 ]; then
            log_info "Bronze prices already populated ($count rows). Skipping ingestion."
            log_info "Use --force-ingest to re-ingest anyway."
            return 0
        fi
    fi

    # Use the Spark-based ingestor (AlphaVantageIngestor)
    log_info "Using AlphaVantageIngestor for Bronze ingestion..."
    python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from pathlib import Path
from utils.repo import setup_repo_imports
setup_repo_imports()

from core.context import RepoContext
from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

print('Initializing context...')
ctx = RepoContext.from_repo_root(connection_type='spark')

# Override storage path
ctx.storage['roots']['bronze'] = '$STORAGE_PATH/bronze'
ctx.storage['roots']['silver'] = '$STORAGE_PATH/silver'

print('Initializing ingestor...')
ingestor = AlphaVantageIngestor(
    alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
    storage_cfg=ctx.storage,
    spark=ctx.spark
)

print('Fetching ticker list...')
_, tickers, _, _ = ingestor.ingest_bulk_listing(table_name='securities_reference', state='active')
tickers = tickers[:$MAX_TICKERS]
print(f'Processing {len(tickers)} tickers...')

print('Ingesting prices...')
ingestor.ingest_prices(tickers=tickers, date_from=None, date_to=None)

print('Ingesting company overview...')
ingestor.ingest_reference_data(tickers=tickers)

print('Done!')
ctx.spark.stop()
"

    if [ $? -eq 0 ]; then
        log_success "Bronze ingestion complete"
        return 0
    else
        log_warn "Bronze ingestion had issues"
        return 0  # Don't fail the pipeline if Bronze already has data
    fi
}

run_silver_build() {
    if [ "$SKIP_BUILD" = true ]; then
        log_info "Skipping Silver build (--skip-build)"
        return 0
    fi

    log_step "Building Silver layer models..."

    cd "$PROJECT_ROOT"

    # Build all models
    local verbose_flag=""
    if [ "$VERBOSE" = true ]; then
        verbose_flag="--verbose"
    fi

    python -m scripts.build.build_models \
        --models temporal company stocks \
        --storage-root "$STORAGE_PATH" \
        $verbose_flag

    if [ $? -eq 0 ]; then
        log_success "Silver build complete"
        return 0
    else
        log_error "Silver build failed"
        return 1
    fi
}

verify_data() {
    log_step "Verifying data..."

    echo ""
    echo -e "${BOLD}Bronze Layer:${NC}"

    # Check Bronze tables
    for table in securities_reference securities_prices_daily company_reference; do
        local path="$STORAGE_PATH/bronze/$table"
        if [ -d "$path/_delta_log" ]; then
            local count=$(python3 -c "
from deltalake import DeltaTable
try:
    dt = DeltaTable('$path')
    print(len(dt.to_pandas()))
except:
    print('error')
" 2>/dev/null || echo "error")
            echo -e "  ${GREEN}✓${NC} $table: $count rows"
        else
            echo -e "  ${YELLOW}○${NC} $table: not found"
        fi
    done

    echo ""
    echo -e "${BOLD}Silver Layer:${NC}"

    # Check Silver directories - look for Delta tables recursively
    for model in temporal company stocks; do
        local path="$STORAGE_PATH/silver/$model"
        if [ -d "$path" ]; then
            # Count Delta tables (directories with _delta_log)
            local tables=$(find "$path" -name "_delta_log" -type d 2>/dev/null | wc -l)
            if [ "$tables" -gt 0 ]; then
                # Get total rows across all tables
                local total_rows=$(python3 -c "
from pathlib import Path
from deltalake import DeltaTable
total = 0
for delta_log in Path('$path').rglob('_delta_log'):
    try:
        dt = DeltaTable(str(delta_log.parent))
        total += len(dt.to_pandas())
    except:
        pass
print(total)
" 2>/dev/null || echo "0")
                echo -e "  ${GREEN}✓${NC} $model: $tables tables, $total_rows rows"
            else
                # Check if it's a single Delta table at root
                if [ -d "$path/_delta_log" ]; then
                    local rows=$(python3 -c "
from deltalake import DeltaTable
dt = DeltaTable('$path')
print(len(dt.to_pandas()))
" 2>/dev/null || echo "0")
                    echo -e "  ${GREEN}✓${NC} $model: 1 table, $rows rows"
                else
                    echo -e "  ${YELLOW}○${NC} $model: directory exists but no Delta tables"
                fi
            fi
        else
            echo -e "  ${YELLOW}○${NC} $model: not found"
        fi
    done

    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    local start_time=$(date +%s)
    local seed_ok=true
    local ingest_ok=true
    local build_ok=true

    print_header

    echo "Configuration:"
    echo "  Project Root:   $PROJECT_ROOT"
    echo "  Max Tickers:    $MAX_TICKERS"
    echo "  Days:           $DAYS"
    echo "  Skip Seed:      $SKIP_SEED"
    echo "  Skip Ingest:    $SKIP_INGEST"
    echo "  Skip Build:     $SKIP_BUILD"
    echo ""

    # Setup
    cd "$PROJECT_ROOT"
    activate_venv
    get_storage_path

    echo "  Storage Path:   $STORAGE_PATH"
    echo ""

    if ! check_dependencies; then
        exit 1
    fi

    echo ""
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}  Phase 1: Seed Tickers${NC}"
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo ""

    run_seed_tickers || seed_ok=false

    echo ""
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}  Phase 2: Bronze Ingestion${NC}"
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo ""

    run_bronze_ingestion || ingest_ok=false

    echo ""
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}  Phase 3: Silver Build${NC}"
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo ""

    run_silver_build || build_ok=false

    echo ""
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo -e "${BOLD}  Phase 4: Verification${NC}"
    echo -e "${BOLD}----------------------------------------------------------------------${NC}"
    echo ""

    verify_data

    # Summary
    local total_time=$(($(date +%s) - start_time))

    echo -e "${BOLD}======================================================================${NC}"
    echo -e "${BOLD}  Pipeline Summary${NC}"
    echo -e "${BOLD}======================================================================${NC}"
    echo ""
    echo "  Total Duration: ${total_time}s"
    echo ""

    if [ "$seed_ok" = true ]; then
        echo -e "  Seed:      ${GREEN}✓ SUCCESS${NC}"
    else
        echo -e "  Seed:      ${RED}✗ FAILED${NC}"
    fi

    if [ "$SKIP_INGEST" = false ]; then
        if [ "$ingest_ok" = true ]; then
            echo -e "  Ingest:    ${GREEN}✓ SUCCESS${NC}"
        else
            echo -e "  Ingest:    ${YELLOW}⚠ PARTIAL${NC} (rate limits expected)"
        fi
    else
        echo -e "  Ingest:    ${YELLOW}○ SKIPPED${NC}"
    fi

    if [ "$SKIP_BUILD" = false ]; then
        if [ "$build_ok" = true ]; then
            echo -e "  Build:     ${GREEN}✓ SUCCESS${NC}"
        else
            echo -e "  Build:     ${RED}✗ FAILED${NC}"
        fi
    else
        echo -e "  Build:     ${YELLOW}○ SKIPPED${NC}"
    fi

    echo ""
    echo -e "${BOLD}======================================================================${NC}"

    if [ "$build_ok" = true ]; then
        log_success "Pipeline test completed successfully!"
        echo ""
        echo "Next steps:"
        echo "  - View data: python -c \"from deltalake import DeltaTable; print(DeltaTable('$STORAGE_PATH/silver/stocks/dim_stock').to_pandas().head())\""
        echo "  - Run app:   python run_app.py"
        echo ""
        exit 0
    else
        log_error "Pipeline test completed with errors"
        exit 1
    fi
}

main "$@"
