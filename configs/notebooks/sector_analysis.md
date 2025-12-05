---
id: sector_analysis
title: Sector Analysis
description: Cross-sector and industry-level aggregated analysis
tags: [sector, industry, aggregates, comparison]
models: [stocks, company]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: sector
  label: Sector
  type: select
  multi: true
  source: {model: stocks, table: dim_stock, column: sector}
  help_text: Select one or more sectors to analyze
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
  id: min_market_cap
  label: Min Market Cap ($B)
  type: slider
  column: market_cap
  min_value: 0
  max_value: 1000000000000
  step: 10000000000
  default: 0
  operator: gte
  help_text: Filter by minimum market capitalization
}

# Sector Analysis

Aggregate analysis across sectors and industries. Compare performance, volume, and composition.

## Sector Overview

### Companies by Sector

$exhibits${
  type: bar_chart
  source: stocks.dim_stock
  x: sector
  y: ticker
  aggregation: count
  title: Number of Companies by Sector
  height: 350
}

### Total Market Cap by Sector

$exhibits${
  type: bar_chart
  source: stocks.dim_stock
  x: sector
  y: market_cap
  aggregation: sum
  title: Total Market Cap by Sector ($)
  height: 350
}

## Sector Performance

### Average Price by Sector

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: sector
  y: close
  aggregation: avg
  title: Average Closing Price by Sector
  height: 350
  join: stocks.dim_stock on ticker
}

### Trading Volume by Sector

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: sector
  y: volume
  aggregation: sum
  title: Total Trading Volume by Sector
  height: 350
  join: stocks.dim_stock on ticker
}

## Industry Breakdown

<details>
<summary>Industry-Level Analysis</summary>

### Companies by Industry

$exhibits${
  type: bar_chart
  source: stocks.dim_stock
  x: industry
  y: ticker
  aggregation: count
  title: Companies by Industry
  height: 500
  orientation: horizontal
}

### Market Cap by Industry

$exhibits${
  type: bar_chart
  source: stocks.dim_stock
  x: industry
  y: market_cap
  aggregation: sum
  title: Market Cap by Industry
  height: 500
  orientation: horizontal
}

</details>

## Top Companies

<details>
<summary>Top Companies by Market Cap</summary>

### Largest Companies

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [ticker, company_name, sector, industry, market_cap, exchange_code]
  sort_by: market_cap
  sort_order: desc
  page_size: 25
  download: true
}

</details>

## Sector Composition

<details>
<summary>Sector & Industry Distribution</summary>

### Sector Distribution

$exhibits${
  type: pie_chart
  source: stocks.dim_stock
  labels: sector
  values: market_cap
  aggregation: sum
  title: Market Cap Distribution by Sector
}

### Sector Summary Table

$exhibits${
  type: data_table
  source: stocks.dim_stock
  columns: [sector, ticker, market_cap]
  aggregations: [
    { column: ticker, aggregation: count, label: "Companies" },
    { column: market_cap, aggregation: sum, label: "Total Market Cap" },
    { column: market_cap, aggregation: avg, label: "Avg Market Cap" }
  ]
  group_by: sector
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

</details>
