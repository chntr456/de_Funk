---
title: "Forecast Model Types"
tags: [finance/forecast, component/model, concept/ml, concept/algorithms]
aliases: ["Model Types", "ARIMA", "Prophet", "Random Forest", "ML Algorithms"]
---

# Forecast Model Types

---

The Forecast model supports three machine learning algorithms for time series prediction: ARIMA, Prophet, and Random Forest. Each has different strengths and configuration options.

---

## Overview

---

| Model Type | Best For | Horizons | Lookback | Strengths | Weaknesses |
|------------|----------|----------|----------|-----------|------------|
| **ARIMA** | Short-term, stable trends | 7-30d | 7-60d | Fast, interpretable | Assumes stationarity |
| **Prophet** | Seasonal patterns, holidays | 7-30d | 7-60d | Handles seasonality well | Slower training |
| **Random Forest** | Non-linear, feature-rich | 7-14d | 14-30d | Flexible, robust | Needs feature engineering |

---

## ARIMA (Auto-Regressive Integrated Moving Average)

---

### Overview

ARIMA models predict future values based on past values, trends, and forecast errors. Well-suited for stationary time series with clear trends.

**Full Name:** Auto-Regressive Integrated Moving Average
**Best Use Cases:** Short-term price forecasts, stable markets
**Typical Accuracy:** MAPE 1-3% for 7-day forecasts

---

### Available Variants

---

#### ARIMA 7-day

**Lookback:** 7 days
**Forecast Horizon:** 7 days
**Parameters:**
- Auto ARIMA: Yes
- Seasonal: No
- Day-of-week adjustment: Yes

**Best For:** Very short-term predictions, day trading

---

#### ARIMA 14-day

**Lookback:** 14 days
**Forecast Horizon:** 14 days
**Parameters:**
- Auto ARIMA: Yes
- Seasonal: No
- Day-of-week adjustment: Yes

**Best For:** Short-term swing trading

---

#### ARIMA 30-day

**Lookback:** 30 days
**Forecast Horizon:** 30 days
**Parameters:**
- Auto ARIMA: Yes
- Seasonal: Yes (weekly)
- Day-of-week adjustment: Yes

**Best For:** Medium-term forecasts, monthly analysis

---

#### ARIMA 60-day

**Lookback:** 60 days
**Forecast Horizon:** 30 days
**Parameters:**
- Auto ARIMA: Yes
- Seasonal: Yes (weekly)
- Day-of-week adjustment: Yes

**Best For:** Longer-term forecasts with more historical context

---

### Model Parameters

**Auto-ARIMA:**
- Automatically selects optimal (p, d, q) parameters
- Tests multiple parameter combinations
- Selects based on AIC (Akaike Information Criterion)

**Common Parameters:**
- **p:** Autoregressive order (1-5)
- **d:** Differencing order (0-2)
- **q:** Moving average order (1-5)

**Example:**
```python
from statsmodels.tsa.arima.model import ARIMA

# Train ARIMA model
model = ARIMA(
    endog=price_series,
    order=(2, 1, 2),  # (p, d, q)
    trend='c'         # Constant trend
)

fitted = model.fit()
forecast = fitted.forecast(steps=7)
```

---

### Strengths

- Fast training
- Interpretable parameters
- Works well for short-term forecasts
- Good for stable, trending time series

### Weaknesses

- Assumes stationarity (requires differencing)
- Struggles with complex seasonality
- Sensitive to outliers
- Limited non-linear pattern recognition

---

## Prophet (Facebook Prophet)

---

### Overview

Prophet is designed for business time series with strong seasonal patterns and holiday effects. Developed by Facebook for forecasting at scale.

**Full Name:** Facebook Prophet
**Best Use Cases:** Seasonal patterns, holiday effects, missing data
**Typical Accuracy:** MAPE 2-4% for 7-day forecasts

---

### Available Variants

---

#### Prophet 7-day

**Lookback:** 7 days
**Forecast Horizon:** 7 days
**Parameters:**
- Seasonality mode: Multiplicative
- Include holidays: No
- Day-of-week adjustment: Yes

**Best For:** Short-term with day-of-week patterns

---

#### Prophet 30-day

**Lookback:** 30 days
**Forecast Horizon:** 30 days
**Parameters:**
- Seasonality mode: Multiplicative
- Include holidays: Yes (US market holidays)
- Day-of-week adjustment: Yes

**Best For:** Monthly forecasts with holiday effects

---

#### Prophet 60-day

**Lookback:** 60 days
**Forecast Horizon:** 30 days
**Parameters:**
- Seasonality mode: Multiplicative
- Include holidays: Yes
- Day-of-week adjustment: Yes

**Best For:** Longer-term forecasts with seasonal patterns

---

### Model Parameters

**Seasonality Mode:**
- **Additive:** Seasonal effect constant
- **Multiplicative:** Seasonal effect proportional to level (stock prices)

**Changepoint Detection:**
- Automatically detects trend changes
- `changepoint_prior_scale`: Controls trend flexibility (default: 0.05)

