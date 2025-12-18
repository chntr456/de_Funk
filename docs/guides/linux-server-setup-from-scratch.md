# Linux Server Setup from Scratch

Complete terminal commands for setting up Ubuntu Server for de_Funk workers.

---

## Part 1: Fresh Ubuntu Server Installation

### Download and Install Ubuntu Server

```bash
# On your main PC, download Ubuntu Server ISO
wget https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso

# Create bootable USB (replace /dev/sdX with your USB device)
sudo dd if=ubuntu-22.04.3-live-server-amd64.iso of=/dev/sdX bs=4M status=progress
```

### First Boot - Initial Setup

```bash
# After installing Ubuntu Server, SSH into the machine
# (Or connect keyboard/monitor directly)

# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    build-essential \
    git \
    curl \
    wget \
    vim \
    htop \
    net-tools \
    nfs-common \
    openssh-server

# Enable SSH
sudo systemctl enable ssh
sudo systemctl start ssh
```

---

## Part 2: Create de_funk User

```bash
# Create user
sudo useradd -m -s /bin/bash de_funk

# Set password
sudo passwd de_funk
# Enter password when prompted

# Add to sudo group
sudo usermod -aG sudo de_funk

# Switch to de_funk user
sudo su - de_funk

# Verify
whoami  # Should output: de_funk
pwd     # Should output: /home/de_funk
```

---

## Part 3: Network Configuration

### Check Network Interface Name

```bash
ip link show
# Note interface name (e.g., eth0, enp0s3, ens18)
```

### Configure Static IP (Netplan)

```bash
# Backup existing config
sudo cp /etc/netplan/*.yaml /etc/netplan/backup.yaml

# Create new config (adjust interface name and IPs)
sudo tee /etc/netplan/01-netcfg.yaml << 'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:  # Change to your interface name
      dhcp4: no
      addresses:
        - 192.168.1.101/24  # Change for each worker
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
EOF

# Apply configuration
sudo netplan apply

# Verify
ip addr show
ping -c 3 8.8.8.8
```

### Set Hostname

```bash
# Set hostname (worker-1, worker-2, etc.)
sudo hostnamectl set-hostname worker-1

# Verify
hostname
```

### Configure /etc/hosts

```bash
sudo tee -a /etc/hosts << 'EOF'
# de_Funk cluster
192.168.1.100   head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
EOF

# Verify
cat /etc/hosts
ping -c 1 head-node
```

---

## Part 4: Install Python 3.11

```bash
# Add deadsnakes PPA for Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Verify
python3.11 --version
```

### Create Virtual Environment

```bash
# As de_funk user
su - de_funk

# Create venv
python3.11 -m venv ~/venv

# Activate
source ~/venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Verify
which python
python --version
```

---

## Part 5: Install Ray and Dependencies

```bash
# Activate venv
source ~/venv/bin/activate

# Install Ray with all extras
pip install 'ray[default]>=2.9.0'

# Install de_funk worker dependencies
pip install \
    pandas \
    numpy \
    pyarrow \
    deltalake \
    statsmodels \
    prophet \
    requests

# Verify Ray installation
python -c "import ray; print(f'Ray version: {ray.__version__}')"
```

---

## Part 6: NFS Client Setup

```bash
# Install NFS client (already done in Part 1)
sudo apt install -y nfs-common

# Create mount point
sudo mkdir -p /shared/storage
sudo chown de_funk:de_funk /shared/storage

# Test mount (head-node must be running NFS server)
sudo mount -t nfs head-node:/home/de_funk/storage /shared/storage

# Verify mount
df -h | grep nfs
ls /shared/storage

# Add to fstab for automatic mounting at boot
echo "head-node:/home/de_funk/storage /shared/storage nfs defaults,_netdev,nofail 0 0" | sudo tee -a /etc/fstab

# Test fstab entry
sudo umount /shared/storage
sudo mount -a

# Verify
mount | grep nfs
```

---

## Part 7: SSH Key Setup

### On Worker (generate key)

```bash
su - de_funk

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Display public key (copy this)
cat ~/.ssh/id_ed25519.pub
```

### On Head Node (authorize worker)

```bash
# Add worker's public key to authorized_keys
echo "PASTE_WORKER_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
```

### Test SSH Connection

```bash
# From worker
ssh de_funk@head-node "echo 'SSH connection successful!'"
```

---

## Part 8: Ray Worker Service Setup

```bash
# Create systemd service file
sudo tee /etc/systemd/system/ray-worker.service << 'EOF'
[Unit]
Description=Ray Worker Node
After=network-online.target nfs-client.target
Wants=network-online.target
Requires=network.target

[Service]
Type=simple
User=de_funk
Group=de_funk
WorkingDirectory=/home/de_funk
Environment="PATH=/home/de_funk/venv/bin:/usr/local/bin:/usr/bin"

# Wait for head node to be ready
ExecStartPre=/bin/bash -c 'until nc -z head-node 6379; do sleep 5; done'

# Start Ray worker
ExecStart=/home/de_funk/venv/bin/ray start --address='head-node:6379' --block

# Stop Ray
ExecStop=/home/de_funk/venv/bin/ray stop

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable ray-worker

# Start service
sudo systemctl start ray-worker

# Check status
sudo systemctl status ray-worker

# View logs
sudo journalctl -u ray-worker -f
```

---

## Part 9: Firewall Configuration

