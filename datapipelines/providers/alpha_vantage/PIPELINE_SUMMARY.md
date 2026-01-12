# Alpha Vantage Pipeline Summary

**Provider ID:** `alpha_vantage`
**Status:** Active (v2.0+ sole securities provider)
**API Type:** REST
**Base URL:** `https://www.alphavantage.co/query`

---

## Overview

Alpha Vantage provides stock market data including real-time and historical prices, company fundamentals, technical indicators, and options chains. It is the exclusive securities data provider for de_Funk v2.0+.

## Rate Limits

| Tier | Calls/Minute | Calls/Day | Cost |
|------|--------------|-----------|------|
| Free | 5 | 25 | $0 |
| Premium | 75 | Unlimited | ~$50/mo |

**Configured Rate:** 1.25 req/sec (headroom below Premium 75/min)

## Authentication

- **Method:** API key as query parameter (`apikey=YOUR_KEY`)
- **Environment Variable:** `ALPHA_VANTAGE_API_KEYS`
- **Location:** `.env` file

---

## Endpoints

| Endpoint ID | Description | Bronze Table | Status |
|-------------|-------------|--------------|--------|
| `listing_status` | All active US tickers | `securities_reference` | Active |
| `company_overview` | Company reference data with CIK | `company_reference` | Active |
| `time_series_daily` | Historical OHLCV prices | `securities_prices_daily` | Active |
| `time_series_daily_adjusted` | Adjusted OHLCV with splits/dividends | `securities_prices_daily` | Active |
| `income_statement` | Quarterly/annual income statements | `income_statements` | Active |
| `balance_sheet` | Quarterly/annual balance sheets | `balance_sheets` | Active |
| `cash_flow` | Quarterly/annual cash flows | `cash_flows` | Active |
| `earnings` | Quarterly/annual earnings | `earnings` | Active |
| `global_quote` | Real-time quote (single ticker) | - | Available |
| `historical_options` | Historical options chains | `historical_options` | Available |
| `etf_profile` | ETF holdings and profile | `etf_profiles` | Available |

### Endpoint Details

#### Core Endpoints
- **listing_status**: Returns CSV of all active US tickers (single API call)
  - Use for ticker discovery before other endpoints
  - ~12,000+ tickers returned

- **company_overview**: Company fundamentals and reference data
  - Provides SEC CIK for company linkage
  - One call per ticker required

#### Price Endpoints
- **time_series_daily**: Full historical OHLCV data
  - Returns up to 20+ years of history
  - One call per ticker

#### Fundamental Endpoints
- All return quarterly and annual data
- One call per ticker per endpoint

---

## Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `securities_reference` | listing_status | `snapshot_dt`, `asset_type` | ticker, name, exchange, asset_type, cik |
| `company_reference` | company_overview | `snapshot_dt` | ticker, cik, sector, industry, market_cap |
| `securities_prices_daily` | time_series_daily | `trade_date`, `asset_type` | ticker, trade_date, open, high, low, close, volume |
| `income_statements` | income_statement | `fiscal_year` | ticker, fiscal_date, revenue, net_income, eps |
| `balance_sheets` | balance_sheet | `fiscal_year` | ticker, fiscal_date, total_assets, total_liabilities |
| `cash_flows` | cash_flow | `fiscal_year` | ticker, fiscal_date, operating_cf, investing_cf |
| `earnings` | earnings | `fiscal_year` | ticker, fiscal_date, reported_eps, estimated_eps |

---

## Usage

### Pipeline Configuration
In `configs/pipelines/run_config.json`:
```json
{
  "providers": {
    "alpha_vantage": {
      "enabled": true,
      "rate_limit_per_sec": 1.25,
      "endpoints": [
        "time_series_daily",
        "company_overview",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "earnings"
      ]
    }
  }
}
```

### Running Ingestion
```bash
# Via test pipeline (with dev profile)
./scripts/test/test_pipeline.sh --profile dev

# Direct ingestion
python -m scripts.ingest.run_bronze_ingestion \
  --provider alpha_vantage \
  --endpoints time_series_daily company_overview \
  --max-tickers 100
```

### Code Example
```python
from datapipelines.providers.alpha_vantage.alpha_vantage_ingestor import AlphaVantageIngestor

# Initialize
ingestor = AlphaVantageIngestor(spark, storage_cfg)

# Run comprehensive ingestion
results = ingestor.run_comprehensive(
    tickers=['AAPL', 'MSFT', 'NVDA'],
    from_date='2024-01-01',
    max_tickers=100,
    include_fundamentals=True
)
```

---

## Known Issues & Quirks

1. **Numeric Fields as Strings**: Many fields returned as strings, including `"None"` for nulls
2. **No Bulk Endpoints**: One API call per ticker (no batch operations)
3. **OVERVIEW Gaps**: Non-US tickers often missing company overview data
4. **CSV Endpoints**: `listing_status` returns CSV, not JSON
5. **Rate Limit Response**: Returns JSON error, not HTTP 429
6. **AssetType Values**: Returns "Common Stock", "ETF" (needs mapping to internal types)

---

## Models Fed

- `stocks` - Stock prices and technicals
- `company` - Corporate entities with CIK linkage
- `options` - Options chains (partial)
- `etf` - ETF profiles and holdings

---

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Prices | Daily | After market close |
| Fundamentals | Weekly | New filings irregular |
| Reference | Weekly | Ticker changes rare |
