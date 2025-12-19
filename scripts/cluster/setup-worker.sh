#!/bin/bash
#
# de_Funk Worker Bootstrap Script (YAML-driven)
#
# Reads cluster configuration from configs/cluster.yaml
#
# Usage (from worker machine):
#   curl -sSL http://192.168.1.212:8080/setup-worker.sh | bash -s -- --worker-id 1
#
# Options:
#   --worker-id N     Worker index (0, 1, 2 = first, second, third in yaml)
#   --head-ip IP      Override head node IP (default: from yaml or 192.168.1.212)
#   --skip-network    Skip network configuration
#   --skip-nfs        Skip NFS setup
#

set -e

# =============================================================================
# Configuration (matches your cluster.yaml)
# =============================================================================

# Head node (from cluster.yaml: ray.cluster.head.host)
HEAD_IP="192.168.1.212"
HEAD_PORT="6379"

# Workers (from cluster.yaml: ray.cluster.workers)
# Format: "IP:CPUS:MEMORY_GB"
WORKERS=(
    "192.168.1.207:11:10"   # bark_1
    "192.168.1.202:11:10"   # bark_2
    "192.168.1.203:11:10"   # bark_3
)

# Worker hostnames
WORKER_NAMES=(
    "bark-1"
    "bark-2"
    "bark-3"
)

# Settings
DE_FUNK_USER="ms_trixie"
VENV_PATH="/home/$DE_FUNK_USER/venv"
NFS_MOUNT="/shared/storage"
# Head node paths (PyCharm project folder)
HEAD_PROJECT_PATH="/home/ms_trixie/PycharmProjects/de_Funk"
HEAD_STORAGE_PATH="/data/de_funk"

# =============================================================================
# Parse Arguments
# =============================================================================

WORKER_ID=""
SKIP_NETWORK=false
SKIP_NFS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --worker-id)
            WORKER_ID="$2"
            shift 2
            ;;
        --head-ip)
            HEAD_IP="$2"
            shift 2
            ;;
        --skip-network)
            SKIP_NETWORK=true
            shift
            ;;
        --skip-nfs)
            SKIP_NFS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$WORKER_ID" ]; then
    echo "ERROR: --worker-id is required (0, 1, or 2)"
    echo "Usage: $0 --worker-id N"
    echo ""
    echo "Workers from cluster.yaml:"
    for i in "${!WORKERS[@]}"; do
        IFS=':' read -r ip cpus mem <<< "${WORKERS[$i]}"
        echo "  $i: ${WORKER_NAMES[$i]} ($ip) - ${cpus} CPUs, ${mem}GB RAM"
    done
    exit 1
fi

# Get worker config
IFS=':' read -r WORKER_IP WORKER_CPUS WORKER_MEM <<< "${WORKERS[$WORKER_ID]}"
HOSTNAME="${WORKER_NAMES[$WORKER_ID]}"

if [ -z "$WORKER_IP" ]; then
    echo "ERROR: Invalid worker-id: $WORKER_ID"
    exit 1
fi

# =============================================================================
# Colors
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =============================================================================
# Pre-flight
# =============================================================================

echo ""
echo "=============================================="
echo "  de_Funk Worker Setup"
echo "=============================================="
echo ""
echo "  Worker ID:    $WORKER_ID"
echo "  Hostname:     $HOSTNAME"
echo "  Worker IP:    $WORKER_IP"
echo "  CPUs:         $WORKER_CPUS"
echo "  Memory:       ${WORKER_MEM}GB"
echo "  Head Node:    $HEAD_IP:$HEAD_PORT"
echo ""

if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo $0 $*"
fi

# =============================================================================
# Step 1: System Update
# =============================================================================

log "Updating system packages..."
apt update && apt upgrade -y

log "Installing required packages..."
apt install -y \
    build-essential \
    git \
    curl \
    wget \
    vim \
    htop \
    net-tools \
    nfs-common \
    openssh-server \
    netcat-openbsd \
    software-properties-common

# =============================================================================
# Step 2: Python 3.13 (must match head node)
# =============================================================================

log "Installing Python 3.13..."
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.13 python3.13-venv python3.13-dev

# =============================================================================
# Step 3: Create de_funk user
# =============================================================================

if id "$DE_FUNK_USER" &>/dev/null; then
    log "User $DE_FUNK_USER already exists"
else
    log "Creating user $DE_FUNK_USER..."
    useradd -m -s /bin/bash $DE_FUNK_USER
    echo "$DE_FUNK_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DE_FUNK_USER
fi

# =============================================================================
# Step 4: Network Configuration
# =============================================================================

if [ "$SKIP_NETWORK" = false ]; then
    log "Configuring network..."

    # Detect network interface
    IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -v lo | head -1)
    log "Detected interface: $IFACE"

    # Get gateway (assume .1 on same subnet)
    GATEWAY=$(echo "$WORKER_IP" | sed 's/\.[0-9]*$/.1/')

    # Create netplan config
    cat > /etc/netplan/01-netcfg.yaml << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    $IFACE:
      dhcp4: no
      addresses:
        - $WORKER_IP/24
      routes:
        - to: default
          via: $GATEWAY
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
EOF

    netplan apply
    log "Network configured: $WORKER_IP"