```bash
# Check if UFW is active
sudo ufw status

# If active, allow necessary ports
sudo ufw allow ssh
sudo ufw allow from 192.168.1.0/24 to any port 6379   # Ray
sudo ufw allow from 192.168.1.0/24 to any port 8265   # Ray Dashboard
sudo ufw allow from 192.168.1.0/24 to any port 10001:10999  # Ray workers

# Reload
sudo ufw reload

# Verify
sudo ufw status verbose
```

---

## Part 10: Performance Tuning

```bash
# Increase file descriptor limits
sudo tee -a /etc/security/limits.conf << 'EOF'
de_funk soft nofile 65535
de_funk hard nofile 65535
EOF

# Increase system limits
sudo tee -a /etc/sysctl.conf << 'EOF'
# de_Funk performance tuning
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
vm.swappiness = 10
EOF

# Apply sysctl changes
sudo sysctl -p

# Verify
ulimit -n
```

---

## Part 11: Monitoring Setup

```bash
# Install monitoring tools
sudo apt install -y htop iotop sysstat

# Enable sysstat
sudo systemctl enable sysstat
sudo systemctl start sysstat

# Quick monitoring commands
htop                    # CPU/Memory usage
iotop                   # Disk I/O
sar -u 1 5              # CPU stats (1 sec interval, 5 times)
sar -r 1 5              # Memory stats
free -h                 # Memory summary
df -h                   # Disk usage
```

---

## Part 12: Verification Script

Create a verification script to test the worker setup:

```bash
# Create test script
tee ~/test_worker.sh << 'EOF'
#!/bin/bash
set -e

echo "=== de_Funk Worker Verification ==="
echo ""

echo "1. Checking hostname..."
hostname
echo ""

echo "2. Checking IP address..."
ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1
echo ""

echo "3. Checking Python..."
source ~/venv/bin/activate
python --version
echo ""

echo "4. Checking Ray..."
python -c "import ray; print(f'Ray {ray.__version__}')"
echo ""

echo "5. Checking NFS mount..."
if mount | grep -q nfs; then
    echo "NFS mounted: $(mount | grep nfs | awk '{print $3}')"
    ls /shared/storage
else
    echo "ERROR: NFS not mounted!"
    exit 1
fi
echo ""

echo "6. Checking head-node connectivity..."
if nc -z head-node 6379 2>/dev/null; then
    echo "Can reach head-node:6379"
else
    echo "WARNING: Cannot reach head-node:6379 (may not be running)"
fi
echo ""

echo "7. Checking Ray worker service..."
systemctl is-active ray-worker || echo "Ray worker service not running"
echo ""

echo "8. Checking system resources..."
echo "  CPUs: $(nproc)"
echo "  Memory: $(free -h | awk '/Mem:/ {print $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $4}') available"
echo ""

echo "=== All checks completed ==="
EOF

chmod +x ~/test_worker.sh

# Run verification
~/test_worker.sh
```

---

## Quick Reference: Worker Setup Checklist

```bash
# Run these commands on each new worker:

# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install packages
sudo apt install -y build-essential git curl wget vim htop net-tools nfs-common openssh-server python3.11 python3.11-venv python3.11-dev software-properties-common

# 3. Create user
sudo useradd -m -s /bin/bash de_funk
sudo passwd de_funk
sudo usermod -aG sudo de_funk

# 4. Configure network (as root)
# Edit /etc/netplan/01-netcfg.yaml with static IP
sudo netplan apply

# 5. Set hostname
sudo hostnamectl set-hostname worker-X

# 6. Add hosts entries
sudo tee -a /etc/hosts << 'EOF'
192.168.1.100   head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
EOF

# 7. Setup Python (as de_funk)
su - de_funk
python3.11 -m venv ~/venv
source ~/venv/bin/activate
pip install --upgrade pip
pip install 'ray[default]>=2.9.0' pandas numpy pyarrow deltalake statsmodels prophet requests

# 8. Setup NFS
sudo mkdir -p /shared/storage
sudo chown de_funk:de_funk /shared/storage
echo "head-node:/home/de_funk/storage /shared/storage nfs defaults,_netdev,nofail 0 0" | sudo tee -a /etc/fstab
sudo mount -a

# 9. Setup systemd service
# (Copy ray-worker.service from Part 8)
sudo systemctl daemon-reload
sudo systemctl enable --now ray-worker

# 10. Verify
~/test_worker.sh
```

---

## Troubleshooting

### Cannot reach head-node

```bash
# Check network
ping head-node
nc -zv head-node 6379

# Check /etc/hosts
cat /etc/hosts | grep head-node

# Check firewall on head
ssh head-node "sudo ufw status"
```

### NFS mount fails

```bash
# Check NFS server is running on head
ssh head-node "systemctl status nfs-kernel-server"

# Check exports
ssh head-node "sudo exportfs -v"

# Manual mount test
sudo mount -v -t nfs head-node:/home/de_funk/storage /shared/storage
```

### Ray worker won't connect

```bash
# Check Ray head is running
ssh head-node "ray status"

# Check logs
sudo journalctl -u ray-worker -n 50

# Try manual start
source ~/venv/bin/activate
ray start --address='head-node:6379' --verbose
```

### Python package errors

```bash
# Reinstall venv
rm -rf ~/venv
python3.11 -m venv ~/venv
source ~/venv/bin/activate
pip install --upgrade pip
pip install 'ray[default]>=2.9.0'
```
