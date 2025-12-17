"""
Distributed computing infrastructure for de_Funk.

Provides Ray-based distributed execution for:
- Parallel forecasting across cluster
- Distributed model building
- Scheduled job management

Usage:
    from orchestration.distributed import RayCluster, DistributedForecaster

    # Connect to cluster or run locally
    cluster = RayCluster()
    cluster.connect()

    # Run distributed forecasting
    forecaster = DistributedForecaster(cluster)
    results = forecaster.run(tickers=['AAPL', 'MSFT', ...], models=['arima'])
"""
from orchestration.distributed.ray_cluster import RayCluster
from orchestration.distributed.tasks import forecast_ticker, build_model_task

__all__ = ['RayCluster', 'forecast_ticker', 'build_model_task']
