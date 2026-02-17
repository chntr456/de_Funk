---
type: domain-model-source
source: time_series_daily
extends: _base.finance.securities
maps_to: _fact_prices
from: bronze.alpha_vantage_time_series_daily_adjusted

aliases:
  - [legal_entity_id, "null"]
  - [ticker, symbol]
  - [trade_date, timestamp]
  - [date_id, "CAST(REGEXP_REPLACE(CAST(timestamp AS STRING), '-', '') AS INT)"]
  - [open, open]
  - [high, high]
  - [low, low]
  - [close, close]
  - [volume, volume]
  - [adjusted_close, adjusted_close]
---

## Time Series Daily
Daily OHLCV price data with adjusted close and split coefficients for all securities.
