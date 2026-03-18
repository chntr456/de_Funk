---
id: stock_price_analysis
title: Stock Price Analysis
description: Comprehensive stock price analysis with sector breakdown and time aggregations
tags: [stocks, prices, analysis, sectors]
models: [stocks, corporate.entity, temporal]
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
  source: {model: company, table: dim_company, column: sector}
  help_text: Filter by sector (from company dimension via auto-join)
}

$filter${
  id: date
  type: date_range
  label: Date Range
  column: temporal.dim_calendar.date
  operator: between
  default: {start: "2020-01-01", end: current_date()}
  help_text: Filter by trading date range
}

# Stock Price Analysis

Analyze stock price movements, trading volume, and key metrics for selected equities.

## Key Metrics

$exhibits${
  type: metric_cards
  source: securities.stocks.fact_stock_prices
  metrics: [
    { column: securities.stocks.fact_stock_prices.close, label: "Avg Close", aggregation: avg, format: "$,.2f" },
    { column: securities.stocks.fact_stock_prices.volume, label: "Total Volume", aggregation: sum, format: ",.0f" },
    { column: securities.stocks.fact_stock_prices.high, label: "Max High", aggregation: max, format: "$,.2f" },
    { column: securities.stocks.fact_stock_prices.low, label: "Min Low", aggregation: min, format: "$,.2f" }
  ]
}

## Price Trend by Ticker

Daily closing prices grouped by security. Uses auto-join to get ticker from dim_stock.

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: securities.stocks.fact_stock_prices.close
  color: securities.stocks.dim_stock.ticker
  title: Daily Closing Prices by Ticker
  height: 450
}

## Annual Performance

Annual average closing price - aggregated by year from calendar dimension.

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.year
  y: securities.stocks.fact_stock_prices.close
  y_agg: avg
  color: securities.stocks.dim_stock.ticker
  title: Annual Average Closing Price
  height: 400
  group_by: [temporal.dim_calendar.year, securities.stocks.dim_stock.ticker]
}

## Sector Analysis

<details>
<summary>Price by Sector</summary>

Average closing prices grouped by sector (via auto-join to corporate.entity.dim_company).

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: corporate.entity.dim_corporate.entity.sector
  y: securities.stocks.fact_stock_prices.close
  y_agg: avg
  title: Average Close Price by Sector
  height: 400
  group_by: [corporate.entity.dim_corporate.entity.sector]
}

### Volume by Sector

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: corporate.entity.dim_corporate.entity.sector
  y: securities.stocks.fact_stock_prices.volume
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
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: securities.stocks.fact_stock_prices.volume
  color: securities.stocks.dim_stock.ticker
  title: Daily Trading Volume
  height: 300
}

### Monthly Volume (Aggregated)

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.month
  y: securities.stocks.fact_stock_prices.volume
  y_agg: sum
  color: securities.stocks.dim_stock.ticker
  title: Monthly Trading Volume
  height: 350
  group_by: [temporal.dim_calendar.month, securities.stocks.dim_stock.ticker]
}

</details>

## Price Range Analysis

<details>
<summary>High/Low Price Analysis</summary>

### Daily Price Range (High - Low)

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.high, securities.stocks.fact_stock_prices.low]
  color: securities.stocks.dim_stock.ticker
  title: Daily High and Low Prices
  height: 350
}

### Quarterly High/Low

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.quarter
  y: [securities.stocks.fact_stock_prices.high, securities.stocks.fact_stock_prices.low]
  y_agg: [max, min]
  color: securities.stocks.dim_stock.ticker
  title: Quarterly Price Range
  height: 350
  group_by: [temporal.dim_calendar.quarter, securities.stocks.dim_stock.ticker]
}

</details>

## Technical Indicators

Technical indicators computed from price data. These provide insights into momentum, trend, and volatility.

<details>
<summary>Moving Averages</summary>

### Price with Moving Averages

Moving averages help identify trends. SMA-20 shows short-term trend, SMA-50 medium-term, and SMA-200 long-term.

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.close, securities.stocks.fact_stock_prices.sma_20, securities.stocks.fact_stock_prices.sma_50, securities.stocks.fact_stock_prices.sma_200]
  color: securities.stocks.dim_stock.ticker
  title: Price with Moving Averages
  height: 450
}

