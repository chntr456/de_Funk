---
id: measures_showcase
title: Measures Showcase
description: Interactive demonstration of measures across all models with live data exhibits
tags: [measures, aggregations, analytics, showcase]
models: [company, equity, corporate, forecast, core]
author: system
created: 2025-11-13
updated: 2025-11-13
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
  source: {model: company, table: fact_prices, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
  help_text: Select stocks to analyze (loaded from database)
}

# 📊 Measures Showcase

Interactive demonstration of measures across all models with live data exhibits. Use filters above to customize your analysis.

---

## 🏢 Company Model Measures

### Overview Metrics

Quick summary metrics for selected stocks:

$exhibits${
  type: metric_cards
  source: company.fact_prices
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

**Measures Demonstrated:**
- `avg_close_price`: Average closing price (aggregation: avg)
- `total_volume`: Total trading volume (aggregation: sum)
- `max_high`: Highest price in period (aggregation: max)
- `min_low`: Lowest price in period (aggregation: min)

---

### Price Trends with Measure Selector

Dynamically select which price measures to display on the chart:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Stock Price Trends
  description: Use the measure selector to choose which price metrics to display
  measure_selector: {
    available_measures: [open, close, high, low],
    default_measures: [close],
    label: "Select Price Measures",
    selector_type: checkbox,
    help_text: "Choose which price metrics to display on chart"
  }
  interactive: true
  collapsible: true
  collapsible_title: "📈 Price Trends (Interactive)"
  collapsible_expanded: true
}

**Measures Demonstrated:**
- `open`: Opening price
- `close`: Closing price
- `high`: Highest intraday price
- `low`: Lowest intraday price

---

### Volume Analysis

Compare trading volume across selected stocks:

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  title: Total Volume by Ticker
  description: Total trading volume for each stock in the selected date range
  interactive: true
  collapsible: true
  collapsible_title: "📊 Volume Analysis"
  collapsible_expanded: false
}

**Measure Demonstrated:**
- `total_volume`: Total trading volume (aggregation: sum)

---

### Market Capitalization Proxy

Market cap proxy calculated as close price × volume:

$exhibits${
  type: data_table
  source: company.fact_prices
  columns: [ticker, close, volume]
  derived_columns:
    market_cap_proxy: close * volume
  aggregations:
    close: avg
    volume: avg
    market_cap_proxy: avg
  group_by: [ticker]
  order_by: [{column: market_cap_proxy, direction: desc}]
  limit: 20
  format:
    close: $#,##0.00
    volume: #,##0
    market_cap_proxy: $#,##0.00
  collapsible: true
  collapsible_title: "💰 Market Cap Proxy (Top 20)"
  collapsible_expanded: false
}

**Measure Demonstrated:**
- `market_cap`: Market capitalization proxy (expression: close * volume, aggregation: avg)
- Demonstrates derived columns with custom expressions

---

### Price Volatility

Standard deviation of closing prices by ticker:

$exhibits${
  type: data_table
  source: company.fact_prices
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

**Measure Demonstrated:**
- `price_volatility`: Price standard deviation (aggregation: stddev)
- Shows both average and standard deviation for context

---

## 📅 Time-Based Aggregations

### Daily Price Range

Average daily price range (high - low):

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: high
  color: ticker
  title: Average Daily Price Range
  description: Average difference between high and low prices
  interactive: true
  collapsible: true
  collapsible_title: "📈 Daily Price Range"
  collapsible_expanded: false
}

**Measure Demonstrated:**
- `avg_daily_range`: Average daily range (expression: high - low, aggregation: avg)

---

### Price Over Time

Track price movements over time with interactive measure selection:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Price Trends Over Time
  description: Track how prices change over your selected date range
  measure_selector: {
    available_measures: [open, high, low, close, volume_weighted],
    default_measures: [close, volume_weighted],
    label: "Select Measures",
    selector_type: checkbox,
    help_text: "Choose which price measures to track"
  }
  interactive: true
  collapsible: true
  collapsible_title: "⏱️ Price Time Series"
  collapsible_expanded: false
}

**Measures Demonstrated:**
- `close`: Closing price
- `volume_weighted`: Volume-weighted average price (VWAP)
- Time-based analysis with measure selector

---

## 🔮 Forecast Model Measures

### Forecast Accuracy Metrics

Performance metrics for forecast models (if forecast data available):

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

**Measures Demonstrated:**
- `avg_forecast_error`: Average MAE (aggregation: avg)
- `avg_forecast_mape`: Average MAPE (aggregation: avg)
- `best_model_r2`: Best R² score (aggregation: max when not grouped)

---

## 📋 Detailed Data

### Raw Price Data Table

Full price data with download capability:

$exhibits${
  type: data_table
  source: company.fact_prices
  download: true
  collapsible: true
  collapsible_title: "📋 View Raw Data (Exportable)"
  collapsible_expanded: false
}

---

## 💡 Key Features

This notebook demonstrates:

1. **Interactive Filters** - Date range and ticker selection at the top
2. **Measure Selectors** - Dynamically choose which measures to display on charts
3. **Collapsible Exhibits** - Keep notebook organized by hiding/showing sections
4. **Multiple Chart Types** - Line charts, bar charts, data tables, metric cards
5. **40+ Measures** - Across 7 models (company, equity, corporate, forecast, macro, city_finance, etf)
6. **Multiple Aggregation Types** - avg, sum, count, stddev, max, min
7. **Format Patterns** - Currency ($#,##0.00), Percentage (#,##0.00%), Integer (#,##0)
8. **Derived Columns** - Computed fields like market_cap_proxy, daily_range

### Measure Configuration

All measures are defined in `configs/models/*.yaml` files with:
- **description**: Human-readable description
- **source**: Source table and column
- **aggregation**: How to aggregate (avg, sum, count, etc.)
- **format**: Display format pattern
- **tags**: Categorization tags

### Adding Custom Measures

To add a new measure:
1. Edit the relevant model YAML file (e.g., `configs/models/company.yaml`)
2. Add measure definition under `measures:` section
3. Reload the model in the app
4. Use in exhibits with aggregations and formatting

---

*This notebook demonstrates real measure usage with live database queries, interactive controls, and formatted output.*
