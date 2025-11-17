---
id: measures_showcase
title: Measures Showcase
description: Interactive demonstration of measures across domain models with live data exhibits
tags: [measures, aggregations, analytics, showcase, equity, forecast]
models: [equity, corporate, forecast, core]
author: system
created: 2025-11-13
updated: 2025-11-14
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2025-10-20"}
  help_text: Filter by trade date range
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: equity, table: fact_equity_prices, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
  help_text: Select stocks to analyze (loaded from database)
}

# 📊 Measures Showcase

Interactive demonstration of measures across domain models with live data exhibits. Use filters above to customize your analysis.

**Domain Models:** equity, corporate, forecast

---

## 📈 Equity Model - Price & Volume Measures

### Overview Metrics

$exhibits${
  type: metric_cards
  source: equity.fact_equity_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max },
    { measure: low, label: "Min Low", aggregation: min }
  ]
  collapsible: true
  collapsible_title: "💳 Key Metrics Summary"
  collapsible_expanded: true
}

---

### Price Trends by Ticker

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Stock Price Trends
  measure_selector: {
    available_measures: [open, close, high, low, volume_weighted],
    default_measures: [close],
    label: "Select Price Measures",
    selector_type: checkbox
  }
  interactive: true
  collapsible: true
  collapsible_title: "📈 Price Trends (Interactive)"
  collapsible_expanded: true
}

---

### Volume Analysis

$exhibits${
  type: bar_chart
  source: equity.fact_equity_prices
  x: ticker
  y: volume
  color: ticker
  title: Total Volume by Ticker
  interactive: true
  collapsible: true
  collapsible_title: "📊 Volume Analysis"
  collapsible_expanded: false
}

---

### Market Capitalization

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, close, volume, market_cap]
  aggregations:
    close: avg
    volume: avg
    market_cap: avg
  group_by: [ticker]
  order_by: [{column: market_cap, direction: desc}]
  limit: 20
  format:
    close: $#,##0.00
    volume: #,##0
    market_cap: $#,##0.00
  collapsible: true
  collapsible_title: "💰 Market Cap (Top 20)"
  collapsible_expanded: false
}

---

### Price Volatility

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, close]
  aggregations:
    close_avg: avg
    close_stddev: stddev
    trading_days: count
  group_by: [ticker]
  order_by: [{column: close_stddev, direction: desc}]
  limit: 20
  format:
    close_avg: $#,##0.00
    close_stddev: $#,##0.00
    trading_days: #,##0
  collapsible: true
  collapsible_title: "📉 Price Volatility (Top 20)"
  collapsible_expanded: false
}

---

## 📅 Time-Based Aggregations

### Price Range Analysis

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [ticker, high, low]
  derived_columns:
    price_range: high - low
  aggregations:
    high: avg
    low: avg
    price_range: avg
  group_by: [ticker]
  order_by: [{column: price_range, direction: desc}]
  limit: 20
  format:
    high: $#,##0.00
    low: $#,##0.00
    price_range: $#,##0.00
  collapsible: true
  collapsible_title: "📈 Daily Price Range"
  collapsible_expanded: false
}

---

### Price Time Series by Ticker

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Price Trends Over Time
  measure_selector: {
    available_measures: [open, high, low, close, volume_weighted],
    default_measures: [close, volume_weighted],
    label: "Select Measures",
    selector_type: checkbox
  }
  interactive: true
  collapsible: true
  collapsible_title: "⏱️ Price Time Series"
  collapsible_expanded: false
}

---

## 📊 Weighted Aggregate Indices

### Market-Wide Index Construction

