#!/bin/bash
#
# de_Funk Cluster Initialization Script
#
# Run this from the HEAD NODE (bigbark) to set up the entire cluster.
# This script will:
#   1. Set up the head node (storage, NFS, Ray head)
#   2. Deploy and run setup on all workers via SSH
#
# Usage:
#   sudo ./scripts/cluster/cluster-init.sh [options]
#
# Options:
#   --head-only       Only set up head node, skip workers
#   --workers-only    Only set up workers (assumes head is ready)
#   --worker N        Set up specific worker only (0, 1, or 2)
#   --skip-storage    Skip LVM/storage setup on head
#
# Prerequisites:
#   - SSH key-based access to workers (ssh-copy-id to each worker)
#   - Workers have Ubuntu 22.04+ installed
#   - Run as root (sudo)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$(dirname "$(dirname "$SCRIPT_DIR")")"

# =============================================================================
# Configuration (matches cluster.yaml)
# =============================================================================

HEAD_IP="192.168.1.212"
HEAD_PORT="6379"

# Workers: IP:CPUS:MEMORY_GB
WORKERS=(
    "192.168.1.207:11:10"   # bark-1
    "192.168.1.202:11:10"   # bark-2
    "192.168.1.203:11:10"   # bark-3
)

WORKER_NAMES=(
    "bark-1"
    "bark-2"
    "bark-3"
)

DE_FUNK_USER="ms_trixie"

# =============================================================================
# Colors
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[*]${NC} $1"; }

# =============================================================================
# Parse Arguments
# =============================================================================

HEAD_ONLY=false
WORKERS_ONLY=false
SPECIFIC_WORKER=""
SKIP_STORAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --head-only)
            HEAD_ONLY=true
            shift
            ;;
        --workers-only)
            WORKERS_ONLY=true
            shift
            ;;
        --worker)
            SPECIFIC_WORKER="$2"
            shift 2
            ;;
        --skip-storage)
            SKIP_STORAGE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Pre-flight Checks
# =============================================================================

echo ""
echo "=============================================="
echo "  de_Funk Cluster Initialization"
echo "=============================================="
echo ""
echo "  Head Node:    $HEAD_IP"
echo "  Workers:      ${#WORKERS[@]} nodes"
echo "  Project:      $PROJECT_PATH"
echo ""

if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo $0 $*"
fi

# =============================================================================
# Step 1: Set Up Head Node
# =============================================================================

