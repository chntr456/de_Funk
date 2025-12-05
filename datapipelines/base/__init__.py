"""
Base classes and utilities for data pipelines.
"""
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.base.progress_tracker import (
    PipelineProgressTracker,
    PhaseProgress,
    PipelineStats,
    TickerProgressCallback,
    ProgressBar,
    BatchProgressTracker,
    format_duration,
    format_eta
)
from datapipelines.base.metrics import MetricsCollector, TimingContext
from datapipelines.base.provider import (
    BaseProvider,
    DataType,
    TickerData,
    FetchResult,
    ProviderConfig
)
from datapipelines.base.ingestor_engine import IngestorEngine, IngestionResults, create_engine

__all__ = [
    # HTTP and Keys
    'HttpClient',
    'ApiKeyPool',
    # Progress Tracking
    'PipelineProgressTracker',
    'PhaseProgress',
    'PipelineStats',
    'TickerProgressCallback',
    'ProgressBar',
    'BatchProgressTracker',
    'format_duration',
    'format_eta',
    # Metrics
    'MetricsCollector',
    'TimingContext',
    # Provider Interface
    'BaseProvider',
    'DataType',
    'TickerData',
    'FetchResult',
    'ProviderConfig',
    # Ingestor Engine
    'IngestorEngine',
    'IngestionResults',
    'create_engine',
]
