"""
Base classes and utilities for data pipelines.

This module provides the foundational components for building data ingestion
pipelines. It includes:
- Facet: Base class for data transformation
- Provider: Abstract interface for data sources
- IngestorEngine: Generic ingestion engine
- HTTP utilities: Rate limiting, key rotation, progress tracking
"""
from datapipelines.base.facet import Facet, coalesce_existing, first_existing
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
from datapipelines.base.ingestor_engine import IngestorEngine, IngestionResults, IngestionError, create_engine

__all__ = [
    # Facet (Data Transformation)
    'Facet',
    'coalesce_existing',
    'first_existing',
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
    'IngestionError',
    'create_engine',
]
