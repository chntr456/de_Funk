"""
Cluster Configuration Loader.

Loads and validates cluster configuration from configs/cluster.yaml.

Usage:
    from orchestration.distributed.config import load_cluster_config, ClusterConfig

    config = load_cluster_config()
    print(config.ray.mode)  # "local"
    print(config.scheduler.jobs)  # dict of job configs

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RayLocalConfig:
    """Local Ray configuration."""
    num_cpus: Optional[int] = None
    memory_gb: Optional[float] = None


@dataclass
class RayHeadConfig:
    """Ray head node configuration."""
    host: str = "localhost"
    port: int = 6379
    dashboard_port: int = 8265


@dataclass
class RayWorkerConfig:
    """Ray worker node configuration."""
    host: str = ""
    cpus: int = 4
    memory_gb: float = 16.0


@dataclass
class RayClusterConfig:
    """Ray cluster configuration."""
    head: RayHeadConfig = field(default_factory=RayHeadConfig)
    workers: List[RayWorkerConfig] = field(default_factory=list)


@dataclass
class RayConfig:
    """Ray configuration."""
    mode: str = "local"  # "local", "auto", "address"
    address: Optional[str] = None
    local: RayLocalConfig = field(default_factory=RayLocalConfig)
    cluster: RayClusterConfig = field(default_factory=RayClusterConfig)
    runtime_env: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageLocalConfig:
    """Local storage paths."""
    bronze: str = "storage/bronze"
    silver: str = "storage/silver"
    forecasts: str = "storage/forecasts"


@dataclass
class StorageNFSConfig:
    """NFS storage configuration."""
    mount_point: str = "/shared/storage"
    server_host: str = ""
    export_path: str = ""


@dataclass
class StorageConfig:
    """Storage configuration."""
    type: str = "local"  # "local" or "nfs"
    local: StorageLocalConfig = field(default_factory=StorageLocalConfig)
    nfs: StorageNFSConfig = field(default_factory=StorageNFSConfig)


@dataclass
class JobScheduleConfig:
    """Job schedule configuration."""
    hour: int = 0
    minute: int = 0
    day_of_week: Optional[str] = None


@dataclass
class JobConfig:
    """Individual job configuration."""
    enabled: bool = True
    description: str = ""
    schedule: JobScheduleConfig = field(default_factory=JobScheduleConfig)
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""
    enabled: bool = True
    timezone: str = "America/New_York"
    jobs: Dict[str, JobConfig] = field(default_factory=dict)


@dataclass
class IngestionConfig:
    """Ingestion configuration."""
    batch_size: int = 20
    auto_compact: bool = True
    rate_limit: float = 1.0
    max_retries: int = 3
    retry_delay_seconds: float = 2.0


@dataclass
class ForecastModelConfig:
    """Individual forecast model configuration."""
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastingConfig:
    """Forecasting configuration."""
    min_data_points: int = 60
    default_horizon: int = 30
    models: Dict[str, ForecastModelConfig] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    metrics_enabled: bool = True
    log_level: str = "INFO"
    progress_mode: str = "minimal"


@dataclass
class ClusterConfig:
    """Complete cluster configuration."""
    ray: RayConfig = field(default_factory=RayConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    forecasting: ForecastingConfig = field(default_factory=ForecastingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


def _parse_ray_config(data: Dict) -> RayConfig:
    """Parse Ray configuration from dict."""
    if not data:
        return RayConfig()

    local_cfg = data.get('local', {})
    local = RayLocalConfig(
        num_cpus=local_cfg.get('num_cpus'),
        memory_gb=local_cfg.get('memory_gb')
    )

    cluster_cfg = data.get('cluster', {})
    head_cfg = cluster_cfg.get('head', {})
    head = RayHeadConfig(
        host=head_cfg.get('host', 'localhost'),
        port=head_cfg.get('port', 6379),
        dashboard_port=head_cfg.get('dashboard_port', 8265)
    )

    workers = []
    for w in cluster_cfg.get('workers', []):
        workers.append(RayWorkerConfig(
            host=w.get('host', ''),
            cpus=w.get('cpus', 4),
            memory_gb=w.get('memory_gb', 16.0)
        ))

    cluster = RayClusterConfig(head=head, workers=workers)

    return RayConfig(
        mode=data.get('mode', 'local'),
        address=data.get('address'),
        local=local,
        cluster=cluster,
        runtime_env=data.get('runtime_env', {})
    )


def _parse_storage_config(data: Dict) -> StorageConfig:
    """Parse storage configuration from dict."""
    if not data:
        return StorageConfig()

    local_cfg = data.get('local', {})
    local = StorageLocalConfig(
        bronze=local_cfg.get('bronze', 'storage/bronze'),
        silver=local_cfg.get('silver', 'storage/silver'),
        forecasts=local_cfg.get('forecasts', 'storage/forecasts')
    )

    nfs_cfg = data.get('nfs', {})
    server_cfg = nfs_cfg.get('server', {})
    nfs = StorageNFSConfig(
        mount_point=nfs_cfg.get('mount_point', '/shared/storage'),
        server_host=server_cfg.get('host', ''),
        export_path=server_cfg.get('export_path', '')
    )

    return StorageConfig(
        type=data.get('type', 'local'),
        local=local,
        nfs=nfs
    )


def _parse_scheduler_config(data: Dict) -> SchedulerConfig:
    """Parse scheduler configuration from dict."""
    if not data:
        return SchedulerConfig()

    jobs = {}
    for job_id, job_data in data.get('jobs', {}).items():
        schedule_data = job_data.get('schedule', {})
        schedule = JobScheduleConfig(
            hour=schedule_data.get('hour', 0),
            minute=schedule_data.get('minute', 0),
            day_of_week=schedule_data.get('day_of_week')
        )
        jobs[job_id] = JobConfig(
            enabled=job_data.get('enabled', True),
            description=job_data.get('description', ''),
            schedule=schedule,
            settings=job_data.get('settings', {})
        )

    return SchedulerConfig(
        enabled=data.get('enabled', True),
        timezone=data.get('timezone', 'America/New_York'),
        jobs=jobs
    )


def load_cluster_config(config_path: Optional[Path] = None) -> ClusterConfig:
    """
    Load cluster configuration from YAML file.

    Searches for config in order:
    1. Explicit config_path parameter
    2. DEFUNK_CLUSTER_CONFIG environment variable
    3. ~/.de_funk/cluster.yaml
    4. configs/cluster.yaml in repo

    Args:
        config_path: Optional explicit path to config file

    Returns:
        ClusterConfig dataclass
    """
    # Determine config path
    if config_path is None:
        # Check environment variable
        env_path = os.environ.get('DEFUNK_CLUSTER_CONFIG')
        if env_path:
            config_path = Path(env_path)
        else:
            # Check user home directory
            home_config = Path.home() / '.de_funk' / 'cluster.yaml'
            if home_config.exists():
                config_path = home_config
            else:
                # Use repo default
                from utils.repo import get_repo_root
                config_path = Path(get_repo_root()) / 'configs' / 'cluster.yaml'

    # Load config
    if not config_path.exists():
        logger.warning(f"Cluster config not found at {config_path}, using defaults")
        return ClusterConfig()

    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        logger.info(f"Loaded cluster config from {config_path}")

        # Parse sections
        ray = _parse_ray_config(data.get('ray', {}))
        storage = _parse_storage_config(data.get('storage', {}))
        scheduler = _parse_scheduler_config(data.get('scheduler', {}))

        ingestion_data = data.get('ingestion', {})
        ingestion = IngestionConfig(
            batch_size=ingestion_data.get('batch_size', 20),
            auto_compact=ingestion_data.get('auto_compact', True),
            rate_limit=ingestion_data.get('rate_limit', 1.0),
            max_retries=ingestion_data.get('max_retries', 3),
            retry_delay_seconds=ingestion_data.get('retry_delay_seconds', 2.0)
        )

        forecasting_data = data.get('forecasting', {})
        models = {}
        for model_id, model_data in forecasting_data.get('models', {}).items():
            models[model_id] = ForecastModelConfig(
                enabled=model_data.get('enabled', True),
                params={k: v for k, v in model_data.items() if k != 'enabled'}
            )
        forecasting = ForecastingConfig(
            min_data_points=forecasting_data.get('min_data_points', 60),
            default_horizon=forecasting_data.get('default_horizon', 30),
            models=models
        )

        monitoring_data = data.get('monitoring', {})
        monitoring = MonitoringConfig(
            metrics_enabled=monitoring_data.get('metrics_enabled', True),
            log_level=monitoring_data.get('log_level', 'INFO'),
            progress_mode=monitoring_data.get('progress_mode', 'minimal')
        )

        return ClusterConfig(
            ray=ray,
            storage=storage,
            scheduler=scheduler,
            ingestion=ingestion,
            forecasting=forecasting,
            monitoring=monitoring
        )

    except Exception as e:
        logger.error(f"Failed to load cluster config: {e}")
        return ClusterConfig()


def get_storage_path(config: ClusterConfig, path_type: str) -> Path:
    """
    Get the appropriate storage path based on cluster configuration.

    Args:
        config: ClusterConfig instance
        path_type: "bronze", "silver", or "forecasts"

    Returns:
        Absolute path to storage location
    """
    if config.storage.type == "nfs":
        base = Path(config.storage.nfs.mount_point)
    else:
        from utils.repo import get_repo_root
        base = Path(get_repo_root())

    paths = {
        'bronze': config.storage.local.bronze,
        'silver': config.storage.local.silver,
        'forecasts': config.storage.local.forecasts
    }

    return base / paths.get(path_type, path_type)
