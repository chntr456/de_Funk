---
type: domain-model-table
table: fact_stock_technicals
table_type: fact
generated: true
primary_key: [technical_id]
partition_by: [date_id]

schema:
  - [technical_id, integer, false, "PK"]
  - [security_id, integer, false, "FK to dim_stock", {fk: dim_stock.security_id}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [sma_20, double, true, "20-day SMA"]
  - [sma_50, double, true, "50-day SMA"]
  - [sma_200, double, true, "200-day SMA"]
  - [daily_return, double, true, "Daily return %"]
  - [volatility_20d, double, true, "20-day annualized volatility"]
  - [volatility_60d, double, true, "60-day annualized volatility"]
  - [rsi_14, double, true, "14-day RSI"]
  - [bollinger_upper, double, true, "Bollinger upper"]
  - [bollinger_middle, double, true, "Bollinger middle"]
  - [bollinger_lower, double, true, "Bollinger lower"]
  - [volume_sma_20, double, true, "20-day volume SMA"]
  - [volume_ratio, double, true, "Volume ratio"]

measures:
  - [avg_rsi, avg, rsi_14, "Average RSI", {format: "#,##0.00"}]
  - [avg_volatility, avg, volatility_20d, "Avg volatility", {format: "#,##0.00%"}]
---

## Stock Technicals Fact Table

Computed post-build from securities prices. Not loaded from bronze.
