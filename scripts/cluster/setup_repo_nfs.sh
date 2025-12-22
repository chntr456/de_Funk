#!/bin/bash
# Setup NFS share for de_Funk repo code
# Run this on the head node (bigbark) to share repo with Ray workers
#
# Usage:
#   ./setup_repo_nfs.sh          # Show instructions
#   ./setup_repo_nfs.sh install  # Install NFS server and configure
#   ./setup_repo_nfs.sh mount    # Run on workers to mount the share

set -e

# Configuration
REPO_PATH="/home/ms_trixie/PycharmProjects/de_Funk"
MOUNT_PATH="/shared/de_Funk"
HEAD_NODE="192.168.1.212"
NETWORK="192.168.1.0/24"
WORKERS=("192.168.1.207" "192.168.1.202" "192.168.1.203")

show_help() {
    echo "=============================================="
    echo "  NFS Setup for de_Funk Repo Sharing"
    echo "=============================================="
    echo ""
    echo "This script shares the repo code with Ray workers via NFS."
    echo ""
    echo "Architecture:"
    echo "  Head node (bigbark): ${HEAD_NODE}"
    echo "    - Exports: ${REPO_PATH}"
    echo "  Workers: ${WORKERS[*]}"
    echo "    - Mount at: ${MOUNT_PATH}"
    echo ""
    echo "Usage:"
    echo "  1. On HEAD NODE (bigbark):"
    echo "     sudo ./setup_repo_nfs.sh install"
    echo ""
    echo "  2. On EACH WORKER:"
    echo "     sudo ./setup_repo_nfs.sh mount"
    echo ""
    echo "  3. Update cluster config to use shared path"
    echo ""
}

install_server() {
    echo "Installing NFS server on head node..."

    # Install NFS server
    if ! command -v exportfs &> /dev/null; then
        echo "Installing nfs-kernel-server..."
        sudo apt-get update
        sudo apt-get install -y nfs-kernel-server
    else
        echo "NFS server already installed"
    fi

    # Check if export already exists
    if grep -q "${REPO_PATH}" /etc/exports 2>/dev/null; then
        echo "Export already configured in /etc/exports"
    else
        echo "Adding export to /etc/exports..."
        echo "${REPO_PATH} ${NETWORK}(ro,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports
    fi

    # Export and restart
    echo "Exporting filesystems..."
    sudo exportfs -ra
    sudo systemctl restart nfs-kernel-server

    echo ""
    echo "✓ NFS server configured!"
    echo ""
    echo "Verify with: showmount -e localhost"
    echo ""
    echo "Next: Run 'sudo ./setup_repo_nfs.sh mount' on each worker"
}

mount_client() {
    echo "Setting up NFS client mount..."

    # Install NFS client
    if ! command -v mount.nfs &> /dev/null; then
        echo "Installing nfs-common..."
        sudo apt-get update
        sudo apt-get install -y nfs-common
    else
        echo "NFS client already installed"
    fi

    # Create mount point
    if [ ! -d "${MOUNT_PATH}" ]; then
        echo "Creating mount point: ${MOUNT_PATH}"
        sudo mkdir -p "${MOUNT_PATH}"
    fi

    # Check if already mounted
    if mountpoint -q "${MOUNT_PATH}"; then
        echo "Already mounted at ${MOUNT_PATH}"
    else
        echo "Mounting ${HEAD_NODE}:${REPO_PATH} -> ${MOUNT_PATH}"
        sudo mount -t nfs "${HEAD_NODE}:${REPO_PATH}" "${MOUNT_PATH}"
    fi

    # Add to fstab for persistence
    if ! grep -q "${MOUNT_PATH}" /etc/fstab 2>/dev/null; then
        echo "Adding to /etc/fstab for auto-mount..."
        echo "${HEAD_NODE}:${REPO_PATH} ${MOUNT_PATH} nfs ro,auto,nofail,noatime 0 0" | sudo tee -a /etc/fstab
    fi

    echo ""
    echo "✓ NFS mount configured!"
    echo ""
    echo "Verify with: ls ${MOUNT_PATH}"
}

mount_all_workers() {
    echo "Mounting on all workers via SSH..."
    for worker in "${WORKERS[@]}"; do
        echo ""
        echo "--- Worker: ${worker} ---"
        ssh "${worker}" "sudo mkdir -p ${MOUNT_PATH} && sudo mount -t nfs ${HEAD_NODE}:${REPO_PATH} ${MOUNT_PATH} && echo '✓ Mounted'"
    done
}

case "${1:-}" in
    install)
        install_server
        ;;
    mount)
        mount_client
        ;;
    mount-all)
        mount_all_workers
        ;;
    *)
        show_help
        ;;
esac
