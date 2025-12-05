---
id: forecast_analysis
title: Price Forecast Analysis
description: Analyze stock price predictions and model performance
tags: [forecast, predictions, ml, analysis]
models: [forecast, stocks]
author: de_Funk Analytics
created: 2025-12-05
---

$filter${
  id: ticker
  label: Stock Ticker
  type: select
  multi: true
  source: {model: stocks, table: dim_stock, column: ticker}
  default: ["AAPL", "MSFT"]
  help_text: Select stocks to view forecasts
}

$filter${
  id: model_name
  label: Forecast Model
  type: select
  multi: true
  source: {model: forecast, table: fact_forecasts, column: model_name}
  help_text: Filter by forecast model type (ARIMA, Prophet, etc.)
}

$filter${
  id: forecast_date
  type: date_range
  label: Forecast Date
  column: forecast_date
  operator: between
  default: {start: "2025-01-01", end: "2025-12-31"}
  help_text: Filter by when the forecast was generated
}

$filter${
  id: horizon
  label: Forecast Horizon (Days)
  type: slider
  column: horizon
  min_value: 1
  max_value: 30
  default: 7
  operator: lte
  help_text: Maximum prediction horizon in days
}

# Price Forecast Analysis

Analyze price predictions from machine learning models including ARIMA, Prophet, and ensemble methods.

## Forecast Overview

### Latest Predictions

$exhibits${
  type: metric_cards
  source: forecast.fact_forecasts
  metrics: [
    { column: predicted_close, label: "Avg Predicted Price", aggregation: avg, format: "$,.2f" },
    { column: confidence, label: "Avg Confidence", aggregation: avg, format: ".1%" },
    { column: horizon, label: "Max Horizon", aggregation: max },
    { column: ticker, label: "Tickers Covered", aggregation: count_distinct }
  ]
}

## Price Predictions

### Predicted Price vs Confidence Bands

$exhibits${
  type: line_chart
  source: forecast.fact_forecasts
  x: prediction_date
  y: [predicted_close, lower_bound, upper_bound]
  color: ticker
  title: Price Predictions with Confidence Intervals
  height: 450
}

### Predictions by Model

$exhibits${
  type: line_chart
  source: forecast.fact_forecasts
  x: prediction_date
  y: predicted_close
  color: model_name
  title: Price Predictions by Model Type
  height: 400
}

## Model Performance

### Accuracy Metrics by Model

$exhibits${
  type: bar_chart
  source: forecast.fact_forecast_metrics
  x: model_name
  y: [mae, rmse]
  title: Model Error Comparison (MAE & RMSE)
  height: 350
}

### Model Accuracy Summary

$exhibits${
  type: metric_cards
  source: forecast.fact_forecast_metrics
  metrics: [
    { column: mae, label: "Avg MAE", aggregation: avg, format: "$,.2f" },
    { column: rmse, label: "Avg RMSE", aggregation: avg, format: "$,.2f" },
    { column: mape, label: "Avg MAPE", aggregation: avg, format: ".2%" },
    { column: r2_score, label: "Avg R-Squared", aggregation: avg, format: ".3f" }
  ]
}

## Detailed Analysis

<details>
<summary>Model Performance by Ticker</summary>

### Error Metrics by Stock

$exhibits${
  type: data_table
  source: forecast.fact_forecast_metrics
  columns: [ticker, model_name, mae, rmse, mape, r2_score, num_predictions]
  sort_by: mae
  sort_order: asc
  page_size: 20
  download: true
}

### MAPE Distribution

$exhibits${
  type: bar_chart
  source: forecast.fact_forecast_metrics
  x: ticker
  y: mape
  aggregation: avg
  color: model_name
  title: Average MAPE by Stock and Model
  height: 400
}

</details>

<details>
<summary>Forecast Details</summary>

### All Predictions

$exhibits${
  type: data_table
  source: forecast.fact_forecasts
  columns: [ticker, model_name, forecast_date, prediction_date, horizon, predicted_close, lower_bound, upper_bound, confidence]
  sort_by: prediction_date
  sort_order: desc
  page_size: 25
  download: true
}

</details>

<details>
<summary>Model Comparison</summary>

### Best Performing Models by MAE

$exhibits${
  type: data_table
  source: forecast.fact_forecast_metrics
  columns: [model_name, ticker, mae, rmse, mape, r2_score]
  aggregations: [
    { column: mae, aggregation: avg, label: "Avg MAE" },
    { column: rmse, aggregation: avg, label: "Avg RMSE" },
    { column: r2_score, aggregation: avg, label: "Avg R2" }
  ]
  group_by: model_name
  sort_by: mae_avg
  sort_order: asc
  download: true
}

</details>

## Model Recommendations

Based on backtesting metrics:
- **Best for short-term (1-7 days)**: ARIMA models typically perform well
- **Best for trends (7-30 days)**: Prophet captures seasonality effectively
- **Ensemble approach**: Combining models often yields more robust predictions

*Note: Past performance does not guarantee future results. Use forecasts as one input among many in investment decisions.*
