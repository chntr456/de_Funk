# Forecast Model

> **Time series predictions and ML model performance metrics**

The Forecast model provides ML-based predictions for stock prices and volumes, along with comprehensive accuracy metrics. It supports multiple forecasting algorithms (ARIMA, Prophet, Random Forest) with configurable horizons and lookback periods.

**Configuration:** `/home/user/de_Funk/configs/models/forecast.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/forecast/`

---

## Table of Contents

- [Overview](#overview)
- [Schema](#schema)
- [ML Model Configurations](#ml-model-configurations)
- [Accuracy Metrics](#accuracy-metrics)
- [Graph Structure](#graph-structure)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)

---

## Overview

### Purpose

The Forecast model provides:
- Price and volume predictions with confidence intervals
- Multiple ML model types (ARIMA, Prophet, Random Forest)
- Forecast accuracy metrics (MAE, RMSE, MAPE, R²)
- Model registry for tracking trained models
- Configurable forecast horizons (7, 14, 30 days)

### Key Features

- **Multiple Algorithms** - ARIMA, Prophet, Random Forest
- **Confidence Intervals** - 95% upper/lower bounds
- **Accuracy Tracking** - MAE, RMSE, MAPE, R² metrics
- **Model Registry** - Track all trained models and parameters
- **Configurable Horizons** - 7, 14, 30 day forecasts
- **Day-of-Week Adjustments** - Account for weekday patterns

### Model Characteristics

| Attribute | Value |
|-----------|-------|
| **Model Name** | `forecast` |
| **Tags** | `timeseries`, `forecast`, `ml` |
| **Dependencies** | `core` (calendar), `company` (training data) |
| **Storage Root** | `storage/silver/forecast` |
| **Format** | Parquet |
| **Tables** | 4 (all facts, 1 registry dimension) |
| **Facts** | 3 (price forecasts, volume forecasts, metrics) |
| **Measures** | 3 (avg error, MAPE, best R²) |
| **Update Frequency** | Daily (after market close + model retraining) |

---

## Schema

### Facts

#### forecast_price

Price forecasts with confidence intervals.

**Path:** `storage/silver/forecast/facts/forecast_price`
**Partitions:** `forecast_date`
**Grain:** One row per ticker per prediction date per model

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker symbol | AAPL |
| **forecast_date** | date | Date when forecast was made (partition) | 2024-11-08 |
| **prediction_date** | date | Date being predicted | 2024-11-15 |
| **horizon** | int | Days ahead (1-30) | 7 |
| **model_name** | string | Model identifier | ARIMA_7d, Prophet_30d |
| **predicted_close** | double | Predicted closing price | 228.50 |
| **lower_bound** | double | Lower 95% confidence interval | 220.30 |
| **upper_bound** | double | Upper 95% confidence interval | 236.70 |
| **confidence** | double | Confidence level (0-1) | 0.95 |

**Sample Data:**
```
+--------+--------------+-----------------+---------+-------------+-----------------+-------------+-------------+------------+
| ticker | forecast_date| prediction_date | horizon | model_name  | predicted_close | lower_bound | upper_bound | confidence |
+--------+--------------+-----------------+---------+-------------+-----------------+-------------+-------------+------------+
| AAPL   | 2024-11-08   | 2024-11-09      |    1    | ARIMA_7d    |     227.20      |   225.80    |   228.60    |    0.95    |
| AAPL   | 2024-11-08   | 2024-11-15      |    7    | ARIMA_7d    |     228.50      |   220.30    |   236.70    |    0.95    |
| AAPL   | 2024-11-08   | 2024-12-08      |   30    | Prophet_30d |     232.80      |   215.40    |   250.20    |    0.95    |
| GOOGL  | 2024-11-08   | 2024-11-09      |    1    | ARIMA_7d    |     170.15      |   168.90    |   171.40    |    0.95    |
+--------+--------------+-----------------+---------+-------------+-----------------+-------------+-------------+------------+
```

#### forecast_volume

Volume forecasts with confidence intervals.

**Path:** `storage/silver/forecast/facts/forecast_volume`
**Partitions:** `forecast_date`
**Grain:** One row per ticker per prediction date per model

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker symbol | AAPL |
| **forecast_date** | date | Date when forecast was made | 2024-11-08 |
| **prediction_date** | date | Date being predicted | 2024-11-15 |
| **horizon** | int | Days ahead (1-30) | 7 |
| **model_name** | string | Model identifier | Prophet_7d |
| **predicted_volume** | long | Predicted trading volume | 54000000 |
| **lower_bound** | long | Lower 95% confidence interval | 48000000 |
| **upper_bound** | long | Upper 95% confidence interval | 60000000 |
| **confidence** | double | Confidence level (0-1) | 0.95 |

**Sample Data:**
```
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
| ticker | forecast_date| prediction_date | horizon | model_name  | predicted_volume | lower_bound | upper_bound | confidence |
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
| AAPL   | 2024-11-08   | 2024-11-09      |    1    | Prophet_7d  |     52500000     |  49000000   |  56000000   |    0.95    |
| AAPL   | 2024-11-08   | 2024-11-15      |    7    | Prophet_7d  |     54000000     |  48000000   |  60000000   |    0.95    |
| GOOGL  | 2024-11-08   | 2024-11-09      |    1    | Prophet_7d  |     29000000     |  26000000   |  32000000   |    0.95    |
+--------+--------------+-----------------+---------+-------------+------------------+-------------+-------------+------------+
```

#### forecast_metrics

Forecast accuracy metrics and errors for model evaluation.

**Path:** `storage/silver/forecast/facts/forecast_metrics`
**Partitions:** `metric_date`
**Grain:** One row per ticker per model per evaluation date

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **ticker** | string | Stock ticker symbol | AAPL |
| **model_name** | string | Model identifier | ARIMA_7d |
| **metric_date** | date | Date when metrics calculated (partition) | 2024-11-08 |
| **training_start** | date | Start of training period | 2024-10-01 |
| **training_end** | date | End of training period | 2024-11-01 |
| **test_start** | date | Start of test period | 2024-11-02 |
| **test_end** | date | End of test period | 2024-11-08 |
| **mae** | double | Mean Absolute Error | 2.45 |
| **rmse** | double | Root Mean Squared Error | 3.12 |
| **mape** | double | Mean Absolute Percentage Error (%) | 1.08 |
| **r2_score** | double | R-squared score (-∞ to 1.0) | 0.92 |
| **num_predictions** | int | Number of predictions evaluated | 7 |
| **avg_error_pct** | double | Average error percentage | 1.12 |

**Sample Data:**
```
+--------+-------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
| ticker | model_name  | metric_date | training_start | training_end | test_start | test_end | mae  | rmse | mape | r2_score | num_predictions | avg_error_pct|
+--------+-------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
| AAPL   | ARIMA_7d    | 2024-11-08  | 2024-10-01     | 2024-11-01   | 2024-11-02 |2024-11-08|  2.45|  3.12| 1.08 |   0.92   |        7        |     1.12     |
| AAPL   | Prophet_30d | 2024-11-08  | 2024-09-01     | 2024-10-31   | 2024-11-01 |2024-11-08|  5.23|  6.87| 2.31 |   0.78   |       30        |     2.45     |
| GOOGL  | ARIMA_7d    | 2024-11-08  | 2024-10-01     | 2024-11-01   | 2024-11-02 |2024-11-08|  1.89|  2.34| 1.12 |   0.89   |        7        |     1.15     |
+--------+-------------+-------------+----------------+--------------+------------+----------+------+------+------+----------+-----------------+--------------+
```

#### model_registry

Registry of trained models and their parameters.

**Path:** `storage/silver/forecast/facts/model_registry`
**Partitions:** `trained_date`
**Grain:** One row per model training instance

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| **model_id** | string | Unique model identifier | arima_7d_AAPL_20241108 |
| **model_name** | string | Model type and config | ARIMA_7d |
| **model_type** | string | Algorithm type | ARIMA, Prophet, RandomForest |
| **ticker** | string | Stock ticker | AAPL |
| **target_variable** | string | Prediction target | close, volume |
| **lookback_days** | int | Training window size | 7, 14, 30, 60 |
| **forecast_horizon** | int | Prediction horizon | 7, 14, 30 |
| **day_of_week_adj** | boolean | Day-of-week adjustment enabled | true, false |
| **parameters** | string | JSON of model parameters | {"p":2,"d":1,"q":2} |
| **trained_date** | date | Date when model trained (partition) | 2024-11-08 |
| **training_samples** | int | Number of training samples | 60 |
| **status** | string | Model status | active, archived |

**Sample Data:**
```
+-------------------------+-------------+-------------+--------+-----------------+--------------+------------------+----------------+
| model_id                | model_name  | model_type  | ticker | target_variable | lookback_days| forecast_horizon | day_of_week_adj|
+-------------------------+-------------+-------------+--------+-----------------+--------------+------------------+----------------+
| arima_7d_AAPL_20241108  | ARIMA_7d    | ARIMA       | AAPL   | close           |      7       |        7         |     true       |
| prophet_30d_AAPL_202411 | Prophet_30d | Prophet     | AAPL   | close           |     30       |       30         |     true       |
| rf_14d_GOOGL_20241108   | RandomForest| RandomForest| GOOGL  | volume          |     14       |        7         |     true       |
+-------------------------+-------------+-------------+--------+-----------------+--------------+------------------+----------------+

+---------------------+--------------+------------------+--------+
| parameters          | trained_date | training_samples | status |
+---------------------+--------------+------------------+--------+
| {"p":2,"d":1,"q":2} | 2024-11-08   |       60         | active |
| {"seasonality":...} | 2024-11-08   |       90         | active |
| {"n_estimators":100}| 2024-11-08   |       42         | active |
+---------------------+--------------+------------------+--------+
```

### Measures

#### avg_forecast_error

Average forecast error (MAE) across models.

```yaml
avg_forecast_error:
  description: "Average forecast error (MAE)"
  source: forecast_metrics.mae
  aggregation: avg
  data_type: double
  format: "$#,##0.00"
  tags: [error, accuracy]
```

#### avg_forecast_mape

Average Mean Absolute Percentage Error across models.

```yaml
avg_forecast_mape:
  description: "Average Mean Absolute Percentage Error"
  source: forecast_metrics.mape
  aggregation: avg
  data_type: double
  format: "#,##0.00%"
  tags: [error, percentage]
```

#### best_model_r2

Best R-squared score across all models.

```yaml
best_model_r2:
  description: "Best R-squared score across models"
  source: forecast_metrics.r2_score
  aggregation: max
  data_type: double
  format: "#,##0.0000"
  tags: [accuracy, r2]
```

---

## ML Model Configurations

The Forecast model supports multiple algorithm types with different configurations.

### ARIMA Models

**Auto-Regressive Integrated Moving Average** - Classic time series forecasting.

#### arima_7d - Short-term forecast

```yaml
arima_7d:
  type: ARIMA
  target: [close, volume]
  lookback_days: 7
  forecast_horizon: 7
  day_of_week_adj: true
  auto_arima: true
  seasonal: false
```

**Use Case:** Next week predictions
**Lookback:** 1 week of history
**Horizon:** 7 days ahead
**Seasonality:** None (short-term)

#### arima_14d - Medium-term forecast

```yaml
arima_14d:
  type: ARIMA
  target: [close, volume]
  lookback_days: 14
  forecast_horizon: 14
  day_of_week_adj: true
  auto_arima: true
  seasonal: false
```

**Use Case:** Two-week predictions
**Lookback:** 2 weeks of history
**Horizon:** 14 days ahead

#### arima_30d - Monthly forecast

```yaml
arima_30d:
  type: ARIMA
  target: [close, volume]
  lookback_days: 30
  forecast_horizon: 30
  day_of_week_adj: true
  auto_arima: true
  seasonal: true
```

**Use Case:** Monthly predictions
**Lookback:** 1 month of history
**Horizon:** 30 days ahead
**Seasonality:** Weekly patterns

#### arima_60d - Long-term forecast

```yaml
arima_60d:
  type: ARIMA
  target: [close, volume]
  lookback_days: 60
  forecast_horizon: 30
  day_of_week_adj: true
  auto_arima: true
  seasonal: true
```

**Use Case:** Long-term monthly predictions
**Lookback:** 2 months of history
**Horizon:** 30 days ahead
**Seasonality:** Weekly/monthly patterns

**ARIMA Parameters:**
- `p` - Auto-regressive order (lags of series)
- `d` - Differencing order (stationarity)
- `q` - Moving average order (lags of errors)
- `auto_arima: true` - Automatically select best (p,d,q)

### Prophet Models

**Facebook Prophet** - Handles seasonality and holidays well.

#### prophet_7d - Short-term forecast

```yaml
prophet_7d:
  type: Prophet
  target: [close, volume]
  lookback_days: 7
  forecast_horizon: 7
  day_of_week_adj: true
  seasonality_mode: multiplicative
  include_holidays: false
```

**Use Case:** Next week with day-of-week patterns
**Seasonality:** Multiplicative (percentage changes)
**Holidays:** Not included (too short-term)

#### prophet_30d - Monthly forecast

```yaml
prophet_30d:
  type: Prophet
  target: [close, volume]
  lookback_days: 30
  forecast_horizon: 30
  day_of_week_adj: true
  seasonality_mode: multiplicative
  include_holidays: true
```

**Use Case:** Monthly predictions with holidays
**Seasonality:** Multiplicative
**Holidays:** US holidays included

#### prophet_60d - Long-term forecast

```yaml
prophet_60d:
  type: Prophet
  target: [close, volume]
  lookback_days: 60
  forecast_horizon: 30
  day_of_week_adj: true
  seasonality_mode: multiplicative
  include_holidays: true
```

**Use Case:** Long-term with full seasonality
**Lookback:** 2 months for better trend detection

**Prophet Components:**
- **Trend** - Overall direction (linear or logistic)
- **Seasonality** - Weekly, monthly, yearly patterns
- **Holidays** - Special days impact
- **Day-of-week** - Weekday effects

### Random Forest Models

**Ensemble ML** - Non-parametric, captures complex patterns.

#### random_forest_14d - Medium-term ML forecast

```yaml
random_forest_14d:
  type: RandomForest
  target: [close, volume]
  lookback_days: 14
  forecast_horizon: 7
  day_of_week_adj: true
  n_estimators: 100
  max_depth: 10
  features:
    - lag_1        # Yesterday's value
    - lag_7        # Last week
    - lag_14       # Two weeks ago
    - day_of_week  # Weekday effect
    - rolling_mean_7
    - rolling_std_7
```

**Use Case:** Capture non-linear patterns
**Ensemble:** 100 decision trees
**Features:** 6 engineered features

#### random_forest_30d - Long-term ML forecast

```yaml
random_forest_30d:
  type: RandomForest
  target: [close, volume]
  lookback_days: 30
  forecast_horizon: 14
  day_of_week_adj: true
  n_estimators: 100
  max_depth: 10
  features:
    - lag_1
    - lag_7
    - lag_14
    - lag_30
    - day_of_week
    - rolling_mean_7
    - rolling_std_7
    - rolling_mean_30
    - rolling_std_30
```

**Use Case:** Complex patterns with more history
**Features:** 9 engineered features including 30-day stats

**Random Forest Parameters:**
- `n_estimators` - Number of trees (100)
- `max_depth` - Tree depth (10)
- **Lags** - Previous values (1, 7, 14, 30 days)
- **Rolling stats** - Mean and std dev over windows
- **Day of week** - Weekday categorical feature

---

## Accuracy Metrics

### MAE (Mean Absolute Error)

**Formula:** `MAE = (1/n) × Σ|actual - predicted|`

**Interpretation:**
- Average absolute difference between predicted and actual
- Same units as target variable (dollars for price)
- Lower is better

**Example:**
```
Actual:    [225, 227, 226, 228, 230]
Predicted: [224, 228, 225, 229, 231]
Errors:    [  1,   1,   1,   1,   1]
MAE = (1 + 1 + 1 + 1 + 1) / 5 = 1.0
```

**Good Values:**
- **MAE < 1.0** - Excellent for daily price predictions
- **MAE < 3.0** - Good for weekly predictions
- **MAE < 5.0** - Acceptable for monthly predictions

### RMSE (Root Mean Squared Error)

**Formula:** `RMSE = √[(1/n) × Σ(actual - predicted)²]`

**Interpretation:**
- Penalizes large errors more than MAE
- Same units as target variable
- Lower is better

**Example:**
```
Actual:    [225, 227, 226, 228, 230]
Predicted: [224, 228, 225, 229, 231]
Squared:   [  1,   1,   1,   1,   1]
RMSE = √(5 / 5) = 1.0
```

**Good Values:**
- **RMSE < 2.0** - Excellent
- **RMSE < 5.0** - Good
- **RMSE < 10.0** - Acceptable

**RMSE vs MAE:**
- RMSE ≈ MAE: Consistent errors
- RMSE >> MAE: Large outlier errors

### MAPE (Mean Absolute Percentage Error)

**Formula:** `MAPE = (100/n) × Σ|((actual - predicted) / actual)|`

**Interpretation:**
- Percentage error (independent of scale)
- Good for comparing across different stocks
- Lower is better

**Example:**
```
Actual:    [225, 227, 226, 228, 230]
Predicted: [224, 228, 225, 229, 231]
% Errors:  [0.44%, 0.44%, 0.44%, 0.44%, 0.43%]
MAPE = (0.44 + 0.44 + 0.44 + 0.44 + 0.43) / 5 = 0.44%
```

**Good Values:**
- **MAPE < 1%** - Excellent
- **MAPE < 3%** - Good
- **MAPE < 5%** - Acceptable
- **MAPE > 10%** - Poor

### R² Score (Coefficient of Determination)

**Formula:** `R² = 1 - (SS_res / SS_tot)`
- `SS_res = Σ(actual - predicted)²` (residual sum of squares)
- `SS_tot = Σ(actual - mean)²` (total sum of squares)

**Interpretation:**
- Proportion of variance explained by model
- Range: -∞ to 1.0
- Higher is better

**Example:**
```
Actual:    [225, 227, 226, 228, 230]
Mean:      227.2
Predicted: [224, 228, 225, 229, 231]

SS_tot = (225-227.2)² + ... = 20.8
SS_res = (225-224)² + ... = 5.0

R² = 1 - (5.0 / 20.8) = 0.76
```

**Interpretation:**
- **R² = 1.0** - Perfect predictions
- **R² = 0.9+** - Excellent (90%+ variance explained)
- **R² = 0.7-0.9** - Good (70-90% variance)
- **R² = 0.5-0.7** - Moderate
- **R² < 0.5** - Poor
- **R² < 0** - Worse than predicting mean

---

## Graph Structure

### ASCII Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   FORECAST MODEL                             │
│           (Loads from Silver - Pre-computed)                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐      ┌──────────────────────┐
│  forecast_price      │      │  forecast_volume     │
│                      │      │                      │
│  • ticker            │      │  • ticker            │
│  • forecast_date     │      │  • forecast_date     │
│  • prediction_date   │      │  • prediction_date   │
│  • horizon           │      │  • horizon           │
│  • model_name        │      │  • model_name        │
│  • predicted_close   │      │  • predicted_volume  │
│  • lower_bound       │      │  • lower_bound       │
│  • upper_bound       │      │  • upper_bound       │
│  • confidence        │      │  • confidence        │
│                      │      │                      │
│  Partitioned by      │      │  Partitioned by      │
│  forecast_date       │      │  forecast_date       │
└──────────────────────┘      └──────────────────────┘

┌──────────────────────┐      ┌──────────────────────┐
│  forecast_metrics    │      │   model_registry     │
│                      │      │                      │
│  • ticker            │      │  • model_id          │
│  • model_name        │      │  • model_name        │
│  • metric_date       │      │  • model_type        │
│  • mae, rmse, mape   │      │  • ticker            │
│  • r2_score          │      │  • target_variable   │
│  • num_predictions   │      │  • lookback_days     │
│  • avg_error_pct     │      │  • forecast_horizon  │
│                      │      │  • parameters (JSON) │
│  Partitioned by      │      │  • trained_date      │
│  metric_date         │      │  • status            │
└──────────────────────┘      └──────────────────────┘
                                       │
                                       │ Partitioned by
                                       │ trained_date
                                       ↓

Training Flow:
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  company    │      │   Train ML   │      │   Generate   │
│fact_prices  │ ───▶ │    Models    │ ───▶ │  Forecasts   │
└─────────────┘      └──────────────┘      └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   Evaluate   │
                     │   Accuracy   │
                     └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   Register   │
                     │    Model     │
                     └──────────────┘
```

### Dependencies

```yaml
depends_on:
  - core     # Uses shared dim_calendar for time-based queries
  - company  # Forecast model reads from company model for training data
```

**Training Data Source:** `company.fact_prices`

**Prediction Output:** `forecast.forecast_price`, `forecast.forecast_volume`

---

## Usage Examples

### 1. Load Forecast Model

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load forecast model
forecast_model = session.load_model('forecast')
```

### 2. Get Price Forecasts

```python
# Get all price forecasts
price_forecasts = forecast_model.get_fact_df('forecast_price')

# Filter for AAPL, 7-day horizon, ARIMA model
aapl_7d = price_forecasts.filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('horizon') == 7) &
    (F.col('model_name') == 'ARIMA_7d')
).orderBy('prediction_date')

aapl_7d.show()
```

### 3. Get Latest Forecasts

```python
# Get most recent forecast date
latest_forecast_date = price_forecasts.agg(
    F.max('forecast_date').alias('max_date')
).first()['max_date']

# Filter for latest forecasts
latest = price_forecasts.filter(
    F.col('forecast_date') == latest_forecast_date
)

latest.select(
    'ticker', 'prediction_date', 'model_name',
    'predicted_close', 'lower_bound', 'upper_bound'
).show()
```

### 4. Compare Models for Same Ticker

```python
# Compare ARIMA vs Prophet for AAPL
aapl_comparison = price_forecasts.filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('forecast_date') == '2024-11-08') &
    (F.col('prediction_date') == '2024-11-15')
)

aapl_comparison.select(
    'model_name', 'predicted_close', 'confidence'
).show()

# +-------------+-----------------+------------+
# | model_name  | predicted_close | confidence |
# +-------------+-----------------+------------+
# | ARIMA_7d    |     228.50      |    0.95    |
# | Prophet_7d  |     229.20      |    0.95    |
# | Prophet_30d |     227.80      |    0.95    |
# +-------------+-----------------+------------+
```

### 5. Analyze Forecast Accuracy

```python
# Get latest metrics
metrics = forecast_model.get_fact_df('forecast_metrics')

# Best performing models by R²
best_models = metrics.filter(
    F.col('metric_date') == '2024-11-08'
).orderBy(F.desc('r2_score'))

best_models.select(
    'ticker', 'model_name', 'mae', 'rmse', 'mape', 'r2_score'
).show(10)
```

### 6. Model Comparison by Ticker

```python
# Compare all models for AAPL
aapl_metrics = metrics.filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('metric_date') == '2024-11-08')
)

aapl_metrics.select(
    'model_name', 'mae', 'mape', 'r2_score'
).orderBy('mae').show()
```

### 7. Get Model Registry

```python
# Get all active models
registry = forecast_model.get_fact_df('model_registry')

active_models = registry.filter(F.col('status') == 'active')

active_models.select(
    'model_id', 'model_type', 'ticker',
    'lookback_days', 'forecast_horizon', 'trained_date'
).show()
```

### 8. Visualize Predictions with Confidence Bands

```python
import pandas as pd
import matplotlib.pyplot as plt

# Get AAPL forecasts
aapl_forecasts = price_forecasts.filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('model_name') == 'Prophet_30d') &
    (F.col('forecast_date') == '2024-11-08')
).toPandas()

# Plot
plt.figure(figsize=(12, 6))
plt.plot(aapl_forecasts['prediction_date'], aapl_forecasts['predicted_close'], label='Predicted')
plt.fill_between(
    aapl_forecasts['prediction_date'],
    aapl_forecasts['lower_bound'],
    aapl_forecasts['upper_bound'],
    alpha=0.3,
    label='95% Confidence'
)
plt.xlabel('Date')
plt.ylabel('Price ($)')
plt.title('AAPL 30-Day Forecast (Prophet)')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### 9. Calculate Average Error by Model Type

```python
# Average MAE by model type
avg_errors = metrics.groupBy('model_name').agg(
    F.avg('mae').alias('avg_mae'),
    F.avg('mape').alias('avg_mape'),
    F.avg('r2_score').alias('avg_r2'),
    F.count('ticker').alias('num_tickers')
).orderBy('avg_mae')

avg_errors.show()
```

### 10. Join Forecasts with Actuals

```python
# Load company model for actuals
company_model = session.load_model('company')
actual_prices = company_model.get_fact_df('fact_prices')

# Join forecasts with actuals
comparison = price_forecasts.join(
    actual_prices,
    (price_forecasts.ticker == actual_prices.ticker) &
    (price_forecasts.prediction_date == actual_prices.trade_date),
    how='left'
).select(
    price_forecasts.ticker,
    price_forecasts.prediction_date,
    price_forecasts.model_name,
    price_forecasts.predicted_close,
    actual_prices.close.alias('actual_close')
).withColumn(
    'error',
    F.abs(F.col('predicted_close') - F.col('actual_close'))
)

comparison.show()
```

---

## Design Decisions

### 1. Multiple Model Types

**Decision:** Support ARIMA, Prophet, and Random Forest

**Rationale:**
- Different algorithms for different patterns
- ARIMA: Classic, fast, good for short-term
- Prophet: Handles seasonality, holidays well
- Random Forest: Non-parametric, captures complexity

**Trade-off:** More models = more computation

### 2. Confidence Intervals

**Decision:** Include 95% upper/lower bounds

**Rationale:**
- Quantifies prediction uncertainty
- Essential for risk management
- Industry standard (95% confidence)

### 3. Multiple Horizons

**Decision:** 7, 14, 30 day forecasts

**Rationale:**
- Different use cases need different horizons
- Short-term (7d): Trading decisions
- Medium-term (14d): Position management
- Long-term (30d): Strategic planning

### 4. Day-of-Week Adjustment

**Decision:** Include `day_of_week_adj` parameter

**Rationale:**
- Stock markets have weekday patterns (Monday effect, Friday effect)
- Volume typically lower on Fridays
- Improves accuracy for weekly+ forecasts

### 5. Model Registry

**Decision:** Track all trained models with parameters

**Rationale:**
- Model versioning and reproducibility
- Compare different hyperparameters
- Audit trail for production models

### 6. Separate Price and Volume Forecasts

**Decision:** `forecast_price` and `forecast_volume` as separate tables

**Rationale:**
- Different target variables need different models
- Volume has different patterns than price
- Cleaner schema (avoid sparse columns)

### 7. Partition by forecast_date

**Decision:** Partition by when forecast was made, not prediction date

**Rationale:**
- Most queries filter by "forecasts made on date X"
- Easy to drop old forecasts
- Aligns with model retraining schedule

---

## Summary

The Forecast model provides comprehensive ML-based predictions with:

- **3 Algorithm Types** - ARIMA, Prophet, Random Forest
- **Multiple Horizons** - 7, 14, 30 day forecasts
- **Confidence Intervals** - 95% bounds for risk management
- **Accuracy Tracking** - MAE, RMSE, MAPE, R² metrics
- **Model Registry** - Version control and reproducibility
- **Production Ready** - Daily retraining and evaluation

This model enables data-driven trading decisions with quantified uncertainty.

---

**Next Steps:**
- See [Company Model](company-model.md) for training data source
- See [Macro Model](macro-model.md) for economic indicators
- See [Overview](../overview.md) for framework concepts

---

**Related Documentation:**
- [Models Framework Overview](../overview.md)
- [ML Model Training Pipeline](../../3-architecture/pipelines/ml-training.md)
- [Forecast API](../../4-api-reference/forecast-api.md)
