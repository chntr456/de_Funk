# Base Securities Template

**Shared schema, graph, and measures inherited by all security models**

---

## Overview

The `_base.securities` template provides a **common foundation** for all tradable securities:

- **stocks** - Common stock equities
- **options** - Options contracts
- **etfs** - Exchange-traded funds
- **futures** - Futures contracts

This inheritance pattern ensures consistent OHLCV schemas, common measures, and reusable graph patterns across all security types.

---

## Template Files

| File | Purpose |
|------|---------|
| `configs/models/_base/securities/schema.yaml` | Base dimension and fact schemas |
| `configs/models/_base/securities/graph.yaml` | Base node and edge patterns |
| `configs/models/_base/securities/measures.yaml` | Common measures |

---

## Base Schema

### _dim_security (Base Dimension)

All security dimensions inherit these columns:

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `ticker` | string | Security symbol (PK) | Yes |
| `security_name` | string | Full security name | Yes |
| `asset_type` | string | Type (stocks, options, etc.) | Yes |
| `asset_class` | string | Broader classification | No |
| `exchange_code` | string | Exchange code | Yes |
| `currency` | string | Trading currency | Yes |
| `is_active` | boolean | Active trading status | Yes |
| `listing_date` | date | Listing/IPO date | No |
| `delisting_date` | date | Delisting date | No |
| `last_updated` | timestamp | Last data update | Yes |

### _fact_prices (Base Fact)

All price facts inherit these columns:

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `ticker` | string | Security symbol (FK) | Yes |
| `trade_date` | date | Trading date | Yes |
| `open` | double | Opening price | Yes |
| `high` | double | High price | Yes |
| `low` | double | Low price | Yes |
| `close` | double | Closing price | Yes |
| `volume` | long | Trading volume | Yes |
| `volume_weighted` | double | Volume-weighted price | No |
| `transactions` | long | Transaction count | No |

---

## Base Graph Patterns

### Node Patterns

```yaml
# _base/securities/graph.yaml
nodes:
  _dim_security_base:
    from: bronze.securities_reference
    filters:
      - "asset_type = '{asset_type}'"  # Overridden by child
    select:
      ticker: ticker
      security_name: security_name
      asset_type: asset_type
      exchange_code: exchange_code
      currency: currency
      is_active: is_active

  _fact_prices_base:
    from: bronze.securities_prices_daily
    filters:
      - "asset_type = '{asset_type}'"  # Overridden by child
    select:
      ticker: ticker
      trade_date: trade_date
      open: open
      high: high
      low: low
      close: close
      volume: volume
      volume_weighted: volume_weighted
```

### Edge Patterns

```yaml
edges:
  _prices_to_security:
    from: "{fact_prices}"
    to: "{dim_security}"
    on: [ticker = ticker]

  _prices_to_calendar:
    from: "{fact_prices}"
    to: core.dim_calendar
    on: [trade_date = date]
```

---

## Base Measures

### Simple Measures (Aggregations)

| Measure | Source | Aggregation | Format | Description |
|---------|--------|-------------|--------|-------------|
| `avg_close_price` | _fact_prices.close | AVG | $#,##0.00 | Average closing price |
| `total_volume` | _fact_prices.volume | SUM | #,##0 | Total trading volume |
| `max_high` | _fact_prices.high | MAX | $#,##0.00 | Maximum high price |
| `min_low` | _fact_prices.low | MIN | $#,##0.00 | Minimum low price |
| `avg_vwap` | _fact_prices.volume_weighted | AVG | $#,##0.00 | Average VWAP |
| `avg_daily_transactions` | _fact_prices.transactions | AVG | #,##0 | Average transactions |

### Computed Measures

| Measure | Expression | Description |
|---------|------------|-------------|
| `price_range` | `high - low` | Daily price range |
| `intraday_return` | `(close - open) / open * 100` | Intraday return % |
| `range_pct` | `(high - low) / open * 100` | Range as % of open |

---

## YAML Configuration

### _base/securities/schema.yaml

```yaml
# Base securities schema - inherited by stocks, options, etfs, futures

dimensions:
  _dim_security:
    description: "Base security dimension template"
    columns:
      ticker:
        type: string
        description: "Security symbol"
        required: true
        primary_key: true

      security_name:
        type: string
        description: "Full security name"
        required: true

      asset_type:
        type: string
        description: "Asset type classification"
        enum: [stocks, options, etfs, futures]
        required: true

      asset_class:
        type: string
        description: "Broader asset classification"

      exchange_code:
        type: string
        description: "Exchange code (NYSE, NASDAQ, etc.)"
        required: true

      currency:
        type: string
        description: "Trading currency"
        default: "USD"

      is_active:
        type: boolean
        description: "Currently trading"
        default: true

      listing_date:
        type: date
        description: "Date listed/IPO"

      delisting_date:
        type: date
        description: "Date delisted (if applicable)"

      last_updated:
        type: timestamp
        description: "Last data update"

    primary_key: [ticker]
    tags: [dim, security, base]

facts:
  _fact_prices:
    description: "Base OHLCV price fact template"
    columns:
      ticker:
        type: string
        description: "Security symbol (FK)"
        required: true

      trade_date:
        type: date
        description: "Trading date"
        required: true

      open:
        type: double
        description: "Opening price"

      high:
        type: double
        description: "High price"

      low:
        type: double
        description: "Low price"

      close:
        type: double
        description: "Closing price"

      volume:
        type: long
        description: "Trading volume"

      volume_weighted:
        type: double
        description: "Volume-weighted average price"

      transactions:
        type: long
        description: "Number of transactions"

    primary_key: [ticker, trade_date]
    partitions: [trade_date]
    tags: [fact, prices, ohlcv, base]
```

