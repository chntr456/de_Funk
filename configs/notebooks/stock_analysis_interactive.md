---
id: stock_analysis_interactive
title: Interactive Stock Analysis with Dynamic Measures
description: Analyzing stock prices with dynamic measure selection and click events
tags: [stocks, prices, analysis, interactive]
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

# Interactive Stock Performance Analysis

This analysis demonstrates the new **dynamic measure selection** and **interactive click events** features. You can now select which measures to display using checkboxes, and interact with charts through clicking and selection.

## Dynamic Metric Cards

Select which metrics you want to see displayed as cards. The metrics will automatically aggregate based on your selected data.

$exhibits${
  type: metric_cards
  source: company.fact_prices
  title: Key Performance Metrics
  measure_selector: {
    available_measures: [close, open, high, low, volume],
    default_measures: [close, volume],
    label: "Select Metrics to Display",
    selector_type: checkbox,
    help_text: "Choose which metrics to show as cards"
  }
  options: {
    default_aggregation: avg
  }
}

## Interactive Line Chart with Multiple Measures

Select multiple measures to compare them over time. Click and drag to select data points on the chart. You can compare different price metrics (open, close, high, low) simultaneously.

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  title: Stock Price Trends (Multi-Measure)
  description: Select which price measures to display on the chart
  measure_selector: {
    available_measures: [open, close, high, low],
    default_measures: [close],
    label: "Price Measures",
    selector_type: checkbox,
    help_text: "Select price metrics to plot on the chart"
  }
  interactive: true
}

## Grouped Bar Chart with Volume Analysis

Compare multiple measures across different stocks using grouped bars. Select which volume-related metrics you want to compare.

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  title: Stock Comparison (Grouped Bars)
  description: Compare multiple measures across stocks
  measure_selector: {
    available_measures: [volume, close, high, low],
    default_measures: [volume, close],
    label: "Comparison Metrics",
    selector_type: checkbox,
    help_text: "Choose metrics to compare across stocks"
  }
  interactive: true
}

## Radio Button Example (Single Selection)

Sometimes you only want to view one measure at a time. Use the radio button selector to switch between different views.

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  title: Single Measure View
  description: Select one measure to focus on
  measure_selector: {
    available_measures: [open, close, high, low, volume],
    default_measures: [close],
    label: "Select Measure",
    selector_type: radio,
    allow_multiple: false,
    help_text: "Choose a single measure to display"
  }
  interactive: true
}

## Multiselect Dropdown Example

For exhibits with many measures, a dropdown selector might be more space-efficient than checkboxes.

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  title: Compact Measure Selection
  measure_selector: {
    available_measures: [open, close, high, low, volume],
    default_measures: [close, volume],
    label: "Select Measures",
    selector_type: multiselect,
    help_text: "Choose measures from the dropdown"
  }
}

## How to Use Interactive Features

### Measure Selection
- **Checkboxes**: Select multiple measures by checking/unchecking boxes
- **Radio Buttons**: Choose one measure at a time
- **Multiselect Dropdown**: Select from a compact dropdown menu

### Chart Interaction
- **Click**: Click on individual data points to select them
- **Box Select**: Click and drag to select multiple points
- **Zoom**: Use the zoom tools in the chart toolbar
- **Pan**: Drag the chart to pan around
- **Export**: Use the camera icon to download charts as PNG images

### Selection State
Selected data points are stored in session state and can be used by other components or for further analysis.

## Traditional Static Exhibits

You can still use the traditional static exhibit configuration if you don't need dynamic measure selection:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Static Configuration (Traditional)
  description: This uses the traditional y-axis configuration
}