**Holiday Effects:**
- US market holidays (New Year's, Thanksgiving, etc.)
- Custom holiday calendars supported

**Example:**
```python
from prophet import Prophet

# Prepare data (requires 'ds' and 'y' columns)
df = pd.DataFrame({
    'ds': dates,
    'y': prices
})

# Train Prophet model
model = Prophet(
    seasonality_mode='multiplicative',
    yearly_seasonality=True,
    weekly_seasonality=True,
    daily_seasonality=False
)

model.fit(df)
future = model.make_future_dataframe(periods=30)
forecast = model.predict(future)
```

---

### Strengths

- Excellent for seasonal data
- Handles missing values well
- Holiday effects built-in
- Automatic changepoint detection
- Interpretable components

### Weaknesses

- Slower than ARIMA
- Can overfit with small datasets
- Less effective for very short-term (1-3 days)
- Requires sufficient history for seasonality

---

## Random Forest

---

### Overview

Random Forest is an ensemble method using multiple decision trees for prediction. Requires feature engineering but handles non-linear patterns well.

**Full Name:** Random Forest Regressor
**Best Use Cases:** Non-linear patterns, feature-rich analysis
**Typical Accuracy:** MAPE 2-5% for 7-day forecasts

---

### Available Variants

---

#### Random Forest 14-day

**Lookback:** 14 days
**Forecast Horizon:** 7 days
**Features:**
- Lag features: 1, 7, 14 days
- Rolling mean: 7 days
- Rolling std: 7 days
- Day of week

**Best For:** Short-term with technical indicators

---

#### Random Forest 30-day

**Lookback:** 30 days
**Forecast Horizon:** 14 days
**Features:**
- Lag features: 1, 7, 14, 30 days
- Rolling mean: 7, 30 days
- Rolling std: 7, 30 days
- Day of week

**Best For:** Medium-term with richer feature set

---

### Model Parameters

**Tree Parameters:**
- `n_estimators`: 100 (number of trees)
- `max_depth`: 10 (tree depth limit)
- `min_samples_split`: 2
- `random_state`: Fixed for reproducibility

**Feature Engineering:**
```python
# Lag features
df['lag_1'] = df['close'].shift(1)
df['lag_7'] = df['close'].shift(7)
df['lag_14'] = df['close'].shift(14)

# Rolling statistics
df['rolling_mean_7'] = df['close'].rolling(window=7).mean()
df['rolling_std_7'] = df['close'].rolling(window=7).std()

# Day of week
df['day_of_week'] = df['date'].dt.dayofweek

# Percentage change
df['pct_change_1'] = df['close'].pct_change()
```

**Example:**
```python
from sklearn.ensemble import RandomForestRegressor

# Train Random Forest
model = RandomForestRegressor(
    n_estimators=100,
    max_depth=10,
    random_state=42
)

# Fit on features
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)
```

---

### Strengths

- Handles non-linear relationships
- Robust to outliers
- Feature importance analysis
- No assumption of stationarity
- Works with multiple predictors

### Weaknesses

- Requires feature engineering
- Slower predictions than ARIMA
- Less interpretable
- Can overfit with too many features
- Needs more training data

---

## Model Selection Guidelines

---

### Choose ARIMA When:

- ✓ Short-term forecasts (1-7 days)
- ✓ Stable, trending time series
- ✓ Fast predictions needed
- ✓ Interpretability important
- ✗ Avoid for: Complex seasonality, non-linear patterns

---

### Choose Prophet When:

- ✓ Seasonal patterns present
- ✓ Holiday effects matter
- ✓ Missing data exists
- ✓ Medium-term forecasts (7-30 days)
- ✗ Avoid for: Very short-term, non-seasonal data

---

### Choose Random Forest When:

- ✓ Non-linear relationships
- ✓ Multiple features available
- ✓ Technical indicators useful
- ✓ Robustness to outliers needed
- ✗ Avoid for: Limited training data, need for speed

---

## Performance Comparison

---

### Typical Accuracy by Horizon

**7-Day Forecasts:**
- ARIMA: MAPE 1-3% ⭐⭐⭐
- Prophet: MAPE 2-4% ⭐⭐
- Random Forest: MAPE 2-5% ⭐⭐

**14-Day Forecasts:**
- ARIMA: MAPE 3-6% ⭐⭐
- Prophet: MAPE 3-5% ⭐⭐⭐
- Random Forest: MAPE 3-6% ⭐⭐

**30-Day Forecasts:**
- ARIMA: MAPE 5-10% ⭐
- Prophet: MAPE 4-7% ⭐⭐⭐
- Random Forest: MAPE 5-9% ⭐⭐

---

## Configuration Examples

---

### Training All Models

```python
from models.forecast.trainer import ForecastTrainer

trainer = ForecastTrainer()

models = [
    ('ARIMA', 7, 7),
    ('ARIMA', 30, 7),
    ('Prophet', 30, 7),
    ('RandomForest', 14, 7)
]

for model_type, lookback, horizon in models:
    trainer.train_model(
        ticker='AAPL',
        model_type=model_type,
        lookback_days=lookback,
        forecast_horizon=horizon
    )
    print(f"Trained {model_type}_{lookback}d")
```

---

## Related Documentation

---

### Model Documentation
- [[Forecast Model Overview]] - Parent model
- [[Forecast Facts]] - Predictions
- [[Forecast Metrics]] - Accuracy metrics
- [[Model Registry]] - Trained models

### External Resources
- [ARIMA Documentation](https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html)
- [Prophet Documentation](https://facebook.github.io/prophet/)
- [Random Forest (sklearn)](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)

---

**Tags:** #finance/forecast #component/model #concept/ml #concept/algorithms

**Last Updated:** 2024-11-08
**Model Types:** ARIMA, Prophet, Random Forest
**Total Variants:** 10
