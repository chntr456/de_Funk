---
id: sector_analysis
title: Sector Analysis
description: Cross-sector and industry-level aggregated analysis
tags: [sector, industry, aggregates, comparison]
models: [stocks, corporate.entity]
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
  column: temporal.dim_calendar.date
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
  source: corporate.entity.dim_company
  x: corporate.entity.dim_corporate.entity.sector
  y: corporate.entity.dim_corporate.entity.ticker
  aggregation: count
  title: Number of Companies by Sector
  height: 350
}

### Total Market Cap by Sector

$exhibits${
  type: bar_chart
  source: corporate.entity.dim_company
  x: corporate.entity.dim_corporate.entity.sector
  y: corporate.entity.dim_corporate.entity.market_cap
  aggregation: sum
  title: Total Market Cap by Sector ($)
  height: 350
}

## Sector Performance

### Company Metrics by Sector

$exhibits${
  type: metric_cards
  source: corporate.entity.dim_company
  metrics: [
    { column: corporate.entity.dim_corporate.entity.ticker, label: "Total Companies", aggregation: count },
    { column: corporate.entity.dim_corporate.entity.market_cap, label: "Total Market Cap", aggregation: sum, format: "$,.0f" },
    { column: corporate.entity.dim_corporate.entity.market_cap, label: "Avg Market Cap", aggregation: avg, format: "$,.0f" },
    { column: corporate.entity.dim_corporate.entity.shares_outstanding, label: "Total Shares", aggregation: sum, format: ",.0f" }
  ]
}

### Sector Performance Summary

Sector-level metrics including total market cap, stock count, and average market cap.

$exhibits${
  type: data_table
  source: corporate.entity.dim_company
  columns: [corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.ticker, corporate.entity.dim_corporate.entity.market_cap, corporate.entity.dim_corporate.entity.shares_outstanding]
  group_by: [corporate.entity.dim_corporate.entity.sector]
  aggregations: [
    { column: corporate.entity.dim_corporate.entity.ticker, aggregation: count, label: "# Stocks" },
    { column: corporate.entity.dim_corporate.entity.market_cap, aggregation: sum, label: "Total Market Cap", format: "$,.0f" },
    { column: corporate.entity.dim_corporate.entity.market_cap, aggregation: avg, label: "Avg Market Cap", format: "$,.0f" },
    { column: corporate.entity.dim_corporate.entity.shares_outstanding, aggregation: sum, label: "Total Shares", format: ",.0f" }
  ]
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

### Trading Volume by Sector

Total trading volume aggregated by sector. Uses auto-join from prices to company dimension.

$exhibits${
  type: bar_chart
  source: securities.stocks.fact_stock_prices
  x: corporate.entity.dim_corporate.entity.sector
  y: securities.stocks.fact_stock_prices.volume
  aggregation: sum
  title: Total Trading Volume by Sector
  height: 350
  group_by: [corporate.entity.dim_corporate.entity.sector]
}

## Industry Breakdown

<details>
<summary>Industry-Level Analysis</summary>

### Companies by Industry

$exhibits${
  type: bar_chart
  source: corporate.entity.dim_company
  x: corporate.entity.dim_corporate.entity.industry
  y: corporate.entity.dim_corporate.entity.ticker
  aggregation: count
  title: Companies by Industry
  height: 500
  orientation: horizontal
}

### Market Cap by Industry

$exhibits${
  type: bar_chart
  source: corporate.entity.dim_company
  x: corporate.entity.dim_corporate.entity.industry
  y: corporate.entity.dim_corporate.entity.market_cap
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
  source: corporate.entity.dim_company
  columns: [corporate.entity.dim_corporate.entity.ticker, corporate.entity.dim_corporate.entity.company_name, corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.industry, corporate.entity.dim_corporate.entity.market_cap, corporate.entity.dim_corporate.entity.shares_outstanding]
  sort_by: corporate.entity.dim_corporate.entity.market_cap
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
  source: corporate.entity.dim_company
  columns: [corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.ticker, corporate.entity.dim_corporate.entity.market_cap]
  aggregations: [
    { column: corporate.entity.dim_corporate.entity.ticker, aggregation: count, label: "Companies" },
    { column: corporate.entity.dim_corporate.entity.market_cap, aggregation: sum, label: "Total Market Cap" },
    { column: corporate.entity.dim_corporate.entity.market_cap, aggregation: avg, label: "Avg Market Cap" }
  ]
  group_by: corporate.entity.dim_corporate.entity.sector
  sort_by: market_cap_sum
  sort_order: desc
  download: true
}

### Industry Summary Table

$exhibits${
  type: data_table
  source: corporate.entity.dim_company
  columns: [corporate.entity.dim_corporate.entity.industry, corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.ticker, corporate.entity.dim_corporate.entity.market_cap]
  aggregations: [
    { column: corporate.entity.dim_corporate.entity.ticker, aggregation: count, label: "Companies" },
    { column: corporate.entity.dim_corporate.entity.market_cap, aggregation: sum, label: "Total Market Cap" }
  ]
  group_by: [corporate.entity.dim_corporate.entity.sector, corporate.entity.dim_corporate.entity.industry]
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
  source: securities.stocks.fact_stock_prices
  x: corporate.entity.dim_corporate.entity.sector
  y: securities.stocks.fact_stock_prices.close
  aggregation: avg
  title: Average Close Price by Sector
  height: 400
  group_by: [corporate.entity.dim_corporate.entity.sector]
}

</details>
