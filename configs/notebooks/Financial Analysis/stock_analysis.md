---
id: stock_analysis
title: Stock Performance Analysis
description: Analyzing stock prices with volume metrics
tags: [stocks, prices, analysis]
models: [company]
author: analyst@company.com
created: 2024-01-01
updated: 2024-01-15
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-01-05"}
  help_text: Filter by trade date range
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: company, table: fact_prices, column: ticker}
  help_text: Select stocks to analyze (loaded from database)
}

$filter${
  id: volume
  label: Minimum Volume
  type: slider
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 0
  operator: gte
  help_text: Filter by minimum trading volume
}

# Stock Performance Analysis

This analysis examines stock price trends and trading volumes for selected equities. All data is dynamically loaded from the database with real-time filtering capabilities.

## Summary Metrics

Key performance indicators for the selected period:

$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max },
    { measure: low, label: "Min Low", aggregation: min }
  ]
}

## Trend Analysis

### Daily Closing Prices

Track price movements over time for each selected stock. Each line represents a different ticker, colored for easy identification.

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Daily Closing Prices
}

### Trading Volume Comparison

<details>
<summary>Click to view volume analysis</summary>

Total trading volume comparison across selected stocks.

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  title: Trading Volume by Stock
}

High trading volumes often indicate strong investor interest and liquidity.

</details>

## Detailed Data

<details>
<summary>View Complete Dataset</summary>

All available price data for the selected filters. You can sort, search, and download this data.

$exhibits${
  type: data_table
  source: company.fact_prices
  download: true
}

</details>
