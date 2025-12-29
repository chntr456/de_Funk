#!/bin/bash
#
# Full Pipeline End-to-End Test Script with Airflow Monitoring
#
# This script runs the complete de_Funk pipeline through Airflow:
# 1. Triggers ingest_alpha_vantage DAG (Bronze ingestion)
# 2. Triggers build_models DAG (Silver layer build)
# 3. Monitors both DAGs until completion
# 4. Reports final status
#
# Usage:
#   ./scripts/test/test_full_pipeline_airflow.sh                    # Full pipeline
#   ./scripts/test/test_full_pipeline_airflow.sh --max-tickers 50   # Limit tickers
#   ./scripts/test/test_full_pipeline_airflow.sh --skip-ingest      # Only build models
#   ./scripts/test/test_full_pipeline_airflow.sh --poll-interval 30 # Check every 30s
#
# Prerequisites:
#   - Airflow scheduler and api-server running
#   - DAGs deployed to AIRFLOW_HOME/dags
#   - Airflow variables configured (or using defaults)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AIRFLOW_SCRIPTS="$PROJECT_ROOT/scripts/airflow"

# Configuration
MAX_TICKERS="${MAX_TICKERS:-100}"
POLL_INTERVAL="${POLL_INTERVAL:-15}"  # seconds between status checks
TIMEOUT="${TIMEOUT:-7200}"             # 2 hours max
SKIP_INGEST=false
SKIP_BUILD=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Logging functions
log_info()    { echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"; }
log_status()  { echo -e "${CYAN}[STATUS]${NC} $(date '+%H:%M:%S') $1"; }
log_success() { echo -e "${GREEN}${BOLD}[SUCCESS]${NC} $(date '+%H:%M:%S') $1"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --poll-interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --skip-ingest)
            SKIP_INGEST=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --max-tickers N    Limit ingestion to N tickers (default: 100)"
            echo "  --poll-interval N  Check status every N seconds (default: 15)"
            echo "  --timeout N        Max wait time in seconds (default: 7200)"
            echo "  --skip-ingest      Skip ingestion, only run build"
            echo "  --skip-build       Skip build, only run ingestion"
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
# Helper Functions
# ============================================================================

check_airflow_running() {
    # Check if Airflow CLI is available and responding
    if ! command -v airflow &> /dev/null; then
        log_error "Airflow CLI not found. Ensure Airflow is installed and in PATH."
        return 1
    fi

    if ! airflow dags list &> /dev/null; then
        log_error "Airflow is not responding. Ensure scheduler and api-server are running."
        log_info "Start with: airflow scheduler & airflow api-server &"
        return 1
    fi

    return 0
}

get_dag_state() {
    local dag_id="$1"
    local run_id="$2"

    # Get the state of the most recent run
    airflow dags list-runs -d "$dag_id" -o json 2>/dev/null | \
        python3 -c "
import sys, json
try:
    runs = json.load(sys.stdin)
    if runs:
        # Find the specific run or most recent
        for run in runs:
            if '$run_id' == '' or run.get('run_id', '') == '$run_id':
                print(run.get('state', 'unknown'))
                break
        else:
            print('not_found')
    else:
        print('no_runs')
except:
    print('error')
" 2>/dev/null || echo "error"
}

get_task_states() {
    local dag_id="$1"
    local run_id="$2"

    airflow tasks states-for-dag-run "$dag_id" "$run_id" -o json 2>/dev/null | \
        python3 -c "
import sys, json
try:
    tasks = json.load(sys.stdin)
    for task in tasks:
        state = task.get('state', 'unknown')
        task_id = task.get('task_id', 'unknown')
        # Color-code states
        if state == 'success':
            print(f'  ✓ {task_id}')
        elif state == 'running':
            print(f'  ▶ {task_id} (running)')
        elif state == 'failed':
            print(f'  ✗ {task_id} (FAILED)')
        elif state == 'queued':
            print(f'  ◯ {task_id} (queued)')
        else:
            print(f'  - {task_id} ({state})')
except Exception as e:
    print(f'  Error getting tasks: {e}')
" 2>/dev/null
}

trigger_dag() {
    local dag_id="$1"
    local conf="$2"

    log_info "Triggering DAG: $dag_id"

    # Unpause if paused
    airflow dags unpause "$dag_id" 2>/dev/null || true

    # Trigger with optional conf
    local run_id
    if [ -n "$conf" ]; then
        run_id=$(airflow dags trigger "$dag_id" --conf "$conf" -o json 2>/dev/null | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('dag_run_id',''))" 2>/dev/null)
    else
        run_id=$(airflow dags trigger "$dag_id" -o json 2>/dev/null | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('dag_run_id',''))" 2>/dev/null)
    fi

    if [ -z "$run_id" ]; then
        # Fallback: get most recent run_id
        sleep 2
        run_id=$(airflow dags list-runs -d "$dag_id" -o json 2>/dev/null | \
            python3 -c "import sys,json; runs=json.load(sys.stdin); print(runs[0]['run_id'] if runs else '')" 2>/dev/null)
    fi

    echo "$run_id"
}

monitor_dag() {
    local dag_id="$1"
    local run_id="$2"
    local start_time=$(date +%s)

    log_status "Monitoring $dag_id (run: $run_id)"
    echo ""

    while true; do
        local elapsed=$(($(date +%s) - start_time))

        # Check timeout
        if [ $elapsed -gt $TIMEOUT ]; then
            log_error "Timeout waiting for $dag_id (${elapsed}s > ${TIMEOUT}s)"
            return 1
        fi

        # Get current state
        local state=$(get_dag_state "$dag_id" "$run_id")

        # Print status update
        printf "\r${CYAN}[%s]${NC} %s: %s (elapsed: %ds)    " \
            "$(date '+%H:%M:%S')" "$dag_id" "$state" "$elapsed"

        case "$state" in
            success)
                echo ""
                log_success "$dag_id completed successfully!"
                echo ""
                get_task_states "$dag_id" "$run_id"
                echo ""
                return 0
                ;;
            failed)
                echo ""
                log_error "$dag_id FAILED!"
                echo ""
                get_task_states "$dag_id" "$run_id"
                echo ""
                return 1
                ;;
            running|queued)
                # Still in progress
                ;;
            *)
                # Unknown or error state
                ;;
        esac

        sleep $POLL_INTERVAL
    done
}

