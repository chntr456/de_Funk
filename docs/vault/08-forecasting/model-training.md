# Model Training

**Time series forecasting model training and prediction**

Source: `models/implemented/forecast/training_methods.py`
Script: `scripts/run_forecasts.py`

---

## Overview

de_Funk implements **three time series forecasting algorithms** for stock price and volume prediction:

1. **ARIMA** - Statistical autoregressive model
2. **Prophet** - Facebook's forecasting library
3. **RandomForest** - Machine learning ensemble model

Each model is trained independently and predictions are stored in the Silver layer.

---

## Quick Reference

### Training a Model

```python
from models.implemented.forecast.training_methods import (
    train_arima_model,
    train_prophet_model,
    train_random_forest_model
)

# Train ARIMA
model, metadata = train_arima_model(
    data_pdf=historical_prices,
    ticker='AAPL',
    target='close',
    lookback_days=90,
    forecast_horizon=30
)

# Generate predictions
predictions = model.forecast(steps=30)
```

### Running Full Pipeline

```bash
# All tickers, all models
python -m scripts.run_forecasts

# Specific tickers
python -m scripts.run_forecasts --tickers AAPL,MSFT,GOOGL

# Specific models
python -m scripts.run_forecasts --models arima_30d,prophet_30d

# Limit tickers
python -m scripts.run_forecasts --max-tickers 10
```

---

## ARIMA Model

### Overview

**ARIMA** (AutoRegressive Integrated Moving Average) is a statistical model for time series forecasting.

**Model Components**:
- **AR (p)**: Autoregressive terms (lagged values)
- **I (d)**: Integration order (differencing)
- **MA (q)**: Moving average terms (lagged errors)

**When to Use**:
- Stationary time series
- Short-term forecasts (7-30 days)
- When interpretability matters

---

### Training Function

**Signature**:
```python
def train_arima_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    day_of_week_adj: bool = True,
    seasonal: bool = False,
    auto: bool = True
) -> Tuple[object, Dict]
```

**Parameters**:
- `data_pdf` - Historical price data (DataFrame)
- `ticker` - Stock ticker symbol
- `target` - Target variable (`'close'` or `'volume'`)
- `lookback_days` - Training window size (e.g., 90, 180, 365)
- `forecast_horizon` - Prediction horizon (e.g., 7, 30, 90)
- `day_of_week_adj` - Include day-of-week effects
- `seasonal` - Use SARIMA (seasonal ARIMA)
- `auto` - Use auto_arima for parameter selection

**Returns**:
- `model` - Fitted ARIMA model object
- `metadata` - Training metadata dict

---

### Example Usage

```python
import pandas as pd
from models.implemented.forecast.training_methods import train_arima_model

# Load historical data
historical_prices = pd.DataFrame({
    'trade_date': pd.date_range('2024-01-01', periods=180),
    'close': [150 + i * 0.5 for i in range(180)]
})

# Train ARIMA model
model, metadata = train_arima_model(
    data_pdf=historical_prices,
    ticker='AAPL',
    target='close',
    lookback_days=90,   # Use last 90 days
    forecast_horizon=30, # Predict 30 days
    auto=True           # Auto-select parameters
)

# Metadata contains training info
print(metadata)
# {
#   'ticker': 'AAPL',
#   'target': 'close',
#   'lookback_days': 90,
#   'forecast_horizon': 30,
#   'model_type': 'ARIMA',
#   'training_samples': 90,
#   'training_end': '2024-06-29',
#   'day_of_week_adj': True
# }

# Generate predictions
predictions = model.forecast(steps=30)
print(predictions)
# [150.5, 151.0, 151.5, ...]
```

---

### Auto-ARIMA

When `auto=True`, the model uses **pmdarima.auto_arima** to automatically select optimal parameters:

```python
model = auto_arima(
    ts[target],
    exogenous=exog,
    seasonal=seasonal,
    m=5 if seasonal else 1,  # Weekly seasonality (5 trading days)
    suppress_warnings=True,
    stepwise=True,
    error_action='ignore'
)
```

**Benefits**:
- No manual parameter tuning
- Optimizes AIC/BIC
- Handles stationarity tests

---

### Manual ARIMA

When `auto=False`, uses default parameters `(p=1, d=1, q=1)`:

```python
from statsmodels.tsa.arima.model import ARIMA

order = (1, 1, 1)
model = ARIMA(ts[target], exog=exog, order=order)
model = model.fit()
```

---

### Seasonal ARIMA (SARIMA)

When `seasonal=True`, uses SARIMA with weekly seasonality:

```python
from statsmodels.tsa.statespace.sarimax import SARIMAX

model = SARIMAX(
    ts[target],
    exog=exog,
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 5)  # 5-day weekly cycle
)
```

