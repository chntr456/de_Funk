# Worker Cluster Setup Guide (Terminal Commands)

Complete bash commands for setting up a distributed Ray cluster.

---

## 1. Network Configuration

### Head Node (192.168.1.100)

```bash
# Set static IP
sudo tee /etc/netplan/01-netcfg.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses: [192.168.1.100/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
EOF

sudo netplan apply

# Set hostname
sudo hostnamectl set-hostname head-node

# Add hosts entries
sudo tee -a /etc/hosts << 'EOF'
192.168.1.100   head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
EOF
```

### Worker Nodes (run on each worker, change IP accordingly)

```bash
# Worker 1: 192.168.1.101
sudo tee /etc/netplan/01-netcfg.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      addresses: [192.168.1.101/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
EOF

sudo netplan apply
sudo hostnamectl set-hostname worker-1

sudo tee -a /etc/hosts << 'EOF'
192.168.1.100   head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
EOF
```

### SSH Keys (from head node)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/de_funk_cluster -N ""
ssh-copy-id -i ~/.ssh/de_funk_cluster.pub de_funk@worker-1
ssh-copy-id -i ~/.ssh/de_funk_cluster.pub de_funk@worker-2
ssh-copy-id -i ~/.ssh/de_funk_cluster.pub de_funk@worker-3

# Test connectivity
ssh worker-1 "hostname"
ssh worker-2 "hostname"
ssh worker-3 "hostname"
```

---

## 2. NFS Shared Storage

### Head Node (NFS Server)

```bash
# Install NFS server
sudo apt update && sudo apt install -y nfs-kernel-server

# Create storage directories
mkdir -p ~/storage/{bronze,silver,forecasts}

# Configure exports
sudo tee -a /etc/exports << 'EOF'
/home/de_funk/storage 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
EOF

# Start NFS
sudo exportfs -ra
sudo systemctl enable --now nfs-kernel-server

# Verify
sudo exportfs -v
```

### Worker Nodes (NFS Client)

```bash
# Install NFS client
sudo apt update && sudo apt install -y nfs-common

# Create mount point
sudo mkdir -p /shared/storage

# Test mount
sudo mount -t nfs head-node:/home/de_funk/storage /shared/storage
ls /shared/storage  # Should show: bronze/ silver/ forecasts/

# Add to fstab for boot mount
echo "head-node:/home/de_funk/storage /shared/storage nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab

# Verify
mount | grep nfs
```

---

## 3. Software Installation

### All Nodes (head + workers)

```bash
# Install Python
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

# Create venv
python3.11 -m venv ~/venv
source ~/venv/bin/activate

# Install Ray
pip install 'ray[default]>=2.9.0'

# Install minimal dependencies for workers
pip install pandas numpy pyarrow deltalake statsmodels prophet
```

### Head Node Only

```bash
source ~/venv/bin/activate

# Clone repo (or copy from existing)
cd ~ && git clone https://github.com/your-org/de_funk.git
cd de_funk

# Install all dependencies
pip install -r requirements.txt
pip install apscheduler
```

---

## 4. Ray Cluster Startup

### Start Head Node

```bash
source ~/venv/bin/activate

# Start head (foreground for testing)
ray start --head --port=6379 --dashboard-host=0.0.0.0 --dashboard-port=8265

# Verify
ray status
```

### Start Workers (run on each worker)

```bash
source ~/venv/bin/activate

# Connect to head
ray start --address='192.168.1.100:6379' --num-cpus=4

# Verify connection
ray status
```

### Verify Full Cluster (from head)

```bash
ray status

# Expected output:
# ======== Cluster Resources ========
# CPUs: 20.0/20.0
# Memory: 80.0GB/80.0GB
# Nodes: 4
```

---

## 5. Systemd Services

### Head Node - Ray Service

```bash
sudo tee /etc/systemd/system/ray-head.service << 'EOF'
[Unit]
Description=Ray Head Node
After=network.target

[Service]
Type=simple
User=de_funk
WorkingDirectory=/home/de_funk
Environment="PATH=/home/de_funk/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/de_funk/venv/bin/ray start --head --port=6379 --dashboard-host=0.0.0.0 --block
ExecStop=/home/de_funk/venv/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ray-head
sudo systemctl start ray-head
sudo systemctl status ray-head
```

### Head Node - Scheduler Service

```bash
sudo tee /etc/systemd/system/de_funk-scheduler.service << 'EOF'
[Unit]
Description=de_Funk Pipeline Scheduler
After=network.target ray-head.service
Requires=ray-head.service

