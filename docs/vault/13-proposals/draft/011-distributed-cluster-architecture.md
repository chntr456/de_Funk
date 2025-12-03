# Proposal: Distributed Cluster Architecture with Mini-PCs

**Status**: Draft
**Author**: Claude
**Date**: 2025-12-02
**Updated**: 2025-12-02
**Priority**: High
**Depends On**: 001-parallel-ingestion-architecture.md

---

## Summary

Extend the de_Funk data pipeline to utilize a cluster of mini-PCs as distributed workers for parallel data ingestion, model building, and forecasting. This enables horizontal scaling beyond single-machine limits and provides redundancy.

---

## Motivation

### Current Bottlenecks

| Bottleneck | Impact | Current State |
|------------|--------|---------------|
| **API Rate Limits** | 1-5 calls/sec per API key | Single key, sequential calls |
| **Single Machine** | CPU/memory bound | All processing on one host |
| **No Redundancy** | Single point of failure | Crash = restart from scratch |
| **Long Running Jobs** | 2+ hours for full OVERVIEW | Blocks other work |

### Mini-PC Cluster Benefits

| Benefit | Description |
|---------|-------------|
| **Multiple API Keys** | Each worker uses its own key = Nx throughput |
| **Parallel Processing** | Spark cluster for model building |
| **Fault Tolerance** | Worker failure doesn't crash pipeline |
| **Cost Effective** | Mini-PCs are inexpensive, low power |
| **Dedicated Workers** | Main machine free for development |

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CONTROL NODE (Main PC)                          │
│  ├── Redis (Task Queue)                                                  │
│  ├── Celery Beat (Scheduler)                                            │
│  ├── Flower (Monitoring UI)                                             │
│  └── DuckDB Analytics (Read-only)                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│   MINI-PC WORKER 1   │ │   MINI-PC WORKER 2   │ │   MINI-PC WORKER 3   │
│  ├── Celery Worker   │ │  ├── Celery Worker   │ │  ├── Celery Worker   │
│  ├── Spark Worker    │ │  ├── Spark Worker    │ │  ├── Spark Worker    │
│  ├── API Key Pool 1  │ │  ├── API Key Pool 2  │ │  ├── API Key Pool 3  │
│  └── Local Bronze    │ │  └── Local Bronze    │ │  └── Local Bronze    │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │     SHARED STORAGE (NFS)      │
                    │  ├── storage/bronze/          │
                    │  ├── storage/silver/          │
                    │  └── storage/duckdb/          │
                    └───────────────────────────────┘
```

---

## Hardware Requirements

### Mini-PC Recommendations

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| CPU | 4 cores | 8+ cores | Intel N100 or AMD Ryzen |
| RAM | 8 GB | 16-32 GB | For Spark worker memory |
| Storage | 128 GB SSD | 256+ GB NVMe | Local cache + Bronze staging |
| Network | 1 Gbps | 2.5 Gbps | For NFS traffic |
| Power | ~15W TDP | ~25W TDP | Mini-PCs are efficient |

### Example Hardware Options

| Device | CPU | RAM | Storage | Price | Notes |
|--------|-----|-----|---------|-------|-------|
| Beelink EQ12 | Intel N100 (4c/4t) | 16GB | 500GB | ~$200 | Budget option |
| Minisforum UM560 | AMD Ryzen 5 5625U | 16GB | 512GB | ~$350 | Good balance |
| Intel NUC 12 | Intel i5-1240P | 32GB | 1TB | ~$500 | High performance |
| Raspberry Pi 5 | ARM Cortex-A76 | 8GB | 128GB | ~$100 | Ultra budget (limited) |

### Cluster Sizing

| Workload | Workers Needed | Est. Speedup |
|----------|----------------|--------------|
| OVERVIEW ingestion (7K tickers) | 3 workers | 3x (40 min vs 2 hr) |
| Full price history (500 tickers) | 3 workers | 3x |
| Silver model build | 3 workers | 2-3x (Spark cluster) |
| Forecasting (all models) | 3 workers | 3x |

---

## Software Architecture

### 1. Worker Deployment

Each mini-PC runs:

```bash
# /etc/systemd/system/de_funk_worker.service
[Unit]
Description=de_Funk Celery Worker
After=network.target

