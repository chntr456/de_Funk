"""
Alpha Vantage Data Provider - IngestorEngine Paradigm

Provides stock market data from Alpha Vantage API:
- Company fundamentals (OVERVIEW)
- Daily/intraday time series (TIME_SERIES_DAILY, TIME_SERIES_INTRADAY)
- Financial statements (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS)
- Technical indicators (SMA, RSI, MACD, etc.)
- Forex, crypto, and commodities

API Key Required:
Set ALPHA_VANTAGE_API_KEYS environment variable with your API key(s).
Pro tier: 75 requests/minute (1.25/sec)
Free tier: 25 requests/day, 5 requests/minute

Architecture:
- AlphaVantageProvider: Implements BaseProvider interface for data fetching
- AlphaVantageRegistry: Maps endpoints to Facet classes for transformation
- IngestorEngine: Generic engine from datapipelines.base for orchestration
- BronzeSink: Writes DataFrames to Bronze layer (Delta Lake)

Usage:
    from datapipelines.providers.alpha_vantage import (
        AlphaVantageProvider,
        create_alpha_vantage_provider,
    )
    from datapipelines.base import IngestorEngine, create_engine
    from datapipelines.ingestors import BronzeSink

    # Create provider
    provider = create_alpha_vantage_provider(config, spark=spark)

    # Option 1: Use IngestorEngine for full pipeline
    engine = create_engine(
        provider=provider,
        storage_cfg=storage_cfg,
        spark=spark
    )
    results = engine.run(tickers, data_types=[DataType.PRICES, DataType.REFERENCE])

    # Option 2: Use provider directly for custom logic
    df = provider.seed_tickers(state='active', filter_us_exchanges=True)
    sink = BronzeSink(spark, storage_cfg)
    sink.write(df, 'ticker_seed', mode='overwrite')
"""

from .alpha_vantage_provider import AlphaVantageProvider, create_alpha_vantage_provider
from .alpha_vantage_registry import AlphaVantageRegistry

__all__ = [
    'AlphaVantageProvider',
    'AlphaVantageRegistry',
    'create_alpha_vantage_provider',
]
