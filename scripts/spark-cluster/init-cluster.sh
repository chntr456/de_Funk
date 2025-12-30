#!/bin/bash
#
# Initialize Spark Cluster
#
# Comprehensive cluster initialization that:
# 1. Validates/mounts NFS shared storage
# 2. Starts Spark master and connects workers
# 3. Validates all worker nodes are connected
# 4. Starts Airflow scheduler and webserver
#
# Usage:
#   ./scripts/spark-cluster/init-cluster.sh              # Full init
#   ./scripts/spark-cluster/init-cluster.sh --skip-nfs   # Skip NFS check
#   ./scripts/spark-cluster/init-cluster.sh --skip-airflow  # Skip Airflow
#   ./scripts/spark-cluster/init-cluster.sh --workers-only  # Only start workers
#
# Prerequisites:
#   - Run setup-head.sh once on master node
#   - Run setup-worker.sh once on each worker node
#   - NFS configured and exported from master
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source spark environment
source "$SCRIPT_DIR/spark-env.sh" 2>/dev/null || true

# =============================================================================
# Configuration
# =============================================================================

# Network - adjust these for your cluster
MASTER_HOST="${SPARK_MASTER_HOST:-192.168.1.212}"
WORKER_HOSTS="${WORKER_HOSTS:-192.168.1.207 192.168.1.202 192.168.1.203}"

# Storage
NFS_SERVER="${NFS_SERVER:-$MASTER_HOST}"
NFS_EXPORT="${NFS_EXPORT:-/shared}"
NFS_MOUNT_POINT="${NFS_MOUNT_POINT:-/shared}"
STORAGE_PATH="${STORAGE_PATH:-$NFS_MOUNT_POINT/storage}"

# User
DE_FUNK_USER="${DE_FUNK_USER:-ms_trixie}"
VENV_PATH="${VENV_PATH:-/home/$DE_FUNK_USER/venv}"

# Spark
SPARK_MASTER_PORT="${SPARK_MASTER_PORT:-7077}"
SPARK_WEBUI_PORT="${SPARK_WEBUI_PORT:-8080}"
SPARK_MASTER_URL="spark://$MASTER_HOST:$SPARK_MASTER_PORT"

# Airflow
AIRFLOW_HOME="${AIRFLOW_HOME:-/home/$DE_FUNK_USER/airflow}"
AIRFLOW_VENV="${AIRFLOW_VENV:-/home/$DE_FUNK_USER/airflow-venv}"
AIRFLOW_PORT="${AIRFLOW_PORT:-8081}"

# Flags
SKIP_NFS=false
SKIP_AIRFLOW=false
SKIP_SPARK=false
WORKERS_ONLY=false
LOCAL_ONLY=false
VERBOSE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-nfs)
            SKIP_NFS=true
            shift
            ;;
        --skip-airflow)
            SKIP_AIRFLOW=true
            shift
            ;;
        --skip-spark)
            SKIP_SPARK=true
            shift
            ;;
        --workers-only)
            WORKERS_ONLY=true
            shift
            ;;
        --local-only)
            LOCAL_ONLY=true
            shift
            ;;
        --master-host)
            MASTER_HOST="$2"
            SPARK_MASTER_URL="spark://$MASTER_HOST:$SPARK_MASTER_PORT"
            shift 2
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-nfs        Skip NFS validation"
            echo "  --skip-airflow    Skip Airflow startup"
            echo "  --skip-spark      Skip Spark startup (only validate NFS)"
            echo "  --workers-only    Only start workers (master already running)"
            echo "  --local-only      Only start local services (no SSH to workers)"
            echo "  --master-host IP  Override master host IP"
            echo "  --storage-path P  Override storage path"
            echo "  --verbose         Show detailed output"
            echo ""
            echo "Environment Variables:"
            echo "  MASTER_HOST       Master node IP (default: 192.168.1.212)"
            echo "  WORKER_HOSTS      Space-separated worker IPs"
            echo "  STORAGE_PATH      Shared storage path (default: /shared/storage)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Logging Functions
# =============================================================================