[Service]
Type=simple
User=de_funk
WorkingDirectory=/opt/de_funk
ExecStart=/opt/de_funk/venv/bin/celery -A orchestration.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --queues=ingestion,build \
    --hostname=worker-${HOSTNAME}@%h
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. API Key Distribution

```python
# config/cluster_keys.py
"""Distribute API keys across workers."""

WORKER_API_KEYS = {
    'worker-1': {
        'alpha_vantage': ['KEY_AV_1', 'KEY_AV_2'],
        'bls': ['KEY_BLS_1'],
    },
    'worker-2': {
        'alpha_vantage': ['KEY_AV_3', 'KEY_AV_4'],
        'bls': ['KEY_BLS_2'],
    },
    'worker-3': {
        'alpha_vantage': ['KEY_AV_5', 'KEY_AV_6'],
        'bls': ['KEY_BLS_3'],
    },
}

def get_worker_keys(worker_name: str, provider: str) -> list:
    """Get API keys assigned to this worker."""
    return WORKER_API_KEYS.get(worker_name, {}).get(provider, [])
```

### 3. Task Partitioning

```python
# orchestration/tasks/distributed_ingestion.py

@app.task
def ingest_tickers_distributed(tickers: list, date_from: str, date_to: str):
    """
    Distribute ticker ingestion across workers.

    Each worker gets a partition of tickers based on worker ID.
    """
    from celery import group

    # Get available workers
    inspect = app.control.inspect()
    active_workers = list(inspect.active().keys())
    num_workers = len(active_workers)

    # Partition tickers
    partitions = [[] for _ in range(num_workers)]
    for i, ticker in enumerate(tickers):
        partitions[i % num_workers].append(ticker)

    # Create task group
    tasks = group(
        ingest_ticker_batch.s(partition, date_from, date_to).set(queue=f'worker-{i+1}')
        for i, partition in enumerate(partitions)
    )

    return tasks.apply_async()


@app.task(bind=True)
def ingest_ticker_batch(self, tickers: list, date_from: str, date_to: str):
    """Ingest a batch of tickers on this worker."""
    worker_name = self.request.hostname.split('@')[0]
    keys = get_worker_keys(worker_name, 'alpha_vantage')

    ingestor = AlphaVantageIngestor(api_keys=keys)

    results = []
    for ticker in tickers:
        try:
            result = ingestor.ingest_prices(ticker, date_from, date_to)
            results.append({'ticker': ticker, 'status': 'success', 'rows': result.count()})
        except Exception as e:
            results.append({'ticker': ticker, 'status': 'failed', 'error': str(e)})

    return results
```

### 4. Spark Cluster Mode

```python
# orchestration/common/spark_cluster.py

def get_spark_cluster():
    """Get Spark session configured for cluster mode."""
    from pyspark.sql import SparkSession

    return SparkSession.builder \
        .appName("de_Funk_Cluster") \
        .master("spark://control-node:7077") \
        .config("spark.executor.memory", "4g") \
        .config("spark.executor.cores", "2") \
        .config("spark.dynamicAllocation.enabled", "true") \
        .config("spark.dynamicAllocation.minExecutors", "1") \
        .config("spark.dynamicAllocation.maxExecutors", "6") \
        .getOrCreate()
```

### 5. Shared Storage (NFS)

```bash
# On control node: /etc/exports
/home/de_funk/storage  192.168.1.0/24(rw,sync,no_subtree_check)

# On worker nodes: /etc/fstab
control-node:/home/de_funk/storage  /opt/de_funk/storage  nfs  defaults  0  0
```

---

## Deployment Steps

### Phase 1: Infrastructure Setup

1. **Set up control node**
   - Install Redis: `docker run -d -p 6379:6379 redis`
   - Install Celery Beat for scheduling
   - Configure NFS exports

2. **Set up mini-PCs**
   - Install Ubuntu Server 22.04 LTS
   - Mount NFS storage
   - Install Python environment
   - Deploy de_Funk codebase

