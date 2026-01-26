"""
Distributed computing infrastructure for de_Funk.

Provides Ray-based distributed execution for:
- Parallel forecasting across cluster
- Distributed data ingestion with coordinated rate limiting
- Distributed model building
- Scheduled job management

Configuration:
    Cluster settings are loaded from configs/cluster.yaml
    See orchestration.distributed.config for details.

Usage:
    from de_funk.orchestration.distributed import RayCluster, load_cluster_config

    # Load configuration
    config = load_cluster_config()

    # Connect to cluster or run locally
    cluster = RayCluster()
    cluster.connect()

    # Run distributed forecasting
    from de_funk.orchestration.distributed.tasks import forecast_ticker
    futures = [forecast_ticker.remote(ticker) for ticker in tickers]
    results = ray.get(futures)

    # Run distributed ingestion with rate limiting
    from de_funk.orchestration.distributed.key_manager import (
        KeyManagerRegistry, init_key_managers_from_env
    )
    from de_funk.orchestration.distributed.tasks import ingest_ticker

    # Initialize key managers (reads from env vars)
    registry = init_key_managers_from_env()
    av_manager = registry.get_manager('alpha_vantage')

    # Ingest with coordinated rate limiting
    futures = [ingest_ticker.remote(t, av_manager) for t in tickers]
    results = ray.get(futures)
"""
from de_funk.orchestration.distributed.ray_cluster import RayCluster
from de_funk.orchestration.distributed.config import load_cluster_config, ClusterConfig
from de_funk.orchestration.distributed.key_manager import (
    KeyManagerRegistry,
    init_key_managers_from_env,
    create_key_manager_for_provider,
)

__all__ = [
    'RayCluster',
    'load_cluster_config',
    'ClusterConfig',
    'KeyManagerRegistry',
    'init_key_managers_from_env',
    'create_key_manager_for_provider',
]