log_info()    { echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"; }
log_step()    { echo -e "${BLUE}[STEP]${NC} $(date '+%H:%M:%S') $1"; }
log_success() { echo -e "${GREEN}${BOLD}[OK]${NC} $1"; }
log_fail()    { echo -e "${RED}${BOLD}[FAIL]${NC} $1"; }

print_header() {
    echo ""
    echo -e "${BOLD}======================================================================"
    echo "  de_Funk Cluster Initialization"
    echo "======================================================================${NC}"
    echo ""
    echo "Configuration:"
    echo "  Master Host:    $MASTER_HOST"
    echo "  Worker Hosts:   $WORKER_HOSTS"
    echo "  Storage Path:   $STORAGE_PATH"
    echo "  Spark URL:      $SPARK_MASTER_URL"
    echo "  Airflow Port:   $AIRFLOW_PORT"
    echo ""
}

# =============================================================================
# NFS Validation
# =============================================================================

validate_nfs() {
    if [ "$SKIP_NFS" = true ]; then
        log_info "Skipping NFS validation (--skip-nfs)"
        return 0
    fi

    log_step "Validating NFS shared storage..."

    # Check if mount point exists
    if [ ! -d "$NFS_MOUNT_POINT" ]; then
        log_error "NFS mount point $NFS_MOUNT_POINT does not exist"
        echo "  Create with: sudo mkdir -p $NFS_MOUNT_POINT"
        return 1
    fi

    # Check if mounted
    if ! mountpoint -q "$NFS_MOUNT_POINT" 2>/dev/null; then
        log_warn "NFS not mounted at $NFS_MOUNT_POINT, attempting to mount..."
        sudo mount -t nfs "$NFS_SERVER:$NFS_EXPORT" "$NFS_MOUNT_POINT" || {
            log_error "Failed to mount NFS"
            echo "  Check NFS server: showmount -e $NFS_SERVER"
            return 1
        }
    fi

    # Check storage directory exists
    if [ ! -d "$STORAGE_PATH" ]; then
        log_warn "Storage directory $STORAGE_PATH does not exist, creating..."
        sudo mkdir -p "$STORAGE_PATH/bronze" "$STORAGE_PATH/silver"
        sudo chown -R "$DE_FUNK_USER:$DE_FUNK_USER" "$STORAGE_PATH"
    fi

    # Check write access
    local test_file="$STORAGE_PATH/.cluster_init_test_$$"
    if touch "$test_file" 2>/dev/null; then
        rm -f "$test_file"
        log_success "NFS storage validated: $STORAGE_PATH"
    else
        log_error "Cannot write to $STORAGE_PATH"
        return 1
    fi

    # Validate on workers (skip if local-only)
    if [ "$LOCAL_ONLY" = true ]; then
        log_info "Skipping remote worker validation (--local-only)"
    else
        for worker in $WORKER_HOSTS; do
            if ssh -o ConnectTimeout=5 -o BatchMode=yes "$worker" "test -d $STORAGE_PATH" 2>/dev/null; then
                log_success "Worker $worker can access storage"
            else
                log_warn "Worker $worker cannot access $STORAGE_PATH (SSH failed or path missing)"
            fi
        done
    fi

    return 0
}

# =============================================================================
# Spark Cluster
# =============================================================================

start_spark_master() {
    log_step "Starting Spark Master..."

    # Check if already running
    if pgrep -f "spark.*Master" > /dev/null; then
        log_info "Spark Master already running"
        return 0
    fi

    "$SCRIPT_DIR/start-master.sh" || {
        log_error "Failed to start Spark Master"
        return 1
    }

    # Wait for master to be ready
    local retries=10
    while [ $retries -gt 0 ]; do
        if curl -s "http://$MASTER_HOST:$SPARK_WEBUI_PORT" > /dev/null 2>&1; then
            log_success "Spark Master running at $SPARK_MASTER_URL"
            return 0
        fi
        sleep 1
        retries=$((retries - 1))
    done

    log_error "Spark Master did not start within timeout"
    return 1
}

start_spark_workers() {
    log_step "Starting Spark Workers..."

    local workers_started=0
    local workers_failed=0

    # Start remote workers (skip if local-only)
    if [ "$LOCAL_ONLY" = true ]; then
        log_info "Skipping remote workers (--local-only)"
    else
        for worker in $WORKER_HOSTS; do
            log_info "Starting worker on $worker..."

            # SSH to worker and start
            if ssh -o ConnectTimeout=10 -o BatchMode=yes "$worker" "
                source $VENV_PATH/bin/activate 2>/dev/null || true
                cd $PROJECT_ROOT/scripts/spark-cluster
                ./start-worker.sh --master $SPARK_MASTER_URL
            " 2>/dev/null; then
                log_success "Worker started on $worker"
                workers_started=$((workers_started + 1))
            else
                log_warn "Failed to start worker on $worker"
                workers_failed=$((workers_failed + 1))
            fi
        done
    fi

    # Also start local worker on master
    log_info "Starting local worker on master..."
    "$SCRIPT_DIR/start-worker.sh" --master "$SPARK_MASTER_URL" 2>/dev/null || true
    workers_started=$((workers_started + 1))

    log_info "Workers started: $workers_started, failed: $workers_failed"
    return 0
}

validate_spark_cluster() {
    log_step "Validating Spark cluster..."

    # Give workers time to register
    sleep 3

    # Check master UI for worker count
    local worker_count=$(curl -s "http://$MASTER_HOST:$SPARK_WEBUI_PORT/json" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('workers',[])))" 2>/dev/null || echo "0")

    if [ "$worker_count" -gt 0 ]; then
        log_success "Spark cluster ready: $worker_count workers connected"

        # Show worker details if verbose
        if [ "$VERBOSE" = true ]; then
            curl -s "http://$MASTER_HOST:$SPARK_WEBUI_PORT/json" 2>/dev/null | \
                python3 -c "
import sys, json
d = json.load(sys.stdin)
for w in d.get('workers', []):
    print(f\"  - {w['host']}: {w['cores']} cores, {w['memory']//1024//1024}MB\")
"
        fi
        return 0
    else
        log_warn "No workers connected to master"
        echo "  Check: http://$MASTER_HOST:$SPARK_WEBUI_PORT"
        return 1
    fi
}

# =============================================================================
# Airflow
# =============================================================================

start_airflow() {
    if [ "$SKIP_AIRFLOW" = true ]; then
        log_info "Skipping Airflow (--skip-airflow)"
        return 0
    fi

    log_step "Starting Airflow..."

    # Check if Airflow is installed
    if [ ! -f "$AIRFLOW_VENV/bin/airflow" ]; then
        log_warn "Airflow not installed at $AIRFLOW_VENV"
        log_info "Install with: ./orchestration/airflow/setup-airflow.sh"
        return 0
    fi

    # Export environment
    export AIRFLOW_HOME="$AIRFLOW_HOME"

    # Check if already running
    if pgrep -f "airflow scheduler" > /dev/null && pgrep -f "airflow webserver" > /dev/null; then
        log_info "Airflow already running"
        return 0
    fi

    # Start scheduler
    if ! pgrep -f "airflow scheduler" > /dev/null; then
        log_info "Starting Airflow scheduler..."
        nohup "$AIRFLOW_VENV/bin/airflow" scheduler > "$AIRFLOW_HOME/logs/scheduler.log" 2>&1 &
        sleep 2
    fi

    # Start webserver (Airflow 3.x uses api-server instead for REST API)
    if ! pgrep -f "airflow webserver" > /dev/null; then
        log_info "Starting Airflow webserver on port $AIRFLOW_PORT..."
        nohup "$AIRFLOW_VENV/bin/airflow" webserver --port "$AIRFLOW_PORT" > "$AIRFLOW_HOME/logs/webserver.log" 2>&1 &
        sleep 3
    fi

    # Validate
    if curl -s "http://localhost:$AIRFLOW_PORT/health" > /dev/null 2>&1; then
        log_success "Airflow running at http://$MASTER_HOST:$AIRFLOW_PORT"
    else
        log_warn "Airflow may still be starting..."
        echo "  Check logs: tail -f $AIRFLOW_HOME/logs/*.log"
    fi

    return 0
}

# =============================================================================
# Summary
# =============================================================================

print_summary() {
    echo ""
    echo -e "${BOLD}======================================================================"
    echo "  Cluster Status"
    echo "======================================================================${NC}"
    echo ""

    # NFS
    if mountpoint -q "$NFS_MOUNT_POINT" 2>/dev/null; then
        echo -e "  NFS Storage:     ${GREEN}✓${NC} $STORAGE_PATH"
    else
        echo -e "  NFS Storage:     ${RED}✗${NC} Not mounted"
    fi

    # Spark Master
    if pgrep -f "spark.*Master" > /dev/null; then
        echo -e "  Spark Master:    ${GREEN}✓${NC} $SPARK_MASTER_URL"
    else
        echo -e "  Spark Master:    ${RED}✗${NC} Not running"
    fi

    # Spark Workers
    local worker_count=$(curl -s "http://$MASTER_HOST:$SPARK_WEBUI_PORT/json" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('workers',[])))" 2>/dev/null || echo "0")
    if [ "$worker_count" -gt 0 ]; then
        echo -e "  Spark Workers:   ${GREEN}✓${NC} $worker_count connected"
    else
        echo -e "  Spark Workers:   ${YELLOW}○${NC} None connected"
    fi

    # Airflow
    if pgrep -f "airflow scheduler" > /dev/null; then
        echo -e "  Airflow:         ${GREEN}✓${NC} http://$MASTER_HOST:$AIRFLOW_PORT"
    else
        echo -e "  Airflow:         ${YELLOW}○${NC} Not running"
    fi

    echo ""
    echo "Web UIs:"
    echo "  Spark Master:  http://$MASTER_HOST:$SPARK_WEBUI_PORT"
    echo "  Airflow:       http://$MASTER_HOST:$AIRFLOW_PORT"
    echo ""
    echo "Next steps:"
    echo "  # Run pipeline test"
    echo "  ./scripts/test/test_full_pipeline_spark.sh --profile dev"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    print_header

    # Step 1: Validate NFS
    validate_nfs || {
        log_error "NFS validation failed"
        exit 1
    }

    if [ "$SKIP_SPARK" = true ]; then
        log_info "Skipping Spark (--skip-spark)"
        print_summary
        exit 0
    fi

    # Step 2: Start Spark
    if [ "$WORKERS_ONLY" = true ]; then
        start_spark_workers
    else
        start_spark_master || exit 1
        start_spark_workers
    fi

    # Step 3: Validate Spark cluster
    validate_spark_cluster

    # Step 4: Start Airflow
    start_airflow

    # Summary
    print_summary
}

main "$@"