---

## Prophet Model

### Overview

**Prophet** is Facebook's forecasting library designed for business time series with seasonality and holidays.

**Model Features**:
- Automatic trend detection
- Multiple seasonality (daily, weekly, yearly)
- Holiday effects
- Robust to missing data and outliers

**When to Use**:
- Multiple seasonal patterns
- Medium to long-term forecasts (30-365 days)
- Data with holidays or special events

---

### Training Function

**Signature**:
```python
def train_prophet_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    day_of_week_adj: bool = True,
    seasonality_mode: str = 'multiplicative'
) -> Tuple[object, Dict]
```

**Parameters**:
- `data_pdf` - Historical price data
- `ticker` - Stock ticker
- `target` - Target variable
- `lookback_days` - Training window
- `forecast_horizon` - Prediction horizon
- `day_of_week_adj` - Enable weekly seasonality
- `seasonality_mode` - `'additive'` or `'multiplicative'`

**Returns**:
- `model` - Fitted Prophet model
- `metadata` - Training metadata

---

### Example Usage

```python
from models.implemented.forecast.training_methods import train_prophet_model

# Train Prophet model
model, metadata = train_prophet_model(
    data_pdf=historical_prices,
    ticker='AAPL',
    target='close',
    lookback_days=180,
    forecast_horizon=30,
    seasonality_mode='multiplicative'
)

# Generate future dataframe
future = model.make_future_dataframe(periods=30)

# Make predictions
forecast = model.predict(future)

# Extract predictions and confidence intervals
predictions = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(30)
print(predictions)
#          ds       yhat  yhat_lower  yhat_upper
# 2024-07-01  151.2      148.5       153.9
# 2024-07-02  151.5      148.8       154.2
# ...
```

---

### Prophet Configuration

```python
from prophet import Prophet

model = Prophet(
    seasonality_mode='multiplicative',  # or 'additive'
    daily_seasonality=False,            # Disable (too noisy for stocks)
    weekly_seasonality=True,            # Enable (day-of-week effects)
    yearly_seasonality=False            # Disable (not enough data)
)

model.fit(prophet_df)
```

**Seasonality Modes**:
- **Additive**: Seasonal effects are constant (y = trend + seasonal)
- **Multiplicative**: Seasonal effects scale with trend (y = trend * seasonal)

**Stock Prices**: Usually multiplicative (percentage changes)

---

## Random Forest Model

### Overview

**Random Forest** is a machine learning ensemble model that uses decision trees for prediction.

**Model Features**:
- Non-parametric (no assumptions about data distribution)
- Handles non-linear relationships
- Uses lagged features and rolling statistics

**When to Use**:
- Complex non-linear patterns
- Short to medium-term forecasts (7-30 days)
- When you have many features

---

### Training Function

**Signature**:
```python
def train_random_forest_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str,
    lookback_days: int,
    forecast_horizon: int,
    n_estimators: int = 100,
    max_depth: int = 10
) -> Tuple[object, Dict]
```

**Parameters**:
- `data_pdf` - Historical price data
- `ticker` - Stock ticker
- `target` - Target variable
- `lookback_days` - Training window
- `forecast_horizon` - Prediction horizon
- `n_estimators` - Number of trees (default: 100)
- `max_depth` - Max tree depth (default: 10)

**Returns**:
- `model` - Fitted RandomForestRegressor
- `metadata` - Training metadata (includes feature names)

---

### Feature Engineering

Random Forest uses **lagged features** and **rolling statistics**:

```python
# Lagged values
lags = [1, 2, 3, 5, 7]
for lag in lags:
    df[f'lag_{lag}'] = df[target].shift(lag)

# Rolling statistics
df['rolling_mean_7'] = df[target].rolling(window=7).mean()
df['rolling_std_7'] = df[target].rolling(window=7).std()
df['rolling_mean_30'] = df[target].rolling(window=30).mean()
df['rolling_std_30'] = df[target].rolling(window=30).std()

# Day of week
df['day_of_week'] = df.index.dayofweek
df['is_monday'] = (df.index.dayofweek == 0).astype(int)
df['is_friday'] = (df.index.dayofweek == 4).astype(int)
```

**Features Created**:
- `lag_1`, `lag_2`, ..., `lag_7` - Previous values
- `rolling_mean_7` - 7-day moving average
- `rolling_std_7` - 7-day volatility
- `rolling_mean_30` - 30-day moving average
- `rolling_std_30` - 30-day volatility
- `day_of_week` - Day of week (0=Monday)
- `is_monday`, `is_friday` - Binary indicators

---

