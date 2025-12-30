#!/bin/bash
#
# Cluster Pipeline Test Script
#
# Validates Spark cluster + Airflow pipeline end-to-end.
#
# Usage:
#   ./scripts/test/test_cluster_pipeline.sh                    # Full test
#   ./scripts/test/test_cluster_pipeline.sh --spark-only       # Spark cluster only
#   ./scripts/test/test_cluster_pipeline.sh --airflow-only     # Airflow only
#   ./scripts/test/test_cluster_pipeline.sh --skip-cluster     # Skip cluster validation
#   ./scripts/test/test_cluster_pipeline.sh --profile dev      # Use specific profile
#
# Prerequisites:
#   - Run init-cluster.sh first to start the cluster
#   - Airflow should be installed (setup-airflow.sh)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$REPO_ROOT/configs/cluster.yaml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"; }
log_step()    { echo -e "${BLUE}[STEP]${NC} $(date '+%H:%M:%S') $1"; }
log_success() { echo -e "${GREEN}${BOLD}[OK]${NC} $1"; }
log_fail()    { echo -e "${RED}${BOLD}[FAIL]${NC} $1"; }

# Parse YAML config using Python
read_config() {
    python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
$1
"
}

# =============================================================================
# Parse Arguments
# =============================================================================

SKIP_CLUSTER=false
SPARK_ONLY=false
AIRFLOW_ONLY=false
PROFILE="dev"
MAX_TICKERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cluster)
            SKIP_CLUSTER=true
            shift
            ;;
        --spark-only)
            SPARK_ONLY=true
            shift
            ;;
        --airflow-only)
            AIRFLOW_ONLY=true
            SKIP_CLUSTER=true
            shift
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-cluster    Skip Spark cluster validation"
            echo "  --spark-only      Only test Spark (no Airflow)"
            echo "  --airflow-only    Only test Airflow"
            echo "  --profile NAME    Use config profile (quick_test, dev, staging, production)"
            echo "  --max-tickers N   Override max tickers"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Load Configuration
# =============================================================================

if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

HEAD_IP=$(read_config "print(cfg['cluster']['head']['ip'])")
DE_FUNK_USER=$(read_config "print(cfg['cluster']['head']['user'])")
SPARK_PORT=$(read_config "print(cfg['spark']['master']['port'])")
SPARK_UI_PORT=$(read_config "print(cfg['spark']['master']['ui_port'])")
AIRFLOW_PORT=$(read_config "print(cfg['airflow']['port'])")
VENV_PATH="/home/$DE_FUNK_USER/venv"
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"
STORAGE_PATH="/shared/storage"

# Count workers
WORKER_COUNT=$(read_config "print(len(cfg['cluster']['workers']))")

echo ""
echo -e "${BOLD}======================================================================"
echo "  de_Funk Cluster Pipeline Test"
echo "======================================================================${NC}"
echo ""
echo "Configuration:"
echo "  Profile:       $PROFILE"
echo "  Master:        $HEAD_IP:$SPARK_PORT"
echo "  Workers:       $WORKER_COUNT"
echo "  Storage:       $STORAGE_PATH"
echo ""

# Track results
TESTS_PASSED=0
TESTS_FAILED=0

