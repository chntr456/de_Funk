---
type: domain-model
model: stocks
version: 3.0
description: "Common stock equities with price data and technical indicators"
tags: [stocks, equities, securities]

# Inheritance and Dependencies
extends: _base.finance.securities
depends_on: [temporal, corporate]

# Storage - provider/endpoint_id for bronze, domain hierarchy for silver
storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      # Table names match endpoint_id from API config
      listing_status: alpha_vantage/listing_status  # All tickers from LISTING_STATUS
      time_series_daily_adjusted: alpha_vantage/time_series_daily_adjusted  # Daily OHLCV
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
    extends: _base.finance.securities._dim_security
    description: "Stock equity dimension with company linkage"
    primary_key: [stock_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [stock_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "Derived security key: ABS(HASH(ticker))", {derived: "ABS(HASH(ticker))"}]
      - [company_id, integer, false, "FK to dim_company", {fk: corporate.dim_company.company_id}]

      # Inherited from base (for reference)
      - [ticker, string, false, "Natural key - trading symbol", {unique: true}]

      # Stock-specific attributes (from securities_reference / LISTING_STATUS)
      - [stock_type, string, true, "Type of stock", {enum: [common, preferred, adr, rights, units, warrants], default: "common"}]

      # Company enrichment fields (from company_reference / OVERVIEW - may be NULL)
      # These are only available for stocks that have been processed through COMPANY_OVERVIEW
      - [cik, string, true, "SEC Central Index Key (from company_reference)", {pattern: "^[0-9]{10}$", transform: "zfill(10)"}]
      - [shares_outstanding, long, true, "Current shares outstanding (from company_reference)", {coerce: long}]
      - [market_cap, double, true, "Market capitalization (from company_reference)", {coerce: double}]
      - [sector, string, true, "GICS Sector (from company_reference)"]
      - [industry, string, true, "GICS Industry (from company_reference)"]

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
      - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
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

  fact_dividends:
    type: fact
    description: "Dividend distribution history"
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
      - [declaration_date, date, true, "Declaration date"]

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
      - [split_factor, double, false, "Split ratio from Bronze (e.g., 4.0 for 4:1)"]
      - [split_ratio, double, false, "Split ratio (derived from split_factor)"]

    measures:
      - [split_count, count_distinct, split_id, "Number of splits", {format: "#,##0"}]
      - [avg_split_ratio, avg, split_ratio, "Average split ratio", {format: "#,##0.00"}]

# Graph
graph:
  extends: _base.finance.securities.graph

  nodes:
    dim_stock:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      # Note: listing_status comes from LISTING_STATUS endpoint (bulk ticker list)
      # This gives us ALL tickers (~12,499), not just those with company data (~197)
      # Company-specific fields (cik, sector, industry, market_cap) are enriched
      # via LEFT JOIN to company_overview in a subsequent step or left NULL
      select:
        ticker: ticker
        security_name: security_name
        exchange_code: exchange_code
        asset_type: asset_type
      filters:
        - "asset_type = 'stocks'"  # Only stock securities, not ETFs
      derive:
        stock_id: "ABS(HASH(CONCAT('STOCK_', ticker)))"
        security_id: "ABS(HASH(ticker))"
        # company_id derived from ticker - will match company if CIK exists
        # For stocks without company data, company_id still derived from ticker
        company_id: "ABS(HASH(CONCAT('COMPANY_', ticker)))"
        # Default stock_type - can be overridden via enrichment
        stock_type: "'common'"
      primary_key: [stock_id]
      unique_key: [ticker]
      foreign_keys:
        # security_id is derived inline, not a true FK (denormalized design)
        - {column: company_id, references: corporate.dim_company.company_id, optional: true}
      tags: [dim, stock]

    fact_stock_prices:
      extends: _base.finance.securities._fact_prices_base
      filter_by_dimension: dim_stock
      filters:
        - "trade_date IS NOT NULL"
        - "ticker IS NOT NULL"
      derive:
        # Integer surrogate keys - facts use FKs only, no natural keys
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(REGEXP_REPLACE(CAST(trade_date AS STRING), '-', '') AS INT)"
        price_id: "ABS(HASH(CONCAT(ticker, '_', CAST(trade_date AS STRING))))"
      # Drop natural keys - fact tables have only FK columns (no ticker, trade_date)
      drop: [ticker, trade_date]
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_stock.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, prices, stocks]

    # NOTE: Technical indicators are computed post-build by StocksBuilder.post_build()
    # and added as columns to fact_stock_prices. There is no separate technicals table.

    fact_dividends:
      from: bronze.alpha_vantage.dividends
      type: fact
      description: "Dividend distribution history (from DIVIDENDS endpoint)"
      select:
        ticker: ticker
        ex_dividend_date: ex_dividend_date
        dividend_amount: dividend_amount  # Already normalized in Bronze
        record_date: record_date
        payment_date: payment_date
        declaration_date: declaration_date
      derive:
        dividend_id: "ABS(HASH(CONCAT(ticker, '_', CAST(ex_dividend_date AS STRING))))"
        security_id: "ABS(HASH(ticker))"
        ex_dividend_date_id: "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"
        payment_date_id: "CAST(REGEXP_REPLACE(CAST(payment_date AS STRING), '-', '') AS INT)"
      drop: [ticker]  # Use security_id instead
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
        split_factor: split_factor  # Already computed ratio in Bronze (e.g., 4.0 for 4:1)
      derive:
        split_id: "ABS(HASH(CONCAT(ticker, '_', CAST(effective_date AS STRING))))"
        security_id: "ABS(HASH(ticker))"
        effective_date_id: "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"
        split_ratio: "CAST(split_factor AS DOUBLE)"  # Use Bronze split_factor directly
      drop: [ticker]  # Use security_id instead
      primary_key: [split_id]
      unique_key: [ticker, effective_date]
      foreign_keys:
        - {column: security_id, references: dim_stock.security_id}
        - {column: effective_date_id, references: temporal.dim_calendar.date_id}
      tags: [fact, splits, corporate_action]

  edges:
    # NOTE: No stock_to_security edge needed - dim_stock IS the complete dimension
    # It inherits the schema from _base.finance.securities.dim_security but is self-contained
    # The security_id column is derived inline: ABS(HASH(ticker))

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

| Source | Provider | Endpoint | Description |
|--------|----------|----------|-------------|
| securities_reference | Alpha Vantage | LISTING_STATUS | All US tickers (~12,499), bulk listing |
| securities_prices_daily | Alpha Vantage | TIME_SERIES_DAILY | OHLCV price data |
| company_reference | Alpha Vantage | COMPANY_OVERVIEW | Company fundamentals (per-ticker, subset) |

### Notes

- **dim_stock** loads from `securities_reference` (LISTING_STATUS) for full ticker coverage
- Company-specific fields (cik, sector, industry, market_cap) may be NULL - only populated for tickers with company_reference data
- Inherits OHLCV schema from `_base.finance.securities`
- Technical indicators are computed columns, not a separate table
- Company linkage via integer `company_id` (optional FK)
- All date filtering through `dim_calendar` join