### Example Usage

```python
from models.implemented.forecast.training_methods import train_random_forest_model

# Train Random Forest
model, metadata = train_random_forest_model(
    data_pdf=historical_prices,
    ticker='AAPL',
    target='close',
    lookback_days=90,
    forecast_horizon=30,
    n_estimators=200,  # More trees = better accuracy
    max_depth=15       # Deeper trees = more complex patterns
)

# Metadata includes feature names
print(metadata['feature_cols'])
# ['lag_1', 'lag_2', 'lag_3', 'lag_5', 'lag_7',
#  'rolling_mean_7', 'rolling_std_7',
#  'rolling_mean_30', 'rolling_std_30',
#  'day_of_week', 'is_monday', 'is_friday']

# Make predictions (requires feature construction)
# See forecast model implementation for full prediction pipeline
```

---

## Data Preparation

All models use shared data preparation functions:

### prepare_time_series

```python
def prepare_time_series(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    Prepare time series data for forecasting.

    Steps:
    1. Select date and target columns
    2. Sort by date
    3. Set date as index
    4. Fill missing dates (market holidays)
    """
    ts = df[['trade_date', target]].copy()
    ts = ts.sort_values('trade_date')
    ts = ts.set_index('trade_date')
    ts.index = pd.to_datetime(ts.index)

    # Forward-fill missing dates (e.g., weekends, holidays)
    ts = ts.asfreq('D', method='ffill')

    return ts
```

---

### add_day_of_week_features

```python
def add_day_of_week_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add day-of-week features."""
    df = df.copy()
    df['day_of_week'] = df.index.dayofweek
    df['is_monday'] = (df.index.dayofweek == 0).astype(int)
    df['is_friday'] = (df.index.dayofweek == 4).astype(int)
    return df
```

**Day-of-Week Effects**:
- **Monday Effect**: Often negative (weekend news)
- **Friday Effect**: Often positive (weekend optimism)

---

### create_lagged_features

```python
def create_lagged_features(
    df: pd.DataFrame,
    target: str,
    lags: List[int]
) -> pd.DataFrame:
    """Create lagged features for ML models."""
    df_feat = df.copy()

    # Lagged values
    for lag in lags:
        if len(df) > lag:
            df_feat[f'lag_{lag}'] = df_feat[target].shift(lag)

    # Rolling statistics
    if len(df) >= 7:
        df_feat['rolling_mean_7'] = df_feat[target].rolling(7).mean()
        df_feat['rolling_std_7'] = df_feat[target].rolling(7).std()

    if len(df) >= 30:
        df_feat['rolling_mean_30'] = df_feat[target].rolling(30).mean()
        df_feat['rolling_std_30'] = df_feat[target].rolling(30).std()

    # Drop rows with NaN
    df_feat = df_feat.dropna()

    return df_feat
```

---

## Forecast Pipeline

### Overview

The full forecast pipeline:
1. **Refresh Data** - Ingest recent prices
2. **Get Tickers** - Determine tickers to forecast
3. **Initialize Model** - Create ForecastModel instance
4. **Run Forecasts** - Train models and generate predictions
5. **Store Results** - Write to Silver layer

---

### Running the Pipeline

**Command**:
```bash
python -m scripts.run_forecasts \
  --tickers AAPL,MSFT,GOOGL \
  --refresh-days 7 \
  --models arima_30d,prophet_30d \
  --max-tickers 10
```

**Arguments**:
- `--tickers` - Comma-separated ticker list (default: all active)
- `--no-refresh` - Skip data refresh
- `--refresh-days` - Days to refresh (default: 7)
- `--models` - Models to run (default: all configured)
- `--max-tickers` - Limit number of tickers

---

### Pipeline Stages

**Stage 1: Refresh Data**
```python
from scripts.refresh_data import refresh_recent_data

refresh_recent_data(days=7, max_tickers=100)
```

**Stage 2: Get Tickers**
```python
# Load active tickers from Silver layer
tickers = get_active_tickers(storage_cfg, limit=max_tickers)
# Returns: ['AAPL', 'MSFT', 'GOOGL', ...]
```

**Stage 3: Initialize Model**
```python
from models.implemented.forecast import ForecastModel

forecast_model = ForecastModel(
    connection=spark,
    storage_cfg=storage_cfg,
    model_cfg=forecast_cfg,
    params={}
)

forecast_model.set_session(session)  # For cross-model access
```

**Stage 4: Run Forecasts**
```python
for ticker in tickers:
    results = forecast_model.run_forecast_for_ticker(
        ticker=ticker,
        model_configs=models  # e.g., ['arima_30d', 'prophet_30d']
    )

    # Results contain:
    # - forecasts_generated: Number of forecasts
    # - models_trained: Number of models
    # - errors: Any errors encountered
```

