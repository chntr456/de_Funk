---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: historical_options

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: data

# Query Parameters
default_query:
  function: HISTORICAL_OPTIONS
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [options, time-series, greeks, derivatives]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Premium endpoint - requires paid subscription"

# Bronze Layer Configuration
bronze:
  table: historical_options
  partitions: [underlying_ticker, expiration_date]
  write_strategy: upsert
  key_columns: [contract_id, trade_date]
  date_column: trade_date
  comment: "Historical options chain with Greeks"
---

## Description

Historical options chain data including strike prices, expiration dates, bid/ask spreads, Greeks (delta, gamma, theta, vega), and implied volatility.

**Premium Endpoint**: Requires paid Alpha Vantage subscription.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
schema:
  - [contract_id, string, contractID, false, "Unique option contract ID"]
  - [underlying_ticker, string, symbol, false, "Underlying stock ticker"]
  - [trade_date, date, date, false, "Trading date"]
  - [expiration_date, date, expiration, false, "Option expiration date"]
  - [strike, double, strike, false, "Strike price"]
  - [option_type, string, type, false, "call or put"]
  - [last_price, double, last, true, "Last traded price"]
  - [mark, double, mark, true, "Mark price (mid)"]
  - [bid, double, bid, true, "Bid price"]
  - [ask, double, ask, true, "Ask price"]
  - [volume, long, volume, true, "Trading volume"]
  - [open_interest, long, open_interest, true, "Open interest"]
  - [implied_volatility, double, implied_volatility, true, "Implied volatility"]
  - [delta, double, delta, true, "Delta Greek"]
  - [gamma, double, gamma, true, "Gamma Greek"]
  - [theta, double, theta, true, "Theta Greek (time decay)"]
  - [vega, double, vega, true, "Vega Greek (volatility sensitivity)"]
  - [rho, double, rho, true, "Rho Greek (interest rate sensitivity)"]
```

## Request Notes

- Returns full options chain for specified underlying
- Optional `date` parameter for historical snapshots
- Greeks calculated using Black-Scholes model

## Homelab Usage

```bash
# Ingest options for specific underlyings
python -m scripts.ingest.run_bronze_ingestion --endpoints historical_options --tickers AAPL SPY
```

## Known Quirks

1. **Premium only**: Requires paid subscription
2. **Large responses**: Full chain can be thousands of contracts
3. **Greeks freshness**: Greeks recalculated at market close
4. **Expiration cycles**: Weekly and monthly expirations included
5. **Historical depth**: Depends on subscription tier
