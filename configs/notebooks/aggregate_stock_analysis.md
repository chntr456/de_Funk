---
id: aggregate_stock_analysis
title: Aggregate Stock Index Analysis
description: Analyzing aggregated stock performance using various weighting methods
tags: [stocks, aggregate, index, weighted]
models: [stocks]
author: analyst@company.com
created: 2024-01-15
updated: 2024-01-15
---

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2025-10-20"}
  help_text: Filter by trade date range
}

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: true
  source: {model: stocks, table: fact_stock_prices, column: ticker}
  default: ["AAPL"]
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

# Aggregate Stock Index Analysis

This analysis aggregates stock performance across multiple equities using various weighting methodologies. Compare how different weighting approaches (equal-weighted, volume-weighted, market cap-weighted, and more) affect the resulting index.

## 📊 Overview

Summary metrics for selected stocks:

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

## 📈 Aggregate Indices

Aggregated stock indices with dynamic weighting methods. These indices combine multiple stocks into a single performance indicator.

### Primary Weighting Methods

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [equal_weighted_index, volume_weighted_index, market_cap_weighted_index]
  title: Aggregate Price Index
}

This chart shows three fundamental index construction methods:
- **Equal-Weighted**: Each stock has equal influence regardless of size
- **Volume-Weighted**: Stocks with higher trading volume have more influence
- **Market Cap-Weighted**: Larger companies (by market cap) dominate the index

## 📊 Advanced Aggregates

### Alternative Weighting Methods

<details>
<summary>Click to view alternative weighting approaches</summary>

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [price_weighted_index, volume_deviation_weighted_index, volatility_weighted_index]
  title: Alternative Weighting Methods
}

Alternative weighting strategies:
- **Price-Weighted**: Higher-priced stocks have more influence (like Dow Jones)
- **Volume Deviation-Weighted**: Weights based on volume volatility
- **Volatility-Weighted**: Less volatile stocks receive higher weights

</details>

### Comprehensive Comparison

<details>
<summary>Click to view all 6 weighting methods side-by-side</summary>

$exhibits${
  type: weighted_aggregate_chart
  aggregate_by: trade_date
  value_measures: [equal_weighted_index, volume_weighted_index, market_cap_weighted_index, price_weighted_index, volume_deviation_weighted_index, volatility_weighted_index]
  title: All Weighting Methods Comparison
}

This comprehensive view allows you to compare all six weighting methodologies simultaneously to understand how different approaches affect index performance.

</details>

## 🔍 Comparison & Analysis

### Individual Stock Performance

For reference, view individual stock prices to compare with the aggregate indices above.

$exhibits${
  type: line_chart
  source: stocks.fact_stock_prices
  x: trade_date
  y: close
  color: ticker
  title: Individual Stock Prices (For Comparison)
}

### Volume Distribution Analysis

<details>
<summary>Click to view volume distribution</summary>

Total trading volume by stock - this affects market cap weighting calculations.

$exhibits${
  type: bar_chart
  source: stocks.fact_stock_prices
  x: ticker
  y: volume
  color: ticker
  title: Volume Distribution by Stock
}

Stocks with higher volume tend to have more influence in volume-weighted indices.

</details>

## 📋 Detailed Data

<details>
<summary>View Raw Data</summary>

Raw price data used for all aggregate calculations. Export for further analysis.

$exhibits${
  type: data_table
  source: stocks.fact_stock_prices
  download: true
}

</details>

---

**Understanding Index Weighting**: Different weighting methodologies serve different analytical purposes. Equal-weighted indices give small-cap stocks equal representation, while market-cap weighted indices better reflect overall market movements. Choose the approach that best fits your analysis goals.
