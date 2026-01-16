---
type: api-provider
provider_id: alpha_vantage
provider: Alpha Vantage

# API Configuration
api_type: rest
base_url: https://www.alphavantage.co/query
homepage: https://www.alphavantage.co/documentation/

# Authentication
auth_model: api-key
env_api_key: ALPHA_VANTAGE_API_KEYS

# Rate Limiting
rate_limit_per_sec: 1.0
rate_limit_comment: "Conservative: 60/min (1.0/sec) - headroom below premium 75/min. Free tier: 5/min (0.0833/sec), 25/day"

# Default Headers (API key passed as query param, not header)
default_headers: {}

# Provider-specific settings
provider_settings:
  ticker_source: seed
  ticker_source_options: [market_cap, seed]
  ticker_source_comment: "How to select tickers: 'market_cap' = ranked by market cap from company_reference, 'seed' = use ticker_seed table"
  us_exchanges: [NYSE, NASDAQ, NYSEAMERICAN, NYSEMKT, BATS, NYSEARCA]
  us_exchanges_comment: "Filter to US exchanges for company data. Foreign exchanges may lack OVERVIEW data."

# Endpoints to ingest (configured in run_config.json)
endpoints:
  - time_series_daily
  - company_overview
  - income_statement
  - balance_sheet
  - cash_flow
  - earnings
endpoints_comment: "Available: time_series_daily, time_series_daily_adjusted, company_overview, global_quote, income_statement, balance_sheet, cash_flow, earnings"

# Models Fed (Silver layer)
models:
  - stocks
  - company
  - options
  - etf

# Metadata
category: commercial
legal_entity_type: vendor
data_domains: [securities, fundamentals, technicals, options]
data_tags: [time-series, daily, market-data, reference]
status: active
bulk_download: false
last_verified:
last_reviewed:
notes:
---

## Description

Alpha Vantage provides stock market data including real-time and historical prices, company fundamentals (income statements, balance sheets, cash flows), technical indicators, options chains, and ETF profiles. It is the sole securities provider for de_Funk v2.0+.

## API Notes

- **Single Base URL**: All endpoints use query parameter differentiation (`function=OVERVIEW`, `function=TIME_SERIES_DAILY`, etc.)
- **API Key**: Passed as `apikey` query parameter (not header)
- **Response Format**: JSON by default, some endpoints return CSV (listing_status, earnings_calendar)
- **Error Handling**: Errors don't use HTTP status codes - check for `"Error Message"` key in JSON response

### Rate Limits

| Tier | Calls/Minute | Calls/Day | Cost |
|------|--------------|-----------|------|
| Free | 5 | 25 | $0 |
| Premium | 75 | Unlimited | ~$50/mo |

### Key Endpoints by Category

| Category | Endpoints | Bronze Tables |
|----------|-----------|---------------|
| Core | company_overview, listing_status, global_quote | company_reference, securities_reference |
| Prices | time_series_daily, time_series_daily_adjusted | securities_prices_daily |
| Fundamentals | income_statement, balance_sheet, cash_flow, earnings | income_statements, balance_sheets, cash_flows, earnings |
| Options | historical_options, realtime_options | historical_options |
| ETFs | etf_profile | etf_profiles |
| Technical | technical_sma, technical_rsi, technical_macd | (computed on demand) |

## Homelab Usage Notes

- **Ingestion Cadence**: Daily for prices, weekly for fundamentals
- **Ticker Discovery**: Use `listing_status` endpoint first to get all active US tickers
- **CIK Extraction**: OVERVIEW endpoint provides SEC CIK for company linkage
- **Retry Strategy**: Exponential backoff on rate limit errors (429-equivalent in JSON)

## Known Quirks

1. **Numeric Fields as Strings**: Many numeric fields returned as strings, including `"None"` for nulls
2. **No Bulk Endpoints**: One API call per ticker for most endpoints (no batch)
3. **OVERVIEW Gaps**: Non-US tickers often missing OVERVIEW data
4. **CSV Endpoints**: `listing_status` and `earnings_calendar` return CSV, not JSON
5. **AssetType Values**: Returns "Common Stock", "ETF", "Mutual Fund" (needs mapping)
6. **Rate Limit Response**: Returns JSON with error message, not HTTP 429
