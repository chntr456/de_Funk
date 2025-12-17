"""
Distributed computing infrastructure for de_Funk.

Provides Ray-based distributed execution for:
- Parallel forecasting across cluster
- Distributed model building
- Scheduled job management

Configuration:
    Cluster settings are loaded from configs/cluster.yaml
    See orchestration.distributed.config for details.

Usage:
    from orchestration.distributed import RayCluster, load_cluster_config

    # Load configuration
    config = load_cluster_config()

    # Connect to cluster or run locally
    cluster = RayCluster()
    cluster.connect()

    # Run distributed forecasting
    from orchestration.distributed.tasks import forecast_ticker
    futures = [forecast_ticker.remote(ticker) for ticker in tickers]
    results = ray.get(futures)
"""
from orchestration.distributed.ray_cluster import RayCluster
from orchestration.distributed.config import load_cluster_config, ClusterConfig

__all__ = ['RayCluster', 'load_cluster_config', 'ClusterConfig']
