---
type: domain-base
base_name: securities
description: "Base template for all tradable securities (stocks, options, ETFs, futures)"

# Base Schema Templates
schema:
  dimensions:
    _dim_security:
      description: "Base dimension for all tradable securities"
      primary_key: [ticker]
      columns:
        ticker: {type: string, description: "Trading symbol", required: true}
        security_name: {type: string, description: "Display name"}
        asset_type: {type: string, description: "Type of asset", enum: [stocks, options, etfs, futures, crypto]}
        asset_class: {type: string, description: "Asset class", enum: [stocks, options, indices, forex, crypto, commodities]}
        exchange_code: {type: string, description: "Primary exchange (NYSE, NASDAQ)"}
        currency: {type: string, description: "Trading currency", default: "USD"}
        is_active: {type: boolean, description: "Currently trading", default: true}
        listing_date: {type: date, description: "Date first listed"}
        delisting_date: {type: date, description: "Date delisted (null if active)"}
        last_updated: {type: timestamp, description: "Last metadata update"}
      tags: [dim, entity, security]

  facts:
    _fact_prices:
      description: "Base OHLCV price data for all securities"
      primary_key: [ticker, trade_date]
      partitions: [trade_date]
      columns:
        ticker: {type: string, description: "FK to dim_security", required: true}
        trade_date: {type: date, description: "Trading date", required: true}
        open: {type: double, description: "Opening price"}
        high: {type: double, description: "Highest price"}
        low: {type: double, description: "Lowest price"}
        close: {type: double, description: "Closing price", required: true}
        volume: {type: double, description: "Trading volume"}
        volume_weighted: {type: double, description: "VWAP"}
        transactions: {type: long, description: "Number of transactions"}
      tags: [fact, prices, timeseries, ohlcv]

# Base Graph Templates
graph:
  nodes:
    _dim_security_base:
      from: bronze.company_reference
      type: dimension
      select:
        ticker: ticker
        security_name: security_name
        asset_type: asset_type
        exchange_code: exchange_code
        currency: "'USD'"
        is_active: is_active
      derive:
        security_id: "CONCAT(asset_type, '_', ticker)"
      unique_key: [ticker]

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

  edges:
    _prices_to_security:
      from: _fact_prices
      to: _dim_security
      on: [ticker=ticker]
      type: many_to_one
      description: "Prices belong to a security"

    _prices_to_calendar:
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
      source: _dim_security.ticker
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