**Stage 5: Store Results**

Forecasts written to Silver layer:
- `storage/silver/forecast/fact_forecasts/` - Predictions
- `storage/silver/forecast/fact_forecast_metrics/` - Accuracy metrics

---

## Model Evaluation

### Metrics

Forecast quality evaluated using:

**RMSE** (Root Mean Squared Error):
```python
rmse = np.sqrt(mean_squared_error(actual, predicted))
```
- Lower is better
- Sensitive to large errors
- Same units as target

**MAE** (Mean Absolute Error):
```python
mae = mean_absolute_error(actual, predicted)
```
- Lower is better
- More robust to outliers
- Same units as target

**MAPE** (Mean Absolute Percentage Error):
```python
mape = np.mean(np.abs((actual - predicted) / actual)) * 100
```
- Percentage error (interpretable)
- Scale-independent
- Fails if actual = 0

---

### Backtesting

Validate models using historical data:

```python
# Split data
train = prices[:-30]  # All but last 30 days
test = prices[-30:]   # Last 30 days

# Train model
model, metadata = train_arima_model(
    data_pdf=train,
    ticker='AAPL',
    target='close',
    lookback_days=90,
    forecast_horizon=30
)

# Generate predictions
predictions = model.forecast(steps=30)

# Calculate metrics
from sklearn.metrics import mean_squared_error, mean_absolute_error

rmse = np.sqrt(mean_squared_error(test['close'], predictions))
mae = mean_absolute_error(test['close'], predictions)
mape = np.mean(np.abs((test['close'] - predictions) / test['close'])) * 100

print(f"RMSE: {rmse:.2f}")
print(f"MAE: {mae:.2f}")
print(f"MAPE: {mape:.2f}%")
```

---

## Best Practices

### Model Selection

**Use ARIMA when**:
- Short-term forecasts (7-30 days)
- Stationary time series
- Interpretability is important

**Use Prophet when**:
- Multiple seasonal patterns
- Medium-term forecasts (30-90 days)
- Data has holidays/special events

**Use Random Forest when**:
- Non-linear patterns
- Many features available
- Short-term forecasts with high accuracy

---

### Training Window (lookback_days)

**Guidelines**:
- **Short-term (7-30 day forecasts)**: 60-90 days
- **Medium-term (30-90 day forecasts)**: 180-365 days
- **Long-term (90+ day forecasts)**: 365+ days

**Trade-off**:
- Shorter window: More responsive to recent changes
- Longer window: More stable, less noise

---

### Forecast Horizon

**Guidelines**:
- **ARIMA**: 7-30 days (degrades beyond)
- **Prophet**: 30-90 days (handles longer)
- **Random Forest**: 7-30 days (requires iterative prediction)

---

### Ensemble Predictions

Combine multiple models for better accuracy:

```python
# Train all three models
arima_pred = train_arima_model(...).forecast(30)
prophet_pred = train_prophet_model(...).predict(...)['yhat'].values[-30:]
rf_pred = train_random_forest_model(...).predict(...)

# Average predictions
ensemble_pred = (arima_pred + prophet_pred + rf_pred) / 3

# Weighted average (if you know model accuracies)
weights = [0.4, 0.4, 0.2]  # ARIMA, Prophet, RF
ensemble_pred = (
    weights[0] * arima_pred +
    weights[1] * prophet_pred +
    weights[2] * rf_pred
)
```

---

## Troubleshooting

### Insufficient Data

**Symptom**: `ValueError: No data available for ticker`

**Solution**:
- Check Bronze layer has data for ticker
- Run data ingestion: `python run_full_pipeline.py`
- Check date range covers lookback period

---

### Prophet Not Installed

**Symptom**: `ImportError: Prophet library not installed`

**Solution**:
```bash
pip install prophet
```

---

### Auto-ARIMA Not Found

**Symptom**: `ImportError: pmdarima not found`

**Solution**:
```bash
pip install pmdarima
```

Falls back to manual ARIMA with default parameters.

---

### Poor Forecast Accuracy

**Symptom**: High RMSE/MAE/MAPE

**Solutions**:
1. Increase `lookback_days` (more training data)
2. Try different models (ensemble)
3. Add more features (Random Forest)
4. Check for data quality issues

---

## Related Documentation

- [Forecast Models](forecast-models.md) - Forecast model overview
- [Implemented Models](../03-model-framework/implemented-models.md#forecast) - Model configuration
- [Providers](../04-data-pipelines/providers.md) - Data ingestion
- `/FORECAST_README.md` - Complete forecasting guide