3. **Network configuration**
   - Static IPs for all nodes
   - Firewall rules for Redis, Spark, NFS
   - SSH keys for deployment

### Phase 2: Worker Deployment

```bash
# On each worker
git clone https://github.com/user/de_Funk.git /opt/de_funk
cd /opt/de_funk
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start worker
celery -A orchestration.celery_app worker --loglevel=info
```

### Phase 3: Monitoring

```bash
# On control node
celery -A orchestration.celery_app flower --port=5555

# Access monitoring at http://control-node:5555
```

---

## Configuration

### Environment Variables (per worker)

```bash
# /opt/de_funk/.env
REDIS_URL=redis://control-node:6379/0
WORKER_NAME=worker-1
ALPHA_VANTAGE_API_KEYS=KEY1,KEY2
BLS_API_KEYS=KEY1
STORAGE_ROOT=/opt/de_funk/storage
SPARK_MASTER=spark://control-node:7077
```

### Celery Configuration

```python
# orchestration/celery_config.py
from config import ConfigLoader

config = ConfigLoader().load()

CELERY_CONFIG = {
    'broker_url': config.redis_url,
    'result_backend': config.redis_url,

    # Task routing
    'task_routes': {
        'orchestration.tasks.ingestion_tasks.*': {'queue': 'ingestion'},
        'orchestration.tasks.build_tasks.*': {'queue': 'build'},
        'orchestration.tasks.forecast_tasks.*': {'queue': 'forecast'},
    },

    # Worker settings
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
    'task_reject_on_worker_lost': True,

    # Rate limiting
    'task_annotations': {
        'orchestration.tasks.ingestion_tasks.ingest_ticker_reference': {
            'rate_limit': '5/m',  # Per worker rate limit
        },
    },
}
```

---

## Cost Analysis

### One-Time Costs

| Item | Quantity | Unit Cost | Total |
|------|----------|-----------|-------|
| Mini-PC (Beelink EQ12) | 3 | $200 | $600 |
| Gigabit switch | 1 | $30 | $30 |
| Ethernet cables | 4 | $5 | $20 |
| USB power strip | 1 | $20 | $20 |
| **Total** | | | **$670** |

### Monthly Costs

| Item | Cost | Notes |
|------|------|-------|
| Electricity | ~$5 | 3 x 15W x 24h x 30d = 32 kWh |
| Alpha Vantage Premium | $50/key x 3 | Optional: 3 premium keys |
| **Total** | ~$5-155 | Depends on API tier |

### ROI Analysis

| Metric | Single Machine | 3-Node Cluster | Improvement |
|--------|----------------|----------------|-------------|
| OVERVIEW ingestion | 2 hours | 40 minutes | 3x faster |
| Full pipeline | 4 hours | 1.5 hours | 2.7x faster |
| Concurrent development | Blocked | Unblocked | ✓ |
| Failure recovery | Restart | Resume | ✓ |

---

## Open Questions

1. **Storage backend**: NFS vs Ceph vs MinIO?
2. **API key sourcing**: How many Alpha Vantage premium keys needed?
3. **Power/cooling**: Where to physically place mini-PCs?
4. **Network topology**: Same subnet or VLAN separation?
5. **Security**: VPN for remote access to cluster?

---

## Implementation Plan

### Week 1: Proof of Concept
- Set up 1 mini-PC as test worker
- Validate Celery task execution
- Test NFS storage mount

### Week 2: Cluster Deployment
- Deploy remaining mini-PCs
- Configure Spark cluster
- Validate distributed ingestion

### Week 3: Production Hardening
- Add monitoring (Flower, Prometheus)
- Configure alerting
- Document runbooks

### Week 4: Integration
- Update pipeline scripts for cluster mode
- Add cluster status commands
- Performance testing

---

## References

- [Celery Distributed Tasks](https://docs.celeryq.dev/en/stable/userguide/routing.html)
- [Apache Spark Cluster Mode](https://spark.apache.org/docs/latest/cluster-overview.html)
- [NFS Best Practices](https://wiki.archlinux.org/title/NFS)
- Proposal 001: Parallel Ingestion Architecture
