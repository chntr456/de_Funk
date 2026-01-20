---
type: domain-model
model: stocks
version: 3.1
description: "Stock equities with company linkage, technicals, dividends, and splits"
tags: [stocks, equities, securities]

# Dependencies - stocks depends on securities (normalized base) and corporate
depends_on: [temporal, securities, corporate]

# Storage - provider/endpoint_id for bronze, domain hierarchy for silver
storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      listing_status: alpha_vantage/listing_status  # All tickers from LISTING_STATUS
      company_overview: alpha_vantage/company_overview  # Company fundamentals
      dividends: alpha_vantage/dividends  # Dividend history (DIVIDENDS endpoint)
      splits: alpha_vantage/splits  # Stock split history (SPLITS endpoint)
  silver:
    root: storage/silver/stocks

# Build
build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true

# Tables
tables:
  dim_stock:
    type: dimension
    description: "Stock equity dimension - extends securities.dim_security with stock-specific attributes"
    primary_key: [stock_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [stock_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to securities.dim_security", {fk: securities.dim_security.security_id}]
      - [company_id, integer, true, "FK to dim_company (optional - not all stocks have company data)", {fk: corporate.dim_company.company_id}]

      # Natural key (denormalized for convenience)
      - [ticker, string, false, "Natural key - trading symbol", {unique: true}]

      # Stock-specific attributes
      - [stock_type, string, true, "Type of stock", {enum: [common, preferred, adr, rights, units, warrants], default: "common"}]

      # Stock-level attributes (MOVED from company - these are per-security, not per-company)
      - [shares_outstanding, long, true, "Current shares outstanding"]
      - [shares_float, long, true, "Shares available for trading"]
      - [market_cap, double, true, "Market capitalization"]

      # Classification (stock-level, can differ from company)
      - [sector, string, true, "GICS Sector"]
      - [industry, string, true, "GICS Industry"]

    # Measures on the table
    measures:
      - [stock_count, count_distinct, stock_id, "Number of stocks", {format: "#,##0"}]
      - [avg_market_cap, avg, market_cap, "Average market cap", {format: "$#,##0.00B"}]
      - [total_market_cap, sum, market_cap, "Total market cap", {format: "$#,##0.00B"}]
      - [avg_shares, avg, shares_outstanding, "Average shares outstanding", {format: "#,##0.00M"}]

  fact_stock_technicals:
    type: fact
    description: "Stock-specific technical indicators (computed from securities.fact_security_prices)"
    primary_key: [technical_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    # NOTE: Technical indicators are computed post-build by scripts/build/compute_technicals.py
    schema:
      # Keys - all integers
      - [technical_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Moving Averages
      - [sma_20, double, true, "20-day Simple Moving Average"]
      - [sma_50, double, true, "50-day Simple Moving Average"]
      - [sma_200, double, true, "200-day Simple Moving Average"]

      # Returns & Volatility
      - [daily_return, double, true, "Daily return percentage"]
      - [volatility_20d, double, true, "20-day annualized volatility"]
      - [volatility_60d, double, true, "60-day annualized volatility"]

      # Momentum
      - [rsi_14, double, true, "14-day Relative Strength Index"]

      # Bollinger Bands
      - [bollinger_upper, double, true, "Bollinger Band Upper"]
      - [bollinger_middle, double, true, "Bollinger Band Middle"]
      - [bollinger_lower, double, true, "Bollinger Band Lower"]

      # Volume Indicators
      - [volume_sma_20, double, true, "20-day volume SMA"]
      - [volume_ratio, double, true, "Volume ratio (current/SMA20)"]

    measures:
      - [avg_rsi, avg, rsi_14, "Average RSI", {format: "#,##0.00"}]
      - [avg_volatility, avg, volatility_20d, "Average 20-day volatility", {format: "#,##0.00%"}]
      - [overbought_days, expression, "SUM(CASE WHEN rsi_14 > 70 THEN 1 ELSE 0 END)", "Days RSI > 70", {format: "#,##0"}]
      - [oversold_days, expression, "SUM(CASE WHEN rsi_14 < 30 THEN 1 ELSE 0 END)", "Days RSI < 30", {format: "#,##0"}]
      - [golden_cross_days, expression, "SUM(CASE WHEN sma_50 > sma_200 THEN 1 ELSE 0 END)", "Days with Golden Cross", {format: "#,##0"}]

  fact_dividends:
    type: fact
    description: "Dividend distribution history (time-series per security)"
    primary_key: [dividend_id]
    partition_by: [ex_dividend_date_id]

    schema:
      # Keys
      - [dividend_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
      - [ex_dividend_date_id, integer, false, "FK to dim_calendar (ex-dividend date)", {fk: temporal.dim_calendar.date_id}]
      - [payment_date_id, integer, true, "FK to dim_calendar (payment date)", {fk: temporal.dim_calendar.date_id}]

      # Dividend data
      - [dividend_amount, double, false, "Dividend per share"]
      - [record_date, date, true, "Record date"]
      - [payment_date, date, true, "Payment date"]
      - [declaration_date, date, true, "Declaration date"]
      - [dividend_type, string, true, "Dividend type (regular, special, stock)"]

    measures:
      - [total_dividends, sum, dividend_amount, "Total dividends paid", {format: "$#,##0.00"}]
      - [avg_dividend, avg, dividend_amount, "Average dividend amount", {format: "$#,##0.00"}]
      - [dividend_count, count_distinct, dividend_id, "Number of dividend events", {format: "#,##0"}]

  fact_splits:
    type: fact
    description: "Stock split history"
    primary_key: [split_id]
    partition_by: [effective_date_id]

    schema:
      # Keys
      - [split_id, integer, false, "PK - Integer surrogate"]
      - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
      - [effective_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Split data
      - [effective_date, date, false, "Split effective date"]
      - [split_factor, double, false, "Split ratio (e.g., 4.0 for 4:1 split)"]

    measures:
      - [split_count, count_distinct, split_id, "Number of splits", {format: "#,##0"}]
      - [avg_split_ratio, avg, split_factor, "Average split ratio", {format: "#,##0.00"}]

# Graph
graph:
  nodes:
    dim_stock:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      description: "Stock dimension filtered from listing_status"
      select:
        ticker: ticker
        security_name: security_name
        exchange_code: exchange_code
        asset_type: asset_type
      filters:
        - "asset_type = 'stocks'"  # Only stock securities, not ETFs
      derive:
        stock_id: "ABS(HASH(CONCAT('STOCK_', ticker)))"
        security_id: "ABS(HASH(ticker))"  # FK to securities.dim_security
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"  # FK to corporate.dim_company
        stock_type: "'common'"
      primary_key: [stock_id]
      unique_key: [ticker]
      foreign_keys:
        - {column: security_id, references: securities.dim_security.security_id}
        - {column: company_id, references: corporate.dim_company.company_id, optional: true}
      tags: [dim, stock]

    # NOTE: fact_stock_technicals is computed post-build from securities.fact_security_prices
    # by scripts/build/compute_technicals.py - it's not loaded from bronze directly

    fact_dividends:
      from: bronze.alpha_vantage.dividends
      type: fact
      description: "Dividend distribution history (from DIVIDENDS endpoint)"
      select:
        ticker: ticker
        ex_dividend_date: ex_dividend_date
        dividend_amount: dividend_amount
        record_date: record_date
        payment_date: payment_date
        declaration_date: declaration_date
      derive:
        dividend_id: "ABS(HASH(CONCAT(ticker, '_', CAST(ex_dividend_date AS STRING))))"
        security_id: "ABS(HASH(ticker))"
        ex_dividend_date_id: "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"
        payment_date_id: "CAST(REGEXP_REPLACE(CAST(payment_date AS STRING), '-', '') AS INT)"
      drop: [ticker]
      primary_key: [dividend_id]
      unique_key: [ticker, ex_dividend_date]
      foreign_keys:
        - {column: security_id, references: dim_stock.security_id}
        - {column: ex_dividend_date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, dividends, corporate_action]

    fact_splits:
      from: bronze.alpha_vantage.splits
      type: fact
      description: "Stock split history (from SPLITS endpoint)"
      select:
        ticker: ticker
        effective_date: effective_date
        split_factor: split_factor
      derive:
        split_id: "ABS(HASH(CONCAT(ticker, '_', CAST(effective_date AS STRING))))"
        security_id: "ABS(HASH(ticker))"
        effective_date_id: "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"
      drop: [ticker]
      primary_key: [split_id]
      unique_key: [ticker, effective_date]
      foreign_keys:
        - {column: security_id, references: dim_stock.security_id}
        - {column: effective_date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, splits, corporate_action]

  edges:
    # Stock to master security dimension
    stock_to_security:
      from: dim_stock
      to: securities.dim_security
      on: [security_id=security_id]
      type: many_to_one

    # Stock to company (optional - not all stocks have company data)
    stock_to_company:
      from: dim_stock
      to: corporate.dim_company
      on: [company_id=company_id]
      type: many_to_one
      optional: true

    # Dividends relationships
    dividends_to_stock:
      from: fact_dividends
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    dividends_to_calendar:
      from: fact_dividends
      to: temporal.dim_calendar
      on: [ex_dividend_date_id=date_id]
      type: many_to_one

    # Splits relationships
    splits_to_stock:
      from: fact_splits
      to: dim_stock
      on: [security_id=security_id]
      type: many_to_one

    splits_to_calendar:
      from: fact_splits
      to: temporal.dim_calendar
      on: [effective_date_id=date_id]
      type: many_to_one

  paths:
    company_to_dividends:
      description: "Navigate from company to dividend history"
      steps:
        - {from: corporate.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_dividends, via: security_id}

    security_to_technicals:
      description: "Navigate from master security to stock technicals"
      steps:
        - {from: securities.dim_security, to: dim_stock, via: security_id}
        - {from: dim_stock, to: fact_stock_technicals, via: security_id}

# Metadata
metadata:
  domain: securities
  owner: data_engineering
  sla_hours: 4
status: active
---

## Stocks Model

Stock equities with company linkage, technical indicators, dividends, and splits.

### Architecture (Normalized)

```
securities.dim_security (MASTER)
         ↑
    security_id FK
         │
      dim_stock ←──── company_id FK ───→ corporate.dim_company
         │
    ┌────┴────────────┬───────────────┐
    ↓                 ↓               ↓
fact_stock_      fact_dividends   fact_splits
technicals       (time-series)    (corporate actions)
```

### Key Points

1. **dim_stock FKs to securities.dim_security** - Master security dimension is in securities model
2. **Prices are in securities.fact_security_prices** - Unified OHLCV for all asset types
3. **Technicals are stock-specific** - Computed from prices, stored in fact_stock_technicals
4. **Dividends/Splits are time-series facts** - NOT static attributes in company

### Integer Keys

| Key | Type | Derivation |
|-----|------|------------|
| `stock_id` | integer | `ABS(HASH('STOCK_' + ticker))` |
| `security_id` | integer | `ABS(HASH(ticker))` - FK to securities |
| `company_id` | integer | `ABS(HASH('COMPANY_' + ticker))` - FK to corporate |
| `date_id` | integer | `YYYYMMDD` format |

### Stock-Level vs Company-Level Attributes

**In dim_stock (security-level):**
- shares_outstanding, shares_float (change over time, per-security)
- market_cap (derived from price × shares)
- sector, industry (stock classification)

**In dim_company (legal entity level):**
- cik, company_name, headquarters
- fiscal_year_end
- Financial statements

### Querying Prices with Technicals

```sql
-- Get stock prices with technicals (join to securities for prices)
SELECT
    c.date AS trade_date,
    s.ticker,
    p.close,
    p.volume,
    t.rsi_14,
    t.sma_50,
    t.sma_200
FROM securities.fact_security_prices p
JOIN securities.dim_security sec ON p.security_id = sec.security_id
JOIN stocks.dim_stock s ON s.security_id = sec.security_id
JOIN stocks.fact_stock_technicals t ON t.security_id = s.security_id AND t.date_id = p.date_id
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
WHERE sec.asset_type = 'stocks'
  AND s.ticker = 'AAPL'
  AND c.year = 2025
```

### Build Order

```
temporal → securities → corporate → stocks
```
