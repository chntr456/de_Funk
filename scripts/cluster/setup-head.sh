#!/bin/bash
#
# de_Funk Head Node Setup Script
#
# Run this on the HEAD NODE (bigbark) to set up storage and NFS.
#
# Usage:
#   sudo ./scripts/cluster/setup-head.sh
#
# This script:
#   1. Creates dedicated 500GB storage LV (if not exists)
#   2. Sets up NFS server
#   3. Creates storage directories
#   4. Sets up Ray head service
#

set -e

# =============================================================================
# Parse Arguments
# =============================================================================

SKIP_STORAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
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
# Configuration (matches cluster.yaml)
# =============================================================================

HEAD_IP="192.168.1.212"
HEAD_PORT="6379"
DASHBOARD_PORT="8265"

# User settings
DE_FUNK_USER="ms_trixie"
PROJECT_PATH="/home/$DE_FUNK_USER/PycharmProjects/de_Funk"

# Storage settings
STORAGE_LV_SIZE="300G"
STORAGE_VG="ubuntu-vg"
STORAGE_LV_NAME="storage-lv"
STORAGE_MOUNT="/data/de_funk"

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
echo "  de_Funk Head Node Setup"
echo "=============================================="
echo ""
echo "  Host:         $(hostname) ($HEAD_IP)"
echo "  User:         $DE_FUNK_USER"
echo "  Project:      $PROJECT_PATH"
echo "  Storage:      $STORAGE_MOUNT ($STORAGE_LV_SIZE)"
echo ""

if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo $0"
fi

# =============================================================================
# Step 1-3: Storage Setup (LVM)
# =============================================================================

if [ "$SKIP_STORAGE" = false ]; then
    log "Checking LVM volume group..."

    VG_FREE=$(vgs --noheadings -o vg_free --units g $STORAGE_VG 2>/dev/null | tr -d ' ')
    log "Available space in $STORAGE_VG: $VG_FREE"

    if lvs $STORAGE_VG/$STORAGE_LV_NAME &>/dev/null; then
        log "Storage LV already exists"
    else
        log "Creating $STORAGE_LV_SIZE logical volume..."
        lvcreate -L $STORAGE_LV_SIZE -n $STORAGE_LV_NAME $STORAGE_VG

        log "Formatting as ext4..."
        mkfs.ext4 /dev/$STORAGE_VG/$STORAGE_LV_NAME
    fi

    log "Setting up mount point..."

    mkdir -p $STORAGE_MOUNT

    # Add to fstab if not present
    if ! grep -q "$STORAGE_MOUNT" /etc/fstab; then
        echo "/dev/$STORAGE_VG/$STORAGE_LV_NAME $STORAGE_MOUNT ext4 defaults 0 2" >> /etc/fstab
        log "Added to /etc/fstab"
    fi

    # Mount
    mount -a
    log "Mounted at $STORAGE_MOUNT"

    # Set ownership
    chown -R $DE_FUNK_USER:$DE_FUNK_USER $STORAGE_MOUNT
else
    warn "Skipping storage setup (--skip-storage)"
    # Just ensure mount point exists
    mkdir -p $STORAGE_MOUNT
fi

# =============================================================================
# Step 4: Create Storage Structure
# =============================================================================

log "Creating storage directories..."

sudo -u $DE_FUNK_USER bash << EOF
mkdir -p $STORAGE_MOUNT/{bronze,silver,forecasts,duckdb}
EOF

log "Storage structure created"

# =============================================================================
# Step 5: Symlink from Project
# =============================================================================

log "Creating symlink from project..."

STORAGE_LINK="$PROJECT_PATH/storage"

if [ -L "$STORAGE_LINK" ]; then
    log "Symlink already exists"
elif [ -d "$STORAGE_LINK" ]; then
    warn "storage/ is a directory - backing up and replacing with symlink"
    mv "$STORAGE_LINK" "${STORAGE_LINK}.backup.$(date +%s)"
    sudo -u $DE_FUNK_USER ln -s $STORAGE_MOUNT "$STORAGE_LINK"
