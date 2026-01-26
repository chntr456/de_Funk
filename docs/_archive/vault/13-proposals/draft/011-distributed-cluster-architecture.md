# Proposal: Distributed Cluster Architecture with Mini-PCs

**Status**: Draft
**Author**: Claude
**Date**: 2025-12-02
**Updated**: 2025-12-02
**Priority**: High
**Depends On**: 001-parallel-ingestion-architecture.md

---

## Summary

Extend de_Funk to utilize a cluster of mini-PCs for distributed forecasting, model building, and data processing using **Ray** for parallelism and **APScheduler** for scheduled jobs. This approach prioritizes compute-heavy tasks (forecasting, model training) over API ingestion.

---

## Why Ray Instead of Celery?

| Aspect | Celery | Ray | Winner |
|--------|--------|-----|--------|
| **ML/Forecasting** | Generic tasks | Native pandas/sklearn/numpy | Ray |
| **Data passing** | Serialize through Redis | Shared memory, zero-copy | Ray |
| **Learning curve** | Task registration, brokers | `@ray.remote` decorator | Ray |
| **Cluster scaling** | Worker config needed | Auto-scales | Ray |
| **Dashboard** | Flower (separate install) | Built-in at :8265 | Ray |
| **Dependencies** | Redis required | Self-contained | Ray |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MAIN PC (Ray Head Node)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  Ray Head       │  │  APScheduler    │  │  DuckDB         │         │
│  │  :6379          │  │  (cron jobs)    │  │  (analytics)    │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│           │                   │                                         │
│           │    ray.init(address="auto")                                │
│           │    submit tasks ──────────────────┐                        │
└───────────│───────────────────────────────────│────────────────────────┘
            │                                   │
            │  Ray Cluster (auto-distributes)   │
            │                                   │
    ┌───────┴───────┬───────────────────┬──────┴────────┐
    ▼               ▼                   ▼               ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│ MINI-PC 1  │ │ MINI-PC 2  │ │ MINI-PC 3  │ │ Main PC    │
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

## Implementation

### 1. Cluster Setup

**On Main PC (Head Node):**
```bash
# Install Ray
pip install "ray[default]"

# Start head node
ray start --head --port=6379 --dashboard-host=0.0.0.0

# Dashboard available at http://localhost:8265
```

**On Each Mini-PC (Worker Node):**
```bash
# Install Ray
pip install "ray[default]"

# Connect to head
ray start --address='192.168.1.100:6379'
```

**Verify Cluster:**
```python
import ray
ray.init(address="auto")
print(ray.cluster_resources())
# {'CPU': 20.0, 'memory': 80GB, 'node:192.168.1.101': 1.0, ...}
```

### 2. Distributed Forecasting

```python
# scripts/forecast/run_forecasts_distributed.py
"""
Distributed forecasting across Ray cluster.

Usage:
    # Local (all cores on this machine)
    python -m scripts.forecast.run_forecasts_distributed --tickers 100

    # Cluster (distributed across mini-PCs)
    python -m scripts.forecast.run_forecasts_distributed --cluster --tickers 500
"""
from __future__ import annotations

import ray
from typing import List, Dict, Any
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


@ray.remote
def forecast_ticker(ticker: str, models: List[str], horizon: int) -> Dict[str, Any]:
    """
    Run forecast for a single ticker. Executes on remote worker.

    Each worker has its own Python environment and loads data independently.
    """
    import pandas as pd
    from statsmodels.tsa.arima.model import ARIMA

    # Load price data from shared storage
    prices_path = Path("/shared/storage/silver/stocks/facts/fact_stock_prices")
    df = pd.read_parquet(prices_path)
    ticker_df = df[df['ticker'] == ticker].sort_values('trade_date')

    if len(ticker_df) < 60:
        return {'ticker': ticker, 'status': 'skipped', 'reason': 'insufficient_data'}

    results = {'ticker': ticker, 'forecasts': {}}

    for model_type in models:
        try:
            if model_type == 'arima':
                model = ARIMA(ticker_df['close'].values, order=(5, 1, 0))
                fitted = model.fit()
                forecast = fitted.forecast(steps=horizon)
                results['forecasts']['arima'] = forecast.tolist()

            elif model_type == 'prophet':
                from prophet import Prophet
                prophet_df = ticker_df[['trade_date', 'close']].rename(
                    columns={'trade_date': 'ds', 'close': 'y'}
                )
                model = Prophet(daily_seasonality=False)
                model.fit(prophet_df)
                future = model.make_future_dataframe(periods=horizon)
                forecast = model.predict(future)
                results['forecasts']['prophet'] = forecast['yhat'].tail(horizon).tolist()

        except Exception as e:
            results['forecasts'][model_type] = {'error': str(e)}

    results['status'] = 'success'
    return results


def run_distributed_forecasts(
    tickers: List[str],
    models: List[str] = ['arima'],
    horizon: int = 30,
    use_cluster: bool = False
) -> List[Dict]:
    """
    Run forecasts across Ray cluster or locally.
    """
    # Connect to Ray
    if use_cluster:
        ray.init(address="auto")
        resources = ray.cluster_resources()
        print(f"Connected to cluster: {resources.get('CPU', 0):.0f} CPUs across {len([k for k in resources if k.startswith('node:')])} nodes")
    else:
        ray.init()
        print(f"Running locally with {ray.cluster_resources().get('CPU', 0):.0f} CPUs")

    # Submit all tasks
    print(f"\nSubmitting {len(tickers)} forecast tasks...")
    futures = [
        forecast_ticker.remote(ticker, models, horizon)
        for ticker in tickers
    ]

    # Collect results with progress bar
    from tqdm import tqdm
    results = []
    for future in tqdm(futures, desc="Forecasting"):
        result = ray.get(future)
        results.append(result)

    # Summary
    successful = sum(1 for r in results if r.get('status') == 'success')
    print(f"\nCompleted: {successful}/{len(tickers)} successful")

    ray.shutdown()
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Distributed forecasting")
    parser.add_argument("--cluster", action="store_true", help="Use Ray cluster")
    parser.add_argument("--tickers", type=int, default=100, help="Number of tickers")
    parser.add_argument("--models", nargs="+", default=["arima"], help="Forecast models")
    parser.add_argument("--horizon", type=int, default=30, help="Forecast horizon days")
    args = parser.parse_args()

    # Get tickers by market cap
    from core.context import RepoContext
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

    ctx = RepoContext.from_repo_root(connection_type="spark")
    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    tickers = ingestor.get_tickers_by_market_cap(max_tickers=args.tickers)
    if not tickers:
        print("No tickers with market cap data. Run refresh_market_cap_rankings first.")
        return

    results = run_distributed_forecasts(
        tickers=tickers,
        models=args.models,
        horizon=args.horizon,
        use_cluster=args.cluster
    )

    # Save results
    import json
    output_path = Path(repo_root) / "storage" / "forecasts" / "latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
```

