# Ray Cleanup Guide

Guide for removing Ray-based orchestration if migrating to Airflow or standalone Spark.

## Ray Assets Inventory

### Files to Remove

```bash
# Ray-specific scripts
scripts/cluster/run_distributed_pipeline.py   # Main Ray pipeline
scripts/cluster/run_production.sh              # Calls Ray pipeline
scripts/cluster/setup-worker.sh                # Ray worker setup
scripts/cluster/setup-head.sh                  # Ray head setup
scripts/cluster/cluster-init.sh                # Ray cluster init
scripts/cluster/test_cluster.py                # Ray cluster tests
scripts/cluster/test_cluster_ingestion.py      # Ray ingestion tests

# Ray orchestration module
orchestration/distributed/ray_cluster.py       # Ray cluster management
orchestration/distributed/key_manager.py       # Ray-based key manager
orchestration/distributed/tasks.py             # Ray remote tasks
orchestration/distributed/config.py            # Ray config
orchestration/distributed/__init__.py

# Test files
scripts/test/test_distributed_key_manager.py
scripts/test/test_cluster_setup.sh
```

### Files to Keep (Reusable)

```bash
# These can be reused with Airflow/Spark:
scripts/seed/seed_tickers.py           # Seeding (no Ray dependency)
scripts/seed/seed_calendar.py          # Seeding (no Ray dependency)
scripts/build/build_models.py          # Model building (Spark only)
scripts/build/compute_technicals.py    # Technicals (Spark only)
scripts/ingest/run_bronze_ingestion.py # Simple ingestion (no Ray)

# Spark cluster scripts (keep these)
scripts/spark-cluster/*
```

### Documentation to Update

```bash
docs/guides/worker-cluster-setup.md           # References Ray
docs/guides/linux-server-setup-from-scratch.md # References Ray
docs/vault/13-proposals/draft/011-distributed-cluster-architecture.md
CLAUDE.md                                      # Update orchestration section
```

## Cleanup Commands

```bash
# 1. Stop Ray on all nodes
ray stop  # On head node

# 2. Remove Ray from requirements
# Edit requirements.txt, remove: ray[default]>=2.9.0

# 3. Remove Ray-specific files
rm -rf scripts/cluster/run_distributed_pipeline.py
rm -rf scripts/cluster/run_production.sh
rm -rf scripts/cluster/setup-worker.sh
rm -rf scripts/cluster/setup-head.sh
rm -rf scripts/cluster/cluster-init.sh
rm -rf scripts/cluster/test_cluster*.py

rm -rf orchestration/distributed/

rm -rf scripts/test/test_distributed_key_manager.py
rm -rf scripts/test/test_cluster_setup.sh

# 4. Remove Ray from workers (optional)
ssh bark-1 "pip uninstall ray -y"
ssh bark-2 "pip uninstall ray -y"
ssh bark-3 "pip uninstall ray -y"

# 5. Remove Ray systemd service (if installed)
sudo systemctl stop ray-worker
sudo systemctl disable ray-worker
sudo rm /etc/systemd/system/ray-worker.service
```

## Migration Checklist

- [ ] Install Airflow (or confirm Spark cluster working)
- [ ] Copy DAG to Airflow dags folder
- [ ] Test DAG runs successfully
- [ ] Update CLAUDE.md with new orchestration approach
- [ ] Remove Ray files (see commands above)
- [ ] Remove `ray` from requirements.txt
- [ ] Update worker setup docs
- [ ] Uninstall Ray from workers (optional)

## What Changes

| Component | Before (Ray) | After (Airflow) |
|-----------|--------------|-----------------|
| Scheduler | Ray head node | Airflow scheduler |
| Worker management | Ray auto-scaling | Spark cluster (fixed) |
| Task distribution | Ray tasks | Airflow operators |
| Monitoring | `ray status` | Airflow web UI |
| Logs | Files on workers | Airflow log viewer |
| API ingestion | Ray tasks | Simple Python |
| Silver builds | Spark-in-Ray | spark-submit |

## Keeping Both (Transitional)

You can keep both during transition:

```bash
# Ray pipeline (existing)
./scripts/cluster/run_production.sh

# Airflow pipeline (new)
airflow dags trigger de_funk_pipeline

# Spark-only (manual)
./scripts/spark-cluster/run_pipeline.sh
```

They all write to the same `/shared/storage`, so data is compatible.