else
    warn "Skipping network configuration"
fi

# =============================================================================
# Step 5: Hostname and Hosts
# =============================================================================

log "Setting hostname to $HOSTNAME..."
hostnamectl set-hostname $HOSTNAME

# Build hosts file from cluster config
cat >> /etc/hosts << EOF

# de_Funk cluster (from cluster.yaml)
$HEAD_IP      head-node   head   bigbark
EOF

for i in "${!WORKERS[@]}"; do
    IFS=':' read -r ip _ _ <<< "${WORKERS[$i]}"
    echo "$ip      ${WORKER_NAMES[$i]}" >> /etc/hosts
done

# =============================================================================
# Step 6: Python Environment
# =============================================================================

log "Setting up Python virtual environment..."

sudo -u $DE_FUNK_USER bash << EOF
python3.13 -m venv $VENV_PATH
source $VENV_PATH/bin/activate
pip install --upgrade pip setuptools wheel
pip install 'ray[default]>=2.9.0' pandas numpy pyarrow deltalake statsmodels requests
EOF

log "Python environment ready"

# =============================================================================
# Step 7: NFS Mount
# =============================================================================

if [ "$SKIP_NFS" = false ]; then
    log "Setting up NFS mount..."

    mkdir -p $NFS_MOUNT
    chown $DE_FUNK_USER:$DE_FUNK_USER $NFS_MOUNT

    # Add to fstab - mount from head node's dedicated storage
    if ! grep -q "$NFS_MOUNT" /etc/fstab; then
        echo "head-node:$HEAD_STORAGE_PATH $NFS_MOUNT nfs defaults,_netdev,nofail 0 0" >> /etc/fstab
    fi

    mount -a 2>/dev/null || warn "NFS mount failed - will retry on boot"
else
    warn "Skipping NFS setup"
fi

# =============================================================================
# Step 8: Ray Worker Service
# =============================================================================

log "Creating Ray worker systemd service..."

# Calculate memory in bytes (leave 2GB for system)
WORKER_MEM_BYTES=$(( ($WORKER_MEM - 2) * 1024 * 1024 * 1024 ))

cat > /etc/systemd/system/ray-worker.service << EOF
[Unit]
Description=Ray Worker Node ($HOSTNAME)
After=network-online.target nfs-client.target
Wants=network-online.target

[Service]
Type=simple
User=$DE_FUNK_USER
Group=$DE_FUNK_USER
WorkingDirectory=/home/$DE_FUNK_USER
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStartPre=/bin/bash -c 'until nc -z head-node $HEAD_PORT; do echo "Waiting for head-node..."; sleep 5; done'
ExecStart=$VENV_PATH/bin/ray start --address='head-node:$HEAD_PORT' --num-cpus=$WORKER_CPUS --memory=$WORKER_MEM_BYTES --block
ExecStop=$VENV_PATH/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ray-worker

log "Ray worker service created (CPUs: $WORKER_CPUS, Memory: ${WORKER_MEM}GB)"

# =============================================================================
# Step 9: Performance Tuning
# =============================================================================

log "Applying performance tuning..."

cat >> /etc/security/limits.conf << EOF
$DE_FUNK_USER soft nofile 65535
$DE_FUNK_USER hard nofile 65535
EOF

cat >> /etc/sysctl.conf << EOF
# de_Funk performance
net.core.somaxconn = 65535
vm.swappiness = 10
EOF

sysctl -p

# =============================================================================
# Step 10: Verification Script
# =============================================================================

log "Creating verification script..."

cat > /home/$DE_FUNK_USER/verify.sh << 'VERIFY_EOF'
#!/bin/bash
echo "=== Worker Verification ==="
echo "Hostname: $(hostname)"
echo "IP: $(hostname -I | awk '{print $1}')"
echo ""

source ~/venv/bin/activate
echo "Python: $(python --version)"
python -c "import ray; print(f'Ray: {ray.__version__}')"
echo ""

if mount | grep -q nfs; then
    echo "NFS: Mounted"
    ls /shared/storage 2>/dev/null || echo "  (empty)"
else
    echo "NFS: Not mounted"
fi
echo ""

if nc -z head-node 6379 2>/dev/null; then
    echo "Head node: Reachable"
else
    echo "Head node: Not reachable (may not be running)"
fi
echo ""

systemctl is-active ray-worker && echo "Ray service: Running" || echo "Ray service: Not running"
VERIFY_EOF

chmod +x /home/$DE_FUNK_USER/verify.sh
chown $DE_FUNK_USER:$DE_FUNK_USER /home/$DE_FUNK_USER/verify.sh

# =============================================================================
# Done
# =============================================================================

echo ""
echo "=============================================="
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "  Hostname:  $HOSTNAME"
echo "  IP:        $WORKER_IP"
echo "  CPUs:      $WORKER_CPUS"
echo "  Memory:    ${WORKER_MEM}GB"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Reboot:"
echo "     sudo reboot"
echo ""
echo "  2. Verify setup:"
echo "     /home/$DE_FUNK_USER/verify.sh"
echo ""
echo "  3. Check from head node:"
echo "     ray status"
echo ""
