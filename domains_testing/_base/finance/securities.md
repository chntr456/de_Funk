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

    measures:
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total trading volume", {format: "#,##0"}]
      - [max_high, max, high, "Maximum high", {format: "$#,##0.00"}]
      - [min_low, min, low, "Minimum low", {format: "$#,##0.00"}]
      - [price_range, expression, "AVG(high - low)", "Average daily range", {format: "$#,##0.00"}]

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
