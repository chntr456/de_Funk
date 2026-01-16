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

  _fact_technicals_base:
    type: fact
    description: "Base technical indicators template"
    primary_key: [technical_id]
    partition_by: [date_id]

    # Schema: [column, type, nullable, description, {options}]
    schema:
      # Keys - all integers
      - [technical_id, integer, false, "PK - Integer surrogate", {derived: "ABS(HASH(CONCAT(security_id, '_', date_id)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]

      # Moving Averages
      - [sma_20, double, true, "20-day Simple Moving Average"]
      - [sma_50, double, true, "50-day Simple Moving Average"]
      - [sma_200, double, true, "200-day Simple Moving Average"]
      - [ema_12, double, true, "12-day Exponential Moving Average"]
      - [ema_26, double, true, "26-day Exponential Moving Average"]

      # Momentum Indicators
      - [rsi_14, double, true, "14-day Relative Strength Index", {range: [0, 100]}]
      - [macd, double, true, "MACD Line (EMA12 - EMA26)"]
      - [macd_signal, double, true, "MACD Signal Line (9-day EMA of MACD)"]
      - [macd_histogram, double, true, "MACD Histogram (MACD - Signal)"]

      # Volatility Indicators
      - [bollinger_upper, double, true, "Bollinger Band Upper (SMA20 + 2*StdDev)"]
      - [bollinger_middle, double, true, "Bollinger Band Middle (SMA20)"]
      - [bollinger_lower, double, true, "Bollinger Band Lower (SMA20 - 2*StdDev)"]
      - [atr_14, double, true, "14-day Average True Range"]

      # Volume Indicators
      - [obv, double, true, "On-Balance Volume"]
      - [vwap, double, true, "Volume Weighted Average Price"]

      # Trend Indicators
      - [adx_14, double, true, "14-day Average Directional Index", {range: [0, 100]}]
      - [plus_di, double, true, "+DI (Positive Directional Indicator)"]
      - [minus_di, double, true, "-DI (Negative Directional Indicator)"]

    # Measures on the table
    measures:
      - [avg_rsi, avg, rsi_14, "Average RSI", {format: "#,##0.00"}]
      - [avg_macd, avg, macd, "Average MACD", {format: "#,##0.0000"}]
      - [avg_atr, avg, atr_14, "Average ATR", {format: "$#,##0.00"}]
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

    _fact_technicals_base:
      from: bronze.securities_technicals
      type: fact
      select:
        ticker: ticker
        trade_date: trade_date
        # Moving Averages
        sma_20: sma_20
        sma_50: sma_50
        sma_200: sma_200
        ema_12: ema_12
        ema_26: ema_26
        # Momentum
        rsi_14: rsi_14
        macd: macd
        macd_signal: macd_signal
        macd_histogram: macd_histogram
        # Volatility
        bollinger_upper: bollinger_upper
        bollinger_middle: bollinger_middle
        bollinger_lower: bollinger_lower
        atr_14: atr_14
        # Volume
        obv: obv
        vwap: vwap
        # Trend
        adx_14: adx_14
        plus_di: plus_di
        minus_di: minus_di
      derive:
        security_id: "ABS(HASH(ticker))"
        date_id: "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)"
        technical_id: "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
      primary_key: [technical_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: date_id, references: temporal.dim_calendar.date_id}

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

    technicals_to_security:
      from: _fact_technicals_base
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one

    technicals_to_calendar:
      from: _fact_technicals_base
      to: temporal.dim_calendar
      on: [date_id=date_id]
      type: many_to_one
      cross_model: temporal

    technicals_to_prices:
      from: _fact_technicals_base
      to: _fact_prices_base
      on: [security_id=security_id, date_id=date_id]
      type: one_to_one
      description: "Technical indicators align with price data"

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
| `technical_id` | integer | `ABS(HASH(ticker + date))` |

### No Date Columns on Facts

Facts have `date_id` (integer FK), not date columns:

```sql
-- Join to get actual date
SELECT c.date AS trade_date, p.close, t.rsi_14
FROM fact_stock_prices p
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
LEFT JOIN fact_stock_technicals t ON p.security_id = t.security_id AND p.date_id = t.date_id
```

### Technical Indicators

The `_fact_technicals_base` template includes:

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

  fact_stock_technicals:
    extends: _base.finance.securities._fact_technicals_base
    # Inherits all technical indicator columns
```

### Models Using This Base

- `stocks` - Common stock equities
- `options` - Options contracts
- `etfs` - Exchange-traded funds
- `futures` - Futures contracts