Compare different index construction methodologies aggregated across all selected tickers:

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Equal Weighted Index
  description: Simple average of all selected stock prices
  aggregations:
    close: avg
  group_by: [trade_date]
  interactive: true
  collapsible: true
  collapsible_title: "📊 Equal Weighted Index (All Tickers)"
  collapsible_expanded: true
}

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [volume_weighted_index]
  title: Volume Weighted Average Price (VWAP)
  description: Price weighted by trading volume across all selected tickers
  interactive: true
  collapsible: true
  collapsible_title: "💹 Volume Weighted Index (All Tickers)"
  collapsible_expanded: true
}

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  columns: [trade_date, close, volume]
  aggregations:
    close: avg
    volume: sum
  group_by: [trade_date]
  order_by: [{column: trade_date, direction: desc}]
  limit: 30
  format:
    close: $#,##0.00
    volume: #,##0
  collapsible: true
  collapsible_title: "📋 Aggregated Values Over Time"
  collapsible_expanded: false
}

---

### Market Cap Weighted Index

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [market_cap_weighted_index]
  title: Market Cap Weighted Index
  description: Price weighted by market capitalization (close * volume proxy)
  interactive: true
  collapsible: true
  collapsible_title: "💰 Market Cap Weighted Index"
  collapsible_expanded: false
}

---

### Index Comparison

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [equal_weighted_index, volume_weighted_index, market_cap_weighted_index, price_weighted_index]
  title: All Index Methods Comparison
  description: Compare all weighting methodologies in one chart
  interactive: true
  collapsible: true
  collapsible_title: "📊 All Index Methods Comparison"
  collapsible_expanded: false
}

---

## 🔮 Forecast Model Measures

### Forecast Accuracy Metrics

$exhibits${
  type: data_table
  source: forecast.fact_forecast_metrics
  columns: [model_name, mae, mape, r2_score, num_predictions]
  aggregations:
    mae: avg
    mape: avg
    r2_score: avg
    num_predictions: sum
  group_by: [model_name]
  order_by: [{column: r2_score, direction: desc}]
  limit: 10
  format:
    mae: $#,##0.00
    mape: #,##0.00%
    r2_score: #,##0.0000
    num_predictions: #,##0
  collapsible: true
  collapsible_title: "🔮 Forecast Model Performance"
  collapsible_expanded: false
}

---

## 📋 Raw Data Export

### Full Data Table

$exhibits${
  type: data_table
  source: equity.fact_equity_prices
  download: true
  collapsible: true
  collapsible_title: "📋 View Raw Data (Exportable)"
  collapsible_expanded: false
}

---

## 💡 Key Features

This notebook demonstrates:

1. **New Domain Models** - equity, corporate, forecast (replaces deprecated company model)
2. **Interactive Filters** - Date range and ticker selection
3. **Measure Selectors** - Dynamically choose which measures to display on charts
4. **Collapsible Exhibits** - Keep notebook organized by hiding/showing sections
5. **Multiple Chart Types** - Line charts, bar charts, data tables, metric cards
6. **Multiple Aggregation Types** - avg, sum, count, stddev, max, min
7. **Format Patterns** - Currency ($#,##0.00), Percentage (#,##0.00%), Integer (#,##0)
8. **Computed Measures** - price_range, market_cap
9. **Weighted Aggregates** - Equal, volume, market-cap weighted indices across all tickers

### Domain Model Structure

**Equity Model** (`equity.yaml`):
- `fact_equity_prices` - OHLCV price data with market_cap
- `dim_equity` - Equity instrument master
- `dim_exchange` - Exchange reference

**Corporate Model** (`corporate.yaml`):
- `dim_corporate` - Corporate entity master

**Forecast Model** (`forecast.yaml`):
- `fact_forecasts` - Price predictions
- `fact_forecast_metrics` - Model performance (MAE, MAPE, R²)

### Measure Configuration

All measures are defined in `configs/models/*.yaml` files with:
- **description**: Human-readable description
- **source**: Source table and column
- **aggregation**: How to aggregate (avg, sum, count, etc.)
- **format**: Display format pattern
- **tags**: Categorization tags
- **type**: simple, computed, or weighted

---

*This notebook demonstrates real measure usage with live database queries, interactive controls, and formatted output from the new domain model architecture.*
