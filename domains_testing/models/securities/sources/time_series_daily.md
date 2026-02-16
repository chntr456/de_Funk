---
type: data-source
source: time_series_daily
bronze_table: alpha_vantage/time_series_daily_adjusted
description: "Daily OHLCV price data for all securities"
update_frequency: daily
feeds: [securities_master, stocks]
---

## Time Series Daily

Daily open/high/low/close/volume with adjusted close and split coefficients.
