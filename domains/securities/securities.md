---
type: domain-model
model: securities
version: 3.0
description: "Master securities domain - unified dimension and prices for all tradable instruments"
tags: [securities, master, unified]

# Dependencies - securities requires temporal for date_id FK pattern
depends_on: [temporal]

# Storage
storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      listing_status: alpha_vantage/listing_status  # All tickers from LISTING_STATUS
      time_series_daily_adjusted: alpha_vantage/time_series_daily_adjusted  # Daily OHLCV
  silver:
    root: storage/silver/securities

# Build
build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true

# Tables
tables:
  dim_security:
    type: dimension
    description: "Master security dimension for ALL tradable instruments (stocks, ETFs, options, futures)"
    primary_key: [security_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys
      - [security_id, integer, false, "PK - Integer surrogate: ABS(HASH(ticker))"]
      - [ticker, string, false, "Natural key - trading symbol", {unique: true}]

      # Core attributes
      - [security_name, string, true, "Display name"]
      - [asset_type, string, false, "Security type", {enum: [stocks, etf, option, future, warrant, unit, rights]}]
      - [exchange_code, string, true, "Primary exchange (NYSE, NASDAQ, etc.)"]
      - [currency, string, true, "Trading currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently trading", {default: true}]

      # Listing metadata
      - [ipo_date, date, true, "IPO or listing date"]
      - [delisting_date, date, true, "Delisting date (if inactive)"]

    measures:
      - [security_count, count_distinct, security_id, "Number of securities", {format: "#,##0"}]
      - [active_securities, expression, "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)", "Active securities", {format: "#,##0"}]

  fact_security_prices:
    type: fact
    description: "Unified OHLCV price data for ALL securities (partitioned by asset_type for efficiency)"
    primary_key: [price_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [price_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Asset type for partition pruning
      - [asset_type, string, false, "Asset type for partition pruning"]

      # Price data (from bronze)
      - [open, double, true, "Opening price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, false, "Closing price"]
      - [volume, long, true, "Trading volume"]
      - [adjusted_close, double, true, "Split/dividend adjusted close"]

    measures:
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
      - [max_high, max, high, "Maximum high price", {format: "$#,##0.00"}]
      - [min_low, min, low, "Minimum low price", {format: "$#,##0.00"}]
      - [price_range, expression, "AVG(high - low)", "Average price range", {format: "$#,##0.00"}]
      - [trading_days, count_distinct, date_id, "Number of trading days", {format: "#,##0"}]

# Graph
graph:
  nodes:
    dim_security:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      description: "Master security dimension from LISTING_STATUS (all US tickers)"
      select:
        ticker: ticker
        security_name: security_name
        exchange_code: exchange_code
        asset_type: asset_type
        ipo_date: ipo_date
        delisting_date: delisting_date
      derive:
        security_id: "ABS(HASH(ticker))"
        currency: "'USD'"
        is_active: "delisting_date IS NULL"
      primary_key: [security_id]
      unique_key: [ticker]
      tags: [dim, master, security]

    fact_security_prices:
      from: bronze.alpha_vantage.time_series_daily_adjusted
      type: fact
      description: "Unified OHLCV prices for all securities"
      filter_by_dimension: dim_security
      select:
        ticker: ticker
        trade_date: trade_date
        open: open
        high: high
        low: low
        close: close
        volume: volume
        adjusted_close: adjusted_close
      filters:
        - "trade_date IS NOT NULL"
        - "ticker IS NOT NULL"
      derive:
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(REGEXP_REPLACE(CAST(trade_date AS STRING), '-', '') AS INT)"
        price_id: "ABS(HASH(CONCAT(ticker, '_', CAST(trade_date AS STRING))))"
        # Get asset_type from dim_security via lookup (or default to 'stocks')
        asset_type: "'stocks'"  # Will be enriched via join to dim_security
      drop: [ticker, trade_date]
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, prices, unified]

  edges:
    prices_to_security:
      from: fact_security_prices
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: fact_security_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    # Cross-model edges for auto-join traversal
    # These allow queries on securities to reach stock/company dimensions
    security_to_stock:
      from: dim_security
      to: stocks.dim_stock
      on: [security_id=security_id]
      type: one_to_one
      optional: true  # Not all securities are stocks

    security_to_company:
      from: dim_security
      to: company.dim_company
      on: [security_id=company_id]  # Derived: company_id = HASH('COMPANY_' + ticker)
      type: many_to_one
      optional: true
      description: "Cross-model edge for sector/industry lookup via company.dim_company"

  paths:
    security_prices_by_date:
      description: "Navigate from calendar to prices to security"
      steps:
        - {from: temporal.dim_calendar, to: fact_security_prices, via: date_id}
        - {from: fact_security_prices, to: dim_security, via: security_id}

    prices_to_stock:
      description: "Navigate from prices to stock dimension for ticker/sector/industry"
      steps:
        - {from: fact_security_prices, to: dim_security, via: security_id}
        - {from: dim_security, to: stocks.dim_stock, via: security_id}

    prices_to_company:
      description: "Navigate from prices to company for sector/industry (via stock)"
      steps:
        - {from: fact_security_prices, to: dim_security, via: security_id}
        - {from: dim_security, to: stocks.dim_stock, via: security_id}
        - {from: stocks.dim_stock, to: company.dim_company, via: company_id}

# Metadata
metadata:
  domain: securities
  owner: data_engineering
  sla_hours: 4
status: active
---

## Securities Model

**Master domain for all tradable instruments.**

This is the normalized foundation that all security-type models reference:
- `stocks` → FK to `dim_security`
- `etfs` → FK to `dim_security`
- `options` → FK to `dim_security`
- `futures` → FK to `dim_security`

### Architecture

```
┌─────────────────────────────────────────────────┐
│              dim_security (MASTER)               │
│  security_id | ticker | asset_type | exchange   │
├─────────────────────────────────────────────────┤
│        ↑                    ↑                    │
│   dim_stock              dim_etf                 │
│   (stock_id,             (etf_id,               │
│    security_id FK,        security_id FK,       │
│    company_id FK,         nav, expense_ratio)   │
│    shares_outstanding)                          │
├─────────────────────────────────────────────────┤
│              fact_security_prices               │
│  price_id | security_id | date_id | OHLCV      │
│  (UNIFIED for all asset types)                 │
└─────────────────────────────────────────────────┘
```

### Integer Keys

| Key | Type | Derivation |
|-----|------|------------|
| `security_id` | integer | `ABS(HASH(ticker))` |
| `date_id` | integer | `YYYYMMDD` format |
| `price_id` | integer | `ABS(HASH(ticker + date))` |

### Cross-Asset Queries

With unified prices, cross-asset analysis is simple:

```sql
-- Compare stock vs ETF performance
SELECT
    s.ticker,
    s.asset_type,
    AVG(p.close) as avg_price,
    SUM(p.volume) as total_volume
FROM fact_security_prices p
JOIN dim_security s ON p.security_id = s.security_id
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
WHERE c.year = 2025
  AND s.asset_type IN ('stocks', 'etf')
GROUP BY s.ticker, s.asset_type
```

### Data Sources

| Table | Source | Description |
|-------|--------|-------------|
| dim_security | LISTING_STATUS | All US tickers (~12,499) |
| fact_security_prices | TIME_SERIES_DAILY | Unified OHLCV |

### Build Order

```
temporal → securities → company → stocks → [etfs, options, futures]
```

Securities must build BEFORE stocks/etfs/etc. since they FK to `dim_security`.
