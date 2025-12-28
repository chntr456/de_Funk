#!/bin/bash
#
# Stop Spark + Airflow Cluster
#
# Gracefully stops all cluster services across head and workers.
# Reads configuration from configs/cluster.yaml
#
# Usage:
#   ./stop-cluster.sh           # Stop everything
#   ./stop-cluster.sh --spark   # Only stop Spark
#   ./stop-cluster.sh --airflow # Only stop Airflow
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$REPO_ROOT/configs/cluster.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Parse YAML config using Python
read_config() {
    python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
$1
"
}

# Configuration from cluster.yaml
HEAD_IP=$(read_config "print(cfg['cluster']['head']['ip'])")
DE_FUNK_USER=$(read_config "print(cfg['cluster']['head']['user'])")
LOCAL_STORAGE="/data/de_funk"

# Build workers array: "name:ip"
WORKERS=()
while IFS= read -r line; do
    WORKERS+=("$line")
done < <(read_config "
for w in cfg['cluster']['workers']:
    print(f\"{w['name']}:{w['ip']}\")
")

STOP_SPARK=true
STOP_AIRFLOW=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --spark)
            STOP_AIRFLOW=false
            shift
            ;;
        --airflow)
            STOP_SPARK=false
            shift
            ;;
        *)
            shift
            ;;
    esac
done

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# Stop workers
if [ "$STOP_SPARK" = true ]; then
    log "Stopping Spark workers..."

    for w in "${WORKERS[@]}"; do
        IFS=':' read -r hostname ip <<< "$w"
        ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" \
            "sudo systemctl stop spark-worker 2>/dev/null; pkill -f 'spark.*Worker' 2>/dev/null" &
    done
    wait

    log "Stopping Spark Master..."
    sudo systemctl stop spark-master 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.master.Master" 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.worker.Worker" 2>/dev/null || true

    log "  ✓ Spark stopped"
fi

if [ "$STOP_AIRFLOW" = true ]; then
    log "Stopping Airflow..."

    # Airflow 3.x uses api-server instead of webserver
    sudo systemctl stop airflow-apiserver 2>/dev/null || true
    sudo systemctl stop airflow-webserver 2>/dev/null || true  # Legacy cleanup
    sudo systemctl stop airflow-scheduler 2>/dev/null || true
    pkill -f "airflow api-server" 2>/dev/null || true
    pkill -f "airflow webserver" 2>/dev/null || true  # Legacy cleanup
    pkill -f "airflow scheduler" 2>/dev/null || true
    pkill -f "airflow standalone" 2>/dev/null || true

    log "  ✓ Airflow stopped"
fi

log "Cluster stopped"
