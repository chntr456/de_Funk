---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: time_series_daily_adjusted

# API Configuration
endpoint_pattern: ""
method: GET
format: json
auth: inherit
response_key: "Time Series (Daily)"

# Query Parameters
default_query:
  function: TIME_SERIES_DAILY_ADJUSTED
  outputsize: full
  datatype: json
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Metadata
domain: securities
legal_entity_type: vendor
subject_entity_tags: [corporate]
data_tags: [time-series, daily, prices, ohlcv]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Full history (20+ years) in single call with outputsize=full"

# Bronze Layer Configuration
bronze:
  table: securities_prices_daily
  partitions: []
  write_strategy: append
  key_columns: [ticker, trade_date]
  date_column: trade_date
  comment: "Daily OHLCV with split/dividend adjustments - append for immutable time-series"
---

## Description

Daily OHLCV (Open, High, Low, Close, Volume) price data with split and dividend adjustments. Returns up to 20+ years of historical data in a single API call when `outputsize=full`.

This is the primary source for the `stocks` Silver model's `fact_stock_prices` table.

## Schema

```yaml
# Format: [field_name, type, source_field, nullable, description]
schema:
  - [trade_date, date, _key, false, "Trading date (from response dict key)"]
  - [ticker, string, _param, false, "Stock ticker (from request param)"]
  - [asset_type, string, _generated, false, "Asset type (stocks)"]
  - [year, int, _generated, false, "Year extracted from trade_date"]
  - [month, int, _generated, false, "Month extracted from trade_date"]
  - [open, double, "1. open", true, "Opening price"]
  - [high, double, "2. high", true, "High price"]
  - [low, double, "3. low", true, "Low price"]
  - [close, double, "4. close", true, "Closing price (unadjusted)"]
  - [volume, double, "6. volume", true, "Trading volume"]
  - [volume_weighted, double, _calculated, true, "VWAP approximation: (H+L+C)/3"]
  - [transactions, long, _na, true, "Not available from Alpha Vantage"]
  - [otc, boolean, _na, false, "Not available, defaults to false"]
  - [adjusted_close, double, "5. adjusted close", true, "Split/dividend adjusted close"]
  - [dividend_amount, double, "7. dividend amount", true, "Dividend amount on ex-date"]
  - [split_coefficient, double, "8. split coefficient", true, "Stock split ratio"]
```

## Request Notes

- **outputsize**: `compact` (100 days) or `full` (20+ years) - default to `full`
- **Response format**: Nested dict with date strings as keys
- **Date format**: `YYYY-MM-DD` (ISO 8601)
- **Adjusted close**: Pre-adjusted for splits and dividends

### Example Response

```json
{
  "Time Series (Daily)": {
    "2024-01-15": {
      "1. open": "185.00",
      "2. high": "187.50",
      "3. low": "184.25",
      "4. close": "186.75",
      "5. adjusted close": "186.75",
      "6. volume": "52341200",
      "7. dividend amount": "0.0000",
      "8. split coefficient": "1.0"
    }
  }
}
```

## Homelab Usage

```bash
# Ingest daily prices for top 100 tickers
python -m scripts.ingest.run_bronze_ingestion --endpoints time_series_daily_adjusted --max-tickers 100

# Incremental update (only recent data)
python -m scripts.ingest.run_bronze_ingestion --endpoints time_series_daily_adjusted --outputsize compact
```

## Known Quirks

1. **All values are strings**: Must convert to numeric types during transformation
2. **No VWAP**: Calculate approximation as `(high + low + close) / 3`
3. **No transactions count**: Set to NULL in Bronze
4. **Date as dict key**: Requires flattening nested structure during normalization
5. **Full history is large**: 20+ years per ticker - watch memory during bulk ingestion
6. **Weekend/holiday gaps**: No data for non-trading days (expected)
