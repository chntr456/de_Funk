---
type: domain-model
model: stocks
version: 3.1
description: "Stock equities with company linkage, technicals, dividends, and splits"
extends: [_base.finance.securities]
depends_on: [temporal, securities_master, company]

sources_from: sources/
storage:
  format: delta
  silver:
    root: storage/silver/stocks/

graph:
  edges:
    - [stock_to_security, dim_stock, securities_master.dim_security, [security_id=security_id], many_to_one, securities_master]
    - [stock_to_company, dim_stock, company.dim_company, [company_id=company_id], many_to_one, company]
    - [prices_to_stock, fact_stock_prices, dim_stock, [security_id=security_id], many_to_one, null]
    - [prices_to_calendar, fact_stock_prices, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [dividends_to_stock, fact_dividends, dim_stock, [security_id=security_id], many_to_one, null]
    - [dividends_to_calendar, fact_dividends, temporal.dim_calendar, [ex_dividend_date_id=date_id], many_to_one, temporal]
    - [splits_to_stock, fact_splits, dim_stock, [security_id=security_id], many_to_one, null]
    - [splits_to_calendar, fact_splits, temporal.dim_calendar, [effective_date_id=date_id], many_to_one, temporal]
    - [technicals_to_stock, fact_stock_technicals, dim_stock, [security_id=security_id], many_to_one, null]
    - [technicals_to_calendar, fact_stock_technicals, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [stock_to_exchange, dim_stock, dim_exchange, [exchange_id=exchange_id], many_to_one, null]
  paths:
    company_to_dividends:
      steps:
        - {from: company.dim_company, to: dim_stock, via: company_id}
        - {from: dim_stock, to: fact_dividends, via: security_id}
    prices_to_sector:
      steps:
        - {from: fact_stock_prices, to: dim_stock, via: security_id}

build:
  partitions: [date_id]
  sort_by: [security_id, date_id]
  optimize: true
  phases:
    1: { tables: [dim_stock] }
    2: { tables: [fact_stock_prices, fact_stock_technicals, fact_dividends, fact_splits] }

measures:
  simple:
    - [stock_count, count_distinct, dim_stock.stock_id, "Number of stocks", {format: "#,##0"}]
    - [total_dividends, sum, fact_dividends.dividend_amount, "Total dividends paid", {format: "$#,##0.00"}]
    - [split_count, count_distinct, fact_splits.split_id, "Number of splits", {format: "#,##0"}]
  computed:
    - [avg_rsi, expression, "AVG(rsi_14)", "Average RSI", {format: "#,##0.00", source_table: fact_stock_technicals}]

metadata:
  domain: securities
  owner: data_engineering
status: active
---

## Stocks Model

Stock equities with company linkage, technical indicators, dividends, and splits.

### Build Order

```
temporal -> securities_master -> company -> stocks
```