### 3. Scheduled Jobs with APScheduler

```python
# orchestration/scheduler.py
"""
Scheduled jobs using APScheduler.

Usage:
    python -m orchestration.scheduler

Runs continuously, executing jobs at scheduled times.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


scheduler = BlockingScheduler()


@scheduler.scheduled_job(CronTrigger(hour=6, minute=0))
def daily_market_cap_refresh():
    """Run at 6:00 AM daily - refresh market cap data."""
    print(f"[{datetime.now()}] Starting daily market cap refresh...")

    from scripts.ingest.refresh_market_cap_rankings import main as refresh_main
    refresh_main()

    print(f"[{datetime.now()}] Market cap refresh complete")


@scheduler.scheduled_job(CronTrigger(hour=16, minute=30))
def daily_price_ingestion():
    """Run at 4:30 PM daily (after market close) - ingest prices."""
    print(f"[{datetime.now()}] Starting daily price ingestion...")

    from scripts.ingest.run_full_pipeline import run_full_pipeline
    run_full_pipeline(
        max_tickers=500,
        skip_forecasts=True,
        skip_reference_refresh=True  # Already done at 6 AM
    )

    print(f"[{datetime.now()}] Price ingestion complete")


@scheduler.scheduled_job(CronTrigger(day_of_week='sun', hour=2, minute=0))
def weekly_forecasts():
    """Run at 2:00 AM Sunday - full forecast run on cluster."""
    print(f"[{datetime.now()}] Starting weekly forecast run...")

    import ray
    ray.init(address="auto")  # Connect to cluster

    from scripts.forecast.run_forecasts_distributed import run_distributed_forecasts
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor
    from core.context import RepoContext

    ctx = RepoContext.from_repo_root(connection_type="spark")
    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    tickers = ingestor.get_tickers_by_market_cap(max_tickers=500)

    run_distributed_forecasts(
        tickers=tickers,
        models=['arima', 'prophet'],
        horizon=30,
        use_cluster=True
    )

    ray.shutdown()
    print(f"[{datetime.now()}] Weekly forecasts complete")


@scheduler.scheduled_job(CronTrigger(hour=5, minute=0))
def daily_silver_rebuild():
    """Run at 5:00 AM daily - rebuild silver layer."""
    print(f"[{datetime.now()}] Starting silver layer rebuild...")

    from scripts.ingest.run_full_pipeline import run_full_pipeline
    run_full_pipeline(
        skip_data_refresh=True,
        skip_forecasts=True
    )

    print(f"[{datetime.now()}] Silver rebuild complete")


def main():
    print("=" * 60)
    print("de_Funk Scheduler")
    print("=" * 60)
    print("\nScheduled jobs:")
    for job in scheduler.get_jobs():
        print(f"  - {job.name}: {job.trigger}")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
```

### 4. Systemd Service for Scheduler

```ini
# /etc/systemd/system/de_funk_scheduler.service
[Unit]
Description=de_Funk Scheduler (APScheduler)
After=network.target

[Service]
Type=simple
User=de_funk
WorkingDirectory=/opt/de_funk
ExecStart=/opt/de_funk/venv/bin/python -m orchestration.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5. Systemd Service for Ray Workers

```ini
# /etc/systemd/system/ray_worker.service (on each mini-PC)
[Unit]
Description=Ray Worker Node
After=network.target

