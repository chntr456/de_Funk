---
id: stock_price_analysis
title: Stock Price Analysis
description: Comprehensive stock price analysis with technical indicators
tags: [stocks, prices, analysis, technical]
models: [stocks]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: ticker
  label: Stock Ticker
  type: select
  multi: true
  source: {model: stocks, table: dim_stock, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL"]
  help_text: Select one or more stocks to analyze
}

$filter${
  id: sector
  label: Sector
  type: select
  multi: true
  source: {model: stocks, table: dim_stock, column: sector}
  help_text: Filter stocks by sector
}

$filter${
  id: exchange_code
  label: Exchange
  type: select
  multi: true
  source: {model: stocks, table: dim_stock, column: exchange_code}
  help_text: Filter by stock exchange
}

$filter${
  id: date_id
  type: date_range
  label: Date Range
  column: date_id
  operator: between
  default: {start: current_date() - 365, end: current_date()}
  help_text: Filter by trading date range
}

# Stock Price Analysis

Analyze stock price movements, trading volume, and key metrics for selected equities.

## Key Metrics

$exhibits${
  type: metric_cards
  source: stocks.fact_stock_prices
  metrics: [
    { column: close, label: "Latest Close", aggregation: last, format: "$,.2f" },
    { column: close, label: "Avg Price", aggregation: avg, format: "$,.2f" },
    { column: volume, label: "Total Volume", aggregation: sum, format: ",.0f" },
    { column: high, label: "52W High", aggregation: max, format: "$,.2f" },
    { column: low, label: "52W Low", aggregation: min, format: "$,.2f" }
  ]
}

## Price Trend

Explore stock price data interactively. Select which metrics to display and how to group them.

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  title: Stock Price Explorer
  height: 450
  measure_selector:
    available_measures: [close, open, high, low, volume]
    default_measures: [close]
    label: Price Metrics
    allow_multiple: true
    selector_type: checkbox
    help_text: Select one or more price metrics to display
  dimension_selector:
    available_dimensions: [ticker, sector, exchange_code]
    default_dimension: ticker
    label: Group By
    selector_type: radio
    applies_to: group_by
    help_text: Choose how to group/color the lines
}

## Technical Indicators

<details>
<summary>Moving Averages & RSI</summary>

### Moving Average Crossovers

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: [close, sma_20, sma_50, sma_200]
  color: ticker
  title: Price with Moving Averages (20, 50, 200 day)
  height: 400
}

### RSI (14-day)

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: rsi_14
  color: ticker
  title: Relative Strength Index (14-day)
  height: 300
}

</details>

## Volume Analysis

<details>
<summary>Trading Volume Breakdown</summary>

### Daily Trading Volume

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: volume
  color: ticker
  title: Daily Trading Volume
  height: 300
}

### Volume Ratio (vs 20-day avg)

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: volume_ratio
  color: ticker
  title: Volume Ratio (Current / 20-day Average)
  height: 300
}

</details>

## Price Range Analysis

<details>
<summary>High/Low Price Analysis</summary>

### Daily Price Range (High - Low)

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: [high, low]
  color: ticker
  title: Daily High and Low Prices
  height: 350
}

### Bollinger Bands

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: [close, bollinger_upper, bollinger_middle, bollinger_lower]
  color: ticker
  title: Bollinger Bands (20-day, 2 std dev)
  height: 400
}

</details>

## Volatility

<details>
<summary>Volatility Analysis</summary>

### Rolling Volatility (Annualized)

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: [volatility_20d, volatility_60d]
  color: ticker
  title: Rolling Volatility (20-day and 60-day)
  height: 350
}

### Daily Returns Distribution

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: daily_return
  color: ticker
  title: Daily Returns (%)
  height: 300
}

</details>

## Data Tables

<details>
<summary>OHLC Summary</summary>

$exhibits${
  type: data_table
  source: stocks.fact_stock_prices
  columns: [ticker, date_id, open, high, low, close, volume, daily_return]
  sort_by: date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Stock Information</summary>

Reference information for selected stocks:

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [ticker, security_name, exchange_code, sector, industry, market_cap, shares_outstanding]
  download: true
}

</details>
