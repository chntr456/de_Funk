---
title: "Forecast Model"
tags: [finance/forecast, component/model, concept/analytics, status/stable]
aliases: ["Forecast", "ML Model", "Prediction Model"]
created: 2024-11-08
updated: 2024-11-08
status: stable
dependencies: ["[[Core Model]]", "[[Company Model]]"]
used_by: []
architecture_components:
  - "[[Models System]]"
  - "[[Silver Storage]]"
  - "[[Universal Session]]"
---

# Forecast Model

---

> **Time series predictions and ML model performance metrics**

The Forecast model provides ML-based predictions for stock prices and volumes, along with comprehensive accuracy metrics. It supports multiple forecasting algorithms (ARIMA, Prophet, Random Forest) with configurable horizons and lookback periods.

**Configuration:** `/home/user/de_Funk/configs/models/forecast.yaml`
**Implementation:** `/home/user/de_Funk/models/implemented/forecast/`

---

## Table of Contents

---

- [Overview](#overview)
- [Schema Overview](#schema-overview)
- [Data Sources](#data-sources)
- [Detailed Schema](#detailed-schema)
- [ML Model Configurations](#ml-model-configurations)
- [Accuracy Metrics](#accuracy-metrics)
- [Graph Structure](#graph-structure)
- [Measures](#measures)
- [How-To Guides](#how-to-guides)
- [Usage Examples](#usage-examples)
- [Design Decisions](#design-decisions)

---

## Overview

---

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
| **Dependencies** | [[Core Model]] (calendar), [[Company Model]] (training data) |
| **Storage Root** | `storage/silver/forecast` |
| **Format** | Parquet |
| **Tables** | 4 (all facts, 1 registry dimension) |
| **Facts** | 3 (price forecasts, volume forecasts, metrics) |
| **Measures** | 3 (avg error, MAPE, best R²) |
| **Update Frequency** | Daily (after market close + model retraining) |

---

## Architecture Components Used

---

This model uses the following architecture components:

### Primary Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **[[Models System/ML]]** | ML model framework with forecast-specific extensions | [[Base Model]] |
| **[[Universal Session]]** | Access training data from Company Model across models | [[Universal Session]] |
| **[[Silver Storage]]** | Store prediction outputs and model registry | [[Silver Layer]] |

### Data Flow

The Forecast model reads training data from the Company model via Universal Session, trains ML models (ARIMA, Prophet, Random Forest), generates predictions with confidence intervals, and stores results in Silver storage.

**Flow:** Company.fact_prices (via UniversalSession) → ML Training → Prediction Generation → Silver/forecast

See [[MODEL_ARCHITECTURE_MAPPING]] for complete architecture mapping.

---

## Schema Overview

---

### High-Level Summary

The Forecast model implements a **fact-based schema** with forecasting outputs and model metadata. All predictions are sourced from [[Company Model]] training data and include confidence intervals for uncertainty quantification.

**Quick Reference:**

| Table Type | Count | Purpose |
|------------|-------|---------|
| **Facts** | 3 | Predictions and performance metrics |
| **Registry** | 1 | Model metadata and parameters |
| **Measures** | 3 | Pre-defined accuracy calculations |

### Facts (Predictions)

| Fact | Grain | Partitions | Purpose |
|------|-------|------------|---------|
| **forecast_price** | Daily per ticker per model | forecast_date | Price predictions with confidence intervals |
| **forecast_volume** | Daily per ticker per model | forecast_date | Volume predictions with confidence intervals |
| **forecast_metrics** | Per model per evaluation | metric_date | Accuracy metrics (MAE, RMSE, MAPE, R²) |

### Registry (Metadata)

| Table | Purpose | Grain |
|-------|---------|-------|
| **model_registry** | Track trained models and parameters | One row per model training instance |

### Forecast Diagram

```
Training Flow:
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  [[Company  │      │   Train ML   │      │   Generate   │
│   Model]]   │ ───▶ │    Models    │ ───▶ │  Forecasts   │
│fact_prices  │      │              │      │              │
└─────────────┘      └──────┬───────┘      └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   Evaluate   │
                     │   Accuracy   │
                     └──────┬───────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   Register   │
                     │    Model     │
                     └──────────────┘
```

---

## Data Sources

---

### Training Data Source

**Source:** [[Company Model]] fact_prices table
**Provider:** Polygon.io (via Company Model)
**Data Coverage:** Historical stock prices (OHLC, volume)

### Training Pipeline

```
[[Company Model]].fact_prices
    ↓
Feature Engineering
    ├─→ Lag features (1, 7, 14, 30 days)
    ├─→ Rolling statistics (mean, std)
    └─→ Day-of-week indicators
    ↓
Model Training
    ├─→ ARIMA (auto-tuned)
    ├─→ Prophet (seasonality)
    └─→ Random Forest (ensemble)
    ↓
Prediction Generation
    ├─→ forecast_price (confidence intervals)
    └─→ forecast_volume (confidence intervals)
    ↓
Model Evaluation
    ├─→ forecast_metrics (MAE, RMSE, MAPE, R²)
    └─→ model_registry (parameters, metadata)
    ↓
Silver Storage (forecast model tables)
```

### Update Schedule

- **Training** - Daily after market close
- **Prediction Generation** - Immediately after training
- **Accuracy Evaluation** - Weekly rolling window
- **Model Retraining** - Daily with latest data

### Data Quality

- **Training Window** - Configurable (7-60 days)
- **Test Window** - Configurable (7-30 days)
- **Validation** - Cross-validation for hyperparameter tuning
- **Monitoring** - Continuous accuracy tracking

---

## Detailed Schema

---

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

---

## ML Model Configurations

---

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

---

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

---

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
│ [[Company   │      │   Train ML   │      │   Generate   │
│  Model]]    │ ───▶ │    Models    │ ───▶ │  Forecasts   │
│fact_prices  │      │              │      │              │
└─────────────┘      └──────┬───────┘      └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   Evaluate   │
                     │   Accuracy   │
                     └──────┬───────┘
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

**Training Data Source:** [[Company Model]].fact_prices

**Prediction Output:** forecast.forecast_price, forecast.forecast_volume

---

## Measures

---

### Simple Aggregations

| Measure | Source | Aggregation | Format | Purpose |
|---------|--------|-------------|--------|---------|
| **avg_forecast_error** | forecast_metrics.mae | avg | $#,##0.00 | Average forecast error (MAE) |
| **avg_forecast_mape** | forecast_metrics.mape | avg | #,##0.00% | Average MAPE across models |
| **best_model_r2** | forecast_metrics.r2_score | max | #,##0.0000 | Best R² score across models |

**Example YAML Definition:**
```yaml
measures:
  avg_forecast_error:
    description: "Average forecast error (MAE)"
    source: forecast_metrics.mae
    aggregation: avg
    data_type: double
    format: "$#,##0.00"
    tags: [error, accuracy]

  avg_forecast_mape:
    description: "Average Mean Absolute Percentage Error"
    source: forecast_metrics.mape
    aggregation: avg
    data_type: double
    format: "#,##0.00%"
    tags: [error, percentage]

  best_model_r2:
    description: "Best R-squared score across models"
    source: forecast_metrics.r2_score
    aggregation: max
    data_type: double
    format: "#,##0.0000"
    tags: [accuracy, r2]
```

---

## How-To Guides

---

### How to Generate Forecasts

**Step 1:** Load the models

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load models
company = session.load_model('company')
forecast = session.load_model('forecast')
```

**Step 2:** Get training data from Company Model

```python
# Get recent price history for training
training_data = company.get_fact_df('fact_prices').filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('trade_date') >= '2024-09-01')
).orderBy('trade_date')

training_df = training_data.to_pandas()
```

**Step 3:** Train a forecasting model

```python
from statsmodels.tsa.arima.model import ARIMA

# Prepare data
prices = training_df['close'].values

# Train ARIMA model (example)
model = ARIMA(prices, order=(2, 1, 2))
fitted_model = model.fit()

# Generate 7-day forecast
forecast_output = fitted_model.forecast(steps=7)
confidence_intervals = fitted_model.get_forecast(steps=7).conf_int()
```

**Step 4:** Store predictions

```python
# Create forecast DataFrame
import pandas as pd
from datetime import datetime, timedelta

forecast_date = datetime.now().date()
forecast_records = []

for i, pred in enumerate(forecast_output):
    forecast_records.append({
        'ticker': 'AAPL',
        'forecast_date': forecast_date,
        'prediction_date': forecast_date + timedelta(days=i+1),
        'horizon': i + 1,
        'model_name': 'ARIMA_7d',
        'predicted_close': pred,
        'lower_bound': confidence_intervals[i, 0],
        'upper_bound': confidence_intervals[i, 1],
        'confidence': 0.95
    })

# Convert to Spark DataFrame and write
forecast_df = spark.createDataFrame(pd.DataFrame(forecast_records))
# Write to silver/forecast/facts/forecast_price
```

---

### How to Compare Models

**Step 1:** Get metrics for all models

```python
# Load forecast metrics
metrics = forecast.get_fact_df('forecast_metrics').filter(
    F.col('metric_date') == '2024-11-08'
)

# Convert to pandas for analysis
metrics_df = metrics.to_pandas()
```

**Step 2:** Compare accuracy by model type

```python
import pandas as pd

# Group by model type
comparison = metrics_df.groupby('model_name').agg({
    'mae': 'mean',
    'rmse': 'mean',
    'mape': 'mean',
    'r2_score': 'mean'
}).round(4)

print("\nModel Comparison:")
print(comparison.sort_values('mae'))
```

**Step 3:** Visualize model performance

```python
import matplotlib.pyplot as plt

# Create comparison plot
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# MAE comparison
axes[0, 0].bar(comparison.index, comparison['mae'])
axes[0, 0].set_title('Mean Absolute Error by Model')
axes[0, 0].set_ylabel('MAE ($)')

# RMSE comparison
axes[0, 1].bar(comparison.index, comparison['rmse'])
axes[0, 1].set_title('RMSE by Model')
axes[0, 1].set_ylabel('RMSE ($)')

# MAPE comparison
axes[1, 0].bar(comparison.index, comparison['mape'])
axes[1, 0].set_title('MAPE by Model')
axes[1, 0].set_ylabel('MAPE (%)')

# R² comparison
axes[1, 1].bar(comparison.index, comparison['r2_score'])
axes[1, 1].set_title('R² Score by Model')
axes[1, 1].set_ylabel('R²')

plt.tight_layout()
plt.show()
```

**Step 4:** Select best model

```python
# Find best model by R² score
best_model = metrics_df.loc[metrics_df['r2_score'].idxmax()]

print(f"\nBest Model: {best_model['model_name']}")
print(f"MAE: ${best_model['mae']:.2f}")
print(f"MAPE: {best_model['mape']:.2f}%")
print(f"R²: {best_model['r2_score']:.4f}")
```

---

### How to Validate Accuracy

**Step 1:** Get forecasts and actuals

```python
# Get forecasts made 7 days ago
forecast_date = '2024-11-01'
forecasts = forecast.get_fact_df('forecast_price').filter(
    (F.col('forecast_date') == forecast_date) &
    (F.col('ticker') == 'AAPL')
)

# Get actual prices
actuals = company.get_fact_df('fact_prices').filter(
    (F.col('ticker') == 'AAPL') &
    (F.col('trade_date') >= forecast_date)
)

# Join forecasts with actuals
comparison = forecasts.join(
    actuals.select(
        F.col('trade_date').alias('prediction_date'),
        F.col('close').alias('actual_close')
    ),
    on='prediction_date',
    how='inner'
)
```

**Step 2:** Calculate errors

```python
# Calculate forecast errors
comparison_df = comparison.withColumn(
    'error',
    F.abs(F.col('predicted_close') - F.col('actual_close'))
).withColumn(
    'error_pct',
    (F.abs(F.col('predicted_close') - F.col('actual_close')) / F.col('actual_close')) * 100
).withColumn(
    'within_bounds',
    (F.col('actual_close') >= F.col('lower_bound')) & (F.col('actual_close') <= F.col('upper_bound'))
)

# Show results
comparison_df.select(
    'prediction_date', 'model_name', 'predicted_close', 'actual_close',
    'error', 'error_pct', 'within_bounds'
).orderBy('prediction_date').show()
```

**Step 3:** Calculate validation metrics

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

# Convert to pandas
comparison_pd = comparison_df.to_pandas()

# Calculate metrics
mae = mean_absolute_error(comparison_pd['actual_close'], comparison_pd['predicted_close'])
rmse = np.sqrt(mean_squared_error(comparison_pd['actual_close'], comparison_pd['predicted_close']))
mape = (comparison_pd['error_pct'].mean())
r2 = r2_score(comparison_pd['actual_close'], comparison_pd['predicted_close'])

# Check confidence interval coverage
coverage = comparison_pd['within_bounds'].mean() * 100

print(f"\nValidation Metrics:")
print(f"MAE: ${mae:.2f}")
print(f"RMSE: ${rmse:.2f}")
print(f"MAPE: {mape:.2f}%")
print(f"R²: {r2:.4f}")
print(f"95% CI Coverage: {coverage:.1f}%")
```

**Step 4:** Identify problematic predictions

```python
# Find predictions with high error
high_error = comparison_pd[comparison_pd['error_pct'] > 5.0].copy()

print(f"\nHigh Error Predictions (>5%):")
print(high_error[['prediction_date', 'model_name', 'predicted_close', 'actual_close', 'error_pct']])

# Find predictions outside confidence bounds
outside_bounds = comparison_pd[~comparison_pd['within_bounds']].copy()

print(f"\nPredictions Outside 95% CI:")
print(outside_bounds[['prediction_date', 'predicted_close', 'actual_close', 'lower_bound', 'upper_bound']])
```

---

## Usage Examples

---

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

---

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

## Related Documentation

---

### Model Documentation
- [[Core Model]] - Shared calendar dimension
- [[Company Model]] - Training data source for forecasts
- [[Macro Model]] - Economic indicators for feature engineering

### Architecture Documentation
- [[MODEL_ARCHITECTURE_MAPPING]] - Complete architecture mapping
- [[Models System/ML]] - ML model framework
- [[Universal Session]] - Cross-model data access
- [[Silver Storage]] - Prediction output storage

---

**Tags:** #finance/forecast #component/model #concept/analytics #status/stable #component/models-system/ml #component/storage/silver #component/session/cross-model #architecture/analytics #pattern/ml-predictions #pattern/time-series

**Last Updated:** 2024-11-08
**Model Version:** 1.0
**Dependencies:** [[Core Model]], [[Company Model]]
**Used By:** N/A