# ============================================================================
# Main Pipeline
# ============================================================================

print_header() {
    echo ""
    echo -e "${BOLD}======================================================================${NC}"
    echo -e "${BOLD}  de_Funk Full Pipeline Test (Airflow)${NC}"
    echo -e "${BOLD}======================================================================${NC}"
    echo ""
    echo "Configuration:"
    echo "  Project Root:   $PROJECT_ROOT"
    echo "  Max Tickers:    $MAX_TICKERS"
    echo "  Poll Interval:  ${POLL_INTERVAL}s"
    echo "  Timeout:        ${TIMEOUT}s"
    echo "  Skip Ingest:    $SKIP_INGEST"
    echo "  Skip Build:     $SKIP_BUILD"
    echo ""
}

run_pipeline() {
    local start_time=$(date +%s)
    local ingest_run_id=""
    local build_run_id=""
    local ingest_success=false
    local build_success=false

    # Check Airflow is running
    log_info "Checking Airflow status..."
    if ! check_airflow_running; then
        exit 1
    fi
    log_info "Airflow is running"
    echo ""

    # Set Airflow variables for this run
    log_info "Setting Airflow variables..."
    airflow variables set ingest_max_tickers "$MAX_TICKERS" 2>/dev/null || true

    # =========================================================================
    # Phase 1: Ingestion
    # =========================================================================
    if [ "$SKIP_INGEST" = false ]; then
        echo -e "${BOLD}----------------------------------------------------------------------${NC}"
        echo -e "${BOLD}  Phase 1: Bronze Ingestion (ingest_alpha_vantage)${NC}"
        echo -e "${BOLD}----------------------------------------------------------------------${NC}"
        echo ""

        ingest_run_id=$(trigger_dag "ingest_alpha_vantage" "{\"max_tickers\": $MAX_TICKERS}")

        if [ -z "$ingest_run_id" ]; then
            log_error "Failed to trigger ingest_alpha_vantage"
            exit 1
        fi

        log_info "Triggered with run_id: $ingest_run_id"
        echo ""

        if monitor_dag "ingest_alpha_vantage" "$ingest_run_id"; then
            ingest_success=true
        else
            log_error "Ingestion failed. Check Airflow logs for details."
            if [ "$SKIP_BUILD" = false ]; then
                log_warn "Skipping build phase due to ingestion failure."
                SKIP_BUILD=true
            fi
        fi
    else
        log_info "Skipping ingestion phase (--skip-ingest)"
        ingest_success=true
    fi

    # =========================================================================
    # Phase 2: Model Build
    # =========================================================================
    if [ "$SKIP_BUILD" = false ]; then
        echo ""
        echo -e "${BOLD}----------------------------------------------------------------------${NC}"
        echo -e "${BOLD}  Phase 2: Silver Layer Build (build_models)${NC}"
        echo -e "${BOLD}----------------------------------------------------------------------${NC}"
        echo ""

        # Trigger build_models
        # Note: build_models has an ExternalTaskSensor for ingest, but we can
        # trigger it directly if ingest succeeded or was skipped
        build_run_id=$(trigger_dag "build_models" "")

        if [ -z "$build_run_id" ]; then
            log_error "Failed to trigger build_models"
            exit 1
        fi

        log_info "Triggered with run_id: $build_run_id"
        echo ""

        if monitor_dag "build_models" "$build_run_id"; then
            build_success=true
        else
            log_error "Model build failed. Check Airflow logs for details."
        fi
    else
        log_info "Skipping build phase (--skip-build)"
        build_success=true
    fi

    # =========================================================================
    # Summary
    # =========================================================================
    local total_time=$(($(date +%s) - start_time))

    echo ""
    echo -e "${BOLD}======================================================================${NC}"
    echo -e "${BOLD}  Pipeline Summary${NC}"
    echo -e "${BOLD}======================================================================${NC}"
    echo ""
    echo "  Total Duration: ${total_time}s ($(date -d@$total_time -u +%H:%M:%S))"
    echo ""

    if [ "$SKIP_INGEST" = false ]; then
        if [ "$ingest_success" = true ]; then
            echo -e "  Ingestion:  ${GREEN}✓ SUCCESS${NC}"
        else
            echo -e "  Ingestion:  ${RED}✗ FAILED${NC}"
        fi
    else
        echo -e "  Ingestion:  ${YELLOW}○ SKIPPED${NC}"
    fi

    if [ "$SKIP_BUILD" = false ]; then
        if [ "$build_success" = true ]; then
            echo -e "  Build:      ${GREEN}✓ SUCCESS${NC}"
        else
            echo -e "  Build:      ${RED}✗ FAILED${NC}"
        fi
    else
        echo -e "  Build:      ${YELLOW}○ SKIPPED${NC}"
    fi

    echo ""

    # Verify data
    log_info "Verifying data..."
    echo ""

    if [ -d "$PROJECT_ROOT/storage/bronze" ] || [ -d "/shared/storage/bronze" ]; then
        echo "Bronze tables:"
        ls -la "$PROJECT_ROOT/storage/bronze" 2>/dev/null || ls -la "/shared/storage/bronze" 2>/dev/null || echo "  (no local bronze)"
    fi

    echo ""

    if [ -d "$PROJECT_ROOT/storage/silver" ] || [ -d "/shared/storage/silver" ]; then
        echo "Silver tables:"
        ls -la "$PROJECT_ROOT/storage/silver" 2>/dev/null || ls -la "/shared/storage/silver" 2>/dev/null || echo "  (no local silver)"
    fi

    echo ""
    echo -e "${BOLD}======================================================================${NC}"

    # Exit with appropriate code
    if [ "$ingest_success" = true ] && [ "$build_success" = true ]; then
        log_success "Pipeline completed successfully!"
        exit 0
    else
        log_error "Pipeline completed with errors"
        exit 1
    fi
}

# ============================================================================
# Entry Point
# ============================================================================

print_header
run_pipeline