[Service]
Type=simple
User=de_funk
ExecStart=/opt/de_funk/venv/bin/ray start --address='192.168.1.100:6379' --block
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Hardware Requirements

### Mini-PC Recommendations

| Device | CPU | RAM | Storage | Price | Notes |
|--------|-----|-----|---------|-------|-------|
| **Beelink EQ12** | Intel N100 (4c/4t) | 16GB | 500GB | ~$200 | Budget, good value |
| **Minisforum UM560** | Ryzen 5 5625U (6c/12t) | 16GB | 512GB | ~$350 | Better CPU |
| **Intel NUC 12** | i5-1240P (12c/16t) | 32GB | 1TB | ~$500 | High performance |

### Recommended Setup (3 Workers)

| Component | Qty | Cost |
|-----------|-----|------|
| Beelink EQ12 | 3 | $600 |
| 8-port Gigabit Switch | 1 | $25 |
| Ethernet Cables | 4 | $15 |
| Power Strip | 1 | $20 |
| **Total** | | **$660** |

---

## Performance Estimates

### Forecasting Speedup

| Tickers | Single Machine | 3-Node Cluster | Speedup |
|---------|----------------|----------------|---------|
| 100 | 10 min | 3.5 min | 2.9x |
| 500 | 50 min | 17 min | 2.9x |
| 2000 | 3.3 hr | 1.1 hr | 3x |

### Silver Layer Build

| Operation | Single Machine | 3-Node Spark | Speedup |
|-----------|----------------|--------------|---------|
| Build stocks model | 35 sec | 15 sec | 2.3x |
| Full silver rebuild | 2 min | 50 sec | 2.4x |

---

## Shared Storage Setup

### NFS Configuration

**On Main PC (NFS Server):**
```bash
# Install NFS server
sudo apt install nfs-kernel-server

# Export storage directory
echo '/home/de_funk/storage 192.168.1.0/24(rw,sync,no_subtree_check)' | sudo tee -a /etc/exports
sudo exportfs -ra
```

**On Mini-PCs (NFS Clients):**
```bash
# Install NFS client
sudo apt install nfs-common

# Create mount point
sudo mkdir -p /shared/storage

# Add to fstab
echo '192.168.1.100:/home/de_funk/storage /shared/storage nfs defaults 0 0' | sudo tee -a /etc/fstab

# Mount
sudo mount -a
```

---

## Deployment Checklist

### Phase 1: Single Mini-PC Test
- [ ] Install Ubuntu Server on one mini-PC
- [ ] Install Python, pip, de_Funk dependencies
- [ ] Mount NFS storage
- [ ] Start Ray worker, verify connection
- [ ] Run test forecast task

### Phase 2: Full Cluster
- [ ] Repeat for remaining mini-PCs
- [ ] Verify all workers in cluster
- [ ] Run distributed forecast test
- [ ] Benchmark performance

### Phase 3: Production
- [ ] Create systemd services
- [ ] Configure APScheduler jobs
- [ ] Test scheduled runs
- [ ] Document runbooks

---

## CLI Commands

```bash
# Check cluster status
ray status

# View dashboard
# Open http://main-pc:8265 in browser

# Run distributed forecast
python -m scripts.forecast.run_forecasts_distributed --cluster --tickers 500

# Start scheduler
python -m orchestration.scheduler

# Manual job trigger
python -c "from orchestration.scheduler import weekly_forecasts; weekly_forecasts()"
```

---

## Open Questions

1. **NFS vs other storage**: Should we use MinIO/S3 for better performance?
2. **Worker scaling**: Auto-scale workers based on queue depth?
3. **Monitoring**: Integrate with Grafana/Prometheus?
4. **API key management**: Secure storage for keys on workers?

---

## Future Improvements

### Polars Migration

Replace pandas with Polars for significant performance gains:

| Operation | Pandas | Polars | Speedup |
|-----------|--------|--------|---------|
| Read parquet | 2.5s | 0.3s | 8x |
| Filter/groupby | 1.2s | 0.1s | 12x |
| Memory usage | 4GB | 1GB | 4x less |

```python
# Current (pandas)
import pandas as pd
df = pd.read_parquet(prices_path)
ticker_df = df[df['ticker'] == ticker]

# Future (polars) - lazy evaluation, parallel execution
import polars as pl
df = pl.scan_parquet(prices_path)
ticker_df = df.filter(pl.col('ticker') == ticker).collect()
```

**Benefits for distributed forecasting:**
- Faster data loading = more time for actual forecasting
- Lower memory = more concurrent tasks per worker
- Native parallel execution within each worker

---

## Dependencies

```
# requirements-cluster.txt
ray[default]>=2.9.0
apscheduler>=3.10.0
```

---

## References

- [Ray Cluster Setup](https://docs.ray.io/en/latest/cluster/getting-started.html)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Ray Dashboard](https://docs.ray.io/en/latest/ray-observability/ray-dashboard.html)
