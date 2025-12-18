#!/bin/bash
#
# de_Funk Worker Bootstrap Script
#
# Run this on a fresh Ubuntu server to set it up as a de_Funk worker.
#
# Usage (from worker machine):
#   curl -sSL http://head-node:8080/setup-worker.sh | bash -s -- --worker-id 1
#
# Or download and run:
#   wget http://head-node:8080/setup-worker.sh
#   chmod +x setup-worker.sh
#   ./setup-worker.sh --worker-id 1
#
# Options:
#   --worker-id N     Worker number (1, 2, 3, etc.) - sets IP to 192.168.1.10N
#   --head-ip IP      Head node IP (default: 192.168.1.100)
#   --skip-network    Skip network configuration
#   --skip-nfs        Skip NFS setup
#

set -e

# =============================================================================
# Configuration
# =============================================================================

HEAD_IP="192.168.1.100"
WORKER_ID=""
SKIP_NETWORK=false
SKIP_NFS=false
DE_FUNK_USER="de_funk"
VENV_PATH="/home/$DE_FUNK_USER/venv"
NFS_MOUNT="/shared/storage"

# Parse arguments
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
    echo "ERROR: --worker-id is required"
    echo "Usage: $0 --worker-id N"
    exit 1
fi

WORKER_IP="192.168.1.10$WORKER_ID"
HOSTNAME="worker-$WORKER_ID"

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
# Pre-flight checks
# =============================================================================

echo ""
echo "=============================================="
echo "  de_Funk Worker Setup"
echo "=============================================="
echo ""
echo "  Worker ID:    $WORKER_ID"
echo "  Worker IP:    $WORKER_IP"
echo "  Hostname:     $HOSTNAME"
echo "  Head Node:    $HEAD_IP"
echo ""

# Check if running as root
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
    netcat \
    software-properties-common

# =============================================================================
# Step 2: Python 3.11
# =============================================================================

log "Installing Python 3.11..."
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev

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

    # Backup existing config
    cp /etc/netplan/*.yaml /etc/netplan/backup.yaml 2>/dev/null || true

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
          via: 192.168.1.1
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
# Step 5: Hostname
# =============================================================================

log "Setting hostname to $HOSTNAME..."
hostnamectl set-hostname $HOSTNAME

# Update /etc/hosts
cat >> /etc/hosts << EOF

# de_Funk cluster
$HEAD_IP      head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
192.168.1.104   worker-4    w4
EOF

# =============================================================================
# Step 6: Python Environment
# =============================================================================

log "Setting up Python virtual environment..."

sudo -u $DE_FUNK_USER bash << EOF
python3.11 -m venv $VENV_PATH
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

    # Add to fstab
    if ! grep -q "$NFS_MOUNT" /etc/fstab; then
        echo "head-node:/home/$DE_FUNK_USER/storage $NFS_MOUNT nfs defaults,_netdev,nofail 0 0" >> /etc/fstab
    fi

    # Try to mount (may fail if head not ready)
    mount -a 2>/dev/null || warn "NFS mount failed - will retry on boot"
else
    warn "Skipping NFS setup"
fi

# =============================================================================
# Step 8: Ray Worker Service
# =============================================================================

log "Creating Ray worker systemd service..."

cat > /etc/systemd/system/ray-worker.service << EOF
[Unit]
Description=Ray Worker Node
After=network-online.target nfs-client.target
Wants=network-online.target

[Service]
Type=simple
User=$DE_FUNK_USER
Group=$DE_FUNK_USER
WorkingDirectory=/home/$DE_FUNK_USER
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStartPre=/bin/bash -c 'until nc -z head-node 6379; do echo "Waiting for head-node..."; sleep 5; done'
ExecStart=$VENV_PATH/bin/ray start --address='head-node:6379' --block
ExecStop=$VENV_PATH/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ray-worker

log "Ray worker service created"

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
    ls /shared/storage 2>/dev/null || echo "  (empty or not accessible)"
else
    echo "NFS: Not mounted"
fi
echo ""

if nc -z head-node 6379 2>/dev/null; then
    echo "Head node: Reachable"
else
    echo "Head node: Not reachable"
fi
echo ""

systemctl is-active ray-worker && echo "Ray worker: Running" || echo "Ray worker: Not running"
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
echo "  Next steps:"
echo ""
echo "  1. Reboot to apply all changes:"
echo "     sudo reboot"
echo ""
echo "  2. After reboot, verify setup:"
echo "     /home/$DE_FUNK_USER/verify.sh"
echo ""
echo "  3. Start Ray worker (if not auto-started):"
echo "     sudo systemctl start ray-worker"
echo ""
echo "  4. Check Ray status from head node:"
echo "     ray status"
echo ""
