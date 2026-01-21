---
id: stock_price_analysis
title: Stock Price Analysis
description: Stock price analysis with OHLCV data
tags: [stocks, prices, analysis]
models: [securities, stocks]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: ticker
  label: Stock Ticker
  type: select
  multi: true
  source: {model: securities, table: dim_security, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL"]
  help_text: Select one or more stocks to analyze
}

$filter${
  id: date_id
  type: date_range
  label: Date Range
  column: date_id
  operator: between
  default: {start: 20240101, end: 20251231}
  help_text: Filter by trading date range (YYYYMMDD format)
}

# Stock Price Analysis

Analyze stock price movements, trading volume, and key metrics for selected equities.

## Key Metrics

$exhibits${
  type: metric_cards
  source: securities.fact_security_prices
  metrics: [
    { column: close, label: "Avg Close", aggregation: avg, format: "$,.2f" },
    { column: volume, label: "Total Volume", aggregation: sum, format: ",.0f" },
    { column: high, label: "Max High", aggregation: max, format: "$,.2f" },
    { column: low, label: "Min Low", aggregation: min, format: "$,.2f" }
  ]
}

## Price Trend

$exhibits${
  type: line_chart
  source: securities.fact_security_prices
  x: date_id
  y: close
  color: security_id
  title: Daily Closing Prices
  height: 450
}

## Volume Analysis

<details>
<summary>Trading Volume Breakdown</summary>

### Daily Trading Volume

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: date_id
  y: volume
  color: security_id
  title: Daily Trading Volume
  height: 300
}

</details>

## Price Range Analysis

<details>
<summary>High/Low Price Analysis</summary>

### Daily Price Range (High - Low)

$exhibits${
  type: line_chart
  source: securities.fact_security_prices
  x: date_id
  y: [high, low]
  color: security_id
  title: Daily High and Low Prices
  height: 350
}

</details>

## Data Tables

<details>
<summary>OHLC Summary</summary>

$exhibits${
  type: data_table
  source: securities.fact_security_prices
  columns: [security_id, date_id, open, high, low, close, volume]
  sort_by: date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Security Information</summary>

Reference information for selected securities:

$exhibits${
  type: data_table
  source: securities.dim_security
  columns: [ticker, security_name, exchange_code, asset_type, is_active]
  download: true
}

</details>

<details>
<summary>Stock Details</summary>

Stock-specific information (from stocks model):

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [ticker, exchange_code, sector, industry, market_cap, shares_outstanding]
  download: true
}

</details>
