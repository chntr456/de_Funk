---
type: domain-model-table
table: fact_stock_technicals
table_type: fact
extends: _base.finance.securities._fact_technicals
generated: true
primary_key: [technical_id]
partition_by: [date_id]

# All columns inherited from base _fact_technicals:
#   technical_id, security_id, date_id,
#   sma_20, sma_50, sma_200, ema_12, ema_26,
#   macd, macd_signal, macd_histogram,
#   rsi_14, atr_14,
#   bollinger_upper, bollinger_middle, bollinger_lower,
#   volatility_20d, volatility_60d,
#   volume_sma_20, volume_ratio

# No stock-specific additional columns needed;
# base technicals cover all standard indicators.

# Measures inherited from base: avg_rsi, avg_volatility, avg_atr
---

## Stock Technicals Fact Table

Extends `_base.finance.securities._fact_technicals`. Computed post-build from securities prices. Not loaded from bronze.

All standard technical indicators (SMA, EMA, MACD, RSI, ATR, Bollinger Bands, volatility, volume indicators) are inherited from the base securities template.
