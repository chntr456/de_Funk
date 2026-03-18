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
  source: {model: forecast, table: fact_forecast_price, column: ticker}
  default: ["AAPL", "MSFT"]
  help_text: Select stocks to view forecasts
}

$filter${
  id: model_name
  label: Forecast Model
  type: select
  multi: true
  source: {model: forecast, table: fact_forecast_price, column: model_name}
  help_text: Filter by forecast model type (ARIMA, Prophet, etc.)
}

$filter${
  id: forecast_date
  type: date_range
  label: Forecast Date
  column: securities.forecast.fact_forecast_price.forecast_date
  operator: between
  help_text: Filter by when the forecast was generated
}

$filter${
  id: horizon
  label: Forecast Horizon (Days)
  type: slider
  column: securities.forecast.fact_forecast_price.horizon
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
  source: securities.forecast.fact_forecast_price
  metrics: [
    { column: securities.forecast.fact_forecast_price.predicted_close, label: "Avg Predicted Price", aggregation: avg, format: "$,.2f" },
    { column: securities.forecast.fact_forecast_price.confidence, label: "Avg Confidence", aggregation: avg, format: ".1%" },
    { column: securities.forecast.fact_forecast_price.horizon, label: "Max Horizon", aggregation: max },
    { column: securities.forecast.fact_forecast_price.ticker, label: "Tickers Covered", aggregation: count_distinct }
  ]
}

## Price Predictions

### Predicted Price vs Confidence Bands

$exhibits${
  type: line_chart
  source: securities.forecast.fact_forecast_price
  x: securities.forecast.fact_forecast_price.prediction_date
  y: [securities.forecast.fact_forecast_price.predicted_close, securities.forecast.fact_forecast_price.lower_bound, securities.forecast.fact_forecast_price.upper_bound]
  color: securities.forecast.fact_forecast_price.ticker
  title: Price Predictions with Confidence Intervals
  height: 450
}

### Predictions by Model

$exhibits${
  type: line_chart
  source: securities.forecast.fact_forecast_price
  x: securities.forecast.fact_forecast_price.prediction_date
  y: securities.forecast.fact_forecast_price.predicted_close
  color: securities.forecast.fact_forecast_price.model_name
  title: Price Predictions by Model Type
  height: 400
}

## Actual Stock Prices

Compare forecast predictions against actual market data.

### Recent Stock Prices

$exhibits${
  type: metric_cards
  source: securities.stocks.fact_stock_prices
  metrics: [
    { column: securities.stocks.fact_stock_prices.close, label: "Latest Close", aggregation: last, format: "$,.2f" },
    { column: securities.stocks.fact_stock_prices.close, label: "Avg Close", aggregation: avg, format: "$,.2f" },
    { column: securities.stocks.fact_stock_prices.high, label: "Period High", aggregation: max, format: "$,.2f" },
    { column: securities.stocks.fact_stock_prices.low, label: "Period Low", aggregation: min, format: "$,.2f" }
  ]
}

### Price History

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: securities.stocks.fact_stock_prices.close
  color: securities.stocks.dim_stock.ticker
  title: Actual Stock Price History
  height: 400
}

### Price with Volume

$exhibits${
  type: line_chart
  source: securities.stocks.fact_stock_prices
  x: temporal.dim_calendar.date
  y: [securities.stocks.fact_stock_prices.close, securities.stocks.fact_stock_prices.volume]
  color: securities.stocks.dim_stock.ticker
  title: Price and Volume Over Time
  height: 350
}

## Model Performance

### Accuracy Metrics by Model

$exhibits${
  type: bar_chart
  source: securities.forecast.fact_forecast_metrics
  x: securities.forecast.fact_forecast_metrics.model_name
  y: [securities.forecast.fact_forecast_metrics.mae, securities.forecast.fact_forecast_metrics.rmse]
  title: Model Error Comparison (MAE & RMSE)
  height: 350
}

### Model Accuracy Summary

$exhibits${
  type: metric_cards
  source: securities.forecast.fact_forecast_metrics
  metrics: [
    { column: securities.forecast.fact_forecast_metrics.mae, label: "Avg MAE", aggregation: avg, format: "$,.2f" },
    { column: securities.forecast.fact_forecast_metrics.rmse, label: "Avg RMSE", aggregation: avg, format: "$,.2f" },
    { column: securities.forecast.fact_forecast_metrics.mape, label: "Avg MAPE", aggregation: avg, format: ".2%" },
    { column: securities.forecast.fact_forecast_metrics.r2_score, label: "Avg R-Squared", aggregation: avg, format: ".3f" }
  ]
}

## Detailed Analysis

<details>
<summary>Model Performance by Ticker</summary>

### Error Metrics by Stock

$exhibits${
  type: data_table
  source: securities.forecast.fact_forecast_metrics
  columns: [securities.forecast.fact_forecast_metrics.ticker, securities.forecast.fact_forecast_metrics.model_name, securities.forecast.fact_forecast_metrics.mae, securities.forecast.fact_forecast_metrics.rmse, securities.forecast.fact_forecast_metrics.mape, securities.forecast.fact_forecast_metrics.r2_score, securities.forecast.fact_forecast_metrics.num_predictions]
  sort_by: securities.forecast.fact_forecast_metrics.mae
  sort_order: asc
  page_size: 20
  download: true
}

### MAPE Distribution

$exhibits${
  type: bar_chart
  source: securities.forecast.fact_forecast_metrics
  x: securities.forecast.fact_forecast_metrics.ticker
  y: securities.forecast.fact_forecast_metrics.mape
  aggregation: avg
  color: securities.forecast.fact_forecast_metrics.model_name
  title: Average MAPE by Stock and Model
  height: 400
}

</details>

<details>
<summary>Forecast Details</summary>

### All Predictions

$exhibits${
  type: data_table
  source: securities.forecast.fact_forecast_price
  columns: [securities.forecast.fact_forecast_price.ticker, securities.forecast.fact_forecast_price.model_name, securities.forecast.fact_forecast_price.forecast_date, securities.forecast.fact_forecast_price.prediction_date, securities.forecast.fact_forecast_price.horizon, securities.forecast.fact_forecast_price.predicted_close, securities.forecast.fact_forecast_price.lower_bound, securities.forecast.fact_forecast_price.upper_bound, securities.forecast.fact_forecast_price.confidence]
  sort_by: securities.forecast.fact_forecast_price.prediction_date
  sort_order: desc
  page_size: 25
  download: true
}

</details>

<details>
<summary>Model Registry</summary>

### Trained Models

$exhibits${
  type: data_table
  source: securities.forecast.dim_model_registry
  columns: [securities.forecast.dim_model_registry.model_name, securities.forecast.dim_model_registry.model_type, securities.forecast.dim_model_registry.ticker, securities.forecast.dim_model_registry.target_variable, securities.forecast.dim_model_registry.lookback_days, securities.forecast.dim_model_registry.forecast_horizon, securities.forecast.dim_model_registry.trained_date, securities.forecast.dim_model_registry.status]
  sort_by: securities.forecast.dim_model_registry.trained_date
  sort_order: desc
  page_size: 20
  download: true
}

</details>

## Model Recommendations

Based on backtesting metrics:
- **Best for short-term (1-7 days)**: ARIMA models typically perform well
- **Best for trends (7-30 days)**: Prophet captures seasonality effectively
- **Ensemble approach**: Combining models often yields more robust predictions

*Note: Past performance does not guarantee future results. Use forecasts as one input among many in investment decisions.*
