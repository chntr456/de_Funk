# Forecast Models

**Time series forecasting for price prediction**

Source: See `/FORECAST_README.md` for complete documentation
Model: `forecast` (`configs/models/forecast.yaml`)

---

## Overview

de_Funk's forecasting system provides **time series price predictions** using multiple statistical and machine learning models.

**Supported Models**:
- ARIMA (AutoRegressive Integrated Moving Average)
- Prophet (Facebook's forecasting library)
- Linear Regression

---

## Forecast Model (forecast.yaml)

**Tables**:
- `fact_forecasts` - Price predictions with confidence intervals
- `fact_forecast_metrics` - Model performance (RMSE, MAE, MAPE)

**Schema**:
```yaml
fact_forecasts:
  columns:
    ticker: string
    prediction_date: date
    predicted_price: double
    lower_bound: double
    upper_bound: double
    model_type: string        # 'arima', 'prophet', 'linear'
    confidence_level: double  # 0.95 for 95% confidence

fact_forecast_metrics:
  columns:
    ticker: string
    model_type: string
    metric_date: date
    rmse: double              # Root Mean Squared Error
    mae: double               # Mean Absolute Error
    mape: double              # Mean Absolute Percentage Error
```

---

## Running Forecasts

**All Models**:
```bash
python scripts/run_forecasts.py
```

**Specific Model**:
```bash
python scripts/run_forecast_model.py --model arima --tickers AAPL,MSFT
```

---

## ARIMA Model

**Auto-ARIMA** automatically selects optimal (p,d,q) parameters

**Usage**:
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

## Prophet Model

**Facebook Prophet** handles seasonality and holidays

**Usage**:
```python
from models.implemented.forecast.prophet_forecaster import ProphetForecaster

forecaster = ProphetForecaster()
predictions = forecaster.fit_predict(
    ticker='AAPL',
    train_data=historical_prices,
    forecast_periods=30
)
```

---

## Forecast Evaluation

**Metrics**:
- **RMSE**: Lower is better, sensitive to large errors
- **MAE**: Average absolute error
- **MAPE**: Percentage error (interpretable)

**Backtesting**:
```python
# Split data
train = prices[:-30]
test = prices[-30:]

# Train and predict
predictions = model.fit_predict(train, forecast_periods=30)

# Evaluate
rmse = calculate_rmse(test['close'], predictions['predicted_price'])
```

---

## Related Documentation

- [Implemented Models](../03-model-framework/implemented-models.md#forecast)
- [Model Training](model-training.md) - Training process
- `/FORECAST_README.md` - Complete forecasting documentation
