#!/bin/bash
#
# Spark + Airflow Cluster - Full Setup
#
# Sequential setup with connection validation. Run from head node.
#
# Usage:
#   ./init-cluster.sh
#

set -e

# =============================================================================
# Configuration
# =============================================================================

HEAD_IP="192.168.1.212"
DE_FUNK_USER="ms_trixie"

WORKERS=(
    "bark-1:192.168.1.207:10:8"
    "bark-2:192.168.1.202:10:8"
    "bark-3:192.168.1.203:10:8"
)

SPARK_VENV="/home/$DE_FUNK_USER/venv"
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"
LOCAL_PROJECT="/home/$DE_FUNK_USER/PycharmProjects/de_Funk"
LOCAL_STORAGE="/data/de_funk"
NFS_ROOT="/shared"

SPARK_MASTER_PORT=7077
SPARK_UI_PORT=8080
AIRFLOW_PORT=8081

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
sudo systemctl stop spark-master 2>/dev/null || true
pkill -9 -f "org.apache.spark.deploy" 2>/dev/null || true
rm -f /tmp/spark-*.pid 2>/dev/null || true

log "Stopping local Airflow..."
sudo systemctl stop airflow-webserver airflow-scheduler 2>/dev/null || true
pkill -9 -f "airflow" 2>/dev/null || true
rm -f ~/airflow/*.pid 2>/dev/null || true

for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Stopping Spark on $name..."
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "sudo systemctl stop spark-worker 2>/dev/null; pkill -9 -f 'org.apache.spark' 2>/dev/null; exit 0" || true
done

sleep 2
log "  ✓ All processes stopped"

# =============================================================================
# Step 2: Setup NFS on Head
# =============================================================================

section "Step 2: NFS Setup (Head Node)"

log "Installing NFS server..."
sudo apt-get update
sudo apt-get install -y nfs-kernel-server nfs-common

log "Creating directories..."
sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk"
sudo mkdir -p "$LOCAL_STORAGE"/{bronze,silver,logs,checkpoints}
sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$LOCAL_STORAGE"

log "Setting up bind mounts..."
sudo umount "$NFS_ROOT/storage" 2>/dev/null || true
sudo umount "$NFS_ROOT/de_Funk" 2>/dev/null || true
sudo mount --bind "$LOCAL_STORAGE" "$NFS_ROOT/storage"
sudo mount --bind "$LOCAL_PROJECT" "$NFS_ROOT/de_Funk"

log "Configuring NFS exports..."
sudo tee /etc/exports > /dev/null <<EOF
$NFS_ROOT 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash,crossmnt)
EOF

sudo exportfs -ra
sudo systemctl restart nfs-kernel-server

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
pip install --upgrade pip
pip install 'pyspark==4.0.1' 'delta-spark==4.0.0' 'deltalake>=0.14.0' pandas numpy pyarrow requests python-dotenv

JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
SPARK_HOME=$(python -c "import pyspark; print(pyspark.__path__[0])")

log "  ✓ JAVA_HOME: $JAVA_HOME"
log "  ✓ SPARK_HOME: $SPARK_HOME"

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
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk python3-pip python3-venv nfs-common

echo "  Mounting NFS..."
sudo mkdir -p /shared
sudo umount /shared 2>/dev/null || true
sudo mount -t nfs $HEAD_IP:$NFS_ROOT /shared
echo "  NFS mounted"
ls -la /shared/

# Persist mount
grep -q "/shared" /etc/fstab || echo "$HEAD_IP:$NFS_ROOT /shared nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab

echo "  Setting up Python..."
if [ ! -d ~/venv ]; then
    python3 -m venv ~/venv
fi
source ~/venv/bin/activate
pip install --upgrade pip
pip install 'pyspark==4.0.1' 'delta-spark==4.0.0' pandas numpy pyarrow

JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=\$(python -c "import pyspark; print(pyspark.__path__[0])")
echo "  JAVA_HOME=\$JAVA_HOME"
echo "  SPARK_HOME=\$SPARK_HOME"

echo "  Creating systemd service..."
# Create a wrapper script that handles classpath glob expansion
# Note: \$ escaping preserves $ for the worker's heredoc processing
cat > ~/start-spark-worker.sh << 'STARTWRAPPER'
#!/bin/bash
source ~/venv/bin/activate
JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=\$(python -c "import pyspark; print(pyspark.__path__[0])")
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

log "Starting Spark Master..."

source "$SPARK_VENV/bin/activate"
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
SPARK_HOME=$(python -c "import pyspark; print(pyspark.__path__[0])")

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

# =============================================================================
# Step 6: Start Workers
# =============================================================================

section "Step 6: Start Spark Workers"

for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Starting worker on $name..."
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "sudo systemctl start spark-worker" || warn "Failed to start $name"
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

    log "Starting Airflow webserver..."
    nohup airflow webserver --port $AIRFLOW_PORT > "$AIRFLOW_HOME/logs/webserver.log" 2>&1 &
    echo $! > "$AIRFLOW_HOME/webserver.pid"

    sleep 2
    log "  ✓ Airflow running at http://$HEAD_IP:$AIRFLOW_PORT"
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
