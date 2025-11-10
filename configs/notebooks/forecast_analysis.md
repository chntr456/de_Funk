---
id: forecast_analysis
title: Time Series Forecast Analysis
description: Stock price forecasts with actuals vs predictions
tags: [forecast, timeseries, predictions]
models: [forecast]
author: analyst@company.com
created: 2024-01-01
updated: 2024-01-15
---

$filter${
  id: ticker
  label: Stock Tickers
  type: select
  multi: false
  source: {model: forecast, table: vw_price_predictions, column: ticker}
  default: ["GOOG"]
  help_text: Select a stock to view (single ticker for cleaner visualization)
}

$filter${
  id: trade_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-10-01", end: "2025-12-31"}
  help_text: Filter by date (unified across actuals and predictions via calendar)
  source: {model: core, table: dim_calendar, column: trade_date}
  applies_to: [forecast.vw_price_predictions.date, company.fact_prices.trade_date]
}

# Time Series Forecast Analysis

Compare actual stock prices with model predictions and confidence intervals.

## Price Forecast - Actuals vs Predictions

$exhibits${
  type: forecast_chart
  source: forecast.vw_price_predictions
  title: "Stock Price - Actuals vs Predictions"
  description: "Historical actuals with model predictions and 95% confidence intervals"

  x_axis:
    dimension: date
    label: "Date"

  y_axis:
    label: "Price ($)"
    measures: [actual, predicted]

  dimension_selector:
    available_dimensions: [model_name]
    default_dimension: model_name
    selector_type: multiselect
    default_values: ["ARIMA_30d", "Prophet_30d"]
    label: "Select Forecast Models"
    help_text: "Choose which models to display (actuals always shown)"
    show_all_option: true

  actual_column: actual
  predicted_column: predicted
  confidence_bounds: [lower_bound, upper_bound]

  series_column: model_name
  show_confidence_bands: true
  confidence_opacity: 0.15

  line_styles:
    actual:
      color: "#1f77b4"
      width: 2.5
      style: solid
      name: "Actual"
    predicted:
      width: 2
      style: solid
    confidence:
      opacity: 0.15

  legend:
    show: true
    position: top_right

  chart_config:
    height: 500
    show_grid: true
    interactive: true
}

## Model Accuracy Metrics

<details>
<summary>View accuracy metrics</summary>

$exhibits${
  type: forecast_metrics_table
  source: forecast.fact_forecast_metrics
  title: Model Performance
}

</details>

---

**Note:** To generate forecast data, run:
```bash
python scripts/run_forecasts.py --tickers AAPL GOOGL MSFT
```
