#!/bin/bash
#
# Spark + Airflow Cluster Initialization
#
# Single script to initialize the entire cluster from the head node.
# Handles cleanup, NFS setup, worker deployment, and service startup.
#
# Usage:
#   ./init-cluster.sh              # Full cluster init
#   ./init-cluster.sh --head-only  # Only setup head node
#   ./init-cluster.sh --workers-only  # Only setup workers
#   ./init-cluster.sh --cleanup    # Just cleanup, no start
#   ./init-cluster.sh --status     # Show cluster status
#
# This script is idempotent - safe to run multiple times.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# =============================================================================
# Configuration
# =============================================================================

# Network
HEAD_IP="192.168.1.212"
HEAD_HOSTNAME="bigbark"

# Workers: hostname:ip:cores:memory_gb
WORKERS=(
    "bark-1:192.168.1.207:10:8"
    "bark-2:192.168.1.202:10:8"
    "bark-3:192.168.1.203:10:8"
)

# User
DE_FUNK_USER="ms_trixie"
SPARK_VENV="/home/$DE_FUNK_USER/venv"
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"

# Storage
LOCAL_PROJECT="/home/$DE_FUNK_USER/PycharmProjects/de_Funk"
LOCAL_STORAGE="/data/de_funk"
NFS_ROOT="/shared"

# Ports
SPARK_MASTER_PORT=7077
SPARK_UI_PORT=8080
AIRFLOW_PORT=8081
WORKER_UI_START_PORT=8082

# Flags
SETUP_HEAD=true
SETUP_WORKERS=true
START_SERVICES=true
CLEANUP_FIRST=true

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --head-only)
            SETUP_WORKERS=false
            shift
            ;;
        --workers-only)
            SETUP_HEAD=false
            shift
            ;;
        --cleanup)
            START_SERVICES=false
            shift
            ;;
        --no-cleanup)
            CLEANUP_FIRST=false
            shift
            ;;
        --status)
            # Jump to status check
            source "$SCRIPT_DIR/../spark-cluster/spark-env.sh" 2>/dev/null || true
            exec "$SCRIPT_DIR/../spark-cluster/status.sh"
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --head-only      Only setup head node"
            echo "  --workers-only   Only setup workers (head must be ready)"
            echo "  --cleanup        Cleanup only, don't start services"
            echo "  --no-cleanup     Skip cleanup step"
            echo "  --status         Show cluster status and exit"
            echo "  -h, --help       Show this help"
            echo ""
            echo "Workers:"
            for w in "${WORKERS[@]}"; do
                IFS=':' read -r name ip cores mem <<< "$w"
                echo "  $name ($ip) - $cores cores, ${mem}GB RAM"
            done
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"
}

section() {
    echo ""
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""
}

# =============================================================================
# Cleanup Functions
# =============================================================================

