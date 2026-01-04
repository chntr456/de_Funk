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

# Configuration - defaults can be overridden by profile or CLI args
PROFILE=""  # Profile from run_config.json (quick_test, dev, staging, production)
MAX_TICKERS=""  # Will be set from profile or default
DAYS=""
STORAGE_PATH=""  # Will be read from run_config.json
VENV_PATH="${VENV_PATH:-$HOME/venv}"
USE_MARKET_CAP=false  # Select tickers by market cap instead of alphabetically
SKIP_SEED=false
SKIP_INGEST=false
SKIP_BUILD=false
SKIP_FORECAST=false
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
        --profile)
            PROFILE="$2"
            shift 2
            ;;
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
        --skip-forecast)
            SKIP_FORECAST=true
            shift
            ;;
        --use-market-cap)
            USE_MARKET_CAP=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Profiles (from run_config.json):"
            echo "  quick_test   10 tickers, dry_run, debug logging"
            echo "  dev          50 tickers (default)"
            echo "  staging      500 tickers"
            echo "  production   All tickers"
            echo ""
            echo "Options:"
            echo "  --profile NAME     Use named profile (quick_test, dev, staging, production)"
            echo "  --max-tickers N    Limit to N tickers (overrides profile)"
            echo "  --days N           Days of historical data"
            echo "  --storage-path P   Override storage path"
            echo "  --venv PATH        Python venv path (default: ~/venv)"
            echo "  --skip-seed        Skip ticker seeding"
            echo "  --skip-ingest      Skip Bronze ingestion"
            echo "  --skip-build       Skip Silver build"
            echo "  --skip-forecast    Skip forecast model build"
            echo "  --use-market-cap   Select tickers by market cap (requires company_reference)"
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

