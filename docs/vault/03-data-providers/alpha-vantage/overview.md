# Alpha Vantage Overview

**Securities market data provider for stocks, options, ETFs, and company fundamentals**

---

## Summary

| Property | Value |
|----------|-------|
| **Provider** | Alpha Vantage |
| **Website** | https://www.alphavantage.co |
| **Data Types** | Stocks, Options, ETFs, Forex, Crypto |
| **Status** | v2.0 sole securities provider |
| **Replaced** | Polygon.io (removed in v2.0) |

---

## Capabilities

### Data Available

| Data Type | Endpoints | de_Funk Usage |
|-----------|-----------|---------------|
| **Company Fundamentals** | OVERVIEW | Company info, CIK, sector, industry |
| **Daily Prices** | TIME_SERIES_DAILY_ADJUSTED | OHLCV with adjustments |
| **Real-time Quotes** | GLOBAL_QUOTE | Latest price |
| **Ticker Discovery** | LISTING_STATUS | Bulk ticker list (1 API call!) |
| **Technical Indicators** | SMA, RSI, MACD | Technical analysis |
| **Symbol Search** | SYMBOL_SEARCH | Company lookup |

### Key Features

- **CIK Integration**: Company fundamentals include SEC Central Index Key
- **Bulk Discovery**: LISTING_STATUS returns all tickers in one call
- **Adjusted Prices**: Split and dividend adjusted OHLCV
- **Technical Indicators**: Built-in SMA, RSI, MACD endpoints
- **20+ Years History**: Full historical data available

---

## de_Funk Integration

### Bronze Tables Generated

| Table | Source Endpoint | Partitions |
|-------|-----------------|------------|
| `securities_reference` | OVERVIEW | snapshot_dt, asset_type |
| `securities_prices_daily` | TIME_SERIES_DAILY_ADJUSTED | asset_type, year, month |

### Facets Implemented

| Facet | Purpose | Output |
|-------|---------|--------|
| `SecuritiesReferenceFacetAV` | Company fundamentals | 50+ columns with CIK |
| `SecuritiesPricesFacetAV` | Daily OHLCV | OHLCV + adjusted close |

### Pipeline Flow

```
Alpha Vantage API
    ↓
AlphaVantageIngestor
    ↓
┌─────────────────────────┬─────────────────────────┐
│ SecuritiesReferenceFacet│ SecuritiesPricesFacet   │
│ (OVERVIEW endpoint)     │ (TIME_SERIES endpoint)  │
└───────────┬─────────────┴───────────┬─────────────┘
            ↓                         ↓
    securities_reference      securities_prices_daily
         (Bronze)                   (Bronze)
```

---

## Data Quality

### Strengths
- Official SEC identifiers (CIK)
- Dividend-adjusted prices
- Comprehensive company fundamentals
- Active US exchange coverage

### Limitations
- Free tier rate limits (5/min)
- One ticker per API call (no batching)
- Some international data limited
- Options data requires separate endpoint

---

## In This Section

| Document | Purpose |
|----------|---------|
| [Terms of Use](terms-of-use.md) | Usage restrictions (no commercial use) |
| [API Reference](api-reference.md) | Endpoints and parameters |
| [Rate Limits](rate-limits.md) | Throttling and optimization |
| [Facets](facets.md) | Data transformation details |
| [Bronze Tables](bronze-tables.md) | Output schemas |

---

## Quick Start

### Get API Key

1. Visit https://www.alphavantage.co/support/#api-key
2. Sign up for free API key
3. Add to `.env`:

```bash
ALPHA_VANTAGE_API_KEYS=your_key_here
```

### Run Ingestion

```bash
# Ingest stock data for top N tickers
python -m scripts.ingest.run_full_pipeline --top-n 100
```

---

## Related Documentation

- [Data Providers Overview](../README.md)
- [Pipelines](../../06-pipelines/README.md)
- [Stocks Model](../../04-implemented-models/stocks/)