cleanup_local_spark() {
    log "Cleaning up local Spark processes..."

    # Stop systemd services if they exist
    sudo systemctl stop spark-master 2>/dev/null || true
    sudo systemctl stop spark-worker 2>/dev/null || true

    # Kill any remaining Spark processes
    pkill -f "org.apache.spark.deploy.master.Master" 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.worker.Worker" 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.history.HistoryServer" 2>/dev/null || true

    # Clean PID files
    rm -f /tmp/spark-*.pid 2>/dev/null || true
    rm -f "$LOCAL_STORAGE/spark-history"/*.pid 2>/dev/null || true

    log "  ✓ Local Spark processes cleaned"
}

cleanup_local_airflow() {
    log "Cleaning up local Airflow processes..."

    # Stop systemd services
    sudo systemctl stop airflow-webserver 2>/dev/null || true
    sudo systemctl stop airflow-scheduler 2>/dev/null || true

    # Kill any remaining
    pkill -f "airflow webserver" 2>/dev/null || true
    pkill -f "airflow scheduler" 2>/dev/null || true

    # Clean PID files
    rm -f ~/airflow/*.pid 2>/dev/null || true

    log "  ✓ Local Airflow processes cleaned"
}

cleanup_worker() {
    local hostname=$1
    local ip=$2

    log "Cleaning up $hostname ($ip)..."

    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$DE_FUNK_USER@$ip" bash <<'REMOTE_CLEANUP' 2>/dev/null || warn "Could not clean $hostname"
        sudo systemctl stop spark-worker 2>/dev/null || true
        pkill -f "org.apache.spark.deploy.worker.Worker" 2>/dev/null || true
        rm -f /tmp/spark-*.pid 2>/dev/null || true
REMOTE_CLEANUP

    log "  ✓ $hostname cleaned"
}

# =============================================================================
# Setup Functions
# =============================================================================

setup_nfs_head() {
    log "Setting up NFS on head node..."

    # Install NFS server if needed
    if ! command -v exportfs &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq nfs-kernel-server
    fi

    # Create NFS root
    sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk"

    # Create storage directory
    sudo mkdir -p "$LOCAL_STORAGE"
    sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$LOCAL_STORAGE"

    # Setup bind mounts (not symlinks - they don't work over NFS)
    if ! mountpoint -q "$NFS_ROOT/storage" 2>/dev/null; then
        sudo mount --bind "$LOCAL_STORAGE" "$NFS_ROOT/storage"
    fi

    if ! mountpoint -q "$NFS_ROOT/de_Funk" 2>/dev/null; then
        sudo mount --bind "$LOCAL_PROJECT" "$NFS_ROOT/de_Funk"
    fi

    # Add to fstab if not present
    if ! grep -q "$NFS_ROOT/storage" /etc/fstab 2>/dev/null; then
        echo "$LOCAL_STORAGE $NFS_ROOT/storage none bind 0 0" | sudo tee -a /etc/fstab
    fi
    if ! grep -q "$NFS_ROOT/de_Funk" /etc/fstab 2>/dev/null; then
        echo "$LOCAL_PROJECT $NFS_ROOT/de_Funk none bind 0 0" | sudo tee -a /etc/fstab
    fi

    # Configure NFS exports
    if ! grep -q "^$NFS_ROOT " /etc/exports 2>/dev/null; then
        echo "$NFS_ROOT 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash,crossmnt)" | sudo tee -a /etc/exports
    fi

    # Restart NFS
    sudo exportfs -ra
    sudo systemctl restart nfs-kernel-server

    log "  ✓ NFS configured: $NFS_ROOT"
}

setup_storage_dirs() {
    log "Creating storage directories..."

    mkdir -p "$LOCAL_STORAGE/bronze"
    mkdir -p "$LOCAL_STORAGE/silver"
    mkdir -p "$LOCAL_STORAGE/spark-history"
    mkdir -p "$LOCAL_STORAGE/checkpoints"
    mkdir -p "$LOCAL_STORAGE/logs"

    log "  ✓ Storage directories ready"
}

setup_python_env() {
    log "Setting up Python environment..."

    # Main venv for Spark (Python 3.13 OK)
    if [ ! -d "$SPARK_VENV" ]; then
        python3 -m venv "$SPARK_VENV"
    fi

    source "$SPARK_VENV/bin/activate"
    pip install --upgrade pip setuptools wheel -q
    pip install -q \
        'pyspark==4.0.1' \
        'delta-spark==4.0.0' \
        'deltalake>=0.14.0' \
        pandas numpy pyarrow requests python-dotenv

    log "  ✓ Spark venv ready: $SPARK_VENV"
}

deploy_worker() {
    local hostname=$1
    local ip=$2
    local cores=$3
    local memory=$4
    local worker_idx=$5

    log "Deploying to $hostname ($ip)..."

    # Copy setup script and run remotely
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$DE_FUNK_USER@$ip" bash <<REMOTE_SETUP
set -e

echo "  Setting up $hostname..."

# Install packages
sudo apt-get update -qq
sudo apt-get install -y -qq openjdk-17-jdk python3-pip python3-venv nfs-common

# Set hostname
sudo hostnamectl set-hostname "$hostname"

# Mount NFS
sudo mkdir -p /shared
if ! mountpoint -q /shared 2>/dev/null; then
    sudo mount -t nfs $HEAD_IP:$NFS_ROOT /shared
fi

# Add to fstab
if ! grep -q "/shared" /etc/fstab 2>/dev/null; then
    echo "$HEAD_IP:$NFS_ROOT /shared nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab
fi

# Create venv
if [ ! -d "$SPARK_VENV" ]; then
    python3 -m venv "$SPARK_VENV"
fi

source "$SPARK_VENV/bin/activate"
pip install --upgrade pip -q
pip install -q 'pyspark==4.0.1' 'delta-spark==4.0.0' 'deltalake>=0.14.0' pandas numpy pyarrow

# Get JAVA_HOME
JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=\$($SPARK_VENV/bin/python -c "import pyspark; print(pyspark.__path__[0])")

# Create systemd service
sudo tee /etc/systemd/system/spark-worker.service > /dev/null <<EOF
[Unit]
Description=Apache Spark Worker
After=network.target

[Service]
Type=simple
User=$DE_FUNK_USER
Environment="JAVA_HOME=\$JAVA_HOME"
Environment="SPARK_HOME=\$SPARK_HOME"
ExecStart=\$JAVA_HOME/bin/java -cp "\$SPARK_HOME/jars/*" -Xmx${memory}g org.apache.spark.deploy.worker.Worker --cores $cores --memory ${memory}g --webui-port $((WORKER_UI_START_PORT + worker_idx)) spark://$HEAD_IP:$SPARK_MASTER_PORT
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spark-worker
sudo systemctl start spark-worker

echo "  ✓ $hostname ready"
REMOTE_SETUP

    log "  ✓ $hostname deployed and started"
}

start_spark_master() {
    log "Starting Spark Master..."

    source "$SPARK_VENV/bin/activate"

    JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
    SPARK_HOME=$($SPARK_VENV/bin/python -c "import pyspark; print(pyspark.__path__[0])")

    # Create log directory
    mkdir -p "$LOCAL_STORAGE/logs"

    # Start master
    nohup "$JAVA_HOME/bin/java" \
        -cp "$SPARK_HOME/jars/*" \
        -Xmx1g \
        org.apache.spark.deploy.master.Master \
        --host $HEAD_IP \
        --port $SPARK_MASTER_PORT \
        --webui-port $SPARK_UI_PORT \
        > "$LOCAL_STORAGE/logs/spark-master.out" 2>&1 &

    MASTER_PID=$!
    echo $MASTER_PID > "$LOCAL_STORAGE/logs/spark-master.pid"

    sleep 3

    if ps -p $MASTER_PID > /dev/null; then
        log "  ✓ Spark Master started (PID: $MASTER_PID)"
        log "    URL: spark://$HEAD_IP:$SPARK_MASTER_PORT"
        log "    UI:  http://$HEAD_IP:$SPARK_UI_PORT"
    else
        error "Failed to start Spark Master"
        cat "$LOCAL_STORAGE/logs/spark-master.out"
        exit 1
    fi
}

start_airflow() {
    log "Starting Airflow..."

    if [ ! -d "$AIRFLOW_VENV" ]; then
        warn "Airflow venv not found. Run setup-airflow.sh first."
        return
    fi

    source "$AIRFLOW_VENV/bin/activate"
    export AIRFLOW_HOME="/home/$DE_FUNK_USER/airflow"

    # Start scheduler
    airflow scheduler &
    echo $! > "$AIRFLOW_HOME/scheduler.pid"

    # Start webserver
    airflow webserver --port $AIRFLOW_PORT &
    echo $! > "$AIRFLOW_HOME/webserver.pid"

    sleep 2

    log "  ✓ Airflow started"
    log "    UI: http://$HEAD_IP:$AIRFLOW_PORT (admin/admin123)"
}

# =============================================================================
# Main
# =============================================================================

section "Spark + Airflow Cluster Initialization"

echo "Configuration:"
echo "  Head: $HEAD_HOSTNAME ($HEAD_IP)"
echo "  Workers: ${#WORKERS[@]}"
echo "  Project: $LOCAL_PROJECT"
echo "  Storage: $LOCAL_STORAGE"
echo "  NFS: $NFS_ROOT"
echo ""

# Step 1: Cleanup
if [ "$CLEANUP_FIRST" = true ]; then
    section "Step 1: Cleanup"

    cleanup_local_spark
    cleanup_local_airflow

    if [ "$SETUP_WORKERS" = true ]; then
        for w in "${WORKERS[@]}"; do
            IFS=':' read -r hostname ip cores mem <<< "$w"
            cleanup_worker "$hostname" "$ip" &
        done
        wait
    fi

    log "Cleanup complete"
fi

# Step 2: Setup Head
if [ "$SETUP_HEAD" = true ]; then
    section "Step 2: Head Node Setup"

    setup_nfs_head
    setup_storage_dirs
    setup_python_env

    log "Head node ready"
fi

# Step 3: Deploy Workers
if [ "$SETUP_WORKERS" = true ]; then
    section "Step 3: Worker Deployment"

    # Wait for NFS to be ready
    sleep 2

    idx=0
    for w in "${WORKERS[@]}"; do
        IFS=':' read -r hostname ip cores mem <<< "$w"
        deploy_worker "$hostname" "$ip" "$cores" "$mem" "$idx" &
        ((idx++))
    done
    wait

    log "All workers deployed"
fi

# Step 4: Start Services
if [ "$START_SERVICES" = true ]; then
    section "Step 4: Starting Services"

    if [ "$SETUP_HEAD" = true ]; then
        start_spark_master
        start_airflow
    fi

    log "Services started"
fi

# Summary
section "Cluster Ready"

echo "Services:"
echo "  Spark Master: spark://$HEAD_IP:$SPARK_MASTER_PORT"
echo "  Spark UI:     http://$HEAD_IP:$SPARK_UI_PORT"
echo "  Airflow UI:   http://$HEAD_IP:$AIRFLOW_PORT"
echo ""
echo "Workers:"
for w in "${WORKERS[@]}"; do
    IFS=':' read -r hostname ip cores mem <<< "$w"
    echo "  $hostname ($ip) - $cores cores, ${mem}GB"
done
echo ""
echo "Storage:"
echo "  Local:  $LOCAL_STORAGE"
echo "  NFS:    $NFS_ROOT (mounted on workers as /shared)"
echo ""
echo "Commands:"
echo "  Status:  $SCRIPT_DIR/init-cluster.sh --status"
echo "  Submit:  $PROJECT_ROOT/scripts/spark-cluster/submit-job.sh <script.py>"
echo "  Stop:    $SCRIPT_DIR/stop-cluster.sh"
echo ""
