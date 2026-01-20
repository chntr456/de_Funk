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
  source: {model: company, table: dim_company, column: sector}
  help_text: Select one or more sectors to analyze
}

$filter${
  id: industry
  label: Industry
  type: select
  multi: true
  source: {model: company, table: dim_company, column: industry}
  help_text: Filter by specific industries
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
  id: date
  type: date_range
  label: Date Range
  column: date
  operator: between
  default: {start: "2024-01-01", end: current_date()}
  help_text: Filter by trading date range
}

# Sector Analysis

Aggregate analysis across sectors and industries. Compare performance, volume, and composition.

## Sector Overview

### Companies by Sector

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: sector
  y: ticker_primary
  aggregation: count
  title: Number of Companies by Sector
  height: 350
}

### Total Market Cap by Sector

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: sector
  y: market_cap
  aggregation: sum
  title: Total Market Cap by Sector ($)
  height: 350
}

## Sector Performance

### Company Metrics by Sector

$exhibits${
  type: metric_cards
  source: company.dim_company
  metrics: [
    { column: ticker_primary, label: "Total Companies", aggregation: count },
    { column: market_cap, label: "Total Market Cap", aggregation: sum, format: "$,.0f" },
    { column: market_cap, label: "Avg Market Cap", aggregation: avg, format: "$,.0f" },
    { column: shares_outstanding, label: "Total Shares", aggregation: sum, format: ",.0f" }
  ]
}

### Trading Volume (All Stocks)

NOTE: Sector-based volume aggregation requires cross-model joins (stocks.fact_stock_prices -> company.dim_company)

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: volume
  aggregation: sum
  title: Total Trading Volume Over Time
  height: 350
}

## Industry Breakdown

<details>
<summary>Industry-Level Analysis</summary>

### Companies by Industry

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: industry
  y: ticker_primary
  aggregation: count
  title: Companies by Industry
  height: 500
  orientation: horizontal
}

### Market Cap by Industry

$exhibits${
  type: bar_chart
  source: company.dim_company
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
  source: company.dim_company
  columns: [ticker_primary, company_name, sector, industry, market_cap, shares_outstanding]
  sort_by: market_cap
  sort_order: desc
  page_size: 25
  download: true
}

</details>

## Sector Composition

<details>
<summary>Sector & Industry Distribution</summary>

### Sector Summary Table

$exhibits${
  type: data_table
  source: company.dim_company
  columns: [sector, ticker_primary, market_cap]
  aggregations: [
    { column: ticker_primary, aggregation: count, label: "Companies" },
    { column: market_cap, aggregation: sum, label: "Total Market Cap" },
    { column: market_cap, aggregation: avg, label: "Avg Market Cap" }
  ]
  group_by: sector
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

### Industry Summary Table

$exhibits${
  type: data_table
  source: company.dim_company
  columns: [industry, sector, ticker_primary, market_cap]
  aggregations: [
    { column: ticker_primary, aggregation: count, label: "Companies" },
    { column: market_cap, aggregation: sum, label: "Total Market Cap" }
  ]
  group_by: [sector, industry]
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

</details>

## Price Performance

<details>
<summary>Price Analysis by Sector</summary>

### Stock Returns

NOTE: Sector-based aggregation requires cross-model joins (planned feature)

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: close
  title: Stock Prices Over Time
  height: 400
  columns: [date_id, close, security_id]
}

### Stock Volatility

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: date_id
  y: volume
  title: Trading Volume Over Time
  height: 350
  columns: [date_id, volume, security_id]
}

</details>
