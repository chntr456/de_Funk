"""
Data Ingestors - Bronze layer data writing utilities.

The main ingestor pattern now uses:
- BaseProvider + IngestorEngine (from datapipelines.base)
- BronzeSink for writing to Delta Lake

This module contains:
- BronzeSink: Writes DataFrames to Bronze layer with Delta Lake support
"""
from datapipelines.ingestors.bronze_sink import BronzeSink

__all__ = ['BronzeSink']
