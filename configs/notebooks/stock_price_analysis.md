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
  id: trade_date
  type: date_range
  label: Date Range
  column: trade_date
  operator: between
  default: {start: "2024-01-01", end: "2025-12-05"}
  help_text: Filter by trading date range
}

$filter${
  id: min_volume
  label: Minimum Volume
  type: slider
  column: volume
  min_value: 0
  max_value: 500000000
  step: 10000000
  default: 0
  operator: gte
  help_text: Filter by minimum daily trading volume
}

# Stock Price Analysis

Analyze stock price movements, trading volume, and key metrics for selected equities.

## Key Metrics

$exhibits${
  type: metric_cards
  source: stocks.fact_stock_prices
  metrics: [
    { column: close, label: "Latest Close", aggregation: last },
    { column: close, label: "Avg Price", aggregation: avg },
    { column: volume, label: "Total Volume", aggregation: sum },
    { column: high, label: "52W High", aggregation: max },
    { column: low, label: "52W Low", aggregation: min }
  ]
}

## Price Trend

Daily closing prices over the selected period. Each line represents a different stock.

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: close
  color: ticker
  title: Daily Closing Prices
  height: 400
}

## Volume Analysis

<details>
<summary>Trading Volume Breakdown</summary>

### Daily Trading Volume

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: volume
  color: ticker
  title: Daily Trading Volume
  height: 300
}

### Volume by Ticker

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: ticker
  y: volume
  aggregation: sum
  color: ticker
  title: Total Volume by Stock
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
  x: trade_date
  y: [high, low]
  color: ticker
  title: Daily High and Low Prices
  height: 350
}

### OHLC Summary

$exhibits${
  type: data_table
  source: stocks.fact_stock_prices
  columns: [ticker, trade_date, open, high, low, close, volume]
  sort_by: trade_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Stock Information

<details>
<summary>Stock Details</summary>

Reference information for selected stocks:

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [ticker, company_name, exchange_code, sector, industry, market_cap]
  download: true
}

</details>
