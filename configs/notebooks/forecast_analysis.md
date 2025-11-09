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
  multi: true
  source: {model: forecast, table: fact_forecasts, column: ticker}
  default: ["AAPL"]
  help_text: Select stocks to view
}

$filter${
  id: prediction_date
  type: date_range
  label: Date Range
  operator: between
  default: {start: "2024-01-01", end: "2024-01-05"}
  help_text: Select date range for predictions
}

# Time Series Forecast Analysis

Compare actual stock prices with model predictions and confidence intervals.

## Price Forecast

$exhibits${
  type: forecast_chart
  source: forecast.fact_forecasts
  title: "Stock Price - Predictions"
  description: "Model predictions with confidence intervals"

  x_axis: {dimension: prediction_date, label: "Date"}
  y_axis: {label: "Price ($)", measures: [predicted_close]}

  measure_selector: {
    available_measures: [predicted_close, predicted_volume, upper_bound, lower_bound],
    default_measures: [predicted_close],
    selector_type: multiselect,
    label: "Select Metrics",
    help_text: "Choose which values to display"
  }

  dimension_selector: {
    available_dimensions: [ticker, model_name],
    default_dimension: model_name,
    label: "Group By",
    help_text: "Group lines by ticker or model"
  }

  predicted_column: predicted_close
  confidence_bounds: [lower_bound, upper_bound]
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
