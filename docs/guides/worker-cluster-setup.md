# Worker Cluster Setup Guide

This guide covers setting up a distributed Ray cluster for de_Funk with mini-PCs or dedicated worker machines.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Network Setup](#network-setup)
4. [Shared Storage (NFS)](#shared-storage-nfs)
5. [Software Installation](#software-installation)
6. [Ray Cluster Setup](#ray-cluster-setup)
7. [Systemd Services](#systemd-services)
8. [Verification](#verification)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MAIN PC (Ray Head Node)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  Ray Head       │  │  APScheduler    │  │  DuckDB         │         │
│  │  :6379          │  │  (cron jobs)    │  │  (analytics)    │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│           │                                                             │
│           │    Submit tasks via ray.remote()                           │
└───────────│─────────────────────────────────────────────────────────────┘
            │
            │  Ray Cluster Network (GigE recommended)
            │
    ┌───────┴───────┬───────────────────┬─────────────────┐
    ▼               ▼                   ▼                 ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│ WORKER 1   │ │ WORKER 2   │ │ WORKER 3   │ │ Main PC    │
│ Ray Worker │ │ Ray Worker │ │ Ray Worker │ │ Ray Worker │
│            │ │            │ │            │ │            │
│ 4 CPU      │ │ 4 CPU      │ │ 4 CPU      │ │ 8 CPU      │
│ 16GB RAM   │ │ 16GB RAM   │ │ 16GB RAM   │ │ 32GB RAM   │
└────────────┘ └────────────┘ └────────────┘ └────────────┘
      │               │               │               │
      └───────────────┴───────────────┴───────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  SHARED STORAGE   │
                    │  (NFS Mount)      │
                    │  /shared/storage/ │
                    │  ├── bronze/      │
                    │  ├── silver/      │
                    │  └── forecasts/   │
                    └───────────────────┘
```

---

## Hardware Requirements

### Recommended Mini-PCs

| Device | CPU | RAM | Storage | Price | Notes |
|--------|-----|-----|---------|-------|-------|
| **Beelink EQ12** | Intel N100 (4c/4t) | 16GB | 500GB SSD | ~$200 | Budget, good value |
| **Minisforum UM560** | Ryzen 5 5625U (6c/12t) | 16GB | 512GB SSD | ~$350 | Better CPU |
| **Intel NUC 12** | i5-1240P (12c/16t) | 32GB | 1TB SSD | ~$500 | High performance |

### Budget Setup (3 Workers)

| Component | Qty | Cost |
|-----------|-----|------|
| Beelink EQ12 (16GB) | 3 | $600 |
| 8-port Gigabit Switch | 1 | $25 |
| CAT6 Ethernet Cables | 4 | $15 |
| Power Strip | 1 | $20 |
| **Total** | | **~$660** |

### Network Requirements

- Gigabit Ethernet (1Gbps) minimum
- All nodes on same subnet
- Static IP addresses recommended
- Ports: 6379 (Ray), 8265 (Dashboard), 2049 (NFS)

---

## Network Setup

### 1. Assign Static IPs

On each machine, edit `/etc/netplan/01-netcfg.yaml` (Ubuntu) or equivalent:

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100/24  # Head node
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

Worker IPs:
- Head node: `192.168.1.100`
- Worker 1: `192.168.1.101`
- Worker 2: `192.168.1.102`
- Worker 3: `192.168.1.103`

Apply changes:
```bash
sudo netplan apply
```

### 2. Configure Hostnames

On each machine, add to `/etc/hosts`:

```
192.168.1.100   head-node   head
192.168.1.101   worker-1    w1
192.168.1.102   worker-2    w2
192.168.1.103   worker-3    w3
```

### 3. Setup SSH Keys (Optional but Recommended)

On head node:
```bash
# Generate SSH key if not exists
ssh-keygen -t ed25519 -C "de_funk_cluster"

# Copy to workers
ssh-copy-id de_funk@worker-1
ssh-copy-id de_funk@worker-2
ssh-copy-id de_funk@worker-3
```

---

## Shared Storage (NFS)

### On Head Node (NFS Server)

```bash
# Install NFS server
sudo apt update
sudo apt install nfs-kernel-server

# Create storage directory (if not exists)
mkdir -p /home/de_funk/storage/{bronze,silver,forecasts}

# Configure exports
sudo tee -a /etc/exports << 'EOF'
/home/de_funk/storage 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
EOF

# Apply exports
sudo exportfs -ra

# Start NFS server
sudo systemctl enable nfs-kernel-server
sudo systemctl start nfs-kernel-server

# Verify
sudo exportfs -v
```

### On Worker Nodes (NFS Clients)

```bash
# Install NFS client
sudo apt update
sudo apt install nfs-common

# Create mount point
sudo mkdir -p /shared/storage

# Test mount
sudo mount -t nfs head-node:/home/de_funk/storage /shared/storage

# Verify
ls /shared/storage
# Should see: bronze/ silver/ forecasts/

# Add to fstab for automatic mounting
sudo tee -a /etc/fstab << 'EOF'
head-node:/home/de_funk/storage /shared/storage nfs defaults,_netdev 0 0
EOF

# Mount via fstab
sudo mount -a
```

---

## Software Installation

### On ALL Nodes (Head + Workers)

```bash
# Create de_funk user (if not exists)
sudo useradd -m -s /bin/bash de_funk
sudo usermod -aG sudo de_funk

# Switch to de_funk user
sudo su - de_funk

# Install Python (if needed)
sudo apt install python3.11 python3.11-venv python3-pip

# Create virtual environment
python3.11 -m venv ~/venv
source ~/venv/bin/activate

# Install Ray
pip install 'ray[default]>=2.9.0'

# Install de_funk dependencies (on workers, minimal set needed)
pip install pandas numpy pyarrow deltalake statsmodels
```

### On Head Node Only

```bash
# Clone de_funk repository
cd ~
git clone https://github.com/your-org/de_funk.git

# Install full dependencies
cd de_funk
pip install -r requirements.txt

# Install scheduler
pip install apscheduler
```

---

## Ray Cluster Setup

### Step 1: Start Head Node

On the **head node** (192.168.1.100):

```bash
# Activate environment
source ~/venv/bin/activate

# Start Ray head node
ray start --head \
    --port=6379 \
    --dashboard-host=0.0.0.0 \
    --dashboard-port=8265 \
    --num-cpus=8 \
    --block &

# Or without --block to run in background
ray start --head --port=6379 --dashboard-host=0.0.0.0
```

Verify:
```bash
ray status
# Should show resources and 1 node

# Dashboard available at:
# http://192.168.1.100:8265
```

### Step 2: Start Worker Nodes

On each **worker node**:

```bash
# Activate environment
source ~/venv/bin/activate

# Connect to head node
ray start --address='192.168.1.100:6379' --num-cpus=4

# Or with explicit resources
ray start \
    --address='192.168.1.100:6379' \
    --num-cpus=4 \
    --memory=16000000000  # 16GB in bytes
```

### Step 3: Verify Cluster

On head node:
```bash
ray status
```

Expected output:
```
======== Cluster Resources ========
CPUs: 20.0/20.0
Memory: 80.0GB/80.0GB

======== Node Status ========
Alive:
  192.168.1.100: CPU=8, Memory=32GB
  192.168.1.101: CPU=4, Memory=16GB
  192.168.1.102: CPU=4, Memory=16GB
  192.168.1.103: CPU=4, Memory=16GB
```

Or via Python:
```python
import ray
ray.init(address="auto")
print(ray.cluster_resources())
# {'CPU': 20.0, 'memory': 85899345920.0, 'node:192.168.1.100': 1.0, ...}
ray.shutdown()
```

---

## Systemd Services

### Ray Head Service (on head node)

Create `/etc/systemd/system/ray-head.service`:

```ini
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
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ray-head
sudo systemctl start ray-head
sudo systemctl status ray-head
```

### Ray Worker Service (on each worker)

Create `/etc/systemd/system/ray-worker.service`:

```ini
[Unit]
Description=Ray Worker Node
After=network.target nfs-client.target
Requires=network.target

[Service]
Type=simple
User=de_funk
WorkingDirectory=/home/de_funk
Environment="PATH=/home/de_funk/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/de_funk/venv/bin/ray start --address='192.168.1.100:6379' --block
ExecStop=/home/de_funk/venv/bin/ray stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ray-worker
sudo systemctl start ray-worker
sudo systemctl status ray-worker
```

### de_Funk Scheduler Service (on head node)

Create `/etc/systemd/system/de_funk-scheduler.service`:

```ini
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
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable de_funk-scheduler
sudo systemctl start de_funk-scheduler
sudo systemctl status de_funk-scheduler
```

---

## Verification

### 1. Test Cluster Connectivity

```bash
# On head node
cd ~/de_funk
source ~/venv/bin/activate

python -c "
import ray
ray.init(address='auto')
print('Cluster resources:', ray.cluster_resources())
print('Nodes:', ray.nodes())
ray.shutdown()
"
```

### 2. Test Distributed Task

```bash
python -c "
import ray
ray.init(address='auto')

@ray.remote
def test_task(x):
    import socket
    return f'{x} processed on {socket.gethostname()}'

# Submit 10 tasks
futures = [test_task.remote(i) for i in range(10)]
results = ray.get(futures)
for r in results:
    print(r)

ray.shutdown()
"
```

Expected output shows tasks running on different workers:
```
0 processed on head-node
1 processed on worker-1
2 processed on worker-2
3 processed on worker-3
4 processed on head-node
...
```

### 3. Test NFS Storage Access

```bash
# On a worker node
python -c "
from pathlib import Path
storage = Path('/shared/storage')
print('Bronze exists:', (storage / 'bronze').exists())
print('Silver exists:', (storage / 'silver').exists())

# Test write access
test_file = storage / 'test_write.txt'
test_file.write_text('Worker can write!')
print('Write test:', test_file.read_text())
test_file.unlink()
"
```

### 4. Run Full Pipeline Test

```bash
cd ~/de_funk
python -m scripts.test.test_pipeline_orchestration --quick
```

### 5. Run Distributed Forecast Test

```bash
python -c "
import ray
ray.init(address='auto')

from orchestration.distributed.tasks import forecast_ticker

# Test with a few tickers
tickers = ['AAPL', 'MSFT', 'GOOGL']
storage_path = '/shared/storage'  # NFS mount

futures = [
    forecast_ticker.remote(
        ticker=t,
        models=['arima'],
        horizon=30,
        storage_path=storage_path
    )
    for t in tickers
]

results = ray.get(futures)
for r in results:
    print(f\"{r['ticker']}: {r['status']}\")

ray.shutdown()
"
```

---

## Troubleshooting

### Ray Connection Issues

```bash
# Check if Ray is running on head
ray status

# Check firewall
sudo ufw status
# If active, allow Ray ports:
sudo ufw allow 6379/tcp  # Ray
sudo ufw allow 8265/tcp  # Dashboard
sudo ufw allow 10001:10999/tcp  # Worker ports

# Check from worker
nc -zv 192.168.1.100 6379
```

### NFS Mount Issues

```bash
# Check NFS server exports
showmount -e head-node

# Check mount
mount | grep nfs

# Remount
sudo umount /shared/storage
sudo mount -a

# Check NFS service
sudo systemctl status nfs-kernel-server  # on head
```

### Service Not Starting

```bash
# Check service logs
sudo journalctl -u ray-worker -f

# Check if port is in use
sudo lsof -i :6379
```

### Memory Issues

```bash
# Check available memory
free -h

# Limit Ray memory
ray start --address='192.168.1.100:6379' --memory=12000000000  # 12GB
```

---

## Quick Reference

### Start/Stop Commands

```bash
# Head node
sudo systemctl start ray-head
sudo systemctl stop ray-head
sudo systemctl restart ray-head

# Worker nodes
sudo systemctl start ray-worker
sudo systemctl stop ray-worker

# Scheduler
sudo systemctl start de_funk-scheduler
sudo systemctl stop de_funk-scheduler
```

### Manual Ray Commands

```bash
# Start head
ray start --head --port=6379 --dashboard-host=0.0.0.0

# Start worker
ray start --address='192.168.1.100:6379'

# Stop Ray
ray stop

# Check status
ray status
```

### Dashboard URLs

- Ray Dashboard: `http://192.168.1.100:8265`
- Scheduler jobs: `python -m orchestration.scheduler --list-jobs`

---

## Configuration

Update `configs/cluster.yaml` with your actual IPs and settings:

```yaml
ray:
  mode: auto  # Connect to existing cluster
  cluster:
    head:
      host: "192.168.1.100"
      port: 6379
    workers:
      - host: "192.168.1.101"
      - host: "192.168.1.102"
      - host: "192.168.1.103"

storage:
  type: nfs
  nfs:
    mount_point: "/shared/storage"
```

---

## Next Steps

1. **Monitor performance** via Ray Dashboard at `http://head-node:8265`
2. **Configure scheduled jobs** in `configs/cluster.yaml`
3. **Scale up** by adding more worker nodes
4. **Tune resources** based on workload patterns
