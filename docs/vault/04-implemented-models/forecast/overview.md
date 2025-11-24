# Forecast Model Overview

**Time series forecasting for price prediction**

---

## Summary

| Property | Value |
|----------|-------|
| **Model** | forecast |
| **Version** | 1.0 |
| **Status** | Production |
| **Tier** | 3 (Analytics) |
| **Dependencies** | core, equity, corporate |
| **Methods** | ARIMA, Prophet, Random Forest |

---

## Purpose

The forecast model provides **time series price predictions** using multiple statistical and machine learning models:

- **ARIMA**: AutoRegressive Integrated Moving Average
- **Prophet**: Facebook's forecasting library
- **Random Forest**: Ensemble ML model

---

## Tables

| Table | Type | Description |
|-------|------|-------------|
| `fact_forecasts` | Fact | Price predictions with confidence intervals |
| `fact_forecast_metrics` | Fact | Model accuracy metrics (RMSE, MAE, MAPE) |
| `fact_model_registry` | Fact | Registry of trained models |

---

## Supported Models

### ARIMA Models

| Model | Lookback | Horizon | Seasonal |
|-------|----------|---------|----------|
| `arima_7d` | 7 days | 7 days | No |
| `arima_14d` | 14 days | 14 days | No |
| `arima_30d` | 30 days | 30 days | Yes |
| `arima_60d` | 60 days | 30 days | Yes |

### Prophet Models

| Model | Lookback | Horizon | Holidays |
|-------|----------|---------|----------|
| `prophet_7d` | 7 days | 7 days | No |
| `prophet_30d` | 30 days | 30 days | Yes |
| `prophet_60d` | 60 days | 30 days | Yes |

### Random Forest Models

| Model | Lookback | Horizon | Features |
|-------|----------|---------|----------|
| `random_forest_14d` | 14 days | 7 days | lag_1, lag_7, lag_14, rolling_mean |
| `random_forest_30d` | 30 days | 14 days | lag_1, lag_7, lag_14, lag_30, rolling |

---

## Measures

| Measure | Source | Aggregation | Description |
|---------|--------|-------------|-------------|
| `avg_forecast_error` | fact_forecast_metrics.mae | avg | Average MAE |
| `avg_forecast_mape` | fact_forecast_metrics.mape | avg | Average MAPE |
| `best_model_r2` | fact_forecast_metrics.r2_score | max | Best R² score |

---

## Running Forecasts

```bash
# Run all forecasts
python -m scripts.forecast.run_forecasts

# Large cap only
python -m scripts.forecast.run_forecasts_large_cap

# Verify configuration
python -m scripts.forecast.verify_forecast_config
```

---

## Usage Example

```python
from models.implemented.forecast.arima_forecaster import ARIMAForecaster

forecaster = ARIMAForecaster()
predictions = forecaster.fit_predict(
    ticker='AAPL',
    train_data=historical_prices,
    forecast_periods=30
)
```

---

## Model Evaluation

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **RMSE** | Root Mean Squared Error | Lower is better, penalizes large errors |
| **MAE** | Mean Absolute Error | Average absolute error |
| **MAPE** | Mean Absolute Percentage Error | Percentage error (interpretable) |
| **R²** | R-squared score | Higher is better (0-1) |

---

## Related Documentation

- [Dimensions](dimensions.md) - Schema details
- [Measures](measures.md) - Forecast measures
- [Stocks Model](../stocks/) - Training data source
