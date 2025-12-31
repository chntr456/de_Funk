#!/bin/bash
#
# Spark + Airflow Cluster - Full Setup
#
# Sequential setup with connection validation. Run from head node.
# Reads configuration from configs/cluster.yaml
#
# Usage:
#   ./init-cluster.sh
#

set -e

# =============================================================================
# Configuration - Read from cluster.yaml
# =============================================================================

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

# Extract cluster configuration
HEAD_IP=$(read_config "print(cfg['cluster']['head']['ip'])")
DE_FUNK_USER=$(read_config "print(cfg['cluster']['head']['user'])")
SPARK_MASTER_PORT=$(read_config "print(cfg['spark']['master']['port'])")
SPARK_UI_PORT=$(read_config "print(cfg['spark']['master']['ui_port'])")
AIRFLOW_PORT=$(read_config "print(cfg['airflow']['port'])")

# Build workers array from config: "name:ip:cores:memory"
WORKERS=()
while IFS= read -r line; do
    WORKERS+=("$line")
done < <(read_config "
for w in cfg['cluster']['workers']:
    print(f\"{w['name']}:{w['ip']}:{w['cores']}:{w['memory_gb']}\")
")

# Derived paths
SPARK_VENV="/home/$DE_FUNK_USER/venv"
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"
LOCAL_PROJECT="/home/$DE_FUNK_USER/PycharmProjects/de_Funk"
LOCAL_STORAGE="/data/de_funk"
NFS_ROOT="/shared"

echo "Loaded configuration from: $CONFIG_FILE"
echo "  Head: $HEAD_IP (user: $DE_FUNK_USER)"
echo "  Workers: ${#WORKERS[@]}"
echo "  Spark Master: port $SPARK_MASTER_PORT, UI port $SPARK_UI_PORT"
echo "  Airflow: port $AIRFLOW_PORT"

# =============================================================================
# Helpers
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
fail() { echo -e "${RED}[$(date '+%H:%M:%S')] FAIL:${NC} $1"; exit 1; }

section() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

# =============================================================================
# Step 0: Validate Connections & Setup Sudo
# =============================================================================

section "Step 0: Validating Connections & Sudo Access"

log "Checking head node..."
if [[ "$(hostname -I)" != *"$HEAD_IP"* ]]; then
    fail "This script must run on head node ($HEAD_IP)"
fi
log "  ✓ Running on head node"

# Cache sudo credentials locally
log "Caching sudo credentials (enter password once)..."
sudo -v || fail "Sudo access required"

# Keep sudo alive in background
(while true; do sudo -n true; sleep 50; done) &
SUDO_KEEPER=$!
trap "kill $SUDO_KEEPER 2>/dev/null" EXIT

log "  ✓ Local sudo cached"

# Check workers and setup passwordless sudo if needed
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Checking $name ($ip)..."

    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "echo ok" &>/dev/null; then
        fail "$name ($ip) not reachable via SSH. Check SSH keys."
    fi
    log "  ✓ $name SSH ok"

    # Check if passwordless sudo works
    if ! ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "sudo -n true" &>/dev/null; then
        log "  Setting up passwordless sudo on $name..."
        # Use ssh -t for interactive sudo, then set up NOPASSWD
        ssh -t "$DE_FUNK_USER@$ip" "echo '$DE_FUNK_USER ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/$DE_FUNK_USER > /dev/null"
        log "  ✓ $name passwordless sudo configured"
    else
        log "  ✓ $name sudo ok"
    fi
done

log "All nodes ready!"

# =============================================================================
# Step 1: Cleanup Everything
# =============================================================================

section "Step 1: Cleanup Existing Processes"

log "Stopping local Spark..."
pkill -9 -f "org.apache.spark.deploy" 2>/dev/null || true
rm -f /tmp/spark-*.pid 2>/dev/null || true

log "Stopping local Airflow..."
pkill -9 -f "airflow" 2>/dev/null || true
rm -f ~/airflow/*.pid 2>/dev/null || true

log "  ✓ Local processes stopped (workers will be restarted in Step 6)"

# =============================================================================
# Step 2: Setup NFS on Head
# =============================================================================

section "Step 2: NFS Setup (Head Node)"

# Check if NFS is already properly set up and working
if mountpoint -q "$NFS_ROOT/storage" 2>/dev/null && [ -d "$NFS_ROOT/storage/bronze" ]; then
    log "NFS already configured at $NFS_ROOT - skipping setup"
else
    # Only clean up mounts if they exist but aren't working
    log "Setting up NFS mounts..."

    # Check if storage directories exist (from previous setup)
    if [ -d "$LOCAL_STORAGE/bronze" ] && [ -d "$LOCAL_STORAGE/silver" ]; then
        log "Storage directories exist at $LOCAL_STORAGE - quick setup"
    else
        log "Installing NFS server..."
        sudo apt-get update
        sudo apt-get install -y nfs-kernel-server nfs-common

        log "Creating directories..."
        sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk" "$NFS_ROOT/spark"
        sudo mkdir -p "$LOCAL_STORAGE"/{bronze,silver,logs,checkpoints}
        sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$LOCAL_STORAGE"
    fi

    log "Setting up bind mounts..."
    sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk" "$NFS_ROOT/spark"
    # Only mount if not already mounted
    mountpoint -q "$NFS_ROOT/storage" || sudo mount --bind "$LOCAL_STORAGE" "$NFS_ROOT/storage"
    mountpoint -q "$NFS_ROOT/de_Funk" || sudo mount --bind "$LOCAL_PROJECT" "$NFS_ROOT/de_Funk"

    log "Configuring NFS exports..."
    sudo tee /etc/exports > /dev/null <<EOF
$NFS_ROOT 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash,crossmnt)
EOF

    sudo exportfs -ra
    sudo systemctl restart nfs-kernel-server
fi

# Ensure firewall allows NFS ports
if command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
    log "Configuring firewall for NFS..."
    sudo ufw allow from 192.168.1.0/24 to any port 111 > /dev/null 2>&1 || true    # rpcbind
    sudo ufw allow from 192.168.1.0/24 to any port 2049 > /dev/null 2>&1 || true   # nfs
    sudo ufw allow from 192.168.1.0/24 to any port 20048 > /dev/null 2>&1 || true  # mountd
    log "  ✓ Firewall configured for NFS"
fi

log "  ✓ NFS ready: $NFS_ROOT"

# =============================================================================
# Step 3: Setup Python on Head
# =============================================================================

section "Step 3: Python Environment (Head Node)"

log "Setting up Spark venv..."
if [ ! -d "$SPARK_VENV" ]; then
    python3 -m venv "$SPARK_VENV"
fi

source "$SPARK_VENV/bin/activate"
pip install -q --upgrade pip

# Core data processing
pip install -q 'pyspark==4.0.1' 'delta-spark==4.0.0' 'deltalake>=0.14.0' pandas numpy pyarrow requests python-dotenv networkx

# Machine learning libraries
pip install -q scikit-learn statsmodels pmdarima prophet xgboost lightgbm

# Deep learning (CPU versions for compatibility - use GPU versions if needed)
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -q tensorflow

JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
SPARK_HOME=$(python -c "import pyspark; print(pyspark.__path__[0])")

log "  ✓ JAVA_HOME: $JAVA_HOME"
log "  ✓ SPARK_HOME: $SPARK_HOME"

# Download and setup Spark distribution for workers
SPARK_VERSION="4.0.1"
SPARK_DIST_DIR="/home/$DE_FUNK_USER/spark-dist"
SPARK_TGZ="spark-${SPARK_VERSION}-bin-hadoop3.tgz"
SPARK_URL="https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_TGZ}"

log "Setting up Spark distribution for workers..."
if [ ! -d "$SPARK_DIST_DIR/spark-${SPARK_VERSION}-bin-hadoop3" ]; then
    log "  Downloading Spark ${SPARK_VERSION}..."
    mkdir -p "$SPARK_DIST_DIR"
    cd "$SPARK_DIST_DIR"
    if [ ! -f "$SPARK_TGZ" ]; then
        wget -q "$SPARK_URL" || curl -sLO "$SPARK_URL"
    fi
    tar xzf "$SPARK_TGZ"
    rm -f "$SPARK_TGZ"
    cd "$REPO_ROOT"
    log "  ✓ Spark distribution extracted"
else
    log "  ✓ Spark distribution already exists"
fi

# Mount Spark distribution to NFS (only if not already mounted)
# Check for duplicate mounts and fix them
SPARK_MOUNT_COUNT=$(mount | grep -c "$NFS_ROOT/spark" || echo "0")
if [ "$SPARK_MOUNT_COUNT" -gt 1 ]; then
    log "  WARNING: Multiple mounts detected for $NFS_ROOT/spark, fixing..."
    sudo umount "$NFS_ROOT/spark" 2>/dev/null || true
fi

if mountpoint -q "$NFS_ROOT/spark" 2>/dev/null && ls "$NFS_ROOT/spark/jars" >/dev/null 2>&1; then
    log "  ✓ Spark already mounted at $NFS_ROOT/spark"
else
    log "  Mounting Spark distribution to NFS..."
    sudo mkdir -p "$NFS_ROOT/spark"
    sudo mount --bind "$SPARK_DIST_DIR/spark-${SPARK_VERSION}-bin-hadoop3" "$NFS_ROOT/spark"
    log "  ✓ Spark available at /shared/spark on workers"
fi

# =============================================================================
# Step 4: Setup Each Worker (Sequential)
# =============================================================================

section "Step 4: Worker Setup"

worker_idx=0
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"

    log "Setting up $name ($ip) - $cores cores, ${mem}GB RAM..."

    if ! ssh -o ConnectTimeout=30 "$DE_FUNK_USER@$ip" bash -s "$HEAD_IP" "$NFS_ROOT" "$name" <<WORKER_SCRIPT
set -e

echo "  Installing packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq openjdk-17-jdk python3-pip python3-venv nfs-common

echo "  Mounting NFS..."
sudo mkdir -p /shared
# Check if mount is working including /shared/spark (which can go stale)
if mountpoint -q /shared && ls /shared/storage >/dev/null 2>&1 && ls /shared/spark >/dev/null 2>&1; then
    echo "  NFS already mounted and working"
else
    # Force unmount stale mount and remount fresh
    echo "  Remounting NFS (stale or missing)..."
    sudo umount -f /shared 2>/dev/null || true
    sudo umount -l /shared 2>/dev/null || true
    sleep 2
    sudo mount -t nfs -o vers=3 $HEAD_IP:$NFS_ROOT /shared
    echo "  NFS mounted"
    # Verify /shared/spark is accessible
    if ! ls /shared/spark >/dev/null 2>&1; then
        echo "  WARNING: /shared/spark still not accessible, retrying mount..."
        sudo umount -l /shared 2>/dev/null || true
        sleep 2
        sudo mount -t nfs $HEAD_IP:$NFS_ROOT /shared
    fi
fi
ls /shared/

# Persist mount
grep -q "/shared" /etc/fstab || echo "$HEAD_IP:$NFS_ROOT /shared nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab

echo "  Setting up Python..."
if [ ! -d ~/venv ]; then
    python3 -m venv ~/venv
fi
source ~/venv/bin/activate
pip install -q --upgrade pip
# Core data processing
pip install -q 'pyspark==4.0.1' 'delta-spark==4.0.0' pandas numpy pyarrow networkx

# Machine learning (for Spark UDFs)
pip install -q scikit-learn statsmodels pmdarima xgboost lightgbm

JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=\$(python -c "import pyspark; print(pyspark.__path__[0])")
echo "  JAVA_HOME=\$JAVA_HOME"
echo "  SPARK_HOME=\$SPARK_HOME"

echo "  Creating systemd service..."
# Create a wrapper script that handles classpath glob expansion
# Uses shared Spark distribution from NFS at /shared/spark
cat > ~/start-spark-worker.sh << 'STARTWRAPPER'
#!/bin/bash
source ~/venv/bin/activate
JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=/shared/spark
export SPARK_HOME
exec "\$JAVA_HOME/bin/java" -cp "\$SPARK_HOME/jars/*" -Xmx${mem}g \
    org.apache.spark.deploy.worker.Worker \
    --cores $cores --memory ${mem}g \
    spark://$HEAD_IP:$SPARK_MASTER_PORT
STARTWRAPPER
chmod +x ~/start-spark-worker.sh

# Systemd service calls the wrapper script (which handles glob expansion via bash)
printf '%s\n' \
    "[Unit]" \
    "Description=Apache Spark Worker" \
    "After=network.target" \
    "" \
    "[Service]" \
    "Type=simple" \
    "User=\$(whoami)" \
    "WorkingDirectory=/home/\$(whoami)" \
    "ExecStart=/home/\$(whoami)/start-spark-worker.sh" \
    "Restart=on-failure" \
    "RestartSec=5" \
    "" \
    "[Install]" \
    "WantedBy=multi-user.target" \
    | sudo tee /etc/systemd/system/spark-worker.service

sudo systemctl daemon-reload
sudo systemctl enable spark-worker

echo "  ✓ $name configured"
WORKER_SCRIPT
    then
        warn "Failed to setup $name - continuing with next worker"
    else
        log "  ✓ $name ready"
    fi
    ((worker_idx++)) || true  # Prevent set -e exit when idx was 0
done

# =============================================================================
# Step 5: Start Spark Master
# =============================================================================

section "Step 5: Start Spark Master"

# Ensure firewall allows Spark Master port from workers
if command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
    if ! sudo ufw status | grep -q "7077.*ALLOW.*192.168.1.0/24"; then
        log "Adding firewall rule for Spark Master port 7077..."
        sudo ufw allow from 192.168.1.0/24 to any port 7077 > /dev/null
        log "  ✓ Firewall rule added"
    fi
fi

log "Starting Spark Master..."

source "$SPARK_VENV/bin/activate"
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
# Use shared Spark distribution for consistency with workers
SPARK_HOME="$NFS_ROOT/spark"

mkdir -p "$LOCAL_STORAGE/logs"

nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx1g \
    org.apache.spark.deploy.master.Master \
    --host $HEAD_IP \
    --port $SPARK_MASTER_PORT \
    --webui-port $SPARK_UI_PORT \
    > "$LOCAL_STORAGE/logs/spark-master.out" 2>&1 &

echo $! > "$LOCAL_STORAGE/logs/spark-master.pid"

sleep 3

if curl -s "http://$HEAD_IP:$SPARK_UI_PORT" > /dev/null; then
    log "  ✓ Spark Master running at spark://$HEAD_IP:$SPARK_MASTER_PORT"
    log "  ✓ Web UI: http://$HEAD_IP:$SPARK_UI_PORT"
else
    fail "Spark Master failed to start. Check: $LOCAL_STORAGE/logs/spark-master.out"
fi

# Start History Server for viewing completed job logs
log "Starting Spark History Server..."
mkdir -p "$LOCAL_STORAGE/spark-events"

# Kill existing history server if running
pkill -f "org.apache.spark.deploy.history.HistoryServer" 2>/dev/null || true
sleep 1

nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx512m \
    -Dspark.history.fs.logDirectory="$LOCAL_STORAGE/spark-events" \
    -Dspark.history.ui.port=18080 \
    org.apache.spark.deploy.history.HistoryServer \
    > "$LOCAL_STORAGE/logs/spark-history.out" 2>&1 &

echo $! > "$LOCAL_STORAGE/logs/spark-history.pid"
sleep 2

if curl -s "http://$HEAD_IP:18080" > /dev/null; then
    log "  ✓ History Server: http://$HEAD_IP:18080"
else
    warn "History Server may not have started. Check: $LOCAL_STORAGE/logs/spark-history.out"
fi

# =============================================================================
# Step 6: Start Workers
# =============================================================================

section "Step 6: Start Spark Workers"

for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Starting worker on $name..."
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "sudo -n systemctl start spark-worker" || warn "Failed to start $name"
done

sleep 3

# Verify workers connected
log "Verifying workers..."
WORKER_COUNT=$(curl -s "http://$HEAD_IP:$SPARK_UI_PORT/json/" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")

log "  ✓ $WORKER_COUNT workers connected"

if [ "$WORKER_COUNT" -lt "${#WORKERS[@]}" ]; then
    warn "Expected ${#WORKERS[@]} workers, got $WORKER_COUNT. Some may still be connecting..."
fi

# =============================================================================
# Step 7: Start Airflow (if configured)
# =============================================================================

section "Step 7: Start Airflow"

if [ -d "$AIRFLOW_VENV" ]; then
    source "$AIRFLOW_VENV/bin/activate"
    export AIRFLOW_HOME="/home/$DE_FUNK_USER/airflow"

    log "Starting Airflow scheduler..."
    nohup airflow scheduler > "$AIRFLOW_HOME/logs/scheduler.log" 2>&1 &
    echo $! > "$AIRFLOW_HOME/scheduler.pid"

    # Airflow 3.x uses api-server instead of webserver
    log "Starting Airflow API server..."
    nohup airflow api-server --port $AIRFLOW_PORT > "$AIRFLOW_HOME/logs/apiserver.log" 2>&1 &
    echo $! > "$AIRFLOW_HOME/apiserver.pid"

    sleep 5
    log "  ✓ Airflow running at http://$HEAD_IP:$AIRFLOW_PORT"
    log "  ✓ Check password: cat $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated"
else
    warn "Airflow not installed. Run: ./orchestration/airflow/setup-airflow.sh"
fi

# =============================================================================
# Summary
# =============================================================================

section "Cluster Ready!"

echo "Services:"
echo "  Spark Master:  spark://$HEAD_IP:$SPARK_MASTER_PORT"
echo "  Spark UI:      http://$HEAD_IP:$SPARK_UI_PORT"
if [ -d "$AIRFLOW_VENV" ]; then
echo "  Airflow UI:    http://$HEAD_IP:$AIRFLOW_PORT (admin/admin123)"
fi
echo ""
echo "Workers: $WORKER_COUNT connected"
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    echo "  - $name ($ip): $cores cores, ${mem}GB"
done
echo ""
echo "Storage:"
echo "  Local:  $LOCAL_STORAGE"
echo "  NFS:    $NFS_ROOT -> /shared on workers"
echo ""
echo "Commands:"
echo "  Status:  curl -s http://$HEAD_IP:$SPARK_UI_PORT/json/ | python3 -m json.tool"
echo "  Stop:    ./scripts/cluster/stop-cluster.sh"
echo "  Submit:  ./scripts/spark-cluster/submit-job.sh <script.py>"
echo ""
