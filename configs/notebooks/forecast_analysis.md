---
id: forecast_analysis
title: Time Series Forecast Analysis
description: Stock price and volume forecasts with multiple models and accuracy metrics
tags: [forecast, timeseries, ml, predictions]
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
  source: {model: forecast, table: forecast_price, column: ticker}
  default: ["AAPL"]
  help_text: Select stocks to view forecasts
}

$filter${
  id: model_name
  label: Forecast Models
  type: select
  multi: true
  source: {model: forecast, table: forecast_metrics, column: model_name}
  default: ["ARIMA_30d", "Prophet_30d"]
  help_text: Select forecast models to compare
}

# Time Series Forecast Analysis

This notebook analyzes stock price and volume forecasts using multiple machine learning and statistical models. Compare model accuracy, view confidence intervals, and explore detailed predictions.

## Forecast Summary

Overview of forecast model accuracy across all selected models:

$exhibits${
  type: metric_cards
  source: forecast.forecast_metrics
  metrics: [
    { measure: mae, label: "Avg MAE", aggregation: avg },
    { measure: rmse, label: "Avg RMSE", aggregation: avg },
    { measure: mape, label: "Avg MAPE (%)", aggregation: avg },
    { measure: r2_score, label: "Avg R²", aggregation: avg }
  ]
}

**Metrics Explained**:
- **MAE** (Mean Absolute Error): Average prediction error in absolute terms
- **RMSE** (Root Mean Square Error): Penalizes larger errors more heavily
- **MAPE** (Mean Absolute Percentage Error): Error as a percentage
- **R²** (R-squared): How well the model fits the data (closer to 1 is better)

## Price & Volume Forecasts

### Price Forecast with Confidence Intervals

Predicted closing prices with 95% confidence intervals showing forecast uncertainty.

$exhibits${
  type: forecast_chart
  source: forecast.forecast_price
  target: price
  title: Price Forecast with Confidence Intervals
}

The shaded area represents the 95% confidence interval - actual prices are expected to fall within this range 95% of the time.

### Volume Forecast with Confidence Intervals

<details>
<summary>Click to view volume forecasts</summary>

Predicted trading volumes with 95% confidence intervals.

$exhibits${
  type: forecast_chart
  source: forecast.forecast_volume
  target: volume
  title: Volume Forecast with Confidence Intervals
}

Volume forecasts help anticipate market liquidity and trading activity levels.

</details>

## Model Performance

### Accuracy Metrics Comparison

<details>
<summary>Click to view detailed model metrics</summary>

Comprehensive accuracy comparison across all forecast models:

$exhibits${
  type: forecast_metrics_table
  source: forecast.forecast_metrics
  title: Model Accuracy Metrics
}

**Available Models**:
- **ARIMA**: AutoRegressive Integrated Moving Average (statistical model)
- **Prophet**: Facebook's time series forecasting model
- **RandomForest**: Machine learning ensemble method

Each with different forecast horizons (7d, 14d, 30d, 60d).

</details>

## Detailed Data

### Price Forecast Data

<details>
<summary>View and download price forecast data</summary>

$exhibits${
  type: data_table
  source: forecast.forecast_price
  download: true
}

</details>

### Volume Forecast Data

<details>
<summary>View and download volume forecast data</summary>

$exhibits${
  type: data_table
  source: forecast.forecast_volume
  download: true
}

</details>

---

**Model Selection Tips**:
- Use **ARIMA** for stable, trend-based forecasts
- Use **Prophet** for seasonal patterns and holidays
- Use **RandomForest** for complex non-linear relationships
- Longer horizons (60d) have higher uncertainty than short-term (7d) forecasts
