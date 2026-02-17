---
type: domain-base
model: securities
version: 3.0
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"
extends: _base._base_.entity

depends_on: [temporal]

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [security_id, integer, nullable: false, description: "Surrogate primary key"]
  - [ticker, string, nullable: false, description: "Trading symbol"]
  - [security_name, string, nullable: true, description: "Display name"]
  - [asset_type, string, nullable: true, description: "Stock, ETF, Option, Future"]
  - [exchange_code, string, nullable: true, description: "Primary exchange (NYSE, NASDAQ)"]
  - [currency, string, nullable: true, description: "Trading currency"]
  - [is_active, boolean, nullable: true, description: "Currently trading"]
  - [open, double, nullable: true, description: "Opening price"]
  - [high, double, nullable: true, description: "High price"]
  - [low, double, nullable: true, description: "Low price"]
  - [close, double, nullable: false, description: "Closing price"]
  - [volume, long, nullable: true, description: "Trading volume"]
  - [adjusted_close, double, nullable: true, description: "Split/dividend adjusted close"]

tables:
  _dim_security:
    type: dimension
    primary_key: [security_id]
    unique_key: [ticker]

    # [column, type, nullable, description, {options}]
    schema:
      - [security_id, integer, false, "PK", {derived: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Natural key", {unique: true}]
      - [security_name, string, true, "Display name"]
      - [asset_type, string, true, "Classification", {enum: [Stock, ETF, "Mutual Fund", Option, Future]}]
      - [exchange_code, string, true, "Primary exchange"]
      - [currency, string, true, "Trading currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently trading", {default: true}]

    measures:
      - [security_count, count_distinct, security_id, "Number of securities", {format: "#,##0"}]

  _fact_prices:
    type: fact
    primary_key: [price_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [price_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(security_id, '_', date_id)))"}]
      - [security_id, integer, false, "FK to dim_security", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [open, double, true, "Opening price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, false, "Closing price"]
      - [volume, long, true, "Trading volume"]
      - [adjusted_close, double, true, "Adjusted close"]

      # --- Build-time technical indicators (computed by builder.post_build) ---
      # Returns
      - [daily_return, double, true, "Daily return %", {derived: "(adjusted_close - LAG(adjusted_close)) / LAG(adjusted_close) * 100"}]

      # Simple Moving Averages
      - [sma_20, double, true, "20-day SMA", {derived: "AVG(adjusted_close) OVER (PARTITION BY security_id ORDER BY date_id ROWS 19 PRECEDING)"}]
      - [sma_50, double, true, "50-day SMA", {derived: "AVG(adjusted_close) OVER (PARTITION BY security_id ORDER BY date_id ROWS 49 PRECEDING)"}]
      - [sma_200, double, true, "200-day SMA", {derived: "AVG(adjusted_close) OVER (PARTITION BY security_id ORDER BY date_id ROWS 199 PRECEDING)"}]

      # Exponential Moving Averages
      - [ema_12, double, true, "12-day EMA", {derived: "EMA(adjusted_close, 12)"}]
      - [ema_26, double, true, "26-day EMA", {derived: "EMA(adjusted_close, 26)"}]

      # MACD
      - [macd, double, true, "MACD line (EMA12 - EMA26)", {derived: "ema_12 - ema_26"}]
      - [macd_signal, double, true, "MACD signal line (9-day EMA of MACD)", {derived: "EMA(macd, 9)"}]
      - [macd_histogram, double, true, "MACD histogram (MACD - signal)", {derived: "macd - macd_signal"}]

      # RSI
      - [rsi_14, double, true, "14-day RSI", {derived: "100 - (100 / (1 + AVG(gain_14) / AVG(loss_14)))"}]

      # Average True Range
      - [atr_14, double, true, "14-day Average True Range", {derived: "AVG(TRUE_RANGE(high, low, prev_close)) OVER (ROWS 13 PRECEDING)"}]

      # Bollinger Bands
      - [bollinger_upper, double, true, "Upper Bollinger Band (SMA20 + 2*std)", {derived: "sma_20 + 2 * STDDEV(adjusted_close) OVER (ROWS 19 PRECEDING)"}]
      - [bollinger_middle, double, true, "Middle Bollinger Band (SMA20)", {derived: "sma_20"}]
      - [bollinger_lower, double, true, "Lower Bollinger Band (SMA20 - 2*std)", {derived: "sma_20 - 2 * STDDEV(adjusted_close) OVER (ROWS 19 PRECEDING)"}]

      # Volatility
      - [volatility_20d, double, true, "20-day annualized volatility", {derived: "STDDEV(daily_return) OVER (ROWS 19 PRECEDING) * SQRT(252)"}]
      - [volatility_60d, double, true, "60-day annualized volatility", {derived: "STDDEV(daily_return) OVER (ROWS 59 PRECEDING) * SQRT(252)"}]

      # Volume indicators
      - [volume_sma_20, double, true, "20-day volume SMA", {derived: "AVG(volume) OVER (ROWS 19 PRECEDING)"}]
      - [volume_ratio, double, true, "Volume vs 20-day average", {derived: "volume / NULLIF(volume_sma_20, 0)"}]

    measures:
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
      - [max_high, max, high, "Maximum high", {format: "$#,##0.00"}]
      - [min_low, min, low, "Minimum low", {format: "$#,##0.00"}]
      - [price_range, expression, "AVG(high - low)", "Average daily range", {format: "$#,##0.00"}]
      - [avg_daily_return, avg, daily_return, "Average daily return %", {format: "#,##0.00%"}]
      - [avg_rsi, avg, rsi_14, "Average RSI", {format: "#,##0.0"}]
      - [avg_volatility, avg, volatility_20d, "Average 20d volatility", {format: "#,##0.00%"}]
      - [avg_atr, avg, atr_14, "Average ATR", {format: "$#,##0.00"}]

    python_measures:
      sharpe_ratio:
        function: "securities.measures.calculate_sharpe_ratio"
        description: "Rolling Sharpe ratio — risk-adjusted return vs risk-free rate"
        params:
          risk_free_rate: 0.045
          window_days: 252
          price_col: "close"
        returns: [security_id, date_id, sharpe_ratio]

      drawdown:
        function: "securities.measures.calculate_drawdown"
        description: "Maximum drawdown from rolling peak price"
        params:
          window_days: 252
          price_col: "close"
        returns: [security_id, date_id, drawdown, peak_price]

      rolling_beta:
        function: "securities.measures.calculate_rolling_beta"
        description: "Rolling beta vs market benchmark (covariance / variance)"
        params:
          market_ticker: "SPY"
          window_days: 252
          price_col: "close"
        returns: [security_id, date_id, beta]

      momentum_score:
        function: "securities.measures.calculate_momentum_score"
        description: "Composite momentum score from RSI, MACD, and price trend"
        params:
          weights: {rsi: 0.3, macd: 0.3, price_trend: 0.4}
        returns: [security_id, date_id, momentum_score, rsi_norm, macd_norm, price_trend_norm]

      volatility_regime:
        function: "securities.measures.calculate_volatility_regime"
        description: "Classify volatility regime (LOW/NORMAL/HIGH) from short vs long vol ratio"
        params:
          short_window: 20
          long_window: 60
          price_col: "close"
        returns: [security_id, date_id, vol_short_ann, vol_long_ann, vol_ratio, regime]

      relative_strength:
        function: "securities.measures.calculate_relative_strength"
        description: "Relative strength vs benchmark — rolling cumulative return differential"
        params:
          benchmark_ticker: "SPY"
          window_days: 20
          price_col: "close"
        returns: [security_id, date_id, relative_strength, outperforming]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [prices_to_security, _fact_prices, _dim_security, [security_id=security_id], many_to_one, null]
    - [prices_to_calendar, _fact_prices, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

domain: finance
tags: [base, template, securities]
status: active
---

## Base Securities Template

Reusable template for all tradable securities. Child models inherit schema and add asset-specific fields.

### Build-Time Technical Indicators

The `_fact_prices` schema includes columns for technical indicators computed at build time by `builder.post_build()`. These are materialized into the fact table, not calculated on query:

| Category | Columns | Window |
|----------|---------|--------|
| Moving Averages | `sma_20`, `sma_50`, `sma_200` | Simple rolling |
| EMA | `ema_12`, `ema_26` | Exponential |
| MACD | `macd`, `macd_signal`, `macd_histogram` | 12/26/9 EMA |
| RSI | `rsi_14` | 14-day |
| ATR | `atr_14` | 14-day |
| Bollinger | `bollinger_upper`, `bollinger_middle`, `bollinger_lower` | 20-day SMA ± 2σ |
| Volatility | `volatility_20d`, `volatility_60d` | Annualized stddev |
| Volume | `volume_sma_20`, `volume_ratio` | 20-day avg |

### Python Measures (Inherited by All Security Types)

| Measure | Description | Key Params |
|---------|-------------|------------|
| `sharpe_ratio` | Rolling risk-adjusted return vs risk-free rate | `risk_free_rate: 0.045`, `window_days: 252` |
| `drawdown` | Maximum drawdown from rolling peak | `window_days: 252` |
| `rolling_beta` | Covariance/variance vs market benchmark | `market_ticker: "SPY"` |
| `momentum_score` | Composite RSI + MACD + price trend score | Weighted: RSI 0.3, MACD 0.3, trend 0.4 |
| `volatility_regime` | LOW/NORMAL/HIGH classification | Short 20d vs long 60d vol |
| `relative_strength` | Rolling return differential vs benchmark | `benchmark_ticker: "SPY"` |

These measures are defined at the securities base so stocks, ETFs, options, and futures all inherit them. Child models can override `params` (e.g., futures might use a different `market_ticker`).

### Child Models

| Model | Extends | Adds |
|-------|---------|------|
| stocks | _dim_security, _fact_prices | company_id, cik, market_cap |
| options | _dim_security, _fact_prices | strike, expiry, greeks |
| etfs | _dim_security, _fact_prices | holdings, nav |
| futures | _dim_security, _fact_prices | contract_size, margin |

### Usage

```yaml
extends: _base.finance.securities
```
