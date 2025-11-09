---
title: "Forecast Model Overview"
tags: [finance/forecast, component/model, concept/ml, status/stable]
aliases: ["Forecast Model", "ML Predictions", "Stock Forecasting"]
dependencies: ["[[Calendar]]", "[[Company Model]]"]
architecture_components:
  - "[[Models System/ML]]"
  - "[[Silver Storage]]"
  - "[[Universal Session]]"
---

# Forecast Model - Overview

---

The Forecast Model provides machine learning-based price and volume predictions with confidence intervals and accuracy metrics, supporting multiple forecasting algorithms.

**Data Source:** Trained on [[Company Model]] price data
**Dependencies:** [[Calendar]], [[Company Model]]
**Storage:** `storage/silver/forecast`

---

## Model Components

---

### Facts
- **[[Forecast Facts]]** - Price and volume predictions with confidence intervals
- **[[Forecast Metrics]]** - Model accuracy and error metrics
- **[[Model Registry]]** - Trained model metadata and parameters

### Model Types
- **[[Forecast Model Types]]** - ARIMA, Prophet, Random Forest configurations

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Model Types** | 3 (ARIMA, Prophet, Random Forest) |
| **Forecast Horizons** | 7, 14, 30 days |
| **Lookback Periods** | 7, 14, 30, 60 days |
| **Confidence Intervals** | 95% |
| **Fact Tables** | 3 |
| **Supported Targets** | Price (close), Volume |

---

## Architecture Pattern

---

Unlike ingestion models (Company, Macro), the Forecast model follows an **analytics pattern**:

```
Company Model (Silver)
         ↓
   ML Training
         ↓
  Forecast Model (Silver)
         ↓
    Analysis
```

**Key Differences:**
- **No Bronze layer** - Trains on existing Silver data
- **No data pipeline** - Consumes from Company model
- **Pure analytics** - Generates predictions, not raw data ingestion

---

## Forecasting Workflow

---

### 1. Training

```python
from models.forecast.trainer import ForecastTrainer

trainer = ForecastTrainer()

# Train ARIMA model
trainer.train_model(
    ticker='AAPL',
    model_type='ARIMA',
    lookback_days=30,
    forecast_horizon=7
)
```

### 2. Prediction

```python
# Generate forecasts
predictions = trainer.predict(
    ticker='AAPL',
    forecast_date='2024-11-08',
    model_name='ARIMA_30d'
)
```

### 3. Evaluation

```python
# Calculate accuracy metrics
metrics = trainer.evaluate(
    ticker='AAPL',
    model_name='ARIMA_30d',
    test_start='2024-01-01',
    test_end='2024-11-08'
)
```

---

## Model Types

---

### ARIMA (Auto-Regressive Integrated Moving Average)

**Variants:** 7d, 14d, 30d, 60d lookback

**Best For:**
- Short-term price predictions (1-7 days)
- Stable time series
- Trend-based forecasting

**Parameters:**
- Auto ARIMA (automatic parameter selection)
- Seasonal adjustment optional
- Day-of-week adjustments

---

### Prophet (Facebook Prophet)

**Variants:** 7d, 30d, 60d lookback

**Best For:**
- Medium-term forecasts (7-30 days)
- Seasonal patterns
- Holiday effects

**Parameters:**
- Multiplicative seasonality
- Holiday calendar (optional)
- Automatic changepoint detection

---

### Random Forest

**Variants:** 14d, 30d lookback

**Best For:**
- Feature-rich predictions
- Non-linear patterns
- Volume forecasting

**Features:**
- Lag features (1, 7, 14, 30 days)
- Rolling statistics (mean, std)
- Day of week
- Technical indicators

---

## Usage Example

---

```python
from models.api.session import UniversalSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Get forecast model
forecast = session.load_model('forecast')

# Get price forecasts
price_forecasts = forecast.get_fact_df('forecast_price').to_pandas()

# Filter to specific ticker and recent forecasts
aapl_forecasts = price_forecasts[
    (price_forecasts['ticker'] == 'AAPL') &
    (price_forecasts['forecast_date'] >= '2024-11-01')
]

# Compare model performance
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(12, 6))

for model_name in aapl_forecasts['model_name'].unique():
    model_data = aapl_forecasts[aapl_forecasts['model_name'] == model_name]
    ax.plot(model_data['prediction_date'], model_data['predicted_close'],
            label=model_name, marker='o')

ax.set_title('AAPL Price Forecasts - Model Comparison')
ax.set_xlabel('Prediction Date')
ax.set_ylabel('Predicted Close Price ($)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

---

## Confidence Intervals

---

All forecasts include 95% confidence intervals:

```python
# Visualize with confidence intervals
model_data = aapl_forecasts[aapl_forecasts['model_name'] == 'ARIMA_30d']

plt.figure(figsize=(12, 6))
plt.plot(model_data['prediction_date'], model_data['predicted_close'],
         label='Prediction', linewidth=2)
plt.fill_between(
    model_data['prediction_date'],
    model_data['lower_bound'],
    model_data['upper_bound'],
    alpha=0.3,
    label='95% Confidence Interval'
)
plt.title('AAPL Price Forecast with Confidence Intervals')
plt.xlabel('Date')
plt.ylabel('Price ($)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

---

## Model Evaluation

---

### Accuracy Metrics

- **MAE** - Mean Absolute Error (average prediction error)
- **RMSE** - Root Mean Squared Error (penalizes large errors)
- **MAPE** - Mean Absolute Percentage Error (error as % of actual)
- **R²** - R-squared score (goodness of fit)

### Example Evaluation

```python
# Get forecast metrics
metrics = forecast.get_fact_df('forecast_metrics').to_pandas()

# Filter to AAPL
aapl_metrics = metrics[metrics['ticker'] == 'AAPL']

# Compare models
print(aapl_metrics[['model_name', 'mae', 'rmse', 'mape', 'r2_score']].sort_values('mape'))
```

---

## Related Documentation

---

### Model Documentation
- [[Forecast Facts]] - Prediction schema
- [[Forecast Metrics]] - Accuracy metrics
- [[Model Registry]] - Trained models
- [[Forecast Model Types]] - Algorithm details

### Architecture Documentation
- [[Models System/ML]] - ML model framework
- [[Universal Session]] - Cross-model data access
- [[Silver Storage]] - Forecast output storage

### How-To Guides
- [[How to Train Forecast Models]]
- [[How to Evaluate Forecast Accuracy]]
- [[How to Compare Model Performance]]

### Related Models
- [[Company Model]] - Training data source
- [[Calendar]] - Time dimension

---

**Tags:** #finance/forecast #component/model #concept/ml #architecture/analytics

**Last Updated:** 2024-11-08
**Model:** forecast
**Version:** 1