else
    sudo -u $DE_FUNK_USER ln -s $STORAGE_MOUNT "$STORAGE_LINK"
fi

log "Symlink: $STORAGE_LINK -> $STORAGE_MOUNT"

# =============================================================================
# Step 6: Install NFS Server
# =============================================================================

log "Setting up NFS server..."

apt install -y nfs-kernel-server

# Configure exports
cat > /etc/exports << EOF
# de_Funk cluster storage (read-write for data)
$STORAGE_MOUNT 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)

# de_Funk repo code (read-only for Silver builds on workers)
$PROJECT_PATH 192.168.1.0/24(ro,sync,no_subtree_check,no_root_squash)
EOF

exportfs -ra
systemctl enable nfs-kernel-server
systemctl restart nfs-kernel-server

log "NFS server configured"

# =============================================================================
# Step 7: Python 3.13 Environment
# =============================================================================

log "Installing Python 3.13..."
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.13 python3.13-venv python3.13-dev

VENV_PATH="/home/$DE_FUNK_USER/venv"

if [ ! -d "$VENV_PATH" ]; then
    log "Creating Python virtual environment..."
    sudo -u $DE_FUNK_USER python3.13 -m venv $VENV_PATH
    sudo -u $DE_FUNK_USER bash -c "source $VENV_PATH/bin/activate && pip install --upgrade pip setuptools wheel && pip install 'ray[default]>=2.9.0' pandas numpy pyarrow deltalake statsmodels requests pyspark"
else
    log "Virtual environment already exists at $VENV_PATH"
fi

# =============================================================================
# Step 8: Ray Head Service
# =============================================================================

log "Creating Ray head systemd service..."

cat > /etc/systemd/system/ray-head.service << EOF
[Unit]
Description=Ray Head Node (bigbark)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DE_FUNK_USER
Group=$DE_FUNK_USER
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStart=$VENV_PATH/bin/ray start --head --port=$HEAD_PORT --dashboard-host=0.0.0.0 --dashboard-port=$DASHBOARD_PORT --num-cpus=12 --block
ExecStop=$VENV_PATH/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ray-head

log "Ray head service created (not started - start manually or reboot)"

# =============================================================================
# Step 9: Firewall
# =============================================================================

if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    log "Configuring firewall..."
    ufw allow from 192.168.1.0/24 to any port 6379   # Ray
    ufw allow from 192.168.1.0/24 to any port 8265   # Dashboard
    ufw allow from 192.168.1.0/24 to any port 2049   # NFS
    ufw allow from 192.168.1.0/24 to any port 8080   # Setup server
    ufw reload
fi

# =============================================================================
# Done
# =============================================================================

echo ""
echo "=============================================="
echo -e "  ${GREEN}Head Node Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "  Storage:"
echo "    Mount:    $STORAGE_MOUNT"
echo "    Symlink:  $PROJECT_PATH/storage -> $STORAGE_MOUNT"
echo "    Size:     $(df -h $STORAGE_MOUNT | awk 'NR==2 {print $2}')"
echo ""
echo "  NFS Export:"
echo "    $(exportfs -v | grep de_funk)"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Start Ray head:"
echo "     sudo systemctl start ray-head"
echo "     # or manually:"
echo "     ray start --head --port=6379 --dashboard-host=0.0.0.0"
echo ""
echo "  2. Serve worker setup script:"
echo "     cd $PROJECT_PATH"
echo "     ./scripts/cluster/serve-setup.sh"
echo ""
echo "  3. On each worker, run:"
echo "     curl -sSL http://$HEAD_IP:8080/setup-worker.sh | sudo bash -s -- --worker-id N"
echo ""
echo "  4. Check cluster:"
echo "     ray status"
echo ""
echo "  Dashboard: http://$HEAD_IP:$DASHBOARD_PORT"
echo ""
