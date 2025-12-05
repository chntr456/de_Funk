---
id: stock_analysis_dynamic
title: Stock Performance Analysis (Dynamic Filters)
description: Analyzing stock prices with dynamic database-driven filters
tags: [stocks, prices, analysis, dynamic]
models: [stocks]
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
  help_text: Select the date range for analysis
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: company, table: dim_company, column: ticker}
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

This analysis examines stock price trends and trading volumes for selected technology equities. All filters are **dynamically loaded from the database** and update automatically as data changes.

## Summary Metrics

Key performance indicators for the selected period:

$exhibits${
  type: metric_cards
  source: stocks.fact_stock_prices
  metrics: [
    { measure: close, label: "Avg Close", aggregation: avg },
    { measure: volume, label: "Total Volume", aggregation: sum },
    { measure: high, label: "Max High", aggregation: max },
    { measure: low, label: "Min Low", aggregation: min }
  ]
}

## Price Trends

The following chart shows daily closing prices for each stock. Each line represents a different ticker, colored for easy identification.

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: close
  color: ticker
  title: Daily Closing Prices
}

You can see from the chart above that prices vary significantly across different stocks and time periods. The filters above allow you to dynamically explore different time windows and stock combinations.

## Volume Analysis

<details>
<summary>Click to view Trading Volume Comparison</summary>

Total trading volume by stock for the selected period. This chart is sorted by volume in descending order to highlight the most actively traded stocks.

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: ticker
  y: volume
  color: ticker
  sort: { by: volume, order: desc }
  title: Trading Volume by Stock
}

High trading volumes often indicate strong investor interest and liquidity in a particular stock. Use the volume slider above to filter for highly-traded stocks only.

</details>

## Key Insights

Based on the analysis above, we can draw several conclusions:

1. **Dynamic Filtering**: All ticker options are loaded directly from the database
2. **Real-time Updates**: As new stocks are added to the system, they automatically appear in filters
3. **Flexible Analysis**: Adjust date ranges and volume thresholds to explore different scenarios

### Filter Features

The new dynamic filter system provides:

- **Database-Driven**: Options pulled directly from data
- **No Static Lists**: Never hardcode ticker lists again
- **Fuzzy Search**: Find stocks quickly (coming soon)
- **Session State**: Filters persist across notebook interactions
- **SQL Generation**: Automatic WHERE clause generation

## Detailed Data

<details>
<summary>View Complete Dataset</summary>

The table below contains all available data points for the selected filters. You can sort, search, and download this data for further analysis.

$exhibits${
  type: data_table
  source: stocks.fact_stock_prices
  download: true
  sortable: true
  pagination: true
  page_size: 50
}

</details>

---

**Note**: This notebook demonstrates the new dynamic filter system. Filters are no longer rendered in the notebook view - they appear only in the sidebar for a cleaner interface.
