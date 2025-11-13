---
id: measures_showcase
title: Measures Showcase
description: Interactive demonstration of measures across all domain models with live data exhibits
tags: [measures, aggregations, analytics, showcase, equity, corporate, forecast]
models: [equity, corporate, forecast, core, macro]
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
  source: {model: equity, table: fact_equity_prices, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
  help_text: Select stocks to analyze (loaded from database)
}

# 📊 Measures Showcase

Interactive demonstration of measures across all domain models with live data exhibits. Use filters above to customize your analysis.

**Domain Models:** equity, corporate, forecast, macro, city_finance, etf

---

## 📈 Equity Model Measures

### Overview Metrics

Quick summary metrics for selected stocks:

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
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  color: ticker
  title: Stock Price Trends
  description: Use the measure selector to choose which price metrics to display
  measure_selector: {
    available_measures: [open, close, high, low, volume_weighted],
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
- `volume_weighted`: Volume-weighted average price (VWAP)

---

### Volume Analysis

Compare trading volume across selected stocks:

$exhibits${
  type: bar_chart
  source: equity.fact_equity_prices
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

### Market Capitalization

Market cap calculated from price data:

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
    market_cap: $#,##0.00M
  collapsible: true
  collapsible_title: "💰 Market Cap (Top 20)"
  collapsible_expanded: false
}

**Measure Demonstrated:**
- `avg_market_cap`: Average market capitalization (aggregation: avg)
- Uses `market_cap` column from equity model (close * shares_outstanding)

---

### Price Volatility & Risk

Standard deviation and volatility metrics:

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

**Measure Demonstrated:**
- `price_volatility`: Price standard deviation (aggregation: stddev)
- Shows both average and standard deviation for context

---

## 🔧 Technical Indicators (Equity Model)

### RSI & Momentum Indicators

Relative Strength Index and momentum metrics:

$exhibits${
  type: data_table
  source: equity.fact_equity_technicals
  columns: [ticker, rsi_14, macd, macd_signal]
  aggregations:
    rsi_14: avg
    macd: avg
    macd_signal: avg
  group_by: [ticker]
  order_by: [{column: rsi_14, direction: desc}]
  limit: 20
  format:
    rsi_14: #,##0.00
    macd: $#,##0.00
    macd_signal: $#,##0.00
  collapsible: true
  collapsible_title: "🎯 Technical Indicators (RSI, MACD)"
  collapsible_expanded: false
}

**Measures Demonstrated:**
- `avg_rsi`: Average RSI across period (aggregation: avg)
- Technical indicators from `fact_equity_technicals` table

---

### Beta & Risk Metrics

Market beta and volatility measures:

$exhibits${
  type: data_table
  source: equity.fact_equity_technicals
  columns: [ticker, beta, volatility_20d, volatility_60d]
  aggregations:
    beta: avg
    volatility_20d: avg
    volatility_60d: avg
  group_by: [ticker]
  order_by: [{column: beta, direction: desc}]
  limit: 20
  format:
    beta: #,##0.00
    volatility_20d: #,##0.00%
    volatility_60d: #,##0.00%
  collapsible: true
  collapsible_title: "⚡ Risk Metrics (Beta, Volatility)"
  collapsible_expanded: false
}

**Measures Demonstrated:**
- `avg_beta`: Average beta vs. market (aggregation: avg)
- `avg_volatility_20d`: 20-day volatility (aggregation: avg)

---

## 📅 Time-Based Aggregations

### Price Range Analysis

Average daily price range (high - low):

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

**Measure Demonstrated:**
- `price_range`: Daily range (computed: high - low, aggregation: avg)

---

### Price Over Time

Track price movements over time with interactive measure selection:

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
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

Performance metrics for forecast models:

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

## 🏢 Corporate Model Measures

### Corporate Fundamentals

Financial metrics from corporate filings:

$exhibits${
  type: data_table
  source: corporate.fact_fundamentals
  columns: [company_id, revenue, net_income, total_assets]
  aggregations:
    revenue: avg
    net_income: avg
    total_assets: avg
  group_by: [company_id]
  order_by: [{column: revenue, direction: desc}]
  limit: 20
  format:
    revenue: $#,##0.00M
    net_income: $#,##0.00M
    total_assets: $#,##0.00M
  collapsible: true
  collapsible_title: "🏢 Corporate Fundamentals (Top 20)"
  collapsible_expanded: false
}

**Measures Demonstrated:**
- Corporate financial measures
- Cross-model relationships (corporate ↔ equity)

---

## 📋 Weighted Aggregate Indices

### Multi-Stock Indices

Compare different index construction methodologies:

$exhibits${
  type: line_chart
  source: equity.fact_equity_prices
  x: trade_date
  y: close
  title: Weighted Aggregate Indices
  description: Compare equal-weighted, volume-weighted, and market-cap weighted indices
  interactive: true
  collapsible: true
  collapsible_title: "📊 Index Construction Methods"
  collapsible_expanded: false
}

**Measures Demonstrated:**
- `equal_weighted_index`: Equal weighted price index
- `volume_weighted_index`: Volume weighted index
- `market_cap_weighted_index`: Market cap weighted index
- `price_weighted_index`: Price weighted (like DJIA)
- `volatility_weighted_index`: Inverse volatility weighted

---

## 📋 Raw Data Export

### Full Data Table

Export complete dataset with all columns:

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
6. **40+ Measures** - Across 7 models (equity, corporate, forecast, macro, city_finance, etf)
7. **Technical Indicators** - RSI, MACD, Beta, Volatility from equity_technicals
8. **Multiple Aggregation Types** - avg, sum, count, stddev, max, min
9. **Format Patterns** - Currency ($#,##0.00), Percentage (#,##0.00%), Integer (#,##0)
10. **Computed Measures** - price_range, market_cap_calc

### Domain Model Structure

**Equity Model** (`equity.yaml`):
- `fact_equity_prices` - OHLCV price data with market_cap
- `fact_equity_technicals` - RSI, MACD, Beta, Volatility, Moving Averages
- `fact_equity_news` - News sentiment
- `dim_equity` - Equity instrument master
- `dim_exchange` - Exchange reference

**Corporate Model** (`corporate.yaml`):
- `fact_fundamentals` - Revenue, earnings, assets
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

### Building the Models

To populate data for these models, run:
```bash
# Build all models from bronze data
python scripts/build_all_models.py --skip-ingestion

# Or build specific models
python scripts/build_all_models.py --models equity corporate forecast
```

---

*This notebook demonstrates real measure usage with live database queries, interactive controls, and formatted output from the new domain model architecture.*
