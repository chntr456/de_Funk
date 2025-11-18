"""
Alpha Vantage Data Provider

Provides stock market data from Alpha Vantage API:
- Company fundamentals (OVERVIEW)
- Daily/intraday time series (TIME_SERIES_DAILY, TIME_SERIES_INTRADAY)
- Technical indicators (SMA, RSI, MACD, etc.)
- Forex, crypto, and commodities

API Key Required:
Set ALPHA_VANTAGE_API_KEYS environment variable with your API key(s).
Free tier: 25 requests/day, 5 requests/minute
Premium tiers available with higher limits.

Key Features:
- Maps to unified bronze schema (securities_reference, securities_prices_daily)
- Compatible with v2.0 modular model architecture
- Supports stocks, ETFs, and other asset types
- Split/dividend adjusted prices available

Limitations:
- No CIK field (use Polygon or SEC EDGAR for company identifiers)
- Lower rate limits compared to Polygon
- No bulk ticker endpoints (one call per ticker)
- No VWAP data (calculated as approximation)

Usage:
    from datapipelines.providers.alpha_vantage import AlphaVantageIngestor

    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=config.apis['alpha_vantage'],
        storage_cfg=config.storage,
        spark=spark_session
    )

    # Ingest reference data
    ingestor.ingest_reference_data(tickers=['AAPL', 'MSFT'])

    # Ingest prices
    ingestor.ingest_prices(
        tickers=['AAPL', 'MSFT'],
        date_from='2024-01-01',
        date_to='2024-12-31'
    )
"""

from .alpha_vantage_ingestor import AlphaVantageIngestor
from .alpha_vantage_registry import AlphaVantageRegistry

__all__ = [
    'AlphaVantageIngestor',
    'AlphaVantageRegistry',
]
