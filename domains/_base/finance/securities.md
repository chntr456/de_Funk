---
type: domain-base
base_name: securities
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"

# Base Tables
tables:
  dim_security:
    type: dimension
    description: "Master security dimension - OWNS ticker uniqueness"
    primary_key: [security_id]
    unique_key: [ticker]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys
      - [security_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Natural key - trading symbol", {unique: true}]

      # Attributes
      - [security_name, string, true, "Display name"]
      - [asset_type, string, true, "Stock, ETF, Option, Future", {enum: [Stock, ETF, "Mutual Fund", Option, Future]}]
      - [exchange_code, string, true, "Primary exchange (NYSE, NASDAQ)"]
      - [currency, string, true, "Trading currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently trading", {default: true}]

    # Measures on the table
    measures:
      - [security_count, count_distinct, security_id, "Number of securities", {format: "#,##0"}]

  _fact_prices_base:
    type: fact
    description: "Base OHLCV price data template"
    primary_key: [price_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [price_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(security_id, '_', date_id)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Price data
      - [open, double, true, "Opening price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, false, "Closing price"]
      - [volume, long, true, "Trading volume"]
      - [adjusted_close, double, true, "Split/dividend adjusted close"]

    # Measures on the table
    measures:
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
      - [max_high, max, high, "Maximum high price", {format: "$#,##0.00"}]
      - [min_low, min, low, "Minimum low price", {format: "$#,##0.00"}]
      - [price_range, expression, "AVG(high - low)", "Average price range", {format: "$#,##0.00"}]
      - [intraday_return, expression, "AVG((close - open) / open * 100)", "Average intraday return %", {format: "#,##0.00%"}]

# Graph Templates
graph:
  nodes:
    dim_security:
      from: bronze.company_reference
      type: dimension
      # Note: company_reference_facet normalizes to snake_case columns
      select:
        ticker: ticker
        security_name: company_name
        exchange_code: exchange_code
        currency: currency
      derive:
        security_id: "ABS(HASH(ticker))"
        # company_reference doesn't have asset_type - default to Stock
        asset_type: "'Stock'"
        is_active: "true"
      primary_key: [security_id]
      unique_key: [ticker]
      tags: [dim, master, security]

    _fact_prices_base:
      from: bronze.securities_prices_daily
      type: fact
      select:
        ticker: ticker
        trade_date: trade_date
        open: open
        high: high
        low: low
        close: close
        volume: volume
        adjusted_close: adjusted_close
      derive:
        # Integer keys
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"
        price_id: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

  edges:
    prices_to_security:
      from: _fact_prices
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: _fact_prices
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

# Metadata
domain: securities
tags: [base, template, securities]
status: active
---

## Base Securities Template

Reusable base template for all tradable securities with integer surrogate keys.

### Key Design

All keys are **integers** for storage efficiency:

| Key | Type | Derivation |
|-----|------|------------|
| `security_id` | integer | `ABS(HASH(ticker))` |
| `date_id` | integer | `YYYYMMDD` format |
| `price_id` | integer | `ABS(HASH(ticker + date))` |

### No Date Columns on Facts

Facts have `date_id` (integer FK), not date columns:

```yaml
# Join to get actual date
SELECT c.date AS trade_date, p.close
FROM fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
```

### Inheritance

Child models inherit using `extends`:

```yaml
tables:
  dim_stock:
    extends: _base.securities.dim_security
    schema:
      # Inherited: security_id, ticker, security_name, asset_type, etc.
      # Add stock-specific:
      - [company_id, integer, false, "FK to dim_company", {fk: corporate.dim_company.company_id}]
      - [cik, string, true, "SEC Central Index Key"]
      - [market_cap, double, true, "Market capitalization"]
```

### Models Using This Base

- `stocks` - Common stock equities
- `options` - Options contracts
- `etfs` - Exchange-traded funds
- `futures` - Futures contracts
