---
type: domain-base
base_name: securities
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"

# Dependencies - base securities requires temporal for date_id FK pattern
depends_on: [temporal]

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
    description: "Base OHLCV price data with technical indicators"
    primary_key: [price_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    # NOTE: Technical indicators are computed post-build by scripts/build/compute_technicals.py
    schema:
      # Keys - all integers
      - [price_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(security_id, '_', date_id)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Price data (from bronze)
      - [open, double, true, "Opening price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, false, "Closing price"]
      - [volume, long, true, "Trading volume"]
      - [adjusted_close, double, true, "Split/dividend adjusted close"]

      # Technical Indicators (computed by scripts/build/compute_technicals.py)
      # Moving Averages
      - [sma_20, double, true, "20-day Simple Moving Average", {computed: true}]
      - [sma_50, double, true, "50-day Simple Moving Average", {computed: true}]
      - [sma_200, double, true, "200-day Simple Moving Average", {computed: true}]

      # Returns & Volatility
      - [daily_return, double, true, "Daily return percentage", {computed: true}]
      - [volatility_20d, double, true, "20-day annualized volatility", {computed: true}]
      - [volatility_60d, double, true, "60-day annualized volatility", {computed: true}]

      # Momentum Indicators
      - [rsi_14, double, true, "14-day Relative Strength Index", {computed: true, range: [0, 100]}]

      # Bollinger Bands
      - [bollinger_upper, double, true, "Bollinger Band Upper (SMA20 + 2*StdDev)", {computed: true}]
      - [bollinger_middle, double, true, "Bollinger Band Middle (SMA20)", {computed: true}]
      - [bollinger_lower, double, true, "Bollinger Band Lower (SMA20 - 2*StdDev)", {computed: true}]

      # Volume Indicators
      - [volume_sma_20, double, true, "20-day volume SMA", {computed: true}]
      - [volume_ratio, double, true, "Volume ratio (current/SMA20)", {computed: true}]

    # Measures on the table
    measures:
      # Price measures
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
      - [max_high, max, high, "Maximum high price", {format: "$#,##0.00"}]
      - [min_low, min, low, "Minimum low price", {format: "$#,##0.00"}]
      - [price_range, expression, "AVG(high - low)", "Average price range", {format: "$#,##0.00"}]
      - [intraday_return, expression, "AVG((close - open) / open * 100)", "Average intraday return %", {format: "#,##0.00%"}]

      # Technical indicator measures
      - [avg_rsi, avg, rsi_14, "Average RSI", {format: "#,##0.00"}]
      - [avg_volatility, avg, volatility_20d, "Average 20-day volatility", {format: "#,##0.00%"}]
      - [overbought_days, expression, "SUM(CASE WHEN rsi_14 > 70 THEN 1 ELSE 0 END)", "Days RSI > 70", {format: "#,##0"}]
      - [oversold_days, expression, "SUM(CASE WHEN rsi_14 < 30 THEN 1 ELSE 0 END)", "Days RSI < 30", {format: "#,##0"}]

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

    # NOTE: Technical indicators are computed post-build by scripts/build/compute_technicals.py
    # and added as columns to _fact_prices_base. There is no separate technicals table.

  edges:
    prices_to_security:
      from: _fact_prices_base
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one

    prices_to_calendar:
      from: _fact_prices_base
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

### Dependencies

This base template depends on:
- **temporal** - For `date_id` FK pattern (all dates reference dim_calendar)

### Key Design

All keys are **integers** for storage efficiency:

| Key | Type | Derivation |
|-----|------|------------|
| `security_id` | integer | `ABS(HASH(ticker))` |
| `date_id` | integer | `YYYYMMDD` format |
| `price_id` | integer | `ABS(HASH(ticker + date))` |

### No Date Columns on Facts

Facts have `date_id` (integer FK), not date columns:

```sql
-- Join to get actual date and technicals (all on same table)
SELECT c.date AS trade_date, p.close, p.rsi_14, p.sma_50
FROM fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
WHERE p.rsi_14 < 30  -- oversold condition
```

### Technical Indicators

Technical indicators are **computed columns** on `_fact_prices_base`, not a separate table.
They are calculated post-build by `scripts/build/compute_technicals.py`.

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

1. Main silver build creates `fact_stock_prices` with OHLCV data
2. `scripts/build/compute_technicals.py` runs post-build to add technical columns
3. Technical columns are computed in batches to avoid OOM on large datasets

### Inheritance

Child models inherit using `extends`:

```yaml
tables:
  dim_stock:
    extends: _base.finance.securities.dim_security
    schema:
      # Inherited: security_id, ticker, security_name, asset_type, etc.
      # Add stock-specific:
      - [company_id, integer, false, "FK to dim_company", {fk: corporate.dim_company.company_id}]
      - [cik, string, true, "SEC Central Index Key"]
      - [market_cap, double, true, "Market capitalization"]

  fact_stock_prices:
    extends: _base.finance.securities._fact_prices_base
    # Inherits OHLCV + technical indicator columns
```

### Models Using This Base

- `stocks` - Common stock equities
- `options` - Options contracts
- `etfs` - Exchange-traded funds
- `futures` - Futures contracts
