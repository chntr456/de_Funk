"""
Pipeline Configuration Loader.

Loads and validates pipeline configuration from YAML files in configs/pipelines/.
Provides type-safe access to pipeline settings, endpoints, and data types.

Usage:
    from config.pipeline_loader import PipelineConfigLoader, PipelineConfig

    loader = PipelineConfigLoader()
    config = loader.load("alpha_vantage")

    # Access settings
    print(config.batch_size)  # 20
    print(config.rate_limit)  # 1.0

    # Access data types
    for name, dt in config.data_types.items():
        print(f"{name}: {dt.endpoint} -> {dt.bronze_table}")

    # Access endpoints
    endpoint = config.get_endpoint("company_overview")
    print(endpoint.function)  # "OVERVIEW"

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
class EndpointConfig:
    """Configuration for a single API endpoint."""
    name: str
    method: str = "GET"
    function: Optional[str] = None
    path: Optional[str] = None
    required_params: List[str] = field(default_factory=list)
    default_params: Dict[str, Any] = field(default_factory=dict)
    response_key: Optional[str] = None
    pagination: Optional[str] = None
    format: Optional[str] = None
    comment: str = ""


@dataclass
class DataTypeConfig:
    """Configuration for a data type to ingest."""
    name: str
    description: str = ""
    endpoint: Optional[str] = None
    series_id: Optional[str] = None  # For BLS
    facet: Optional[str] = None
    bronze_table: Optional[str] = None
    enabled: bool = True


@dataclass
class ProgressConfig:
    """Progress display configuration."""
    show_batch_header: bool = True
    show_ticker_status: bool = True
    show_eta: bool = True
    data_type_short_names: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    provider: str
    description: str = ""
    version: str = "1.0"

    # API settings
    base_url: str = ""
    credentials_env_var: str = ""
    rate_limit: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)

    # Pipeline settings
    batch_size: int = 20
    batch_write_size: int = 20
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    strategy: str = "per_ticker"

    # Data types and endpoints
    data_types: Dict[str, DataTypeConfig] = field(default_factory=dict)
    endpoints: Dict[str, EndpointConfig] = field(default_factory=dict)

    # Progress settings
    progress: ProgressConfig = field(default_factory=ProgressConfig)

    # Extra provider-specific settings
    extra: Dict[str, Any] = field(default_factory=dict)

    def get_endpoint(self, name: str) -> Optional[EndpointConfig]:
        """Get endpoint configuration by name."""
        return self.endpoints.get(name)

    def get_data_type(self, name: str) -> Optional[DataTypeConfig]:
        """Get data type configuration by name."""
        return self.data_types.get(name)

    def get_enabled_data_types(self) -> Dict[str, DataTypeConfig]:
        """Get only enabled data types."""
        return {k: v for k, v in self.data_types.items() if v.enabled}

    def get_short_name(self, data_type: str) -> str:
        """Get short display name for a data type."""
        return self.progress.data_type_short_names.get(data_type, data_type[:3])


class PipelineConfigLoader:
    """
    Loads pipeline configurations from YAML files.

    Configuration files are expected in configs/pipelines/{provider}.yaml

    Example:
        loader = PipelineConfigLoader()
        config = loader.load("alpha_vantage")
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the loader.

        Args:
            config_dir: Directory containing pipeline YAML files.
                       Defaults to configs/pipelines/ relative to repo root.
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Find configs/pipelines relative to this file
            self.config_dir = Path(__file__).parent.parent / "configs" / "pipelines"

        self._cache: Dict[str, PipelineConfig] = {}

    def load(self, provider: str, refresh: bool = False) -> PipelineConfig:
        """
        Load pipeline configuration for a provider.

        Args:
            provider: Provider name (e.g., "alpha_vantage", "bls", "chicago")
            refresh: If True, reload from disk even if cached

        Returns:
            PipelineConfig with all settings

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not refresh and provider in self._cache:
            return self._cache[provider]

        config_path = self.config_dir / f"{provider}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"Pipeline config not found: {config_path}. "
                f"Available: {self.list_providers()}"
            )

        logger.debug(f"Loading pipeline config: {config_path}")

        with open(config_path, 'r') as f:
            raw = yaml.safe_load(f)

        config = self._parse_config(provider, raw)
        self._cache[provider] = config
        return config

    def _parse_config(self, provider: str, raw: Dict) -> PipelineConfig:
        """Parse raw YAML dict into PipelineConfig."""
        # API settings
        api = raw.get('api', {})
        base_url = api.get('base_url', '')
        credentials = api.get('credentials', {})
        rate_limit_cfg = api.get('rate_limit', {})
        headers = api.get('headers', {})

        # Pipeline settings
        pipeline = raw.get('pipeline', {})

        # Parse data types
        data_types = {}
        for name, dt_raw in raw.get('data_types', {}).items():
            data_types[name] = DataTypeConfig(
                name=name,
                description=dt_raw.get('description', ''),
                endpoint=dt_raw.get('endpoint'),
                series_id=dt_raw.get('series_id'),
                facet=dt_raw.get('facet'),
                bronze_table=dt_raw.get('bronze_table'),
                enabled=dt_raw.get('enabled', True)
            )

        # Parse endpoints
        endpoints = {}
        for name, ep_raw in raw.get('endpoints', {}).items():
            endpoints[name] = EndpointConfig(
                name=name,
                method=ep_raw.get('method', 'GET'),
                function=ep_raw.get('function'),
                path=ep_raw.get('path'),
                required_params=ep_raw.get('required_params', []),
                default_params=ep_raw.get('default_params', {}),
                response_key=ep_raw.get('response_key'),
                pagination=ep_raw.get('pagination'),
                format=ep_raw.get('format'),
                comment=ep_raw.get('comment', '')
            )

        # Parse progress config
        progress_raw = raw.get('progress', {})
        progress = ProgressConfig(
            show_batch_header=progress_raw.get('show_batch_header', True),
            show_ticker_status=progress_raw.get('show_ticker_status', True),
            show_eta=progress_raw.get('show_eta', True),
            data_type_short_names=progress_raw.get('data_type_short_names', {})
        )

        return PipelineConfig(
            provider=provider,
            description=raw.get('description', ''),
            version=raw.get('version', '1.0'),
            base_url=base_url,
            credentials_env_var=credentials.get('env_var', ''),
            rate_limit=rate_limit_cfg.get('calls_per_second', 1.0),
            headers=headers,
            batch_size=pipeline.get('batch_size', 20),
            batch_write_size=pipeline.get('batch_write_size', 20),
            max_retries=pipeline.get('max_retries', 3),
            retry_delay_seconds=pipeline.get('retry_delay_seconds', 2.0),
            strategy=pipeline.get('strategy', 'per_ticker'),
            data_types=data_types,
            endpoints=endpoints,
            progress=progress,
            extra={
                'us_exchanges': api.get('us_exchanges', []),
                'notes': raw.get('notes', {}),
            }
        )

    def list_providers(self) -> List[str]:
        """List available pipeline providers."""
        if not self.config_dir.exists():
            return []

        return [
            p.stem for p in self.config_dir.glob("*.yaml")
            if not p.name.startswith('_')
        ]

    def load_all(self) -> Dict[str, PipelineConfig]:
        """Load all available pipeline configurations."""
        configs = {}
        for provider in self.list_providers():
            try:
                configs[provider] = self.load(provider)
            except Exception as e:
                logger.warning(f"Failed to load config for {provider}: {e}")
        return configs


# Convenience function
def load_pipeline_config(provider: str) -> PipelineConfig:
    """
    Load pipeline configuration for a provider.

    Args:
        provider: Provider name (e.g., "alpha_vantage")

    Returns:
        PipelineConfig
    """
    loader = PipelineConfigLoader()
    return loader.load(provider)


# Module-level singleton loader
_loader: Optional[PipelineConfigLoader] = None


def get_pipeline_loader() -> PipelineConfigLoader:
    """Get singleton pipeline config loader."""
    global _loader
    if _loader is None:
        _loader = PipelineConfigLoader()
    return _loader