[Service]
Type=simple
User=de_funk
WorkingDirectory=/home/de_funk/de_funk
Environment="PATH=/home/de_funk/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/de_funk/venv/bin/python -m orchestration.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable de_funk-scheduler
sudo systemctl start de_funk-scheduler
sudo systemctl status de_funk-scheduler
```

### Worker Nodes - Ray Worker Service

```bash
sudo tee /etc/systemd/system/ray-worker.service << 'EOF'
[Unit]
Description=Ray Worker Node
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=de_funk
WorkingDirectory=/home/de_funk
Environment="PATH=/home/de_funk/venv/bin:/usr/local/bin:/usr/bin"
ExecStartPre=/bin/sleep 10
ExecStart=/home/de_funk/venv/bin/ray start --address='192.168.1.100:6379' --block
ExecStop=/home/de_funk/venv/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ray-worker
sudo systemctl start ray-worker
sudo systemctl status ray-worker
```

---

## 6. Verification Tests

### Test 1: Cluster Resources

```bash
python3 << 'EOF'
import ray
ray.init(address='auto')
print("Resources:", ray.cluster_resources())
print("Nodes:", len(ray.nodes()))
ray.shutdown()
EOF
```

### Test 2: Distributed Task Execution

```bash
python3 << 'EOF'
import ray
import socket

ray.init(address='auto')

@ray.remote
def get_hostname(i):
    return f"Task {i} on {socket.gethostname()}"

futures = [get_hostname.remote(i) for i in range(12)]
for result in ray.get(futures):
    print(result)

ray.shutdown()
EOF
```

### Test 3: NFS Write/Read

```bash
python3 << 'EOF'
from pathlib import Path

storage = Path('/shared/storage')
test_file = storage / 'cluster_test.txt'

# Write test
test_file.write_text('Cluster NFS working!')
print(f"Written: {test_file.read_text()}")

# Cleanup
test_file.unlink()
print("NFS test passed!")
EOF
```

### Test 4: Full Pipeline Test

```bash
cd ~/de_funk
source ~/venv/bin/activate
python -m scripts.test.test_pipeline_orchestration --quick
```

### Test 5: Distributed Forecast

```bash
python3 << 'EOF'
import ray
ray.init(address='auto')

from orchestration.distributed.tasks import forecast_ticker

tickers = ['AAPL', 'MSFT']
storage = '/shared/storage'

futures = [
    forecast_ticker.remote(ticker=t, models=['arima'], horizon=30, storage_path=storage)
    for t in tickers
]

for result in ray.get(futures):
    print(f"{result['ticker']}: {result['status']}")

ray.shutdown()
EOF
```

---

## 7. Firewall Configuration

```bash
# If UFW is enabled
sudo ufw allow 6379/tcp      # Ray GCS
sudo ufw allow 8265/tcp      # Ray Dashboard
sudo ufw allow 10001:10999/tcp  # Ray worker ports
sudo ufw allow 2049/tcp      # NFS
sudo ufw reload
sudo ufw status
```

---

## 8. Troubleshooting Commands

### Check Services

```bash
# Head node
sudo systemctl status ray-head
sudo journalctl -u ray-head -f

# Workers
sudo systemctl status ray-worker
sudo journalctl -u ray-worker -f

# Scheduler
sudo systemctl status de_funk-scheduler
sudo journalctl -u de_funk-scheduler -f
```

### Check Ray Status

```bash
ray status
ray memory
```

### Check Network

```bash
# Test Ray port from worker
nc -zv 192.168.1.100 6379

# Test NFS mount
showmount -e head-node
mount | grep nfs
```

### Restart Everything

```bash
# On head
sudo systemctl restart ray-head
sudo systemctl restart de_funk-scheduler

# On workers
sudo systemctl restart ray-worker

# Verify
ray status
```

### Kill Stuck Ray

```bash
ray stop --force
pkill -9 -f raylet
pkill -9 -f gcs_server
```

---

## 9. Quick Reference

```bash
# === HEAD NODE ===
# Start services
sudo systemctl start ray-head
sudo systemctl start de_funk-scheduler

# Stop services
sudo systemctl stop de_funk-scheduler
sudo systemctl stop ray-head

# Logs
sudo journalctl -u ray-head -f
sudo journalctl -u de_funk-scheduler -f

# Manual start
ray start --head --port=6379 --dashboard-host=0.0.0.0

# === WORKER NODES ===
# Start/stop
sudo systemctl start ray-worker
sudo systemctl stop ray-worker

# Manual start
ray start --address='192.168.1.100:6379'

# === MONITORING ===
# Dashboard: http://192.168.1.100:8265
# Status: ray status
# Memory: ray memory
```

---

## 10. cluster.yaml Configuration

```bash
cat ~/de_funk/configs/cluster.yaml

# Edit for your setup:
# - Update IPs
# - Set storage.type to "nfs"
# - Configure scheduler jobs
```