*Note: Moving average columns (sma_20, sma_50, sma_200) require running `python -m scripts.build.compute_technicals` to populate.*

</details>

<details>
<summary>Momentum Indicators</summary>

### RSI (Relative Strength Index)

RSI measures momentum. Values above 70 suggest overbought conditions, below 30 suggests oversold.

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: securities.stocks.fact_stock_prices.rsi_14
  color: securities.stocks.dim_stock.ticker
  title: RSI (14-day)
  height: 350
}

*Note: RSI column (rsi_14) requires running `python -m scripts.build.compute_technicals` to populate.*

</details>

<details>
<summary>Volatility</summary>

### Bollinger Bands

Bollinger Bands show price volatility. Prices near the upper band may be overbought, near lower band may be oversold.

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.close, securities.stocks.fact_stock_prices.bollinger_upper, securities.stocks.fact_stock_prices.bollinger_middle, securities.stocks.fact_stock_prices.bollinger_lower]
  color: securities.stocks.dim_stock.ticker
  title: Bollinger Bands (20-day, 2 std dev)
  height: 400
}

### Daily Volatility

20-day and 60-day annualized volatility measures price fluctuation intensity.

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.volatility_20d, securities.stocks.fact_stock_prices.volatility_60d]
  color: securities.stocks.dim_stock.ticker
  title: Annualized Volatility
  height: 350
}

*Note: Volatility columns require running `python -m scripts.build.compute_technicals` to populate.*

</details>

<details>
<summary>Volume Analysis</summary>

### Volume vs Moving Average

Volume ratio shows current volume relative to 20-day average. High ratios indicate unusual activity.

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.volume, securities.stocks.fact_stock_prices.volume_sma_20]
  color: securities.stocks.dim_stock.ticker
  title: Volume vs 20-day SMA
  height: 350
}

*Note: Volume SMA column (volume_sma_20) requires running `python -m scripts.build.compute_technicals` to populate.*

</details>

## Data Tables

<details>
<summary>OHLCV Data</summary>

Price data with auto-joined ticker from dim_stock:

$exhibits${
  type: data_table
  source: securities.stocks.fact_stock_prices
  columns: [securities.stocks.dim_stock.ticker, temporal.dim_calendar.date, securities.stocks.fact_stock_prices.open, securities.stocks.fact_stock_prices.high, securities.stocks.fact_stock_prices.low, securities.stocks.fact_stock_prices.close, securities.stocks.fact_stock_prices.volume]
  sort_by: temporal.dim_calendar.date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Stock Dimension</summary>

Stock details including sector, industry (via company), and market cap:

$exhibits${
  type: data_table
  source: securities.stocks.dim_stock
  columns: [securities.stocks.dim_stock.ticker, securities.stocks.dim_stock.stock_id, corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.industry, securities.stocks.dim_stock.market_cap, securities.stocks.dim_stock.shares_outstanding, securities.stocks.dim_stock.exchange_code]
  sort_by: securities.stocks.dim_stock.market_cap
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
  source: securities.stocks.fact_stock_prices
  columns: [securities.stocks.dim_stock.ticker, temporal.dim_calendar.year, securities.stocks.fact_stock_prices.close, securities.stocks.fact_stock_prices.volume, securities.stocks.fact_stock_prices.high, securities.stocks.fact_stock_prices.low]
  aggregations: {close: avg, volume: sum, high: max, low: min}
  group_by: [securities.stocks.dim_stock.ticker, temporal.dim_calendar.year]
  sort_by: temporal.dim_calendar.year
  sort_order: desc
  page_size: 20
  download: true
}

</details>

<details>
<summary>Stock Master</summary>

Master stock dimension:

$exhibits${
  type: data_table
  source: securities.stocks.dim_stock
  columns: [securities.stocks.dim_stock.ticker, securities.stocks.dim_stock.security_name, securities.stocks.dim_stock.asset_type, securities.stocks.dim_stock.exchange_code, securities.stocks.dim_stock.is_active]
  download: true
}

</details>
