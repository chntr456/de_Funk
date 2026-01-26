"""
Base classes and utilities for data pipelines.

This module provides the foundational components for building data ingestion
pipelines. It includes:
- Facet: Base class for data transformation
- Provider: Abstract interface for data sources (config loaded from markdown)
- SocrataBaseProvider: Base class for Socrata API providers
- IngestorEngine: Generic ingestion engine
- HTTP utilities: Rate limiting, key rotation, progress tracking
"""
from de_funk.pipelines.base.facet import Facet, coalesce_existing, first_existing
from de_funk.pipelines.base.http_client import HttpClient
from de_funk.pipelines.base.key_pool import ApiKeyPool
from de_funk.pipelines.base.progress_tracker import (
    PipelineProgressTracker,
    PhaseProgress,
    PipelineStats,
    TickerProgressCallback,
    ProgressBar,
    BatchProgressTracker,
    format_duration,
    format_eta
)
from de_funk.pipelines.base.metrics import MetricsCollector, TimingContext
from de_funk.pipelines.base.provider import (
    BaseProvider,
    DataType,
    FetchResult,
    WorkItemResult,
)
from de_funk.pipelines.base.socrata_provider import SocrataBaseProvider
from de_funk.pipelines.base.ingestor_engine import IngestorEngine, IngestionResults, create_engine

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
    'SocrataBaseProvider',
    'DataType',
    'FetchResult',
    'WorkItemResult',
    # Ingestor Engine
    'IngestorEngine',
    'IngestionResults',
    'create_engine',
]