setup_head() {
    log "Setting up head node..."

    if [ "$SKIP_STORAGE" = true ]; then
        bash "$SCRIPT_DIR/setup-head.sh" --skip-storage 2>&1 | tee /tmp/head-setup.log
    else
        bash "$SCRIPT_DIR/setup-head.sh" 2>&1 | tee /tmp/head-setup.log
    fi

    log "Head node setup complete"

    # Clean up any existing Ray processes
    log "Cleaning up existing Ray processes..."
    sudo -u $DE_FUNK_USER bash -c "source /home/$DE_FUNK_USER/venv/bin/activate && ray stop --force" 2>/dev/null || true
    pkill -9 -f "ray::" 2>/dev/null || true
    pkill -9 -f "gcs_server" 2>/dev/null || true
    pkill -9 -f "raylet" 2>/dev/null || true
    rm -rf /tmp/ray/* 2>/dev/null || true
    sleep 2

    # Start Ray head
    log "Starting Ray head node..."
    sudo -u $DE_FUNK_USER bash -c "source /home/$DE_FUNK_USER/venv/bin/activate && ray start --head --port=$HEAD_PORT --dashboard-host=0.0.0.0 --dashboard-port=8265 --num-cpus=12"

    log "Ray head started"
}

# =============================================================================
# Step 2: Set Up Workers
# =============================================================================

setup_worker() {
    local worker_id=$1
    IFS=':' read -r worker_ip worker_cpus worker_mem <<< "${WORKERS[$worker_id]}"
    local worker_name="${WORKER_NAMES[$worker_id]}"

    info "Setting up worker $worker_id: $worker_name ($worker_ip)"

    # Check SSH connectivity
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes root@$worker_ip "echo 'SSH OK'" 2>/dev/null; then
        warn "Cannot SSH to $worker_ip as root. Trying $DE_FUNK_USER..."
        if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $DE_FUNK_USER@$worker_ip "echo 'SSH OK'" 2>/dev/null; then
            error "Cannot SSH to $worker_ip. Please set up SSH keys first:
  ssh-copy-id root@$worker_ip
  # or
  ssh-copy-id $DE_FUNK_USER@$worker_ip"
        fi
        SSH_USER=$DE_FUNK_USER
        SSH_PREFIX="sudo"
    else
        SSH_USER="root"
        SSH_PREFIX=""
    fi

    log "Copying setup script to $worker_name..."
    scp "$SCRIPT_DIR/setup-worker.sh" $SSH_USER@$worker_ip:/tmp/

    log "Running setup on $worker_name (this may take 10-15 minutes)..."
    ssh $SSH_USER@$worker_ip "$SSH_PREFIX bash /tmp/setup-worker.sh --worker-id $worker_id" 2>&1 | tee /tmp/worker-$worker_id-setup.log

    log "Worker $worker_name setup complete"

    # Clean up any existing Ray processes on worker
    log "Cleaning up existing Ray processes on $worker_name..."
    ssh $SSH_USER@$worker_ip "$SSH_PREFIX systemctl stop ray-worker" 2>/dev/null || true
    ssh $SSH_USER@$worker_ip "$SSH_PREFIX pkill -9 -f 'ray::' 2>/dev/null; pkill -9 -f 'raylet' 2>/dev/null; rm -rf /tmp/ray/* 2>/dev/null" || true
    sleep 2

    # Start worker service
    log "Starting Ray worker on $worker_name..."
    ssh $SSH_USER@$worker_ip "$SSH_PREFIX systemctl start ray-worker"

    # Wait a moment then check status
    sleep 5
    if ssh $SSH_USER@$worker_ip "$SSH_PREFIX systemctl is-active ray-worker" 2>/dev/null | grep -q "active"; then
        log "Ray worker on $worker_name is running"
    else
        warn "Ray worker on $worker_name may not be running. Check logs with:
  ssh $SSH_USER@$worker_ip 'journalctl -u ray-worker -n 50'"
    fi
}

setup_all_workers() {
    log "Setting up all ${#WORKERS[@]} workers..."

    for i in "${!WORKERS[@]}"; do
        setup_worker $i
    done

    log "All workers set up"
}

# =============================================================================
# Main
# =============================================================================

if [ "$WORKERS_ONLY" = true ]; then
    if [ -n "$SPECIFIC_WORKER" ]; then
        setup_worker "$SPECIFIC_WORKER"
    else
        setup_all_workers
    fi
elif [ "$HEAD_ONLY" = true ]; then
    setup_head
else
    setup_head

    # Give head node time to fully start
    log "Waiting for Ray head to be ready..."
    sleep 10

    if [ -n "$SPECIFIC_WORKER" ]; then
        setup_worker "$SPECIFIC_WORKER"
    else
        setup_all_workers
    fi
fi

# =============================================================================
# Verification
# =============================================================================

echo ""
echo "=============================================="
echo -e "  ${GREEN}Cluster Setup Complete!${NC}"
echo "=============================================="
echo ""

log "Checking cluster status..."
sudo -u $DE_FUNK_USER bash -c "source /home/$DE_FUNK_USER/venv/bin/activate && ray status"

echo ""
echo "  Dashboard:    http://$HEAD_IP:8265"
echo ""
echo "  Quick verification:"
echo "    ray status"
echo ""
echo "  Test cluster:"
echo "    python -c \"import ray; ray.init(); print(ray.cluster_resources())\""
echo ""
