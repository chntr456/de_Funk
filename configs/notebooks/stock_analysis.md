---
id: stock_analysis_md
title: Stock Performance Analysis
description: Analyzing stock prices with volume metrics
tags: [stocks, prices, analysis]
models: [company]
dimensions: [trade_date, ticker]
measures: [close, volume, high, low]
author: analyst@company.com
created: 2024-01-01
updated: 2024-01-15
---

# Filters

- **Date Range**: trade_date (2024-01-01 to 2024-01-05) [date_range]
- **Stock Tickers**: ticker (AAPL, GOOGL, MSFT) [multi_select]
- **Min Volume**: volume (0) [number]

# Stock Performance Analysis

This analysis examines stock price trends and trading volumes for selected technology equities over a specified date range. The data is sourced from our company model and includes daily trading information.

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

## Price Trends

The following chart shows daily closing prices for each stock. Each line represents a different ticker, colored for easy identification.

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Daily Closing Prices
}

You can see from the chart above that prices vary significantly across different stocks and time periods. This visualization helps identify trends, patterns, and anomalies in the data.

## Volume Analysis

<details>
<summary>Click to view Trading Volume Comparison</summary>

Total trading volume by stock for the selected period. This chart is sorted by volume in descending order to highlight the most actively traded stocks.

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  sort: { by: volume, order: desc }
  title: Trading Volume by Stock
}

High trading volumes often indicate strong investor interest and liquidity in a particular stock.

</details>

## Key Insights

Based on the analysis above, we can draw several conclusions:

1. **Price Stability**: Some stocks show more stable price movements than others
2. **Volume Patterns**: Trading volumes vary significantly across different equities
3. **Trend Direction**: Clear upward or downward trends are visible in certain periods

### Next Steps

Consider the following actions based on this analysis:

- Monitor stocks with unusual volume spikes
- Investigate price movements that deviate from sector trends
- Review fundamental factors for stocks with significant changes

## Detailed Data

<details>
<summary>View Complete Dataset</summary>

The table below contains all available data points for the selected filters. You can sort, search, and download this data for further analysis.

$exhibits${
  type: data_table
  source: company.fact_prices
  download: true
  sortable: true
  pagination: true
  page_size: 50
}

</details>

---

**Note**: This analysis is for informational purposes only and should not be considered investment advice.
