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
  help_text: Filter by sector (from company dimension)
}

$filter${
  id: industry
  label: Industry
  type: select
  multi: true
  source: {model: company, table: dim_company, column: industry}
  help_text: Filter by industry (from company dimension)
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
  column: stocks.fact_stock_prices.trade_date
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
  x: company.dim_company.sector
  y: company.dim_company.ticker
  aggregation: count
  title: Number of Companies by Sector
  height: 350
}

### Total Market Cap by Sector

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: company.dim_company.sector
  y: company.dim_company.market_cap
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
    { column: company.dim_company.ticker, label: "Total Companies", aggregation: count },
    { column: company.dim_company.market_cap, label: "Total Market Cap", aggregation: sum, format: "$,.0f" },
    { column: company.dim_company.market_cap, label: "Avg Market Cap", aggregation: avg, format: "$,.0f" },
    { column: company.dim_company.shares_outstanding, label: "Total Shares", aggregation: sum, format: ",.0f" }
  ]
}

### Sector Performance Summary

Sector-level metrics including total market cap, stock count, and average market cap.

$exhibits${
  type: data_table
  source: company.dim_company
  columns: [company.dim_company.sector, company.dim_company.ticker, company.dim_company.market_cap, company.dim_company.shares_outstanding]
  group_by: [company.dim_company.sector]
  aggregations: [
    { column: company.dim_company.ticker, aggregation: count, label: "# Stocks" },
    { column: company.dim_company.market_cap, aggregation: sum, label: "Total Market Cap", format: "$,.0f" },
    { column: company.dim_company.market_cap, aggregation: avg, label: "Avg Market Cap", format: "$,.0f" },
    { column: company.dim_company.shares_outstanding, aggregation: sum, label: "Total Shares", format: ",.0f" }
  ]
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

### Trading Volume by Sector

Total trading volume aggregated by sector. Uses auto-join from prices to company dimension.

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: company.dim_company.sector
  y: stocks.fact_stock_prices.volume
  aggregation: sum
  title: Total Trading Volume by Sector
  height: 350
  group_by: [company.dim_company.sector]
}

## Industry Breakdown

<details>
<summary>Industry-Level Analysis</summary>

### Companies by Industry

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: company.dim_company.industry
  y: company.dim_company.ticker
  aggregation: count
  title: Companies by Industry
  height: 500
  orientation: horizontal
}

### Market Cap by Industry

$exhibits${
  type: bar_chart
  source: company.dim_company
  x: company.dim_company.industry
  y: company.dim_company.market_cap
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
  columns: [company.dim_company.ticker, company.dim_company.company_name, company.dim_company.sector, company.dim_company.industry, company.dim_company.market_cap, company.dim_company.shares_outstanding]
  sort_by: company.dim_company.market_cap
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
  columns: [company.dim_company.sector, company.dim_company.ticker, company.dim_company.market_cap]
  aggregations: [
    { column: company.dim_company.ticker, aggregation: count, label: "Companies" },
    { column: company.dim_company.market_cap, aggregation: sum, label: "Total Market Cap" },
    { column: company.dim_company.market_cap, aggregation: avg, label: "Avg Market Cap" }
  ]
  group_by: company.dim_company.sector
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

### Industry Summary Table

$exhibits${
  type: data_table
  source: company.dim_company
  columns: [company.dim_company.industry, company.dim_company.sector, company.dim_company.ticker, company.dim_company.market_cap]
  aggregations: [
    { column: company.dim_company.ticker, aggregation: count, label: "Companies" },
    { column: company.dim_company.market_cap, aggregation: sum, label: "Total Market Cap" }
  ]
  group_by: [company.dim_company.sector, company.dim_company.industry]
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

</details>

## Price Performance

<details>
<summary>Price Analysis by Sector</summary>

### Average Close Price by Sector

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: company.dim_company.sector
  y: stocks.fact_stock_prices.adjusted_close
  aggregation: avg
  title: Average Adjusted Close Price by Sector
  height: 400
  group_by: [company.dim_company.sector]
}

</details>
