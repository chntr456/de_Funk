---
type: domain-base
base_name: securities
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"

# Base Schema Templates
schema:
  dimensions:
    dim_security:
      description: "Master dimension for all tradable securities - OWNS ticker uniqueness"
      primary_key: [security_id]
      columns:
        security_id: {type: string, description: "PK - Surrogate key (e.g., STOCK_AAPL)", required: true}
        ticker: {type: string, description: "Trading symbol - UNIQUE natural key", required: true, unique: true}
        security_name: {type: string, description: "Display name"}
        asset_type: {type: string, description: "Type of asset", enum: [Stock, ETF, Mutual Fund, Option, Future]}
        exchange_code: {type: string, description: "Primary exchange (NYSE, NASDAQ)"}
        currency: {type: string, description: "Trading currency", default: "USD"}
        is_active: {type: boolean, description: "Currently trading", default: true}
      tags: [dim, entity, security, master]

  facts:
    _fact_prices:
      description: "Base OHLCV price data for all securities"
      primary_key: [price_id]
      partitions: [trade_date]
      columns:
        price_id: {type: string, description: "PK - Surrogate key (ticker_date)", required: true}
        security_id: {type: string, description: "FK to dim_security.security_id", required: true}
        trade_date: {type: date, description: "Trading date", required: true}
        open: {type: double, description: "Opening price"}
        high: {type: double, description: "Highest price"}
        low: {type: double, description: "Lowest price"}
        close: {type: double, description: "Closing price", required: true}
        volume: {type: double, description: "Trading volume"}
        adjusted_close: {type: double, description: "Split/dividend adjusted close"}
      tags: [fact, prices, timeseries, ohlcv]

# Base Graph Templates
graph:
  nodes:
    dim_security:
      from: bronze.company_reference
      type: dimension
      description: "Master security dimension - OWNS ticker uniqueness"
      select:
        ticker: ticker
        security_name: company_name
        asset_type: AssetType
        exchange_code: exchange_code
        currency: currency
      derive:
        security_id: "CONCAT(COALESCE(AssetType, 'UNKNOWN'), '_', ticker)"
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
        price_id: "CONCAT(ticker, '_', trade_date)"
        security_id: "CONCAT('Stock_', ticker)"
      primary_key: [price_id]
      unique_key: [ticker, trade_date]
      foreign_keys:
        - {column: security_id, references: dim_security.security_id}
        - {column: trade_date, references: temporal.dim_calendar.date}

  edges:
    prices_to_security:
      from: _fact_prices
      to: dim_security
      on: [security_id=security_id]
      type: many_to_one
      description: "Prices belong to a security via security_id"

    prices_to_calendar:
      from: _fact_prices
      to: temporal.dim_calendar
      on: [trade_date=date]
      type: left
      cross_model: temporal
      description: "Link prices to calendar"

# Base Measures
measures:
  simple:
    avg_close_price:
      description: "Average closing price"
      source: _fact_prices.close
      aggregation: avg
      format: "$#,##0.00"
      tags: [price, core]

    total_volume:
      description: "Total trading volume"
      source: _fact_prices.volume
      aggregation: sum
      format: "#,##0"
      tags: [volume, core]

    max_high:
      description: "Maximum high price"
      source: _fact_prices.high
      aggregation: max
      format: "$#,##0.00"
      tags: [price, range]

    min_low:
      description: "Minimum low price"
      source: _fact_prices.low
      aggregation: min
      format: "$#,##0.00"
      tags: [price, range]

    avg_vwap:
      description: "Average VWAP"
      source: _fact_prices.volume_weighted
      aggregation: avg
      format: "$#,##0.00"
      tags: [price, vwap]

    security_count:
      description: "Number of securities"
      source: dim_security.security_id
      aggregation: count_distinct
      format: "#,##0"
      tags: [count, core]

  computed:
    price_range:
      description: "Price range (high - low)"
      expression: "high - low"
      source_table: _fact_prices
      aggregation: avg
      format: "$#,##0.00"
      tags: [price, range]

    intraday_return:
      description: "Intraday return %"
      expression: "(close - open) / open * 100"
      source_table: _fact_prices
      aggregation: avg
      format: "#,##0.00%"
      tags: [returns]

# Metadata
domain: securities
tags: [base, template, securities]
status: active
---

## Base Securities Template

Reusable base template providing common schema, graph, and measure patterns for all tradable securities.

### Usage

Child models inherit using `inherits_from` and `extends`:

```yaml
---
type: domain-model
model: stocks
inherits_from: _base.securities

schema:
  dimensions:
    dim_stock:
      extends: _base.securities._dim_security
      columns:
        # Inherited: ticker, security_name, asset_type, exchange_code, etc.
        # Add model-specific columns:
        company_id: {type: string, description: "FK to company"}
        shares_outstanding: {type: long}
---
```

### Inherited Components

**Schema**: `_dim_security`, `_fact_prices`
**Graph**: `_dim_security_base`, `_fact_prices_base`, common edges
**Measures**: `avg_close_price`, `total_volume`, `price_range`, etc.

### Models Using This Base

- `stocks` - Common stock equities
- `options` - Options contracts (adds Greeks, strike, expiry)
- `etfs` - Exchange-traded funds (adds holdings)
- `futures` - Futures contracts (adds expiry, margin)

### Notes

- Templates prefixed with `_` are not instantiated directly
- Child definitions override parent via deep merge
- Use `extends` for component-level inheritance
- Use `inherits_from` for model-level inheritance
