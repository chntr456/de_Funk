---
type: domain-model-table
table: fact_stock_prices
extends: _base.finance.securities._fact_prices
table_type: fact
from: securities_master.fact_security_prices
primary_key: [price_id]
partition_by: [date_id]
filters:
  - "asset_type = 'stocks'"

schema:
  - [price_id, integer, false, "PK"]
  - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [ticker, string, false, "Trading symbol"]
  - [trade_date, date, false, "Trading date"]
  - [open, double, true, "Opening price"]
  - [high, double, true, "High price"]
  - [low, double, true, "Low price"]
  - [close, double, false, "Closing price"]
  - [volume, long, true, "Trading volume"]
  - [adjusted_close, double, true, "Adjusted close"]

measures:
  - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
  - [total_volume, sum, volume, "Total volume", {format: "#,##0"}]
---

## Stock Prices Fact Table

Filtered from securities_master.fact_security_prices for stocks only.