record_pass() {
    log_success "$1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

record_fail() {
    log_fail "$1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# =============================================================================
# Step 1: Validate Spark Cluster
# =============================================================================

if [ "$SKIP_CLUSTER" = false ] && [ "$AIRFLOW_ONLY" = false ]; then
    log_step "Step 1: Validating Spark Cluster"

    # Check Spark Master
    if curl -s "http://$HEAD_IP:$SPARK_UI_PORT" > /dev/null 2>&1; then
        record_pass "Spark Master is running at http://$HEAD_IP:$SPARK_UI_PORT"
    else
        record_fail "Spark Master not accessible. Run: ./scripts/spark-cluster/init-cluster.sh"
        echo "  Hint: curl -s http://$HEAD_IP:$SPARK_UI_PORT"
        exit 1
    fi

    # Check worker count
    CONNECTED_WORKERS=$(curl -s "http://$HEAD_IP:$SPARK_UI_PORT/json/" | \
        python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")

    if [ "$CONNECTED_WORKERS" -gt 0 ]; then
        record_pass "$CONNECTED_WORKERS workers connected to cluster"

        # Show worker details
        curl -s "http://$HEAD_IP:$SPARK_UI_PORT/json/" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for w in d.get('workers', []):
    print(f\"  - {w['host']}: {w['cores']} cores, {w['memory']//1024//1024}MB\")
"
    else
        record_fail "No workers connected (expected $WORKER_COUNT)"
        echo "  Check worker logs or run: ./scripts/spark-cluster/init-cluster.sh"
    fi

    # Check NFS storage
    if [ -d "$STORAGE_PATH" ]; then
        if [ -w "$STORAGE_PATH" ]; then
            record_pass "Storage accessible and writable: $STORAGE_PATH"
        else
            record_fail "Storage not writable: $STORAGE_PATH"
        fi
    else
        record_fail "Storage not found: $STORAGE_PATH"
        echo "  Mount NFS or check path"
    fi
else
    log_info "Skipping cluster validation"
fi

# =============================================================================
# Step 2: Test Spark Pipeline (Bronze Ingestion + Silver Build)
# =============================================================================

if [ "$AIRFLOW_ONLY" = false ]; then
    log_step "Step 2: Testing Spark Pipeline"

    cd "$REPO_ROOT"
    source "$VENV_PATH/bin/activate" 2>/dev/null || {
        log_error "Virtual environment not found: $VENV_PATH"
        exit 1
    }

    # Build Spark submit arguments
    SPARK_ARGS="--profile $PROFILE"
    if [ -n "$MAX_TICKERS" ]; then
        SPARK_ARGS="$SPARK_ARGS --max-tickers $MAX_TICKERS"
    fi

    # Run the full pipeline test
    log_info "Running: test_full_pipeline_spark.sh $SPARK_ARGS"

    if ./scripts/test/test_full_pipeline_spark.sh $SPARK_ARGS; then
        record_pass "Spark pipeline completed successfully"
    else
        record_fail "Spark pipeline failed"
        echo "  Check logs for details"
    fi
else
    log_info "Skipping Spark pipeline test"
fi

# =============================================================================
# Step 3: Test Airflow
# =============================================================================

if [ "$SPARK_ONLY" = false ]; then
    log_step "Step 3: Testing Airflow"

    # Check if Airflow venv exists
    if [ ! -d "$AIRFLOW_VENV" ]; then
        log_warn "Airflow not installed at $AIRFLOW_VENV"
        echo "  Install with: ./orchestration/airflow/setup-airflow.sh"
        record_fail "Airflow not installed"
    else
        source "$AIRFLOW_VENV/bin/activate" 2>/dev/null
        export AIRFLOW_HOME="/home/$DE_FUNK_USER/airflow"

        # Check if Airflow is running
        if pgrep -f "airflow scheduler" > /dev/null && \
           (pgrep -f "airflow api-server" > /dev/null || pgrep -f "airflow webserver" > /dev/null); then
            record_pass "Airflow processes are running"
        else
            log_warn "Airflow not running - starting in standalone mode"

            # Start Airflow standalone for testing
            log_info "Starting Airflow standalone..."
            mkdir -p "$AIRFLOW_HOME/logs"
            nohup airflow standalone > "$AIRFLOW_HOME/logs/standalone.log" 2>&1 &

            # Wait for it to start
            for i in {1..30}; do
                if airflow dags list &>/dev/null; then
                    record_pass "Airflow started successfully"
                    break
                fi
                sleep 2
            done
        fi

        # List DAGs
        log_info "Available DAGs:"
        airflow dags list 2>/dev/null | grep -E "(ingest|build|forecast|dag_id)" || echo "  No DAGs found"

        # Check if our DAGs exist
        if airflow dags list 2>/dev/null | grep -q "ingest_alpha_vantage"; then
            record_pass "DAG: ingest_alpha_vantage"
        else
            record_fail "DAG ingest_alpha_vantage not found"
        fi

        if airflow dags list 2>/dev/null | grep -q "build_models"; then
            record_pass "DAG: build_models"
        else
            record_fail "DAG build_models not found"
        fi

        # Test DAG validity
        log_info "Validating DAG syntax..."
        if python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT/orchestration/airflow/dags')
import ingest_alpha_vantage
import build_models
print('DAGs validated successfully')
" 2>/dev/null; then
            record_pass "DAG syntax is valid"
        else
            record_fail "DAG syntax errors detected"
        fi

        # Optional: Trigger test run
        if [ "$PROFILE" = "quick_test" ] || [ -n "$MAX_TICKERS" ]; then
            log_info "Triggering test ingestion DAG..."

            CONF="{\"max_tickers\": ${MAX_TICKERS:-10}}"

            # Unpause and trigger
            airflow dags unpause ingest_alpha_vantage 2>/dev/null || true

            if airflow dags trigger ingest_alpha_vantage --conf "$CONF" 2>/dev/null; then
                record_pass "Ingestion DAG triggered successfully"
                echo "  Monitor: tail -f $AIRFLOW_HOME/logs/scheduler/latest/*.log"
            else
                log_warn "Could not trigger DAG (may need manual intervention)"
            fi
        fi
    fi
else
    log_info "Skipping Airflow test"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${BOLD}======================================================================"
echo "  Test Summary"
echo "======================================================================${NC}"
echo ""
echo -e "  ${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "  ${RED}Failed:${NC} $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    echo "Some tests failed. Check the output above for details."
    echo ""
    echo "Common fixes:"
    echo "  1. Start cluster:     ./scripts/spark-cluster/init-cluster.sh"
    echo "  2. Install Airflow:   ./orchestration/airflow/setup-airflow.sh"
    echo "  3. Check logs:        tail -f /data/de_funk/logs/*.log"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Cluster is ready for pipeline execution."
    echo ""
    echo "Next steps:"
    echo "  # Run full pipeline via Spark"
    echo "  ./scripts/test/test_full_pipeline_spark.sh --profile dev"
    echo ""
    echo "  # Run pipeline via Airflow"
    echo "  airflow dags trigger ingest_alpha_vantage --conf '{\"max_tickers\": 50}'"
    echo "  airflow dags trigger build_models"
    echo ""
    echo "  # Stop cluster when done"
    echo "  ./scripts/spark-cluster/stop-cluster.sh"
fi
