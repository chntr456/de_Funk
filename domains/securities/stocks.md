---
type: domain-model
model: stocks
version: 3.0
description: "Common stock equities with price data and technical indicators"
tags: [stocks, equities, securities]

# Inheritance and Dependencies
extends: _base.finance.securities
depends_on: [temporal, corporate]

# Storage
storage:
  root: storage/silver/stocks
  format: delta

# Build
build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true

# Tables
tables:
  dim_stock:
    type: dimension
    extends: _base.finance.securities.dim_security
    description: "Stock equity dimension with company linkage"
    primary_key: [stock_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [stock_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: _base.finance.securities.dim_security.security_id}]
      - [company_id, integer, false, "FK to dim_company", {fk: corporate.dim_company.company_id}]

      # Inherited from base (for reference)
      - [ticker, string, false, "Natural key - trading symbol", {unique: true}]

      # Stock-specific attributes
      - [cik, string, true, "SEC Central Index Key", {pattern: "^[0-9]{10}$", transform: "zfill(10)"}]
      - [stock_type, string, true, "Type of stock", {enum: [common, preferred, adr, rights, units, warrants], default: "common"}]
      - [shares_outstanding, long, true, "Current shares outstanding", {coerce: long}]
      - [market_cap, double, true, "Market capitalization", {coerce: double}]
      - [sector, string, true, "GICS Sector"]
      - [industry, string, true, "GICS Industry"]

    # Measures on the table
    measures:
      - [stock_count, count_distinct, stock_id, "Number of stocks", {format: "#,##0"}]
      - [avg_market_cap, avg, market_cap, "Average market cap", {format: "$#,##0.00B"}]
      - [total_market_cap, sum, market_cap, "Total market cap", {format: "$#,##0.00B"}]
      - [avg_shares, avg, shares_outstanding, "Average shares outstanding", {format: "#,##0.00M"}]

  fact_stock_prices:
    type: fact
    extends: _base.finance.securities._fact_prices_base
    description: "Daily stock prices with technical indicators"
    primary_key: [price_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    # NOTE: Technical indicators are computed post-build by scripts/build/compute_technicals.py
    schema:
      # Keys - all integers (NO trade_date column - use date_id)
      - [price_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Inherited from base: open, high, low, close, volume, adjusted_close
      # Inherited technicals: sma_20, sma_50, sma_200, rsi_14, bollinger_*, volatility_*, volume_sma_20, volume_ratio

    # Measures on the table (inherits base measures + stock-specific)
    measures:
      # Inherited: avg_close, total_volume, max_high, min_low, price_range, intraday_return
      # Inherited: avg_rsi, avg_volatility, overbought_days, oversold_days
      - [avg_dollar_volume, expression, "AVG(close * volume)", "Average dollar volume", {format: "$#,##0.00M"}]
      - [golden_cross_days, expression, "SUM(CASE WHEN sma_50 > sma_200 THEN 1 ELSE 0 END)", "Days with Golden Cross (SMA50 > SMA200)", {format: "#,##0"}]
      - [death_cross_days, expression, "SUM(CASE WHEN sma_50 < sma_200 THEN 1 ELSE 0 END)", "Days with Death Cross (SMA50 < SMA200)", {format: "#,##0"}]

# Graph
graph:
  extends: _base.finance.securities.graph

  nodes:
    dim_stock:
      from: bronze.company_reference
      type: dimension
      # Note: company_reference_facet normalizes to snake_case columns
      select:
        ticker: ticker
        cik: cik
        market_cap: market_cap
        sector: sector
        industry: industry
      derive:
        stock_id: "ABS(HASH(CONCAT('STOCK_', ticker)))"
        security_id: "ABS(HASH(ticker))"
        company_id: "ABS(HASH(CONCAT('COMPANY_', COALESCE(cik, ticker))))"
      primary_key: [stock_id]
      unique_key: [ticker]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: company_id, references: corporate.dim_company.company_id}
      tags: [dim, stock]

    fact_stock_prices:
      extends: _base.finance.securities._fact_prices_base
      filter_by_dimension: dim_stock
      filters:
        - "trade_date IS NOT NULL"
        - "ticker IS NOT NULL"
      derive:
        price_id: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, prices, stocks]

    # NOTE: Technical indicators are computed post-build by StocksBuilder.post_build()
    # and added as columns to fact_stock_prices. There is no separate technicals table.

  edges:
    stock_to_security:
      from: dim_stock
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one

    stock_to_company:
      from: dim_stock
      to: corporate.dim_company
      on: [company_id=company_id]
      type: many_to_one

    prices_to_stock:
      from: fact_stock_prices
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: fact_stock_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

  paths:
    company_to_prices:
      description: "Enable company filter to prices"
      steps:
        - {from: corporate.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_stock_prices, via: security_id}

# Metadata
metadata:
  domain: securities
  owner: data_engineering
  sla_hours: 4
status: active
---

## Stocks Model

Common stock equities with daily prices and technical indicators.

### Integer Keys

All keys are integers for storage efficiency:

| Key | Type | Derivation |
|-----|------|------------|
| `stock_id` | integer | `HASH('STOCK_' + ticker)` |
| `security_id` | integer | `HASH(ticker)` |
| `company_id` | integer | `HASH('COMPANY_' + cik)` |
| `date_id` | integer | `YYYYMMDD` format |
| `price_id` | integer | `HASH(ticker + date)` |

### No trade_date Column

Prices have `date_id` FK, not `trade_date`:

```sql
-- Get prices with technicals and actual dates (all on same table)
SELECT
    c.date AS trade_date,
    c.day_of_week_name,
    s.ticker,
    p.close,
    p.volume,
    p.rsi_14,
    p.sma_50,
    p.sma_200
FROM fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
JOIN dim_stock s ON p.security_id = s.security_id
WHERE c.year = 2025
  AND c.is_trading_day = true
  AND s.ticker = 'AAPL'
```

### Technical Indicators

Technical indicators are **computed columns** on `fact_stock_prices`, not a separate table.
They are calculated during the build process by `StocksBuilder.post_build()`.

**Moving Averages:**
- SMA (20, 50, 200 day)

**Returns & Volatility:**
- Daily return percentage
- 20-day and 60-day annualized volatility

**Momentum:**
- RSI (14 day)

**Bollinger Bands:**
- Upper, Middle, Lower (20 day, 2 std dev)

**Volume:**
- 20-day volume SMA
- Volume ratio (current/SMA)

### Build Workflow

1. `StocksBuilder.build()` creates `dim_stock` and `fact_stock_prices` with OHLCV data
2. `StocksBuilder.post_build()` computes technical indicators in batches
3. Technical columns are added to `fact_stock_prices`

### Data Sources

| Source | Provider |
|--------|----------|
| company_reference | Alpha Vantage |
| securities_prices_daily | Alpha Vantage |

### Notes

- Inherits OHLCV schema from `_base.finance.securities`
- Technical indicators are computed columns, not a separate table
- Company linkage via integer `company_id`
- All date filtering through `dim_calendar` join
