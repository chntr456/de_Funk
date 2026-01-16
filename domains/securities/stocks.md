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
    description: "Daily stock prices"
    primary_key: [price_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers (NO trade_date column - use date_id)
      - [price_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Inherited from base: open, high, low, close, volume, adjusted_close

    # Measures on the table (inherits base measures + stock-specific)
    measures:
      # Inherited: avg_close, total_volume, max_high, min_low, price_range, intraday_return
      - [avg_dollar_volume, expression, "AVG(close * volume)", "Average dollar volume", {format: "$#,##0.00M"}]

  fact_stock_technicals:
    type: fact
    extends: _base.finance.securities._fact_technicals_base
    description: "Daily stock technical indicators"
    primary_key: [technical_id]
    partition_by: [date_id]

    # Schema: Inherited from base
    # - Moving Averages: sma_20, sma_50, sma_200, ema_12, ema_26
    # - Momentum: rsi_14, macd, macd_signal, macd_histogram
    # - Volatility: bollinger_upper/middle/lower, atr_14
    # - Volume: obv, vwap
    # - Trend: adx_14, plus_di, minus_di

    # Stock-specific measures (in addition to base measures)
    measures:
      # Inherited: avg_rsi, avg_macd, avg_atr, overbought_days, oversold_days
      - [golden_cross_days, expression, "SUM(CASE WHEN sma_50 > sma_200 THEN 1 ELSE 0 END)", "Days with Golden Cross (SMA50 > SMA200)", {format: "#,##0"}]
      - [death_cross_days, expression, "SUM(CASE WHEN sma_50 < sma_200 THEN 1 ELSE 0 END)", "Days with Death Cross (SMA50 < SMA200)", {format: "#,##0"}]
      - [macd_bullish_days, expression, "SUM(CASE WHEN macd > macd_signal THEN 1 ELSE 0 END)", "Days MACD bullish", {format: "#,##0"}]

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

    fact_stock_technicals:
      extends: _base.finance.securities._fact_technicals_base
      filter_by_dimension: dim_stock
      filters:
        - "trade_date IS NOT NULL"
        - "ticker IS NOT NULL"
      derive:
        technical_id: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"
      primary_key: [technical_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, technicals, stocks]

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

    technicals_to_stock:
      from: fact_stock_technicals
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    technicals_to_calendar:
      from: fact_stock_technicals
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one

    technicals_to_prices:
      from: fact_stock_technicals
      to: fact_stock_prices
      on: [security_id=security_id, date_id=date_id]
      type: one_to_one
      description: "Technical indicators align with price data"

  paths:
    company_to_prices:
      description: "Enable company filter to prices"
      steps:
        - {from: corporate.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_stock_prices, via: security_id}

    company_to_technicals:
      description: "Enable company filter to technicals"
      steps:
        - {from: corporate.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_stock_technicals, via: security_id}

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
| `technical_id` | integer | `HASH(ticker + date)` |

### No trade_date Column

Prices and technicals have `date_id` FK, not `trade_date`:

```sql
-- Get prices with technicals and actual dates
SELECT
    c.date AS trade_date,
    c.day_of_week_name,
    s.ticker,
    p.close,
    p.volume,
    t.rsi_14,
    t.macd,
    t.sma_50,
    t.sma_200
FROM fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
JOIN dim_stock s ON p.security_id = s.security_id
LEFT JOIN fact_stock_technicals t ON p.security_id = t.security_id AND p.date_id = t.date_id
WHERE c.year = 2025
  AND c.is_trading_day = true
  AND s.ticker = 'AAPL'
```

### Technical Indicators

Inherited from `_base.finance.securities._fact_technicals_base`:

**Moving Averages:**
- SMA (20, 50, 200 day)
- EMA (12, 26 day)

**Momentum:**
- RSI (14 day)
- MACD (12/26/9)

**Volatility:**
- Bollinger Bands (20 day, 2 std dev)
- ATR (14 day)

**Volume:**
- OBV (On-Balance Volume)
- VWAP

**Trend:**
- ADX (14 day)
- +DI / -DI

### Data Sources

| Source | Provider |
|--------|----------|
| company_reference | Alpha Vantage |
| securities_prices_daily | Alpha Vantage |
| securities_technicals | Alpha Vantage (computed) |

### Notes

- Inherits OHLCV schema from `_base.finance.securities`
- Inherits technical indicators from `_base.finance.securities`
- Company linkage via integer `company_id`
- All date filtering through `dim_calendar` join