### _base/securities/measures.yaml

```yaml
# Base securities measures - inherited by all security models

simple_measures:
  avg_close_price:
    description: "Average closing price"
    type: simple
    source: _fact_prices.close
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [price, average]

  total_volume:
    description: "Total trading volume"
    type: simple
    source: _fact_prices.volume
    aggregation: sum
    data_type: long
    format: "#,##0"
    tags: [volume, total]

  max_high:
    description: "Maximum high price"
    type: simple
    source: _fact_prices.high
    aggregation: max
    data_type: double
    format: "$#,##0.00"
    tags: [price, max]

  min_low:
    description: "Minimum low price"
    type: simple
    source: _fact_prices.low
    aggregation: min
    data_type: double
    format: "$#,##0.00"
    tags: [price, min]

  avg_vwap:
    description: "Average volume-weighted price"
    type: simple
    source: _fact_prices.volume_weighted
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [price, vwap]

  avg_daily_transactions:
    description: "Average daily transactions"
    type: simple
    source: _fact_prices.transactions
    aggregation: avg
    data_type: double
    format: "#,##0"
    tags: [activity]

computed_measures:
  price_range:
    description: "Daily price range (high - low)"
    type: computed
    expression: "high - low"
    source_table: _fact_prices
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [price, range]

  intraday_return:
    description: "Intraday return percentage"
    type: computed
    expression: "(close - open) / open * 100"
    source_table: _fact_prices
    aggregation: avg
    data_type: double
    format: "#,##0.00%"
    tags: [return, intraday]

  range_pct:
    description: "Price range as percentage of open"
    type: computed
    expression: "(high - low) / open * 100"
    source_table: _fact_prices
    aggregation: avg
    data_type: double
    format: "#,##0.00%"
    tags: [price, volatility]

python_measures: {}  # Children add their own Python measures
```

---

## How Inheritance Works

### Child Model Configuration

```yaml
# stocks/schema.yaml
extends: _base.securities.schema

dimensions:
  dim_stock:
    extends: _base.securities._dim_security
    columns:
      # All base columns inherited automatically
      # Add stocks-specific columns:
      company_id:
        type: string
        description: "FK to company.dim_company"
      cik:
        type: string
        description: "SEC Central Index Key"
      shares_outstanding:
        type: long
```

### Resolution Process

1. **Load base template**: `_base/securities/schema.yaml`
2. **Load child config**: `stocks/schema.yaml`
3. **Deep merge**: Child overrides/extends parent
4. **Result**: Child has ALL base fields + additions

```
Base (_dim_security):           Child (dim_stock):           Result:
- ticker                   +    - company_id             =   - ticker (inherited)
- security_name                 - cik                        - security_name (inherited)
- asset_type                    - shares_outstanding         - asset_type (inherited)
- exchange_code                                              - exchange_code (inherited)
- currency                                                   - currency (inherited)
- is_active                                                  - is_active (inherited)
- listing_date                                               - listing_date (inherited)
- delisting_date                                             - delisting_date (inherited)
- last_updated                                               - last_updated (inherited)
                                                             - company_id (NEW)
                                                             - cik (NEW)
                                                             - shares_outstanding (NEW)
```

---

## Usage by Child Models

### Stocks

```yaml
# stocks/measures.yaml
extends: _base.securities.measures

# Inherits all base measures:
# - avg_close_price, total_volume, max_high, min_low, etc.

# Adds stocks-specific:
simple_measures:
  avg_market_cap: ...
  stock_count: ...

python_measures:
  sharpe_ratio: ...
```

### Options (Future)

```yaml
# options/measures.yaml
extends: _base.securities.measures

# Inherits base measures

# Adds options-specific:
simple_measures:
  avg_premium: ...
  total_open_interest: ...

python_measures:
  calculate_greeks: ...
  implied_volatility: ...
```

### ETFs (Future)

```yaml
# etfs/measures.yaml
extends: _base.securities.measures

# Inherits base measures

# Adds ETF-specific:
simple_measures:
  avg_nav: ...
  tracking_error: ...

computed_measures:
  premium_discount: "(close - nav) / nav * 100"
```

---

## Benefits of Inheritance

1. **Consistency**: All securities have same OHLCV schema
2. **Reusability**: Base measures work across all types
3. **Maintainability**: Fix once, all children benefit
4. **Extensibility**: Easy to add new security types
5. **Documentation**: Clear what's inherited vs. specific

---

## Related Documentation

- [YAML Inheritance](yaml-inheritance.md) - Technical details
- [Stocks Model](../stocks/) - Example implementation
- [Options Model](../options/) - Partial implementation
