---
id: stock_price_analysis
title: Stock Price Analysis
description: Comprehensive stock price analysis with sector breakdown and time aggregations
tags: [stocks, prices, analysis, sectors]
models: [securities, stocks, temporal]
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
  help_text: Filter by sector (from stock dimension)
}

$filter${
  id: year
  label: Year
  type: select
  multi: true
  source: {model: temporal, table: dim_calendar, column: year}
  help_text: Filter by year for time-based analysis
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

## Price Trend by Ticker

Daily closing prices grouped by security. Uses auto-join to get ticker from dim_security.

$exhibits${
  type: line_chart
  source: securities.fact_security_prices
  x: date_id
  y: close
  color: ticker
  title: Daily Closing Prices by Ticker
  height: 450
}

## Annual Performance

Annual average closing price - aggregated by year from calendar dimension.

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: year
  y: close
  y_agg: avg
  color: ticker
  title: Annual Average Closing Price
  height: 400
  group_by: [year, ticker]
}

## Sector Analysis

<details>
<summary>Price by Sector</summary>

Average closing prices grouped by sector (via auto-join to stocks.dim_stock).

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: sector
  y: close
  y_agg: avg
  title: Average Close Price by Sector
  height: 400
  group_by: [sector]
}

### Volume by Sector

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: sector
  y: volume
  y_agg: sum
  title: Total Volume by Sector
  height: 350
}

</details>

## Volume Analysis

<details>
<summary>Trading Volume Breakdown</summary>

### Daily Trading Volume

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: date_id
  y: volume
  color: ticker
  title: Daily Trading Volume
  height: 300
}

### Monthly Volume (Aggregated)

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: month
  y: volume
  y_agg: sum
  color: ticker
  title: Monthly Trading Volume
  height: 350
  group_by: [month, ticker]
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
  color: ticker
  title: Daily High and Low Prices
  height: 350
}

### Quarterly High/Low

$exhibits${
  type: bar_chart
  source: securities.fact_security_prices
  x: quarter
  y: [high, low]
  y_agg: [max, min]
  color: ticker
  title: Quarterly Price Range
  height: 350
  group_by: [quarter, ticker]
}

</details>

## Data Tables

<details>
<summary>OHLCV Data</summary>

Price data with auto-joined ticker from dim_security:

$exhibits${
  type: data_table
  source: securities.fact_security_prices
  columns: [ticker, date_id, open, high, low, close, volume]
  sort_by: date_id
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Stock Dimension</summary>

Stock details including sector, industry, and market cap:

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [ticker, security_id, sector, industry, market_cap, shares_outstanding, exchange_code]
  sort_by: market_cap
  sort_order: desc
  page_size: 25
  download: true
}

</details>

<details>
<summary>Annual Summary</summary>

Annual aggregated metrics per stock:

$exhibits${
  type: data_table
  source: securities.fact_security_prices
  columns: [ticker, year, close, volume, high, low]
  aggregations: {close: avg, volume: sum, high: max, low: min}
  group_by: [ticker, year]
  sort_by: year
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Security Master</summary>

Master security dimension (all asset types):

$exhibits${
  type: data_table
  source: securities.dim_security
  columns: [ticker, security_name, asset_type, exchange_code, is_active]
  download: true
}

</details>
