---
type: domain-base
base_name: securities
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"

# Dependencies - base securities requires temporal for date_id FK pattern
depends_on: [temporal]

# Storage - provider/dataset for bronze, domain hierarchy for silver
# NOTE: This is a BASE TEMPLATE (type: domain-base) - NO tables are materialized here!
# Child models (stocks, options, etfs, futures) inherit schema and write to their own paths.
storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      # Table names match endpoint_id from API config
      listing_status: alpha_vantage/listing_status  # All tickers from LISTING_STATUS
      time_series_daily_adjusted: alpha_vantage/time_series_daily_adjusted  # Daily OHLCV
  silver:
    # NOT USED - base templates don't write to Silver
    root: storage/silver/_base_securities_UNUSED

# Base Tables (TEMPLATES - prefix with _ to exclude from materialization)
# Tables starting with _ are templates for inheritance, not built directly
tables:
  _dim_security:
    type: dimension
    description: "TEMPLATE: Master security dimension - inherit via extends"
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

# Graph Templates (nodes starting with _ are templates for inheritance)
graph:
  nodes:
    _dim_security:
      from: bronze.alpha_vantage.listing_status
      type: dimension
      # TEMPLATE: listing_status comes from LISTING_STATUS endpoint (bulk ticker list)
      # Child models override this node (e.g., stocks uses dim_stock)
      select:
        ticker: ticker
        security_name: security_name
        exchange_code: exchange_code
        asset_type: asset_type
      derive:
        security_id: "ABS(HASH(ticker))"
        # Default currency and is_active
        currency: "'USD'"
        is_active: "true"
      primary_key: [security_id]
      unique_key: [ticker]
      tags: [dim, master, security, template]

    _fact_prices_base:
      from: bronze.alpha_vantage.time_series_daily_adjusted
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
        # Integer surrogate keys - facts use FKs, not natural keys
        # security_id: FK to dim_security (derived from ticker)
        security_id: "ABS(HASH(ticker))"
        # date_id: FK to dim_calendar (YYYYMMDD format, works with both DATE and STRING)
        date_id: "CAST(REGEXP_REPLACE(CAST(trade_date AS STRING), '-', '') AS INT)"
        # price_id: PK (surrogate from ticker + date)
        price_id: "ABS(HASH(CONCAT(ticker, '_', CAST(trade_date AS STRING))))"
      # Drop natural keys after deriving FKs - facts should only have surrogate/FK columns
      drop: [ticker, trade_date]
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

    # NOTE: Technical indicators are computed post-build by scripts/build/compute_technicals.py
    # and added as columns to _fact_prices_base. There is no separate technicals table.

  # TEMPLATE EDGES - These are inherited and overridden by child models
  # Child models should replace references to _dim_security with their concrete dimension
  # e.g., stocks replaces _dim_security -> dim_stock
  edges:
    _prices_to_security:
      from: _fact_prices_base
      to: _dim_security  # Template reference - override in child model
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

**⚠️ TEMPLATE ONLY - NEVER MATERIALIZED**

This is a base template (`type: domain-base`) that provides reusable schema definitions
for all tradable securities. It is inherited by child models but **NO TABLES ARE BUILT**
from this template directly.

**Child models using this template:**
- `stocks` → produces `dim_stock` and `fact_stock_prices`
- `options` → produces `dim_option` and `fact_option_prices`
- `etfs` → produces `dim_etf` and `fact_etf_prices`
- `futures` → produces `dim_future` and `fact_future_prices`

**Inheritance pattern:**
Child models use `extends: _base.finance.securities` to inherit schema definitions.
The schema columns are COPIED into the child dimension, creating a denormalized
document-style table. There is no FK relationship to a shared `dim_security` table.

### Integer Surrogate Keys

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