load_config() {
    # Load configuration from run_config.json, applying profile if specified
    local config_output
    config_output=$(python3 -c "
import json
from pathlib import Path

config_path = Path('$PROJECT_ROOT') / 'configs' / 'pipelines' / 'run_config.json'
if not config_path.exists():
    print('STORAGE_PATH=$PROJECT_ROOT/storage')
    print('MAX_TICKERS=50')
    print('DAYS=30')
    exit(0)

with open(config_path) as f:
    config = json.load(f)

defaults = config.get('defaults', {})
profile_name = '$PROFILE'

# Apply profile settings if specified
if profile_name and profile_name in config.get('profiles', {}):
    profile = config['profiles'][profile_name]
    for key, value in profile.items():
        if value is not None:
            defaults[key] = value

# Output configuration as shell variables
storage_path = defaults.get('storage_path', '$PROJECT_ROOT/storage')
max_tickers = defaults.get('max_tickers')
days = defaults.get('days', 30)
use_market_cap = defaults.get('use_market_cap', False)

print(f'CONFIG_STORAGE_PATH={storage_path}')
print(f'CONFIG_MAX_TICKERS={max_tickers if max_tickers else 0}')
print(f'CONFIG_DAYS={days}')
print(f'CONFIG_USE_MARKET_CAP={str(use_market_cap).lower()}')
print(f'CONFIG_PROFILE={profile_name}')
" 2>/dev/null)

    # Parse the output
    eval "$config_output"

    # Apply config values if not overridden by CLI args
    if [ -z "$STORAGE_PATH" ]; then
        STORAGE_PATH="$CONFIG_STORAGE_PATH"
    fi
    if [ -z "$MAX_TICKERS" ]; then
        if [ "$CONFIG_MAX_TICKERS" -gt 0 ] 2>/dev/null; then
            MAX_TICKERS="$CONFIG_MAX_TICKERS"
        else
            MAX_TICKERS=0  # 0 means all tickers
        fi
    fi
    if [ -z "$DAYS" ]; then
        DAYS="$CONFIG_DAYS"
    fi
    # Only set USE_MARKET_CAP from config if not already set via CLI
    if [ "$USE_MARKET_CAP" = false ] && [ "$CONFIG_USE_MARKET_CAP" = "true" ]; then
        USE_MARKET_CAP=true
    fi

    # Log configuration
    if [ -n "$PROFILE" ]; then
        log_info "Using profile: $PROFILE"
    fi
    log_info "Storage path: $STORAGE_PATH"
    if [ "$MAX_TICKERS" -gt 0 ] 2>/dev/null; then
        log_info "Max tickers: $MAX_TICKERS"
    else
        log_info "Max tickers: ALL"
    fi
    log_info "Days: $DAYS"
}

detect_cluster_mode() {
    # Auto-detect if we should use cluster mode
    # If SPARK_MASTER_URL is already set, just ensure memory is appropriate
    if [ -n "$SPARK_MASTER_URL" ]; then
        log_info "Using existing SPARK_MASTER_URL: $SPARK_MASTER_URL"
        # Ensure cluster-appropriate memory settings (workers have 10GB, need headroom)
        export SPARK_EXECUTOR_MEMORY="${SPARK_EXECUTOR_MEMORY:-4g}"
        export SPARK_DRIVER_MEMORY="${SPARK_DRIVER_MEMORY:-2g}"
        log_info "Memory: executor=${SPARK_EXECUTOR_MEMORY}, driver=${SPARK_DRIVER_MEMORY}"
        return 0
    fi

    local cluster_config="$PROJECT_ROOT/configs/cluster.yaml"
    if [ ! -f "$cluster_config" ]; then
        log_info "No cluster config found, using local Spark mode"
        return 0
    fi

    # Read cluster config
    local head_ip
    local spark_port
    head_ip=$(python3 -c "
import yaml
with open('$cluster_config') as f:
    cfg = yaml.safe_load(f)
print(cfg['cluster']['head']['ip'])
" 2>/dev/null)

    spark_port=$(python3 -c "
import yaml
with open('$cluster_config') as f:
    cfg = yaml.safe_load(f)
print(cfg['spark']['master']['port'])
" 2>/dev/null)

    if [ -z "$head_ip" ] || [ -z "$spark_port" ]; then
        log_info "Could not read cluster config, using local Spark mode"
        return 0
    fi

    # Check if we're on the head node
    local local_ips
    local_ips=$(hostname -I 2>/dev/null || echo "")

    if [[ "$local_ips" != *"$head_ip"* ]]; then
        log_info "Not on cluster head node, using local Spark mode"
        return 0
    fi

    # Check if Spark master is running
    if ! curl -s "http://$head_ip:8080/json/" > /dev/null 2>&1; then
        log_warn "Spark master not responding at $head_ip:8080, using local Spark mode"
        return 0
    fi

    # Check if workers are connected
    local worker_count
    worker_count=$(curl -s "http://$head_ip:8080/json/" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('workers', [])))
except:
    print(0)
" 2>/dev/null)

    if [ "$worker_count" -gt 0 ]; then
        export SPARK_MASTER_URL="spark://$head_ip:$spark_port"
        # Set cluster-appropriate memory (workers have 10GB, leave room for OS)
        export SPARK_EXECUTOR_MEMORY="6g"
        export SPARK_DRIVER_MEMORY="4g"
        log_info "Cluster mode enabled: $SPARK_MASTER_URL ($worker_count workers)"
    else
        log_warn "No workers connected to master, using local Spark mode"
    fi
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

    local ticker_limit_msg="ALL"
    if [ "$MAX_TICKERS" -gt 0 ] 2>/dev/null; then
        ticker_limit_msg="$MAX_TICKERS"
    fi
    local market_cap_msg=""
    if [ "$USE_MARKET_CAP" = true ]; then
        market_cap_msg=" (by market cap)"
    fi
    log_step "Running Bronze ingestion (tickers: ${ticker_limit_msg}${market_cap_msg})..."

    cd "$PROJECT_ROOT"

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
_, all_tickers, _, _ = ingestor.ingest_bulk_listing(table_name='securities_reference', state='active')

max_tickers = $MAX_TICKERS
use_market_cap = '$USE_MARKET_CAP' == 'true'

# Select tickers by market cap or alphabetically
if use_market_cap and max_tickers > 0:
    from deltalake import DeltaTable
    import pandas as pd

    # Known large-cap tickers (fallback if no Bronze data)
    SEED_LARGE_CAPS = [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'GOOG', 'AMZN', 'META', 'BRK.B', 'BRK.A',
        'LLY', 'AVGO', 'JPM', 'TSLA', 'WMT', 'V', 'XOM', 'UNH', 'MA', 'PG', 'JNJ',
        'COST', 'HD', 'ORCL', 'MRK', 'ABBV', 'CVX', 'BAC', 'KO', 'CRM', 'PEP',
        'AMD', 'NFLX', 'TMO', 'MCD', 'LIN', 'CSCO', 'ADBE', 'WFC', 'ABT', 'ACN'
    ]

    company_ref_path = Path('$STORAGE_PATH/bronze/company_reference')
    prices_path = Path('$STORAGE_PATH/bronze/securities_prices_daily')
    rankings_path = Path('$STORAGE_PATH/bronze/market_cap_rankings')

    tickers = None

    # Option 1: Use pre-seeded market_cap_rankings table if exists
    if rankings_path.exists():
        print('Using pre-seeded market_cap_rankings table...')
        rankings_dt = DeltaTable(str(rankings_path))
        rankings_df = rankings_dt.to_pandas()
        tickers = rankings_df.nsmallest(max_tickers, 'market_cap_rank')['ticker'].tolist()
        print(f'Selected top {len(tickers)} from market_cap_rankings')

    # Option 2: Calculate market cap from Bronze data using Spark SQL
    elif company_ref_path.exists() and prices_path.exists():
        print('Calculating market cap from Bronze data (price x shares_outstanding)...')

        # Register as Spark temp views
        ctx.spark.read.format('delta').load(str(prices_path)).createOrReplaceTempView('prices')
        ctx.spark.read.format('delta').load(str(company_ref_path)).createOrReplaceTempView('company')

        # SQL with window function to get latest price and calculate market cap
        query = f'''
        WITH latest_prices AS (
            SELECT ticker, close, trade_date,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
            FROM prices
            WHERE close IS NOT NULL AND close > 0
        ),
        market_caps AS (
            SELECT
                c.ticker,
                c.sector,
                COALESCE(c.market_cap, CAST(lp.close AS DOUBLE) * CAST(c.shares_outstanding AS DOUBLE)) as market_cap
            FROM company c
            INNER JOIN latest_prices lp ON c.ticker = lp.ticker AND lp.rn = 1
            WHERE c.shares_outstanding IS NOT NULL AND c.shares_outstanding > 0
        )
        SELECT ticker, sector, market_cap,
               ROW_NUMBER() OVER (ORDER BY market_cap DESC) as rank
        FROM market_caps
        ORDER BY market_cap DESC
        LIMIT {max_tickers}
        '''

        result = ctx.spark.sql(query).toPandas()

        if len(result) >= max_tickers:
            tickers = result['ticker'].tolist()
            print(f'Selected top {len(tickers)} by calculated market cap:')
            for _, row in result.head(5).iterrows():
                cap = row['market_cap']
                cap_str = f'\${cap/1e9:.1f}B' if cap and cap > 1e9 else (f'\${cap/1e6:.0f}M' if cap else 'N/A')
                print(f'  {int(row[\"rank\"]):3}. {row[\"ticker\"]:6} {cap_str} [{row[\"sector\"]}]')
            if len(result) > 5:
                print(f'  ... and {len(result) - 5} more')

    # Option 3: Fallback to seed list
    if tickers is None or len(tickers) < max_tickers:
        print('Using seed list of known large-cap tickers (no market cap data yet)...')
        available_large_caps = [t for t in SEED_LARGE_CAPS if t in all_tickers]
        tickers = available_large_caps[:max_tickers]
        print(f'Selected {len(tickers)} from seed large-cap list:')
        for t in tickers[:5]:
            print(f'  {t}')
        if len(tickers) > 5:
            print(f'  ... and {len(tickers) - 5} more')

elif max_tickers > 0:
    tickers = sorted(all_tickers)[:max_tickers]
    print(f'Selected {len(tickers)} tickers alphabetically')
else:
    tickers = all_tickers

print(f'Processing {len(tickers)} tickers...')

print('Ingesting prices...')
ingestor.ingest_prices(tickers=tickers, date_from=None, date_to=None)

print('Ingesting company overview...')
# skip_securities=True because ingest_bulk_listing already populated securities_reference
ingestor.ingest_reference_data(tickers=tickers, skip_securities=True)

print('Ingesting financial statements...')
try:
    ingestor.ingest_income_statements(tickers=tickers)
except Exception as e:
    print(f'  Warning: income_statement failed: {e}')

try:
    ingestor.ingest_balance_sheets(tickers=tickers)
except Exception as e:
    print(f'  Warning: balance_sheet failed: {e}')

try:
    ingestor.ingest_cash_flows(tickers=tickers)
except Exception as e:
    print(f'  Warning: cash_flow failed: {e}')

try:
    ingestor.ingest_earnings(tickers=tickers)
except Exception as e:
    print(f'  Warning: earnings failed: {e}')

print('Done!')
ctx.spark.stop()
"

    local ingest_status=$?
    if [ $ingest_status -eq 0 ]; then
        log_success "Bronze ingestion complete"
        return 0
    else
        log_error "Bronze ingestion failed (exit code: $ingest_status)"
        return 1  # Properly propagate failure
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

    # Determine which models to build
    local models_to_build="temporal company stocks"

    # Add forecast if not skipped and dependencies available
    if [ "$SKIP_FORECAST" = true ]; then
        log_info "Forecast will be skipped (--skip-forecast)"
    elif timeout 10 python3 -c "import statsmodels; import sklearn" 2>/dev/null; then
        models_to_build="temporal company stocks forecast"
        log_info "Including forecast in build"
    else
        log_info "Forecast skipped (statsmodels/sklearn not installed)"
    fi

    python -m scripts.build.build_models \
        --models $models_to_build \
        --storage-root "$STORAGE_PATH" \
        --max-tickers "$MAX_TICKERS" \
        $verbose_flag

    local build_status=$?

    if [ $build_status -eq 0 ]; then
        log_success "Silver build complete"
    else
        log_error "Silver build failed"
        return 1
    fi

    return 0
}

verify_data() {
    log_step "Verifying data..."

    echo ""
    echo -e "${BOLD}Bronze Layer:${NC}"

    # Check Bronze tables - use metadata for row counts (don't load data!)
    for table in securities_reference securities_prices_daily company_reference; do
        local path="$STORAGE_PATH/bronze/$table"
        if [ -d "$path/_delta_log" ]; then
            local count=$(python3 -c "
from deltalake import DeltaTable
import pyarrow.parquet as pq
try:
    dt = DeltaTable('$path')
    # Use PyArrow metadata to count rows without loading data
    total_rows = 0
    for f in dt.file_uris():
        # Handle both file:// URIs and plain paths
        path = f.replace('file://', '') if f.startswith('file://') else f
        total_rows += pq.read_metadata(path).num_rows
    print(total_rows)
except Exception as e:
    print('error')
" 2>/dev/null || echo "error")
            echo -e "  ${GREEN}✓${NC} $table: $count rows"
        else
            echo -e "  ${YELLOW}○${NC} $table: not found"
        fi
    done

    echo ""
    echo -e "${BOLD}Silver Layer:${NC}"

    # Check Silver directories - structure is: silver/{model}/dims/* and silver/{model}/facts/*
    for model in temporal company stocks forecast; do
        local path="$STORAGE_PATH/silver/$model"
        if [ -d "$path" ]; then
            # Check dims and facts subdirectories - use metadata for row counts (don't load data!)
            local result=$(python3 -c "
from pathlib import Path
import pyarrow.parquet as pq

def count_delta_rows(table_path):
    '''Count rows using PyArrow metadata without loading data'''
    from deltalake import DeltaTable
    dt = DeltaTable(str(table_path))
    total = 0
    for f in dt.file_uris():
        path = f.replace('file://', '') if f.startswith('file://') else f
        total += pq.read_metadata(path).num_rows
    return total

path = Path('$path')
dims_count = 0
facts_count = 0
total_rows = 0

# Check dims subdirectory
dims_path = path / 'dims'
if dims_path.exists():
    for table_dir in dims_path.iterdir():
        if table_dir.is_dir():
            if (table_dir / '_delta_log').exists():
                dims_count += 1
                try:
                    total_rows += count_delta_rows(table_dir)
                except:
                    pass
            elif any(table_dir.glob('*.parquet')):
                dims_count += 1
                total_rows += 1000  # Estimate for non-Delta

# Check facts subdirectory
facts_path = path / 'facts'
if facts_path.exists():
    for table_dir in facts_path.iterdir():
        if table_dir.is_dir():
            if (table_dir / '_delta_log').exists():
                facts_count += 1
                try:
                    total_rows += count_delta_rows(table_dir)
                except:
                    pass
            elif any(table_dir.glob('*.parquet')) or any(table_dir.rglob('*.parquet')):
                facts_count += 1
                total_rows += 1000000  # Estimate for non-Delta

print(f'{dims_count},{facts_count},{total_rows}')
" 2>/dev/null || echo "0,0,0")

            local dims_count=$(echo "$result" | cut -d',' -f1)
            local facts_count=$(echo "$result" | cut -d',' -f2)
            local total_rows=$(echo "$result" | cut -d',' -f3)

            if [ "$dims_count" -gt 0 ] || [ "$facts_count" -gt 0 ]; then
                echo -e "  ${GREEN}✓${NC} $model: $dims_count dims, $facts_count facts (~$total_rows rows)"
            else
                echo -e "  ${YELLOW}○${NC} $model: directory exists but no tables found"
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

    # Setup
    cd "$PROJECT_ROOT"
    activate_venv
    load_config
    detect_cluster_mode

    echo ""
    echo "Configuration:"
    echo "  Project Root:   $PROJECT_ROOT"
    echo "  Storage Path:   $STORAGE_PATH"
    if [ -n "$PROFILE" ]; then
        echo "  Profile:        $PROFILE"
    fi
    if [ "$MAX_TICKERS" -gt 0 ] 2>/dev/null; then
        echo "  Max Tickers:    $MAX_TICKERS"
    else
        echo "  Max Tickers:    ALL"
    fi
    echo "  Use Market Cap: $USE_MARKET_CAP"
    echo "  Days:           $DAYS"
    if [ -n "$SPARK_MASTER_URL" ]; then
        echo "  Spark Mode:     CLUSTER ($SPARK_MASTER_URL)"
    else
        echo "  Spark Mode:     LOCAL"
    fi
    echo "  Skip Seed:      $SKIP_SEED"
    echo "  Skip Ingest:    $SKIP_INGEST"
    echo "  Skip Build:     $SKIP_BUILD"
    echo "  Skip Forecast:  $SKIP_FORECAST"
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
            echo -e "  Ingest:    ${RED}✗ FAILED${NC}"
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

    # Overall success requires all enabled phases to succeed
    local overall_ok=true
    if [ "$seed_ok" = false ]; then
        overall_ok=false
    fi
    if [ "$SKIP_INGEST" = false ] && [ "$ingest_ok" = false ]; then
        overall_ok=false
    fi
    if [ "$SKIP_BUILD" = false ] && [ "$build_ok" = false ]; then
        overall_ok=false
    fi

    if [ "$overall_ok" = true ]; then
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
